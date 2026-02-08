"""Diarization service interface for STT v2."""
from __future__ import annotations

from typing import Protocol

from app.domain.stt_v2.contracts import AudioWindow, DiarFrame, DiarPatch, StreamId


class DiarizationService(Protocol):
    def start(self, stream_id: StreamId, sr: int) -> None:
        """Initialize per-stream diarization state."""

    def process_window(self, window: AudioWindow) -> list[DiarFrame | DiarPatch]:
        """Process an audio window and emit diarization frames/patches."""
