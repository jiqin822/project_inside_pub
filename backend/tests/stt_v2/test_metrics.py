from app.api.stt_v2.metrics import MetricsCollector
from app.domain.stt_v2.contracts import SpeakerSentence, TimeRangeMs, UiSentence


def _sentence(sentence_id: str, duration_ms: int) -> SpeakerSentence:
    ui = UiSentence(
        id=sentence_id,
        range_ms=TimeRangeMs(start_ms=0, end_ms=duration_ms),
        text="hello",
        is_final=True,
    )
    return SpeakerSentence(
        ui_sentence=ui,
        label="spk0",
        label_conf=1.0,
        coverage=1.0,
        flags={"overlap": False, "uncertain": False, "patched": False},
    )


def test_metrics_sentence_length_histogram():
    metrics = MetricsCollector()
    durations = [300, 900, 3000, 9000, 20000]
    for idx, duration in enumerate(durations):
        metrics.record_sentence(_sentence(f"sent_{idx}", duration))

    snapshot = metrics.snapshot()
    hist = snapshot["sentence_len_hist"]
    assert hist["<= 500ms"] == 1
    assert hist["<= 1000ms"] == 1
    assert hist["<= 4000ms"] == 1
    assert hist["<= 12000ms"] == 1
    assert hist["> 12000ms"] == 1
