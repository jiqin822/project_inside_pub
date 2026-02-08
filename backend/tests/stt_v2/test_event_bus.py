from app.api.stt_v2.event_bus import EventQueue
from app.domain.stt_v2.contracts import DiarFrame, TimeRangeSamples


def test_event_bus_drops_preview_before_patch():
    # Scenario: when queue is full, preview diarization frames are dropped before patches.
    q = EventQueue(maxsize=2)
    preview = DiarFrame(TimeRangeSamples(0, 160, 16000), "spk0", 0.5, is_patch=False)
    patch = DiarFrame(TimeRangeSamples(160, 320, 16000), "spk1", 0.9, is_patch=True)
    q.push(preview, drop_preview_first=True)
    q.push(patch, drop_preview_first=True)
    q.push(DiarFrame(TimeRangeSamples(320, 480, 16000), "spk2", 0.9, is_patch=True), drop_preview_first=True)
    items = q.pop_all()
    assert all(getattr(i, "is_patch", False) for i in items)
