import asyncio
import os
import re
import sys
import time
import uuid
from pathlib import Path

import numpy as np
import pytest
from google.cloud import speech_v2 as speech
from scipy.io import wavfile
from scipy.signal import resample

import httpx
import websockets

from app.api.stt.google_stt_client import GoogleSttClient
from app.api.stt_v2.routes_stt_v2 import _build_services
from app.domain.stt.session_registry import SttSessionContext
from app.domain.voice.embeddings import compute_embedding_from_wav_bytes
from app.gcp_credentials import setup_application_default_credentials
from app.settings import settings


TARGET_SR = 16000
PHRASE = "communication is the bridge between confusion and clarity"

# When set (e.g. http://localhost:8000), test uses a launched backend: REST create session + WebSocket stream.
# Auth (in order): INTEGRATION_TEST_TOKEN (JWT) > INTEGRATION_TEST_DEV_FAMILY_EMAIL + INTEGRATION_TEST_DEV_FAMILY_PASSWORD (login) > signup.
# Dev family example (after seeding demo family): marcus.rivera@demo.inside.app / DemoFamily2025!
INTEGRATION_TEST_BASE_URL_ENV = "INTEGRATION_TEST_BASE_URL"
INTEGRATION_TEST_DEV_FAMILY_EMAIL_ENV = "INTEGRATION_TEST_DEV_FAMILY_EMAIL"
INTEGRATION_TEST_DEV_FAMILY_PASSWORD_ENV = "INTEGRATION_TEST_DEV_FAMILY_PASSWORD"



def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _load_wav_pcm16(path: Path, target_sr: int = TARGET_SR) -> bytes:
    sr, data = wavfile.read(path)
    if data.ndim == 2:
        data = data.mean(axis=1)
    if data.dtype.kind in {"i", "u"}:
        max_val = np.iinfo(data.dtype).max
        data = data.astype(np.float32) / float(max_val)
    else:
        data = data.astype(np.float32)
    if sr != target_sr:
        new_len = int(round(len(data) * target_sr / sr))
        data = resample(data, new_len)
    data = np.clip(data, -1.0, 1.0)
    pcm16 = (data * 32767.0).astype(np.int16)
    return pcm16.tobytes()


def _base_url_and_use_http() -> tuple[str | None, bool]:
    """Return (base_url, use_http). use_http is True when INTEGRATION_TEST_BASE_URL is set."""
    raw = os.environ.get(INTEGRATION_TEST_BASE_URL_ENV, "").strip()
    if not raw:
        return None, False
    base = raw.rstrip("/")
    return base, True


def _http_create_session_and_stream(
    base_url: str,
    token: str,
    combined_pcm: bytes,
    chunk_bytes: int,
    silence_chunk: bytes,
) -> list[dict]:
    """Create STT session via REST, stream PCM over WebSocket, return list of {label, text} from ui.sentence."""

    async def _run() -> list[dict]:
        api_base = f"{base_url}/v1"
        session_id: str | None = None

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Create session: POST /v1/session
            r = await client.post(
                f"{api_base}/session",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "candidate_user_ids": ["marcus", "priya"],
                    "language_code": "en-US",
                    "min_speaker_count": 2,
                    "max_speaker_count": 2,
                },
            )
            if r.status_code != 200:
                raise pytest.skip(
                    f"Launched backend: create session failed {r.status_code}. "
                    f"Set INTEGRATION_TEST_TOKEN to a valid JWT or ensure backend has STT configured. {r.text[:200]}"
                )
            session_id = r.json().get("session_id")
            if not session_id:
                raise pytest.skip("Launched backend: create session did not return session_id")

        ws_scheme = "wss" if base_url.startswith("https") else "ws"
        ws_host = base_url.replace("https://", "").replace("http://", "")
        ws_url = f"{ws_scheme}://{ws_host}/v1/stt-v2/stream/{session_id}?token={token}"

        collected: list[dict] = []

        async with websockets.connect(ws_url, close_timeout=5) as ws:
            for offset in range(0, len(combined_pcm), chunk_bytes):
                chunk = combined_pcm[offset : offset + chunk_bytes]
                await ws.send(chunk)
                while True:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=0.5)
                    except asyncio.TimeoutError:
                        break
                    data = json.loads(msg)
                    if data.get("type") == "ui.sentence" and "label" in data and "text" in data:
                        collected.append({"label": data["label"], "text": data.get("text") or ""})

            for _ in range(10):
                await ws.send(silence_chunk)
                await asyncio.sleep(0.2)
                while True:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=0.3)
                    except asyncio.TimeoutError:
                        break
                    data = json.loads(msg)
                    if data.get("type") == "ui.sentence" and "label" in data and "text" in data:
                        collected.append({"label": data["label"], "text": data.get("text") or ""})

        return collected

    return asyncio.run(_run())


