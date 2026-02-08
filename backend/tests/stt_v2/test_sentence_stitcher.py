from app.api.stt_v2.sentence_stitcher import SentenceStitcher
from app.domain.stt_v2.contracts import SpeakerSentence, TimeRangeMs, UiSentence


def test_sentence_stitcher_merges_adjacent():
    # Scenario: adjacent sentences from the same speaker within stitch gap should merge.
    stitcher = SentenceStitcher(stitch_gap_ms=300, max_stitched_ms=9000)
    s1 = SpeakerSentence(
        ui_sentence=UiSentence(
            id="sent_1",
            range_ms=TimeRangeMs(start_ms=0, end_ms=1000),
            text="hello",
            is_final=True,
        ),
        label="spk0",
        label_conf=0.8,
        coverage=0.8,
        flags={"overlap": False, "uncertain": False, "patched": False},
    )
    s2 = SpeakerSentence(
        ui_sentence=UiSentence(
            id="sent_2",
            range_ms=TimeRangeMs(start_ms=1100, end_ms=1800),
            text="world",
            is_final=True,
        ),
        label="spk0",
        label_conf=0.9,
        coverage=0.9,
        flags={"overlap": False, "uncertain": False, "patched": False},
    )
    assert stitcher.on_speaker_sentence("s1", s1) == []
    assert stitcher.on_speaker_sentence("s1", s2) == []
    merged = stitcher.flush("s1")
    assert merged
    assert merged[0].ui_sentence.text == "hello world"
