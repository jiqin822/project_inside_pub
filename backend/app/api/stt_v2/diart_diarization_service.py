"""Diart streaming diarization wrapper (preview + optional refine patches).

Includes a lightweight fallback diarizer when Diart is unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import logging

from app.domain.stt_v2.contracts import (
    AudioWindow,
    DiarFrame,
    DiarPatch,
    StreamId,
    TimeRangeSamples,
    OVERLAP_LABEL,
    UNCERTAIN_LABEL,
)


@dataclass
class _DiarState:
    stream_id: StreamId
    sr: int
    version: int = 0
    last_patch_sample: int = 0
    recent_frames: List[DiarFrame] = field(default_factory=list)
    pipeline: Optional[object] = None
    label_map: Dict[str, str] = field(default_factory=dict)
    next_label: int = 0
    expected_samples: int = 0


class DiartDiarizationService:
    """Thin wrapper for Diart streaming diarization.

    If Diart is unavailable, this service returns no frames (safe no-op).
    """

    def __init__(
        self,
        preview_mode: bool = True,
        patch_window_s: float = 6.0,
        patch_emit_s: float = 2.0,
        energy_threshold: float = 0.01,
        window_s: float = 1.6,
        hop_s: float = 0.4,
    ) -> None:
        self.preview_mode = preview_mode
        self.patch_window_s = patch_window_s
        self.patch_emit_s = patch_emit_s
        self.energy_threshold = energy_threshold
        self.window_s = window_s
        self.hop_s = hop_s
        self._states: Dict[StreamId, _DiarState] = {}
        self._logger = logging.getLogger(__name__)
        self._unavailable_reason: Optional[str] = None
        try:
            import diart  # noqa: F401
            self._logger.info("!!!!!!!!import diart success!!!!!!!!!!!!!!!!!!!!")
            self._available = True
        except Exception as exc:
            self._logger.warning("!!!!!!!!error importing diart: %s", exc)
            self._available = False
            self._unavailable_reason = str(exc)[:200]

    def start(self, stream_id: StreamId, sr: int) -> None:
        state = _DiarState(stream_id=stream_id, sr=sr)
        if self._available:
            try:
                state.pipeline = self._build_pipeline(sr)
                state.expected_samples = int(np.rint(self.window_s * sr))
            except Exception as exc:
                self._logger.warning("Diart pipeline unavailable: %s", exc)
                state.pipeline = None
                self._available = False
                self._unavailable_reason = str(exc)[:200]
        self._states[stream_id] = state

    def process_window(self, window: AudioWindow) -> List[DiarFrame | DiarPatch]:
        state = self._states.get(window.stream_id)
        if state is None:
            self.start(window.stream_id, window.range_samples.sr)
            state = self._states[window.stream_id]

        # Prefer Diart if available; fallback to simple energy-based diarization.
        frames: List[DiarFrame] = []
        if self._available and state.pipeline is not None:
            try:
                frames = self._run_diart(state, window)
            except Exception as exc:
                self._logger.warning("Diart run failed, falling back: %s", exc)
                frames = self._fallback_diarize(window)
        else:
            frames = self._fallback_diarize(window)

        state.recent_frames.extend(frames)
        # Keep only recent frames for patch window.
        self._prune_frames(state)

        outputs: List[DiarFrame | DiarPatch] = []
        outputs.extend(frames)

        # Emit refine patches on a rolling cadence.
        patch = self._maybe_emit_patch(state, window.range_samples.end)
        if patch is not None:
            outputs.append(patch)
        return outputs

    def _build_pipeline(self, sr: int) -> object:
        import os
        import traceback
        from diart.blocks.diarization import SpeakerDiarization, SpeakerDiarizationConfig

        try:
            import diart.models as diart_models
            self._logger.info("!!!!!!!!import diart.models as diart_models success")

            token = os.getenv("HUGGINGFACE_HUB_TOKEN") or True
            segmentation = diart_models.SegmentationModel.from_pretrained(
                "pyannote/segmentation", use_hf_token=token
            )
            embedding = diart_models.EmbeddingModel.from_pretrained(
                "pyannote/embedding", use_hf_token=token
            )
            segmentation.load()
            embedding.load()
            if segmentation.model is None or embedding.model is None:
                raise RuntimeError("Diart model load failed (pyannote models unavailable)")

            config = SpeakerDiarizationConfig(
                segmentation=segmentation,
                embedding=embedding,
                duration=self.window_s,
                step=self.hop_s,
                latency=self.hop_s,
                sample_rate=sr,
            )
            pipeline = SpeakerDiarization(config)
        except Exception as exc:
            logger.warning("!!!!!!!!error importing diart.models: %s", exc)
            raise
        return pipeline

    def _run_diart(self, state: _DiarState, window: AudioWindow) -> List[DiarFrame]:
        from pyannote.core import SlidingWindow, SlidingWindowFeature

        samples = window.pcm16_np
        if samples.size == 0:
            return []
        mono = samples if samples.ndim == 1 else samples[:, 0]
        expected = state.expected_samples or int(np.rint(self.window_s * state.sr))
        if mono.shape[0] < expected:
            pad_width = expected - mono.shape[0]
            mono = np.pad(mono, (0, pad_width), mode="constant")
        elif mono.shape[0] > expected:
            mono = mono[:expected]
        waveform = (mono.astype(np.float32) / 32768.0).reshape(-1, 1)

        start_sec = window.range_samples.start / window.range_samples.sr
        duration_sec = expected / window.range_samples.sr
        extent = SlidingWindow(start=start_sec, duration=duration_sec, step=duration_sec)
        window_feature = SlidingWindowFeature(waveform, extent)

        outputs = state.pipeline([window_feature])
        if not outputs:
            return []
        annotation, agg_waveform = outputs[0]
        return self._annotation_to_frames(
            state,
            annotation,
            agg_waveform.extent.start,
            agg_waveform.extent.end,
            window.range_samples.sr,
        )

    def _annotation_to_frames(
        self,
        state: _DiarState,
        annotation: object,
        start_sec: float,
        end_sec: float,
        sr: int,
    ) -> List[DiarFrame]:
        segments: List[tuple[float, float, str]] = []
        boundaries = {start_sec, end_sec}
        for segment, _track, label in annotation.itertracks(yield_label=True):
            seg_start = max(start_sec, float(segment.start))
            seg_end = min(end_sec, float(segment.end))
            if seg_end <= seg_start:
                continue
            label_str = str(label)
            segments.append((seg_start, seg_end, label_str))
            boundaries.add(seg_start)
            boundaries.add(seg_end)

        if not segments:
            return [
                DiarFrame(
                    range_samples=TimeRangeSamples(
                        start=int(np.rint(start_sec * sr)),
                        end=int(np.rint(end_sec * sr)),
                        sr=sr,
                    ),
                    label=UNCERTAIN_LABEL,
                    conf=0.0,
                    is_patch=False,
                )
            ]

        sorted_bounds = sorted(boundaries)
        frames: List[DiarFrame] = []
        for left, right in zip(sorted_bounds, sorted_bounds[1:]):
            if right <= left:
                continue
            active = {
                label
                for seg_start, seg_end, label in segments
                if seg_start < right and seg_end > left
            }
            if not active:
                label = UNCERTAIN_LABEL
                conf = 0.0
            elif len(active) == 1:
                label = self._normalize_label(state, next(iter(active)))
                conf = 1.0
            else:
                label = OVERLAP_LABEL
                conf = 0.5

            start_sample = int(np.rint(left * sr))
            end_sample = int(np.rint(right * sr))
            if end_sample <= start_sample:
                continue
            frames.append(
                DiarFrame(
                    range_samples=TimeRangeSamples(start=start_sample, end=end_sample, sr=sr),
                    label=label,
                    conf=conf,
                    is_patch=False,
                )
            )
        return self._merge_adjacent(frames)

    def _normalize_label(self, state: _DiarState, label: str) -> str:
        if label.startswith("spk"):
            return label
        if label in state.label_map:
            return state.label_map[label]
        digits = "".join(ch for ch in label if ch.isdigit())
        if digits:
            normalized = f"spk{int(digits)}"
        else:
            normalized = f"spk{state.next_label}"
            state.next_label += 1
        state.label_map[label] = normalized
        return normalized

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

    def _fallback_diarize(self, window: AudioWindow) -> List[DiarFrame]:
        if window.pcm16_np.size == 0:
            return []
        energy = float(
            np.sqrt(np.mean(window.pcm16_np.astype(np.float32) ** 2)) / 32768.0
        )
        label = "spk0" if energy >= self.energy_threshold else UNCERTAIN_LABEL
        conf = min(1.0, energy * 10)
        return [
            DiarFrame(
                range_samples=window.range_samples,
                label=label,
                conf=conf,
                is_patch=False,
            )
        ]

    def _maybe_emit_patch(self, state: _DiarState, window_end_sample: int) -> DiarPatch | None:
        if not state.recent_frames:
            return None
        emit_every_samples = int(self.patch_emit_s * state.sr)
        if window_end_sample - state.last_patch_sample < emit_every_samples:
            return None

        patch_window_samples = int(self.patch_window_s * state.sr)
        patch_start = max(0, window_end_sample - patch_window_samples)
        patch_end = window_end_sample
        patch_frames = [
            DiarFrame(
                range_samples=frame.range_samples,
                label=frame.label,
                conf=frame.conf,
                is_patch=True,
            )
            for frame in state.recent_frames
            if frame.range_samples.end > patch_start
        ]
        if not patch_frames:
            return None

        state.version += 1
        state.last_patch_sample = window_end_sample
        return DiarPatch(
            range_samples=TimeRangeSamples(start=patch_start, end=patch_end, sr=state.sr),
            frames=patch_frames,
            version=state.version,
        )

    def _prune_frames(self, state: _DiarState) -> None:
        if not state.recent_frames:
            return
        max_samples = int(self.patch_window_s * state.sr)
        latest_end = state.recent_frames[-1].range_samples.end
        min_sample = max(0, latest_end - max_samples)
        state.recent_frames = [
            frame for frame in state.recent_frames if frame.range_samples.end > min_sample
        ]
