from dataclasses import replace
from types import SimpleNamespace

from app.api.stt_v2.routes_stt_v2 import _build_services, _speaker_sentence_payload
from app.domain.stt_v2.contracts import (
    SpeakerSentence,
    TimeRangeMs,
    UiSentence,
    UNCERTAIN_LABEL,
)


def _ui_sentence(sentence_id: str, start_ms: int, end_ms: int, text: str) -> UiSentence:
    return UiSentence(
        id=sentence_id,
        range_ms=TimeRangeMs(start_ms=start_ms, end_ms=end_ms),
        text=text,
    )


def test_speaker_sentence_payload_includes_ui_fields() -> None:
    ui_sentence = _ui_sentence("sent_1", 0, 500, "hello")
    ui_sentence = replace(
        ui_sentence,
        ui_context={"provisional": True},
        split_from="sent_0",
    )
    ss = SpeakerSentence(
        ui_sentence=ui_sentence,
        label="spk1",
        label_conf=0.9,
        coverage=0.8,
        flags={"provisional": True},
        speaker_color="self",
    )
    payload = _speaker_sentence_payload("stream-1", ss, "ui.sentence", debug_enabled=False)
    assert payload["speaker_color"] == "self"
    assert payload["ui_context"] == {"provisional": True}
    assert payload["split_from"] == "sent_0"


def test_prepare_updates_handles_splits_and_provisional() -> None:
    services = _build_services()
    orchestrator = services.orchestrator
    ctx = SimpleNamespace(user_id="user-1", candidate_user_ids=["user-2"])

    ui_a = _ui_sentence("sent_3_a", 0, 500, "hello")
    ss_a = SpeakerSentence(
        ui_sentence=ui_a,
        label="user-1",
        label_conf=0.9,
        coverage=0.9,
        flags={},
    )
    patches, new_items = orchestrator._prepare_updates(ss_a, ctx)
    assert len(patches) == 1
    assert not new_items
    assert patches[0].ui_sentence.id == "sent_3"
    assert patches[0].ui_sentence.split_from is None
    assert patches[0].flags.get("provisional") is False

    ui_b = _ui_sentence("sent_3_b", 500, 900, "there")
    ss_b = SpeakerSentence(
        ui_sentence=ui_b,
        label="user-2",
        label_conf=0.8,
        coverage=0.8,
        flags={},
    )
    patches, new_items = orchestrator._prepare_updates(ss_b, ctx)
    assert not patches
    assert len(new_items) == 1
    assert new_items[0].ui_sentence.split_from == "sent_3"

    provisional = orchestrator._build_provisional_sentence(ui_b, ctx)
    assert provisional.label == UNCERTAIN_LABEL
    assert provisional.flags.get("provisional") is True
    assert provisional.ui_sentence.ui_context == {"provisional": True}
    assert provisional.speaker_color == "unknown"
