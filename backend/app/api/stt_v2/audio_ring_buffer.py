"""Multi-stream audio ring buffer for STT V2."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np

from app.domain.stt_v2.contracts import SampleIndex, StreamId, TimeRangeSamples


@dataclass
class _StreamRingBuffer:
    sample_rate: int
    max_seconds: int

    def __post_init__(self) -> None:
        self.max_samples = self.max_seconds * self.sample_rate
        self.buffer = np.zeros(self.max_samples, dtype=np.int16)
        self.write_index = 0
        self.total_samples: SampleIndex = 0

    def append(self, chunk: bytes) -> None:
        data = np.frombuffer(chunk, dtype=np.int16)
        if data.size == 0:
            return
        if data.size >= self.max_samples:
            data = data[-self.max_samples :]
        end_index = self.write_index + data.size
        if end_index <= self.max_samples:
            self.buffer[self.write_index:end_index] = data
        else:
            first_part = self.max_samples - self.write_index
            self.buffer[self.write_index:] = data[:first_part]
            self.buffer[: end_index % self.max_samples] = data[first_part:]
        self.write_index = end_index % self.max_samples
        self.total_samples += data.size

    def slice(self, start_sample: SampleIndex, end_sample: SampleIndex) -> Optional[np.ndarray]:
        if end_sample <= start_sample:
            return None
        earliest_sample = max(0, self.total_samples - self.max_samples)
        if start_sample < earliest_sample or end_sample > self.total_samples:
            return None
        start_offset = start_sample - earliest_sample
        end_offset = end_sample - earliest_sample
        if end_offset <= self.max_samples:
            data = self.buffer[start_offset:end_offset]
        else:
            first_part = self.buffer[start_offset:]
            second_part = self.buffer[: end_offset % self.max_samples]
            data = np.concatenate([first_part, second_part])
        return data


class AudioRingBuffer:
    """Ring buffers per stream_id with read/write by sample range."""

    def __init__(self, sample_rate: int, max_seconds: int = 60) -> None:
        self.sample_rate = sample_rate
        self.max_seconds = max_seconds
        self._streams: Dict[StreamId, _StreamRingBuffer] = {}

    def _get_stream(self, stream_id: StreamId) -> _StreamRingBuffer:
        if stream_id not in self._streams:
            self._streams[stream_id] = _StreamRingBuffer(
                sample_rate=self.sample_rate, max_seconds=self.max_seconds
            )
        return self._streams[stream_id]

    def write(self, stream_id: StreamId, range_samples: TimeRangeSamples, pcm16_bytes: bytes) -> None:
        stream = self._get_stream(stream_id)
        expected_samples = range_samples.end - range_samples.start
        expected_bytes = expected_samples * 2
        if expected_samples <= 0 or expected_bytes != len(pcm16_bytes):
            # Accept but do not write on mismatch to avoid corrupting timeline.
            return
        stream.append(pcm16_bytes)

    def read(self, stream_id: StreamId, range_samples: TimeRangeSamples) -> Optional[np.ndarray]:
        stream = self._get_stream(stream_id)
        return stream.slice(range_samples.start, range_samples.end)

    def latest_sample(self, stream_id: StreamId) -> SampleIndex:
        return self._get_stream(stream_id).total_samples

    def read_last_seconds(self, stream_id: StreamId, seconds: int) -> Optional[np.ndarray]:
        if seconds <= 0:
            return None
        stream = self._get_stream(stream_id)
        end_sample = stream.total_samples
        start_sample = max(0, end_sample - (seconds * self.sample_rate))
        return stream.slice(start_sample, end_sample)
