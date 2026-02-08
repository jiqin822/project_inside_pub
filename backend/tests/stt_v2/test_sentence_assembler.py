from app.api.stt_v2.sentence_assembler import SentenceAssembler
from app.domain.stt_v2.contracts import PauseEvent, SttSegment, TimeRangeMs, TimeRangeSamples


def test_sentence_assembler_finalizes_on_strong_punctuation():
    # Scenario: strong punctuation should finalize a sentence when min_chars is satisfied.
    assembler = SentenceAssembler(sample_rate=16000)
    seg = SttSegment(
        range_ms=TimeRangeMs(start_ms=0, end_ms=1200),
        text="Hello there.",
        stt_conf=0.9,
        is_final=True,
    )
    sentences = assembler.on_stt_segment("s1", seg)
    assert len(sentences) == 1
    assert sentences[0].text == "Hello there."


def test_sentence_assembler_finalizes_on_pause():
    # Scenario: an obvious pause should finalize a buffered sentence.
    assembler = SentenceAssembler(sample_rate=16000, pause_split_ms=600, min_chars=5)
    seg = SttSegment(
        range_ms=TimeRangeMs(start_ms=0, end_ms=1000),
        text="We should talk",
        stt_conf=0.9,
        is_final=True,
    )
    assert assembler.on_stt_segment("s1", seg) == []

    pause = PauseEvent(
        range_samples=TimeRangeSamples(start=16000, end=17600, sr=16000),
        pause_ms=600,
        conf=1.0,
    )
    sentences = assembler.on_pause_event("s1", pause)
    assert len(sentences) == 1
    assert sentences[0].text.startswith("We should talk")


def test_sentence_assembler_forced_split_on_max_chars():
    # Scenario: overly long text should be split at the best available boundary.
    assembler = SentenceAssembler(sample_rate=16000, max_chars=20, min_chars=5)
    seg = SttSegment(
        range_ms=TimeRangeMs(start_ms=0, end_ms=1000),
        text="This sentence is definitely longer than twenty chars",
        stt_conf=0.9,
        is_final=True,
    )
    sentences = assembler.on_stt_segment("s1", seg)
    assert sentences, "Expected at least one sentence from forced split"
    assert all(len(s.text) <= 60 for s in sentences)
