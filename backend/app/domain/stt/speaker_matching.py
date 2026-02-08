from __future__ import annotations

import numpy as np
from typing import Optional


class AudioRingBuffer:
    def __init__(self, sample_rate: int, max_seconds: int = 30) -> None:
        self.sample_rate = sample_rate
        self.max_samples = max_seconds * sample_rate
        self.buffer = np.zeros(self.max_samples, dtype=np.int16)
        self.write_index = 0
        self.total_samples = 0

    def append(self, chunk: bytes) -> None:
        data = np.frombuffer(chunk, dtype=np.int16)
        if data.size == 0:
            return
        if data.size >= self.max_samples:
            data = data[-self.max_samples:]
        end_index = self.write_index + data.size
        if end_index <= self.max_samples:
            self.buffer[self.write_index:end_index] = data
        else:
            first_part = self.max_samples - self.write_index
            self.buffer[self.write_index:] = data[:first_part]
            self.buffer[: end_index % self.max_samples] = data[first_part:]
        self.write_index = end_index % self.max_samples
        self.total_samples += data.size

    def slice(self, start_sample: int, end_sample: int) -> Optional[np.ndarray]:
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
            # Wrap around
            first_part = self.buffer[start_offset:]
            second_part = self.buffer[: end_offset % self.max_samples]
            data = np.concatenate([first_part, second_part])
        return data


