"""NeMo streaming diarization wrapper for STT v2 (preview + optional patches).

Implements the same interface as DiartDiarizationService: start(stream_id, sr) and
process_window(window) -> [DiarFrame | DiarPatch]. Uses per-stream NeMo Sortformer
streaming state; when NeMo is unavailable, falls back to energy-based diarization
so the pipeline keeps working.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import logging
import time
import numpy as np

from app.api.stt.constants import STT_SAMPLE_RATE_HZ
from app.domain.stt.nemo_sortformer_diarizer import (
    create_streaming_diarizer,
    nemo_diarization_available,
    get_frame_bytes,
    segments_from_frame_probs,
    streaming_frame_len_s,
)
from app.domain.stt_v2.contracts import (
    AudioWindow,
    DiarFrame,
    DiarPatch,
    StreamId,
    TimeRangeSamples,
    UNCERTAIN_LABEL,
)

_logger = logging.getLogger(__name__)


@dataclass
class _DiarState:
    """Per-stream state for NeMo streaming diarization."""

    stream_id: StreamId
    sr: int
    version: int = 0  # Incremented per patch for downstream re-attribution
    last_patch_sample: int = 0  # Sample index of last emitted patch (throttles patch_emit_s)
    recent_frames: List[DiarFrame] = field(default_factory=list)  # Used to build patches; pruned by patch_window_s
    streaming_diarizer: Optional[object] = None  # NeMo Sortformer streaming instance (stateful)
    pending_pcm: bytearray = field(default_factory=bytearray)  # Buffered bytes until we have full frame(s)
    pending_start_sample: Optional[int] = None  # Absolute sample index of pending_pcm[0]
    last_appended_sample: Optional[int] = None  # For gap detection: last window end we accounted for


class NemoDiarizationService:
    """NeMo Sortformer streaming diarization for STT v2."""
    is_nemo_backend: bool = True

    def __init__(
        self,
        *,
        preview_mode: bool = True,           # If True, runs in preview mode (may skip actual diarizer for speed/testing)
        patch_window_s: float = 6.0,         # Window (seconds) covered by emitted diarization patches
        patch_emit_s: float = 2.0,           # Minimum period (seconds) between patch emissions/refinements
        energy_threshold: float = 0.01,      # RMS energy threshold (for fallback diarization, below = uncertain/silence)
        max_speakers: Optional[int] = None,  # Maximum speakers to diarize (if supported by backend/model)
        required_sr: int = STT_SAMPLE_RATE_HZ, # Required audio sample rate (Hz) for NeMo streaming
    ) -> None:
        self.preview_mode = preview_mode
        self.patch_window_s = patch_window_s
        self.patch_emit_s = patch_emit_s
        self.energy_threshold = energy_threshold
        self.max_speakers = max_speakers
        self.required_sr = required_sr
        self._states: Dict[StreamId, _DiarState] = {}
        self._logger = logging.getLogger(__name__)
        # NeMo streaming model uses fixed 80ms frames at 16 kHz; we must feed frame-aligned bytes.
        self._frame_bytes = get_frame_bytes()
        self._frame_len_s = streaming_frame_len_s()
        self._available = False
        self._unavailable_reason: Optional[str] = None
        ok, err = nemo_diarization_available()
        if ok:
            self._available = True
        else:
            self._unavailable_reason = err

    def start(self, stream_id: StreamId, sr: int) -> None:
        """Initialize per-stream state; create a NeMo streaming diarizer only if available and sr matches (16k)."""
        state = _DiarState(stream_id=stream_id, sr=sr)
        if self._available and sr == self.required_sr:
            try:
                state.streaming_diarizer = create_streaming_diarizer()
                if state.streaming_diarizer is None:
                    self._available = False
                    self._unavailable_reason = "NeMo streaming diarizer unavailable"
            except Exception as exc:
                self._logger.warning("NeMo diarization init failed: %s", exc)
                self._available = False
                self._unavailable_reason = str(exc)[:200]
        self._states[stream_id] = state

    def process_window(self, window: AudioWindow) -> List[DiarFrame | DiarPatch]:
        """Process one audio window: run NeMo streaming (or energy fallback), accumulate frames, maybe emit a patch."""
        state = self._states.get(window.stream_id)
        if state is None:
            self.start(window.stream_id, window.range_samples.sr)
            state = self._states[window.stream_id]

        frames: List[DiarFrame] = []
        if self._available and state.streaming_diarizer is not None:
            try:
                frames = self._run_streaming(state, window)
            except Exception as exc:
                self._logger.warning("NeMo streaming failed: %s", exc)
                frames = []
        else:
            frames = []

        state.recent_frames.extend(frames)
        self._prune_frames(state)

        outputs: List[DiarFrame | DiarPatch] = []
        outputs.extend(frames)

        # Emit a refine patch on a rolling cadence (patch_emit_s) so downstream can re-attribute sentences.
        patch = self._maybe_emit_patch(state, window.range_samples.end)
        if patch is not None:
            outputs.append(patch)
        return outputs

    def _run_streaming(self, state: _DiarState, window: AudioWindow) -> List[DiarFrame]:
        """Run NeMo streaming on new audio only: buffer to frame boundaries, step model, convert segments to DiarFrames."""
        if window.pcm16_np.size == 0:
            return []
        if window.range_samples.sr != self.required_sr:
            self._logger.warning(
                "NeMo diarization requires %d Hz; got %d Hz",
                self.required_sr,
                window.range_samples.sr,
            )
            return []
        if state.streaming_diarizer is None:
            return []

        window_start = window.range_samples.start
        window_end = window.range_samples.end
        if state.last_appended_sample is None:
            state.last_appended_sample = window_start

        # Detect gap in stream (e.g. network pause): reset model state so timeline stays correct.
        gap_samples = window_start - state.last_appended_sample
        if gap_samples > (self._frame_bytes // 2):
            self._reset_stream_state(state)
            state.last_appended_sample = window_start

        # Only process the slice of this window that we haven't already accounted for (no double-counting).
        new_start_sample = max(window_start, state.last_appended_sample)
        offset_samples = new_start_sample - window_start
        if offset_samples >= window.range_samples.duration_samples:
            return []

        pcm_slice = window.pcm16_np[offset_samples:]
        if pcm_slice.size == 0:
            return []

        # Ensure pending buffer is contiguous: if this window doesn't continue from pending, reset and realign.
        if state.pending_start_sample is None:
            state.pending_start_sample = new_start_sample
        else:
            expected_next = state.pending_start_sample + (len(state.pending_pcm) // 2)
            if expected_next != new_start_sample:
                self._reset_stream_state(state)
                state.pending_start_sample = new_start_sample

        state.pending_pcm.extend(pcm_slice.tobytes())
        state.last_appended_sample = max(state.last_appended_sample, window_end)


        # NeMo expects input in multiples of frame_bytes (80ms); process only complete frames.
        if len(state.pending_pcm) < self._frame_bytes:
            return []

        usable_len = len(state.pending_pcm) - (len(state.pending_pcm) % self._frame_bytes)
        if usable_len == 0:
            return []

        chunk_start_sample = state.pending_start_sample or new_start_sample
        chunk_bytes = bytes(state.pending_pcm[:usable_len])
        del state.pending_pcm[:usable_len]
        state.pending_start_sample = chunk_start_sample + (usable_len // 2)

        step_start = time.time()
        frame_probs = state.streaming_diarizer.step(chunk_bytes)
        step_ms = int((time.time() - step_start) * 1000)
        segments = segments_from_frame_probs(
            frame_probs,
            frame_len_s=self._frame_len_s,
            max_speakers=self.max_speakers,
        )

        # Map relative-time segments (seconds) to absolute sample range for this stream.
        frames: List[DiarFrame] = []
        for seg in segments:
            start_sample = chunk_start_sample + int(
                np.rint(seg.start_s * window.range_samples.sr)
            )
            end_sample = chunk_start_sample + int(
                np.rint(seg.end_s * window.range_samples.sr)
            )
            if end_sample <= start_sample:
                continue
            frames.append(
                DiarFrame(
                    range_samples=TimeRangeSamples(
                        start=start_sample,
                        end=end_sample,
                        sr=window.range_samples.sr,
                    ),
                    label=self._normalize_label(seg.speaker_id),
                    conf=1.0,
                    is_patch=False,
                )
            )
        return self._merge_adjacent(frames)

    @staticmethod
    def _normalize_label(label: str) -> str:
        """NeMo uses 'spk_0'; v2 timeline and VoiceIdMatcher expect 'spk0' (no underscore)."""
        if label.startswith("spk_"):
            return "spk" + label.split("_", 1)[1]
        return label

    def _fallback_diarize(self, window: AudioWindow) -> List[DiarFrame]:
        """When NeMo is unavailable or fails: one frame per window from RMS energy (spk0 or UNCERTAIN)."""
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
        """Emit a refine patch at most every patch_emit_s seconds; patch covers last patch_window_s of recent_frames."""
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
        """Keep only recent_frames within the last patch_window_s so patch building stays bounded."""
        if not state.recent_frames:
            return
        max_samples = int(self.patch_window_s * state.sr)
        latest_end = state.recent_frames[-1].range_samples.end
        min_sample = max(0, latest_end - max_samples)
        state.recent_frames = [
            frame for frame in state.recent_frames if frame.range_samples.end > min_sample
        ]

    @staticmethod
    def _merge_adjacent(frames: List[DiarFrame]) -> List[DiarFrame]:
        """Merge consecutive frames with same label and abutting ranges to reduce timeline fragmentation."""
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
                # Static methods have no self; use module-level _logger for warnings.
                _logger.warning(
                    "Non-adjacent diar frame (label=%s, range=%s-%s), appended",
                    frame.label,
                    frame.range_samples.start,
                    frame.range_samples.end,
                )
                merged.append(frame)
        return merged

    def _reset_stream_state(self, state: _DiarState) -> None:
        """Clear pending buffer and NeMo streaming state so the next window starts from a clean timeline (e.g. after gap)."""
        state.pending_pcm.clear()
        state.pending_start_sample = None
        if state.streaming_diarizer is not None and hasattr(
            state.streaming_diarizer, "reset_state"
        ):
            state.streaming_diarizer.reset_state()
