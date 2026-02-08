"""Audio ingestion for STT V2."""
from __future__ import annotations

from dataclasses import dataclass

from app.api.stt_v2.audio_ring_buffer import AudioRingBuffer
from app.domain.stt_v2.contracts import AudioChunk, StreamId, TimeRangeSamples


@dataclass
class AudioIngestor:
    ring_buffer: AudioRingBuffer
    sample_rate: int

    def push_pcm16(self, stream_id: StreamId, pcm16_bytes: bytes, sr: int) -> AudioChunk:
        """Receive PCM16 bytes, assign sample indices, write to ring buffer."""
        latest = self.ring_buffer.latest_sample(stream_id)
        samples_count = len(pcm16_bytes) // 2
        range_samples = TimeRangeSamples(
            start=latest, end=latest + samples_count, sr=sr
        )
        self.ring_buffer.write(stream_id, range_samples, pcm16_bytes)
        return AudioChunk(stream_id=stream_id, range_samples=range_samples, pcm16_bytes=pcm16_bytes)
