"""Zone-aware diarization stabilizer for STT v2 (NeMo-only)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from app.domain.stt_v2.contracts import (
    DiarFrame,
    DiarPatch,
    DiarLabel,
    TimeRangeSamples,
    OVERLAP_LABEL,
    UNCERTAIN_LABEL,
)


@dataclass
class _StabilizerState:
    current_label: Optional[DiarLabel] = None
    current_conf: float = 0.0
    current_duration_samples: int = 0
    candidate_label: Optional[DiarLabel] = None
    candidate_conf: float = 0.0
    candidate_duration_samples: int = 0
    last_switch_sample: int = 0
    next_track_id: int = 0
    label_map: Dict[DiarLabel, DiarLabel] = None  # raw -> stable


class DiarizationStabilizer:
    """Stabilize diarization frames with zones and track mapping."""

    def __init__(
        self,
        *,
        sample_rate: int,
        live_zone_ms: int,
        refine_zone_ms: int,
        commit_zone_ms: int,
        min_segment_ms: int,
        commit_conf_th: float,
        switch_confirm_ms: int,
        switch_margin: float,
    ) -> None:
        self.sample_rate = sample_rate
        self.live_zone_samples = int(live_zone_ms * sample_rate / 1000)
        self.refine_zone_samples = int(refine_zone_ms * sample_rate / 1000)
        self.commit_zone_samples = int(commit_zone_ms * sample_rate / 1000)
        self.min_segment_samples = int(min_segment_ms * sample_rate / 1000)
        self.commit_conf_th = commit_conf_th
        self.switch_confirm_samples = int(switch_confirm_ms * sample_rate / 1000)
        self.switch_margin = switch_margin
        self._state = _StabilizerState(label_map={})

    def stabilize_outputs(
        self, outputs: List[DiarFrame | DiarPatch], now_sample: int
    ) -> List[DiarFrame | DiarPatch]:
        stabilized: List[DiarFrame | DiarPatch] = []
        stabilized_frames: List[DiarFrame] = []
        for item in outputs:
            if isinstance(item, DiarFrame):
                stable = self._stabilize_frame(item, now_sample)
                if stable is not None:
                    stabilized_frames.append(stable)
            elif isinstance(item, DiarPatch):
                patch_frames = []
                for frame in item.frames:
                    stable = self._stabilize_frame(frame, now_sample, is_patch=True)
                    if stable is not None:
                        patch_frames.append(stable)
                patch_frames = self._merge_and_enforce_min(patch_frames)
                if patch_frames:
                    stabilized.append(
                        DiarPatch(
                            range_samples=item.range_samples,
                            frames=patch_frames,
                            version=item.version,
                        )
                    )
        stabilized_frames = self._merge_and_enforce_min(stabilized_frames)
        stabilized.extend(stabilized_frames)
        return stabilized

    def _stabilize_frame(
        self, frame: DiarFrame, now_sample: int, is_patch: Optional[bool] = None
    ) -> Optional[DiarFrame]:
        if frame.range_samples.end <= frame.range_samples.start:
            return None

        if frame.label in (OVERLAP_LABEL, UNCERTAIN_LABEL):
            return DiarFrame(
                range_samples=frame.range_samples,
                label=frame.label,
                conf=frame.conf,
                is_patch=frame.is_patch if is_patch is None else is_patch,
            )

        stable_label = self._map_label(frame.label)
        zone = self._zone_for_frame(now_sample, frame.range_samples.end)

        label = stable_label
        conf = frame.conf

        if zone == "live":
            label = UNCERTAIN_LABEL
            conf = min(conf, 0.2)
        else:
            if zone == "committed":
                if (
                    self._state.current_label is not None
                    and stable_label != self._state.current_label
                    and conf < self.commit_conf_th
                ):
                    label = self._state.current_label
            label, conf = self._stabilize_label(
                label, conf, frame.range_samples, now_sample
            )

        return DiarFrame(
            range_samples=frame.range_samples,
            label=label,
            conf=conf,
            is_patch=frame.is_patch if is_patch is None else is_patch,
        )

    def _zone_for_frame(self, now_sample: int, frame_end: int) -> str:
        lag = max(0, now_sample - frame_end)
        if lag <= self.live_zone_samples:
            return "live"
        if lag <= self.refine_zone_samples:
            return "refine"
        return "committed"

    def _map_label(self, raw_label: DiarLabel) -> DiarLabel:
        if raw_label in self._state.label_map:
            return self._state.label_map[raw_label]
        stable = f"spk{self._state.next_track_id}"
        self._state.next_track_id += 1
        self._state.label_map[raw_label] = stable
        return stable

    def _stabilize_label(
        self,
        label: DiarLabel,
        conf: float,
        range_samples: TimeRangeSamples,
        end_sample: int,
    ) -> tuple[DiarLabel, float]:
        frame_len = range_samples.end - range_samples.start
        state = self._state
        if state.current_label is None:
            state.current_label = label
            state.current_conf = conf
            state.current_duration_samples = frame_len
            state.last_switch_sample = end_sample
            return label, conf

        if label == state.current_label:
            state.current_duration_samples += frame_len
            state.current_conf = (state.current_conf * 0.9) + (conf * 0.1)
            state.candidate_label = None
            state.candidate_conf = 0.0
            state.candidate_duration_samples = 0
            return state.current_label, state.current_conf

        if state.candidate_label == label:
            state.candidate_duration_samples += frame_len
            state.candidate_conf = (state.candidate_conf * 0.9) + (conf * 0.1)
        else:
            state.candidate_label = label
            state.candidate_conf = conf
            state.candidate_duration_samples = frame_len

        can_switch = (
            state.candidate_duration_samples >= self.switch_confirm_samples
            and state.candidate_conf >= state.current_conf + self.switch_margin
        )
        if can_switch and state.candidate_label is not None:
            state.current_label = state.candidate_label
            state.current_conf = state.candidate_conf
            state.current_duration_samples = state.candidate_duration_samples
            state.last_switch_sample = end_sample
            state.candidate_label = None
            state.candidate_conf = 0.0
            state.candidate_duration_samples = 0
            return state.current_label, state.current_conf

        state.current_duration_samples += frame_len
        return state.current_label, state.current_conf

    def _merge_and_enforce_min(self, frames: List[DiarFrame]) -> List[DiarFrame]:
        merged = self._merge_adjacent(frames)
        if not merged or self.min_segment_samples <= 0:
            return merged

        result: List[DiarFrame] = []
        for frame in merged:
            duration = frame.range_samples.end - frame.range_samples.start
            if duration < self.min_segment_samples and result:
                prev = result[-1]
                result[-1] = DiarFrame(
                    range_samples=TimeRangeSamples(
                        start=prev.range_samples.start,
                        end=frame.range_samples.end,
                        sr=prev.range_samples.sr,
                    ),
                    label=prev.label,
                    conf=(prev.conf + frame.conf) / 2,
                    is_patch=prev.is_patch,
                )
                continue
            result.append(frame)

        if len(result) >= 2:
            first = result[0]
            if (
                first.range_samples.end - first.range_samples.start
                < self.min_segment_samples
            ):
                second = result[1]
                result[1] = DiarFrame(
                    range_samples=TimeRangeSamples(
                        start=first.range_samples.start,
                        end=second.range_samples.end,
                        sr=second.range_samples.sr,
                    ),
                    label=second.label,
                    conf=(first.conf + second.conf) / 2,
                    is_patch=second.is_patch,
                )
                result = result[1:]
        return result

    @staticmethod
    def _merge_adjacent(frames: List[DiarFrame]) -> List[DiarFrame]:
        if not frames:
            return []
        merged = [frames[0]]
        for frame in frames[1:]:
            last = merged[-1]
            if (
                last.label == frame.label
                and last.is_patch == frame.is_patch
                and last.range_samples.end == frame.range_samples.start
            ):
                merged[-1] = DiarFrame(
                    range_samples=TimeRangeSamples(
                        start=last.range_samples.start,
                        end=frame.range_samples.end,
                        sr=last.range_samples.sr,
                    ),
                    label=last.label,
                    conf=(last.conf + frame.conf) / 2,
                    is_patch=last.is_patch,
                )
            else:
                merged.append(frame)
        return merged
