from app.api.stt_v2.speaker_timeline_store import SpeakerTimelineStore
from app.domain.stt_v2.contracts import DiarFrame, TimeRangeSamples


def test_speaker_timeline_store_merges_intervals():
    # Scenario: adjacent frames with same label should merge into one interval.
    store = SpeakerTimelineStore(
        sample_rate=16000,
        min_turn_ms=0,
        switch_confirm_ms=0,
        cooldown_ms=0,
        switch_margin=0.0,
        max_minutes=1,
    )
    stream_id = "s1"
    frame1 = DiarFrame(
        range_samples=TimeRangeSamples(start=0, end=1600, sr=16000),
        label="spk0",
        conf=0.8,
    )
    frame2 = DiarFrame(
        range_samples=TimeRangeSamples(start=1600, end=3200, sr=16000),
        label="spk0",
        conf=0.7,
    )
    store.apply_frames(stream_id, [frame1, frame2])
    stats = store.stats(stream_id)
    assert stats["intervals"] == 1


def test_speaker_timeline_store_switches_when_allowed():
    # Scenario: stabilizer should switch when all commit conditions are satisfied.
    store = SpeakerTimelineStore(
        sample_rate=16000,
        min_turn_ms=0,
        switch_confirm_ms=0,
        cooldown_ms=0,
        switch_margin=0.0,
        max_minutes=1,
    )
    stream_id = "s1"
    frame1 = DiarFrame(
        range_samples=TimeRangeSamples(start=0, end=1600, sr=16000),
        label="spk0",
        conf=0.2,
    )
    frame2 = DiarFrame(
        range_samples=TimeRangeSamples(start=1600, end=3200, sr=16000),
        label="spk1",
        conf=0.9,
    )
    store.apply_frames(stream_id, [frame1, frame2])
    intervals = store.query(stream_id, TimeRangeSamples(start=0, end=3200, sr=16000))
    labels = [label for _range, label, _conf, _patch in intervals]
    assert "spk0" in labels and "spk1" in labels
