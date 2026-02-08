"""No-op diarization service for STT v2. Skips diarization entirely; pipeline still runs (STT, sentences, etc.)."""
from __future__ import annotations

from typing import Dict, List

from app.domain.stt_v2.contracts import (
    AudioWindow,
    DiarFrame,
    DiarPatch,
    StreamId,
)


class NoneDiarizationService:
    """Diarization backend that returns no frames or patches. No model loaded."""

    def __init__(self) -> None:
        self._states: Dict[StreamId, None] = {}

    def start(self, stream_id: StreamId, sr: int) -> None:
        self._states[stream_id] = None

    def process_window(self, window: AudioWindow) -> List[DiarFrame | DiarPatch]:
        if window.stream_id not in self._states:
            self.start(window.stream_id, window.range_samples.sr)
        return []
