import time

from app.api.stt.google_stt_client import GoogleSttClient
from app.api.stt_v2.chirp3_stt_service import Chirp3SttService
from app.domain.stt.session_registry import SttSessionContext
from app.domain.stt_v2.contracts import AudioChunk, TimeRangeMs, TimeRangeSamples


class _FakeDuration:
    def __init__(self, seconds: int, nanos: int = 0) -> None:
        self.seconds = seconds
        self.nanos = nanos


class _FakeAlternative:
    def __init__(self, transcript: str, confidence: float) -> None:
        self.transcript = transcript
        self.confidence = confidence


class _FakeResult:
    def __init__(self, is_final: bool, transcript: str, confidence: float, end_ms: int) -> None:
        self.is_final = is_final
        self.alternatives = [_FakeAlternative(transcript, confidence)]
        seconds = end_ms // 1000
        nanos = (end_ms % 1000) * 1_000_000
        self.result_end_offset = _FakeDuration(seconds, nanos)


class _FakeResponse:
    def __init__(self, results) -> None:
        self.results = results


class _FakeSpeechClient:
    def streaming_recognize(self, requests):
        # Consume initial config request if present.
        try:
            next(iter(requests))
        except Exception:
            pass
        yield _FakeResponse([_FakeResult(True, "hello", 0.9, 1000)])


def test_chirp3_emits_final_segments():
    ctx = SttSessionContext(
        session_id="s1",
        user_id="u1",
        candidate_user_ids=[],
        language_code="en-US",
        min_speaker_count=1,
        max_speaker_count=2,
    )
    service = Chirp3SttService(GoogleSttClient())
    service.start("s1", 16000, ctx, _FakeSpeechClient())

    chunk = AudioChunk(
        stream_id="s1",
        range_samples=TimeRangeSamples(start=0, end=16000, sr=16000),
        pcm16_bytes=b"\x00" * 320,
    )

    segments = []
    for _ in range(50):
        segments = service.process_audio_chunk(chunk)
        if segments:
            break
        time.sleep(0.01)

    service.stop("s1")
    assert segments, "Expected at least one final segment"
    seg = segments[0]
    assert seg.text == "hello"
    assert seg.is_final is True
    assert seg.range_ms.end_ms >= seg.range_ms.start_ms