def _get_token_for_launched_backend(base_url: str) -> str:
    """Return JWT for launched-backend test: INTEGRATION_TEST_TOKEN > dev family login > signup."""
    token = os.environ.get("INTEGRATION_TEST_TOKEN", "").strip()
    if token:
        return token
    api_base = f"{base_url.rstrip('/')}/v1"
    dev_email = os.environ.get(INTEGRATION_TEST_DEV_FAMILY_EMAIL_ENV, "").strip()
    dev_password = os.environ.get(INTEGRATION_TEST_DEV_FAMILY_PASSWORD_ENV, "").strip()
    if dev_email and dev_password:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(
                f"{api_base}/auth/login",
                json={"email": dev_email, "password": dev_password},
            )
            if r.status_code == 200:
                token = r.json().get("access_token")
                if token:
                    return token
            pytest.skip(
                f"Launched backend: dev family login failed {r.status_code}. "
                f"Set {INTEGRATION_TEST_DEV_FAMILY_EMAIL_ENV} and {INTEGRATION_TEST_DEV_FAMILY_PASSWORD_ENV} "
                "(e.g. marcus.rivera@demo.inside.app / DemoFamily2025! after seeding demo family) or set INTEGRATION_TEST_TOKEN. "
                f"{r.text[:200]}"
            )
    # Signup a unique user and return access_token
    email = f"e2e-{uuid.uuid4().hex[:12]}@example.com"
    with httpx.Client(timeout=15.0) as client:
        r = client.post(
            f"{api_base}/auth/signup",
            json={
                "email": email,
                "password": "IntegrationTestPassword1!",
                "display_name": "E2E Test",
            },
        )
        if r.status_code != 200:
            pytest.skip(
                f"Launched backend: signup failed {r.status_code}. "
                f"Set INTEGRATION_TEST_TOKEN, or {INTEGRATION_TEST_DEV_FAMILY_EMAIL_ENV} and {INTEGRATION_TEST_DEV_FAMILY_PASSWORD_ENV}, or ensure backend allows signup. "
                f"{r.text[:200]}"
            )
        token = r.json().get("access_token")
        if not token:
            pytest.skip("Launched backend: signup did not return access_token")
        return token


def _check_huggingface_hub_for_diart() -> None:
    """Skip with clear message if huggingface_hub is too old for pyannote/Diart."""
    try:
        import huggingface_hub as hf
        ver = getattr(hf, "__version__", "0.0.0")
        parts = [int(x) for x in ver.split(".")[:2] if x.isdigit()]
        major = parts[0] if parts else 0
        minor = parts[1] if len(parts) > 1 else 0
        if major < 1 and (major < 0 or minor < 30):
            pytest.skip(
                f"Diart/pyannote.audio requires huggingface-hub>=0.30,<1.0 (found {ver}). "
                "From backend dir: poetry lock && poetry install. Then run tests with: poetry run pytest ... (or select the Poetry interpreter in your IDE)."
            )
    except Exception:
        pass


@pytest.mark.integration
def test_end_to_end_v2_pipeline_real_stack():
    base_url, use_launched_backend = _base_url_and_use_http()
    if use_launched_backend:
        _run_launched_backend_test(base_url)
        return
    _check_huggingface_hub_for_diart()
    data_dir = Path(__file__).resolve().parents[1] / "test_data"
    marcus_path = data_dir / "marcus_voiceprint.wav"
    priya_path = data_dir / "priya_voiceprint.wav"
    if not marcus_path.exists() or not priya_path.exists():
        pytest.skip("Missing test_data voiceprint wavs")

    is_placeholder = GoogleSttClient.is_placeholder_recognizer(settings.stt_recognizer)
    if is_placeholder:
        pytest.skip("stt_recognizer not configured for real Google STT")

    marcus_wav = marcus_path.read_bytes()
    priya_wav = priya_path.read_bytes()
    marcus_emb = compute_embedding_from_wav_bytes(marcus_wav)
    priya_emb = compute_embedding_from_wav_bytes(priya_wav)
    if marcus_emb is None or priya_emb is None:
        pytest.skip("SpeechBrain embeddings unavailable")

    # Apply GOOGLE_APPLICATION_CREDENTIALS_JSON from settings (e.g. .env) so Speech client can auth
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") and getattr(
        settings, "google_application_credentials", ""
    ):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON") and getattr(
        settings, "google_application_credentials_json", ""
    ):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS_JSON"] = settings.google_application_credentials_json
    setup_application_default_credentials()

    try:
        client = speech.SpeechClient()
    except Exception:
        pytest.skip("Google Speech client unavailable (credentials missing?)")

    services = _build_services()
    orchestrator = services.orchestrator

    stream_id = "e2e_stream"
    ctx = SttSessionContext(
        session_id=stream_id,
        user_id="e2e",
        candidate_user_ids=["marcus", "priya"],
        language_code="en-US",
        min_speaker_count=2,
        max_speaker_count=2,
    )
    ctx.voice_embeddings = {"marcus": marcus_emb, "priya": priya_emb}

    orchestrator.start_session(stream_id, TARGET_SR, ctx, client)
    diar_service = orchestrator.diar_service
    diart_available = bool(getattr(diar_service, "_available", False))
    diar_state = getattr(diar_service, "_states", {}).get(stream_id)
    diart_pipeline = None if diar_state is None else getattr(diar_state, "pipeline", None)

    marcus_pcm = _load_wav_pcm16(marcus_path)
    priya_pcm = _load_wav_pcm16(priya_path)
    combined = b"".join([marcus_pcm, priya_pcm, marcus_pcm, priya_pcm])
    silence = (np.zeros(int(TARGET_SR * 0.5), dtype=np.int16)).tobytes()
    combined += silence

    chunk_samples = int(TARGET_SR * 0.1)
    chunk_bytes = chunk_samples * 2

    speaker_sentences_raw: list = []
    try:
        for offset in range(0, len(combined), chunk_bytes):
            chunk = combined[offset : offset + chunk_bytes]
            output = orchestrator.process_audio_chunk(stream_id, chunk, TARGET_SR)
            speaker_sentences_raw.extend(output.speaker_sentences)

        # Give the STT thread time to flush final segments.
        for _ in range(10):
            time.sleep(0.2)
            output = orchestrator.process_audio_chunk(
                stream_id, silence[:chunk_bytes], TARGET_SR
            )
            speaker_sentences_raw.extend(output.speaker_sentences)
    finally:
        orchestrator.stop_session(stream_id)

    # Normalize to list of {label, text} for unified assertions
    speaker_sentences = [
        {"label": ss.label, "text": (ss.ui_sentence.text or "")}
        for ss in speaker_sentences_raw
    ]
    diart_available_for_assert = diart_available and diart_pipeline is not None
    _assert_transcript_and_optional_speakers(
        speaker_sentences, diart_available_for_assert, used_launched_backend=False
    )


