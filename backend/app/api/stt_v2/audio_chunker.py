"""Convert audio chunks into fixed frames and diarization windows."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Union

import numpy as np

from app.domain.stt_v2.contracts import (
    AudioChunk,
    AudioFrame,
    AudioWindow,
    StreamId,
    TimeRangeSamples,
)


@dataclass
class _ChunkState:
    pending_samples: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int16))
    pending_start_sample: int = 0
    window_buffer: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int16))
    window_start_sample: int = 0
    next_window_start_sample: int = 0


class AudioChunker:
    def __init__(self, sample_rate: int, frame_ms: int = 20, window_s: float = 1.6, hop_s: float = 0.4) -> None:
        self.sample_rate = sample_rate
        self.frame_samples = max(1, int((frame_ms * sample_rate) / 1000))
        self.window_samples = max(1, int(window_s * sample_rate))
        self.hop_samples = max(1, int(hop_s * sample_rate))
        self._states: Dict[StreamId, _ChunkState] = {}

    def _state(self, stream_id: StreamId) -> _ChunkState:
        if stream_id not in self._states:
            self._states[stream_id] = _ChunkState()
        return self._states[stream_id]

    def on_audio_chunk(self, chunk: AudioChunk) -> List[Union[AudioFrame, AudioWindow]]:
        state = self._state(chunk.stream_id)
        output: List[Union[AudioFrame, AudioWindow]] = []
        samples = np.frombuffer(chunk.pcm16_bytes, dtype=np.int16)
        if samples.size == 0:
            return output

        # Update pending buffer for frames (ensure continuity).
        if state.pending_samples.size == 0:
            state.pending_start_sample = chunk.range_samples.start
            state.pending_samples = samples
        else:
            expected_start = state.pending_start_sample + state.pending_samples.size
            if chunk.range_samples.start != expected_start:
                state.pending_start_sample = chunk.range_samples.start
                state.pending_samples = samples
            else:
                state.pending_samples = np.concatenate([state.pending_samples, samples])

        # Emit fixed-size frames.
        while state.pending_samples.size >= self.frame_samples:
            frame_samples = state.pending_samples[: self.frame_samples]
            frame_start = state.pending_start_sample
            frame_end = frame_start + self.frame_samples
            frame_range = TimeRangeSamples(start=frame_start, end=frame_end, sr=chunk.range_samples.sr)
            output.append(
                AudioFrame(stream_id=chunk.stream_id, range_samples=frame_range, pcm16_np=frame_samples)
            )
            state.pending_samples = state.pending_samples[self.frame_samples :]
            state.pending_start_sample = frame_end

        # Update window buffer (ensure continuity).
        if state.window_buffer.size == 0:
            state.window_start_sample = chunk.range_samples.start
            state.window_buffer = samples
            state.next_window_start_sample = chunk.range_samples.start
        else:
            expected_start = state.window_start_sample + state.window_buffer.size
            if chunk.range_samples.start != expected_start:
                state.window_start_sample = chunk.range_samples.start
                state.window_buffer = samples
                state.next_window_start_sample = chunk.range_samples.start
            else:
                state.window_buffer = np.concatenate([state.window_buffer, samples])

        # Emit windows on hop boundaries when enough samples are available.
        while (
            state.next_window_start_sample + self.window_samples
            <= state.window_start_sample + state.window_buffer.size
        ):
            offset = state.next_window_start_sample - state.window_start_sample
            window_samples = state.window_buffer[offset : offset + self.window_samples]
            window_range = TimeRangeSamples(
                start=state.next_window_start_sample,
                end=state.next_window_start_sample + self.window_samples,
                sr=chunk.range_samples.sr,
            )
            output.append(
                AudioWindow(stream_id=chunk.stream_id, range_samples=window_range, pcm16_np=window_samples)
            )
            state.next_window_start_sample += self.hop_samples

        # Trim window buffer to keep memory bounded (retain last 2 windows).
        keep_start = max(
            state.next_window_start_sample - 2 * self.window_samples,
            state.window_start_sample,
        )
        if keep_start > state.window_start_sample:
            trim_offset = keep_start - state.window_start_sample
            state.window_buffer = state.window_buffer[trim_offset:]
            state.window_start_sample = keep_start

        return output
