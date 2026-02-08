from app.api.stt.google_stt_client import GoogleSttClient
from app.api.stt_v2.routes_stt_v2 import _build_services, _speaker_sentence_payload
from app.domain.stt_v2.contracts import SpeakerSentence, TimeRangeMs, UiSentence


def test_build_services_wires_chirp3_client():
    # Scenario: router services should wire Chirp3 with Google STT client.
    services = _build_services()
    stt_service = services.orchestrator.stt_service
    assert isinstance(stt_service.google_stt_client, GoogleSttClient)


def test_speaker_sentence_payload_shape():
    # Scenario: ui.sentence payload matches contract shape.
    sentence = UiSentence(
        id="sent_1",
        range_ms=TimeRangeMs(start_ms=100, end_ms=200),
        text="hello",
        is_final=True,
    )
    ss = SpeakerSentence(
        ui_sentence=sentence,
        label="spk0",
        label_conf=0.9,
        coverage=0.8,
        flags={"overlap": False, "uncertain": False, "patched": False},
    )
    payload = _speaker_sentence_payload("stream_1", ss, "ui.sentence")
    assert payload["type"] == "ui.sentence"
    assert payload["id"] == "sent_1"
    assert payload["stream_id"] == "stream_1"
    assert payload["start_ms"] == 100
    assert payload["end_ms"] == 200
    assert payload["label"] == "spk0"
    assert payload["label_conf"] == 0.9
    assert payload["coverage"] == 0.8
    assert payload["text"] == "hello"
    assert payload["flags"]["patched"] is False
