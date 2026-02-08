import pytest
from starlette.websockets import WebSocketDisconnect

from app.api.stt_v2.routes_stt_v2 import _V2Services, stream_stt_v2
from app.api.stt_v2.session_orchestrator import OrchestratorOutput
from app.domain.stt_v2.contracts import SpeakerSentence, TimeRangeMs, UiSentence
from app.settings import get_config_store


class DummyWebSocket:
    def __init__(self):
        self.sent = []
        self._received = False

    async def accept(self):
        return None

    async def receive_bytes(self):
        if self._received:
            raise WebSocketDisconnect()
        self._received = True
        return b"\x00" * 320

    async def send_json(self, data):
        self.sent.append(data)

    async def close(self, code: int = 1000, reason: str | None = None):
        _ = code
        _ = reason
        return None

    @property
    def query_params(self):
        return {}


class DummyGoogleStt:
    async def ensure_credentials_and_client(self, _ws):
        return object(), None


class DummySessionService:
    def __init__(self):
        self.google_stt_client = DummyGoogleStt()

    async def validate_stream_request(self, _ws, _session_id, _token):
        class DummyCtx:
            language_code = "en-US"

        return "user", DummyCtx()


class DummyOrchestrator:
    def start_session(self, *_args, **_kwargs):
        return None

    def stop_session(self, *_args, **_kwargs):
        return None

    def process_audio_chunk(self, *_args, **_kwargs):
        sentence = UiSentence(
            id="sent_1",
            range_ms=TimeRangeMs(start_ms=0, end_ms=1000),
            text="hello",
            is_final=True,
        )
        ss = SpeakerSentence(
            ui_sentence=sentence,
            label="spk0",
            label_conf=0.9,
            coverage=0.9,
            flags={"overlap": False, "uncertain": False, "patched": False},
        )
        return OrchestratorOutput(speaker_sentences=[ss], ui_sentence_patches=[], nudges=[])


@pytest.mark.asyncio
async def test_shadow_mode_suppresses_emits(monkeypatch):
    # Scenario: when shadow mode is enabled, websocket emits are suppressed.
    store = get_config_store()
    store.update({"stt_v2_shadow_mode": True})

    def fake_build_services():
        return _V2Services(stt_session_service=DummySessionService(), orchestrator=DummyOrchestrator())

    monkeypatch.setattr("app.api.stt_v2.routes_stt_v2._build_services", fake_build_services)

    ws = DummyWebSocket()
    await stream_stt_v2(ws, "session_1")
    assert ws.sent == []

    store.clear_overrides()
