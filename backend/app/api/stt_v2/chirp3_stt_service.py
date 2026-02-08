"""Chirp3 streaming STT wrapper (segment-level timestamps only)."""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional

from google.cloud import speech_v2 as speech

from app.api.stt.google_stt_client import GoogleSttClient
from app.domain.stt.session_registry import SttSessionContext
from app.domain.stt_v2.contracts import AudioChunk, SttSegment, StreamId, TimeRangeMs


@dataclass
class _StreamState:
    audio_queue: queue.Queue[Optional[bytes]]
    segment_queue: queue.Queue[SttSegment]
    stop_event: threading.Event
    thread: threading.Thread
    last_end_ms: int = 0


class Chirp3SttService:
    """Placeholder Chirp3 streaming STT integration.

    Implement streaming requests to Chirp3 and emit SttSegment events.
    """

    def __init__(self, google_stt_client: GoogleSttClient) -> None:
        self.google_stt_client = google_stt_client
        self._streams: Dict[StreamId, _StreamState] = {}

    def start(
        self,
        stream_id: StreamId,
        sr: int,
        ctx: SttSessionContext,
        client: speech.SpeechClient,
    ) -> None:
        if stream_id in self._streams:
            return
        audio_queue: queue.Queue[Optional[bytes]] = queue.Queue()
        segment_queue: queue.Queue[SttSegment] = queue.Queue()
        stop_event = threading.Event()

        lang = (ctx.language_code or "").strip().lower()
        language_codes = ["auto"] if lang == "auto" else [ctx.language_code or "en-US"]
        request_generator_sync = self.google_stt_client.build_request_generator(
            audio_queue=audio_queue,
            ctx=ctx,
            language_codes=language_codes,
            model_id="chirp_3",
            enable_diarization_for_request=False,
        )

        thread = threading.Thread(
            target=self._run_streaming_recognize,
            args=(client, request_generator_sync, audio_queue, segment_queue, stop_event),
            daemon=True,
        )
        self._streams[stream_id] = _StreamState(
            audio_queue=audio_queue,
            segment_queue=segment_queue,
            stop_event=stop_event,
            thread=thread,
            last_end_ms=0,
        )
        thread.start()

    def stop(self, stream_id: StreamId) -> None:
        state = self._streams.get(stream_id)
        if not state:
            return
        state.stop_event.set()
        try:
            state.audio_queue.put(None)
        except Exception as exc:
            pass
        state.thread.join(timeout=2)
        self._streams.pop(stream_id, None)

    def process_audio_chunk(self, chunk: AudioChunk) -> List[SttSegment]:
        state = self._streams.get(chunk.stream_id)
        if state is None:
            return []
        state.audio_queue.put(chunk.pcm16_bytes)
        segments: List[SttSegment] = []
        try:
            while True:
                segments.append(state.segment_queue.get_nowait())
        except queue.Empty:
            return segments

    @staticmethod
    def _build_segment(start_ms: int, end_ms: int, text: str, conf: float, is_final: bool) -> SttSegment:
        return SttSegment(range_ms=TimeRangeMs(start_ms=start_ms, end_ms=end_ms), text=text, stt_conf=conf, is_final=is_final)

    def _run_streaming_recognize(
        self,
        client: speech.SpeechClient,
        request_generator_sync,
        audio_queue: queue.Queue[Optional[bytes]],
        segment_queue: queue.Queue[SttSegment],
        stop_event: threading.Event,
    ) -> None:
        try:
            responses = client.streaming_recognize(
                requests=request_generator_sync(enable_diarization=False)
            )
            last_end_ms = 0
            for response in responses:
                if stop_event.is_set():
                    break
                results = getattr(response, "results", []) or []
                for result in results:
                    is_final = bool(getattr(result, "is_final", False))
                    if not is_final:
                        continue
                    alternatives = getattr(result, "alternatives", []) or []
                    if not alternatives:
                        continue
                    alt = alternatives[0]
                    text = getattr(alt, "transcript", "") or ""
                    conf = float(getattr(alt, "confidence", 0.0) or 0.0)
                    end_ms = self._duration_to_ms(getattr(result, "result_end_offset", None))
                    if end_ms <= 0:
                        end_ms = last_end_ms
                    start_ms = last_end_ms
                    if end_ms < start_ms:
                        end_ms = start_ms
                    last_end_ms = end_ms
                    segment_queue.put(
                        self._build_segment(start_ms, end_ms, text, conf, True)
                    )
        except Exception:
            return

    @staticmethod
    def _duration_to_ms(duration: Optional[object]) -> int:
        if duration is None:
            return 0
        seconds = getattr(duration, "seconds", 0) or 0
        nanos = getattr(duration, "nanos", 0) or 0
        return int(seconds * 1000 + nanos / 1_000_000)
