"""Speaker timeline store with stabilization and patch application."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.domain.stt_v2.contracts import DiarFrame, DiarPatch, DiarLabel, StreamId, TimeRangeSamples


@dataclass
class TimelineInterval:
    start_sample: int
    end_sample: int
    label: DiarLabel
    conf: float
    is_patch: bool = False


@dataclass
class _StabilizerState:
    current_label: Optional[DiarLabel] = None
    current_conf: float = 0.0
    current_duration_samples: int = 0
    candidate_label: Optional[DiarLabel] = None
    candidate_conf: float = 0.0
    candidate_duration_samples: int = 0
    last_switch_sample: int = 0


class SpeakerTimelineStore:
    def __init__(
        self,
        sample_rate: int,
        min_turn_ms: int = 800,
        switch_confirm_ms: int = 160,
        cooldown_ms: int = 600,
        switch_margin: float = 0.08,
        max_minutes: int = 10,
    ) -> None:
        self.sample_rate = sample_rate
        self.min_turn_samples = int((min_turn_ms * sample_rate) / 1000)
        self.switch_confirm_samples = int((switch_confirm_ms * sample_rate) / 1000)
        self.cooldown_samples = int((cooldown_ms * sample_rate) / 1000)
        self.switch_margin = switch_margin
        self.max_samples = max_minutes * 60 * sample_rate
        self._intervals: Dict[StreamId, List[TimelineInterval]] = {}
        self._states: Dict[StreamId, _StabilizerState] = {}

    def _state(self, stream_id: StreamId) -> _StabilizerState:
        if stream_id not in self._states:
            self._states[stream_id] = _StabilizerState()
        return self._states[stream_id]

    def _intervals_for(self, stream_id: StreamId) -> List[TimelineInterval]:
        if stream_id not in self._intervals:
            self._intervals[stream_id] = []
        return self._intervals[stream_id]

    def apply_frames(self, stream_id: StreamId, frames: List[DiarFrame]) -> None:
        state = self._state(stream_id)
        intervals = self._intervals_for(stream_id)
        for frame in frames:
            # Stabilize labels to reduce twitchiness before storing intervals.
            stable_label, stable_conf = self._stabilize_label(state, frame)
            stable_frame = DiarFrame(
                range_samples=frame.range_samples,
                label=stable_label,
                conf=stable_conf,
                is_patch=frame.is_patch,
            )
            self._append_interval(intervals, stable_frame)
        self._prune_old(intervals)

    def apply_patch(self, stream_id: StreamId, patch: DiarPatch) -> None:
        intervals = self._intervals_for(stream_id)
        self._remove_range(intervals, patch.range_samples)
        for frame in patch.frames:
            self._append_interval(intervals, frame)
        self._prune_old(intervals)

    def query(self, stream_id: StreamId, range_samples: TimeRangeSamples) -> List[Tuple[TimeRangeSamples, DiarLabel, float, bool]]:
        intervals = self._intervals_for(stream_id)
        results: List[Tuple[TimeRangeSamples, DiarLabel, float, bool]] = []
        for interval in intervals:
            if interval.end_sample <= range_samples.start or interval.start_sample >= range_samples.end:
                continue
            start = max(interval.start_sample, range_samples.start)
            end = min(interval.end_sample, range_samples.end)
            results.append(
                (TimeRangeSamples(start=start, end=end, sr=range_samples.sr), interval.label, interval.conf, interval.is_patch)
            )
        return results

    def stats(self, stream_id: StreamId) -> dict:
        intervals = self._intervals_for(stream_id)
        total = sum(i.end_sample - i.start_sample for i in intervals)
        return {"intervals": len(intervals), "total_samples": total}

    def export_intervals(self, stream_id: StreamId) -> List[dict]:
        intervals = self._intervals_for(stream_id)
        return [
            {
                "start_sample": i.start_sample,
                "end_sample": i.end_sample,
                "label": i.label,
                "conf": i.conf,
                "is_patch": i.is_patch,
            }
            for i in intervals
        ]

    def _stabilize_label(self, state: _StabilizerState, frame: DiarFrame) -> Tuple[DiarLabel, float]:
        frame_len = frame.range_samples.end - frame.range_samples.start
        if state.current_label is None:
            # Initialize on first frame.
            state.current_label = frame.label
            state.current_conf = frame.conf
            state.current_duration_samples = frame_len
            state.last_switch_sample = frame.range_samples.end
            return frame.label, frame.conf

        if frame.label == state.current_label:
            # Same label keeps accumulating duration and smooths confidence.
            state.current_duration_samples += frame_len
            state.current_conf = (state.current_conf * 0.9) + (frame.conf * 0.1)
            state.candidate_label = None
            state.candidate_conf = 0.0
            state.candidate_duration_samples = 0
            return state.current_label, state.current_conf

        # Candidate update (potential switch).
        if state.candidate_label == frame.label:
            state.candidate_duration_samples += frame_len
            state.candidate_conf = (state.candidate_conf * 0.9) + (frame.conf * 0.1)
        else:
            state.candidate_label = frame.label
            state.candidate_conf = frame.conf
            state.candidate_duration_samples = frame_len

        time_since_last_switch = frame.range_samples.end - state.last_switch_sample
        can_switch = (
            state.candidate_duration_samples >= self.switch_confirm_samples
            and time_since_last_switch >= self.cooldown_samples
            and state.current_duration_samples >= self.min_turn_samples
            and state.candidate_conf >= state.current_conf + self.switch_margin
        )
        if can_switch and state.candidate_label is not None:
            # Switch is confirmed: commit the candidate as the new current label.
            state.current_label = state.candidate_label
            state.current_conf = state.candidate_conf
            state.current_duration_samples = state.candidate_duration_samples
            state.last_switch_sample = frame.range_samples.end
            state.candidate_label = None
            state.candidate_conf = 0.0
            state.candidate_duration_samples = 0
            return state.current_label, state.current_conf

        # Keep current label until switch is confirmed.
        state.current_duration_samples += frame_len
        return state.current_label, state.current_conf

    def _append_interval(self, intervals: List[TimelineInterval], frame: DiarFrame) -> None:
        if frame.range_samples.end <= frame.range_samples.start:
            return
        if intervals:
            last = intervals[-1]
            if (
                last.label == frame.label
                and last.is_patch == frame.is_patch
                and last.end_sample == frame.range_samples.start
            ):
                last.end_sample = frame.range_samples.end
                last.conf = (last.conf + frame.conf) / 2
                return
        intervals.append(
            TimelineInterval(
                start_sample=frame.range_samples.start,
                end_sample=frame.range_samples.end,
                label=frame.label,
                conf=frame.conf,
                is_patch=frame.is_patch,
            )
        )

    def _remove_range(self, intervals: List[TimelineInterval], range_samples: TimeRangeSamples) -> None:
        updated: List[TimelineInterval] = []
        for interval in intervals:
            if interval.end_sample <= range_samples.start or interval.start_sample >= range_samples.end:
                updated.append(interval)
                continue
            if interval.start_sample < range_samples.start:
                updated.append(
                    TimelineInterval(
                        start_sample=interval.start_sample,
                        end_sample=range_samples.start,
                        label=interval.label,
                        conf=interval.conf,
                        is_patch=interval.is_patch,
                    )
                )
            if interval.end_sample > range_samples.end:
                updated.append(
                    TimelineInterval(
                        start_sample=range_samples.end,
                        end_sample=interval.end_sample,
                        label=interval.label,
                        conf=interval.conf,
                        is_patch=interval.is_patch,
                    )
                )
        intervals.clear()
        intervals.extend(updated)

    def _prune_old(self, intervals: List[TimelineInterval]) -> None:
        if not intervals:
            return
        latest_end = intervals[-1].end_sample
        min_sample = max(0, latest_end - self.max_samples)
        pruned: List[TimelineInterval] = []
        for interval in intervals:
            if interval.end_sample <= min_sample:
                continue
            if interval.start_sample < min_sample:
                pruned.append(
                    TimelineInterval(
                        start_sample=min_sample,
                        end_sample=interval.end_sample,
                        label=interval.label,
                        conf=interval.conf,
                        is_patch=interval.is_patch,
                    )
                )
            else:
                pruned.append(interval)
        intervals.clear()
        intervals.extend(pruned)
