import numpy as np

from app.api.stt_v2.pause_vad_service import PauseVADService
from app.domain.stt_v2.contracts import AudioFrame, PauseEvent, TimeRangeSamples


def _silent_frame(stream_id: str, start_sample: int, end_sample: int, sr: int = 16000) -> AudioFrame:
    return AudioFrame(
        stream_id=stream_id,
        range_samples=TimeRangeSamples(start=start_sample, end=end_sample, sr=sr),
        pcm16_np=np.zeros(end_sample - start_sample, dtype=np.int16),
    )

def _speech_frame(stream_id: str, start_sample: int, end_sample: int, sr: int = 16000) -> AudioFrame:
    pcm = np.ones(end_sample - start_sample, dtype=np.int16) * 1000
    return AudioFrame(
        stream_id=stream_id,
        range_samples=TimeRangeSamples(start=start_sample, end=end_sample, sr=sr),
        pcm16_np=pcm,
    )


def test_pause_vad_emits_pause_after_threshold():
    # Scenario: sustained silence should trigger a PauseEvent once the split threshold is reached.
    vad = PauseVADService(sample_rate=16000, pause_split_ms=600, pause_merge_ms=200)
    pause_events = []
    # 30 frames * 20ms = 600ms of silence
    for i in range(30):
        frame = _silent_frame("s1", i * 320, (i + 1) * 320)
        events = vad.process_frame(frame)
        pause_events.extend([e for e in events if isinstance(e, PauseEvent)])
    assert pause_events, "Expected at least one pause event after 600ms of silence"


def test_pause_vad_merges_short_gaps():
    vad = PauseVADService(sample_rate=16000, pause_split_ms=600, pause_merge_ms=200)
    events = []
    # Start with speech.
    for i in range(5):
        frame = _speech_frame("s1", i * 320, (i + 1) * 320)
        events.extend(vad.process_frame(frame))
    # Short silence (< pause_merge_ms): should be merged into speech.
    silence_start = 5 * 320
    for i in range(5):
        frame = _silent_frame("s1", silence_start + i * 320, silence_start + (i + 1) * 320)
        events.extend(vad.process_frame(frame))
    # Resume speech.
    speech_start = silence_start + 5 * 320
    for i in range(5):
        frame = _speech_frame("s1", speech_start + i * 320, speech_start + (i + 1) * 320)
        events.extend(vad.process_frame(frame))

    assert not any(isinstance(e, PauseEvent) for e in events)