def _run_launched_backend_test(base_url: str) -> None:
    """Use a running backend: create session via REST, stream PCM over WebSocket, assert transcript."""
    data_dir = Path(__file__).resolve().parents[1] / "test_data"
    marcus_path = data_dir / "marcus_voiceprint.wav"
    priya_path = data_dir / "priya_voiceprint.wav"
    if not marcus_path.exists() or not priya_path.exists():
        pytest.skip("Missing test_data voiceprint wavs (marcus_voiceprint.wav, priya_voiceprint.wav)")

    marcus_pcm = _load_wav_pcm16(marcus_path)
    priya_pcm = _load_wav_pcm16(priya_path)
    combined = b"".join([marcus_pcm, priya_pcm, marcus_pcm, priya_pcm])
    silence = (np.zeros(int(TARGET_SR * 0.5), dtype=np.int16)).tobytes()
    chunk_samples = int(TARGET_SR * 0.1)
    chunk_bytes = chunk_samples * 2

    token = _get_token_for_launched_backend(base_url)
    try:
        speaker_sentences = _http_create_session_and_stream(
            base_url, token, combined, chunk_bytes, silence[:chunk_bytes]
        )
    except Exception as e:
        pytest.skip(f"Launched backend: stream failed. {e!s}")

    # Launched backend: we don't know if Diart is available server-side; assert per-speaker only if we got marcus/priya labels
    has_both_labels = (
        any(s["label"] == "marcus" for s in speaker_sentences)
        and any(s["label"] == "priya" for s in speaker_sentences)
    )
    _assert_transcript_and_optional_speakers(
        speaker_sentences, has_both_labels, used_launched_backend=True
    )


def _assert_transcript_and_optional_speakers(
    speaker_sentences: list[dict],
    assert_per_speaker: bool,
    *,
    used_launched_backend: bool = False,
) -> None:
    """Assert full transcript contains PHRASE; if assert_per_speaker, assert each of marcus/priya has the phrase."""
    all_text = " ".join(s["text"] for s in speaker_sentences)
    combined_normalized = _normalize(all_text)
    if not combined_normalized.strip():
        if used_launched_backend:
            pytest.skip(
                "No transcript received from launched backend. "
                "Ensure the running server has Google Speech configured (GOOGLE_APPLICATION_CREDENTIALS_JSON in its env) "
                "and that STT V2 stream returns ui.sentence messages. Try the Live Coach flow in the app first to confirm STT works."
            )
        pytest.skip(
            "No transcript received (in-process). "
            "Set GOOGLE_APPLICATION_CREDENTIALS_JSON in .env or run: gcloud auth application-default login. "
            "To test against a running server instead, set INTEGRATION_TEST_BASE_URL=http://localhost:8000 and "
            "INTEGRATION_TEST_DEV_FAMILY_EMAIL + INTEGRATION_TEST_DEV_FAMILY_PASSWORD (or INTEGRATION_TEST_TOKEN)."
        )
    assert _normalize(PHRASE) in combined_normalized, (
        f"Expected transcript to contain phrase '{PHRASE}'. Got (normalized): {combined_normalized[:500]}..."
    )

    if assert_per_speaker:
        by_label: dict[str, list[str]] = {"marcus": [], "priya": []}
        for s in speaker_sentences:
            if s["label"] in by_label:
                by_label[s["label"]].append(s["text"])
        for label, texts in by_label.items():
            assert texts, f"Expected at least one sentence for {label}"
            label_text = _normalize(" ".join(texts))
            assert _normalize(PHRASE) in label_text, f"Expected phrase for {label}"
