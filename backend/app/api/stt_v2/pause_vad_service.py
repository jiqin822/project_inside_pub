"""Simple energy-based VAD with pause event generation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from app.domain.stt_v2.contracts import AudioFrame, PauseEvent, SpeechRegion, StreamId, TimeRangeSamples


@dataclass
class _VadState:
    in_speech: bool = False
    speech_start_sample: int = 0
    silence_start_sample: int | None = None
    pause_emitted: bool = False


class PauseVADService:
    def __init__(
        self,
        sample_rate: int,
        vad_frame_ms: int = 20,
        vad_hangover_ms: int = 300,
        pause_split_ms: int = 600,
        pause_merge_ms: int = 200,
        energy_threshold: float = 0.01,
    ) -> None:
        self.sample_rate = sample_rate
        self.vad_frame_ms = vad_frame_ms
        self.vad_hangover_ms = vad_hangover_ms
        self.pause_split_ms = pause_split_ms
        self.pause_merge_ms = pause_merge_ms
        self.energy_threshold = energy_threshold
        self._states: Dict[StreamId, _VadState] = {}

    def _state(self, stream_id: StreamId) -> _VadState:
        if stream_id not in self._states:
            self._states[stream_id] = _VadState()
        return self._states[stream_id]

    def process_frame(self, frame: AudioFrame) -> List[SpeechRegion | PauseEvent]:
        state = self._state(frame.stream_id)
        output: List[SpeechRegion | PauseEvent] = []
        if frame.pcm16_np.size == 0:
            return output

        # RMS energy-based VAD.
        energy = float(np.sqrt(np.mean(frame.pcm16_np.astype(np.float32) ** 2)) / 32768.0)
        is_speech = energy >= self.energy_threshold

        if is_speech:
            if not state.in_speech:
                state.in_speech = True
                state.speech_start_sample = frame.range_samples.start
            state.silence_start_sample = None
            state.pause_emitted = False
            output.append(SpeechRegion(range_samples=frame.range_samples, vad_conf=min(1.0, energy * 10)))
            return output

        # Silence frame.
        if state.silence_start_sample is None:
            state.silence_start_sample = frame.range_samples.start
        silence_samples = frame.range_samples.end - state.silence_start_sample
        silence_ms = int((silence_samples * 1000) / frame.range_samples.sr)

        # Short gaps are merged into speech; no pause event.
        if silence_ms < self.pause_merge_ms:
            return output

        # Emit pause event once when silence exceeds split threshold.
        if silence_ms >= self.pause_split_ms and not state.pause_emitted:
            pause_range = TimeRangeSamples(
                start=state.silence_start_sample,
                end=frame.range_samples.end,
                sr=frame.range_samples.sr,
            )
            output.append(
                PauseEvent(
                    range_samples=pause_range,
                    pause_ms=silence_ms,
                    conf=min(1.0, silence_ms / max(1, self.pause_split_ms)),
                )
            )
            state.pause_emitted = True

        # Mark speech as ended after hangover.
        if state.in_speech and silence_ms >= self.vad_hangover_ms:
            state.in_speech = False

        return output
