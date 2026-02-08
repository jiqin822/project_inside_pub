"""
Google Cloud Speech-to-Text v2 integration for STT stream.

Request generator, streaming recognize loop, and credentials/client setup.
"""
from __future__ import annotations

import asyncio
import logging
import os
import queue
import threading
from typing import Any, Callable, Optional

from fastapi import WebSocket, status
from google.auth import default as google_auth_default
from google.auth import exceptions as google_auth_exceptions
from google.cloud import speech_v2 as speech

from app.domain.stt.session_registry import SttSessionContext
from app.gcp_credentials import setup_application_default_credentials

from app.api.stt.constants import MSG_STT_ERROR, STT_SAMPLE_RATE_HZ
from app.settings import settings

logger = logging.getLogger(__name__)


class GoogleSttClient:
    """Handles Google Cloud Speech-to-Text streaming: config, request generator, and recognize loop."""

    @staticmethod
    def is_placeholder_recognizer(recognizer: str) -> bool:
        """True if recognizer is empty or looks like a placeholder (your-project, recognizers/default)."""
        if not recognizer:
            return True
        lowered = recognizer.lower()
        return "projects/your-project" in lowered or "recognizers/default" in lowered

    def get_language_config(
        self, ctx: SttSessionContext
    ) -> tuple[list[str], str, bool]:
        """
        Return (language_codes, model_id, enable_diarization_for_request) for the STT stream.
        When language_code is 'auto' we use chirp_3 and disable diarization; else latest_short with diarization.
        """
        use_auto_language = (ctx.language_code or "").strip().lower() == "auto"
        if use_auto_language:
            return ["auto"], "chirp_3", False
        return [ctx.language_code or "en-US"], "latest_short", True

    def build_request_generator(
        self,
        audio_queue: queue.Queue[Optional[bytes]],
        ctx: SttSessionContext,
        language_codes: list[str],
        model_id: str,
        enable_diarization_for_request: bool,
    ) -> Callable[[bool], Any]:
        """
        Return a synchronous generator function that yields StreamingRecognizeRequest.

        First yield: config and streaming_config. Subsequent yields: one request per
        audio chunk from audio_queue until None (stream end sentinel).
        """

        def request_generator_sync(enable_diarization: bool):
            diarization_config = None
            if enable_diarization and enable_diarization_for_request:
                diarization_config = speech.SpeakerDiarizationConfig(
                    min_speaker_count=ctx.min_speaker_count,
                    max_speaker_count=ctx.max_speaker_count,
                )
            enable_word_offsets = model_id != "chirp_3"
            config = speech.RecognitionConfig(
                explicit_decoding_config=speech.ExplicitDecodingConfig(
                    encoding=speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                    sample_rate_hertz=STT_SAMPLE_RATE_HZ,
                    audio_channel_count=1,
                ),
                language_codes=language_codes,
                model=model_id,
                features=speech.RecognitionFeatures(
                    enable_automatic_punctuation=True,
                    enable_word_time_offsets=enable_word_offsets,
                    diarization_config=diarization_config,
                ),
            )
            streaming_config = speech.StreamingRecognitionConfig(
                config=config,
                streaming_features=speech.StreamingRecognitionFeatures(
                    interim_results=True,
                ),
            )
            yield speech.StreamingRecognizeRequest(
                recognizer=settings.stt_recognizer,
                streaming_config=streaming_config,
            )
            while True:
                chunk = audio_queue.get()
                if chunk is None:
                    break
                yield speech.StreamingRecognizeRequest(audio=chunk)

        return request_generator_sync

    def run_streaming_recognize(
        self,
        deps: Any,
        stop_event: threading.Event,
        handle_response_message: Any,
    ) -> None:
        """Run Google Cloud StreamingRecognize in a blocking loop (called from a worker thread).

        Consumes audio from deps.request_generator_sync(enable_diarization). For each
        response, schedules handle_response_message(response, stream_base, deps) on deps.loop.
        On speaker_diarization errors, retries once with diarization disabled.
        """
        enable_diarization = True
        restarted = False
        while True:
            try:
                drained_chunks_list: list[Optional[bytes]] = []
                if restarted:
                    try:
                        while True:
                            drained_chunks_list.append(deps.audio_queue.get_nowait())
                    except queue.Empty:
                        pass
                    total_drained_samples = sum(
                        len(c) // 2 for c in drained_chunks_list if c
                    )
                    deps.ctx.stream_start_samples = max(
                        0, deps.ring_buffer.total_samples - total_drained_samples
                    )
                    for c in drained_chunks_list:
                        deps.audio_queue.put(c)
                else:
                    deps.ctx.stream_start_samples = deps.ring_buffer.total_samples

                responses = deps.client.streaming_recognize(
                    requests=deps.request_generator_sync(enable_diarization)
                )
                stream_base = deps.ctx.stream_start_samples
                for response in responses:
                    asyncio.run_coroutine_threadsafe(
                        handle_response_message(response, stream_base, deps), deps.loop
                    )
                    if stop_event.is_set():
                        return
                restarted = True
                continue
            except Exception as exc:
                error_message = str(exc)
                if (
                    enable_diarization
                    and "speaker_diarization" in error_message
                ):
                    enable_diarization = False
                    continue
                asyncio.run_coroutine_threadsafe(
                    deps.websocket.send_json(
                        {"type": MSG_STT_ERROR, "message": error_message}
                    ),
                    deps.loop,
                )
                return

    async def ensure_credentials_and_client(
        self, websocket: WebSocket
    ) -> tuple[Optional[speech.SpeechClient], Optional[str]]:
        """Ensure Google credentials and create Speech v2 client for streaming.

        On failure sends stt.error and closes WebSocket; returns (None, None).
        On success returns (client, endpoint).
        """
        endpoint = None
        if "/locations/" in settings.stt_recognizer:
            try:
                location = settings.stt_recognizer.split("/locations/")[1].split("/")[0]
                if location and location != "global":
                    endpoint = f"{location}-speech.googleapis.com"
            except Exception:
                endpoint = None

        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") and getattr(
            settings, "google_application_credentials", ""
        ):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = (
                settings.google_application_credentials
            )
        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON") and getattr(
            settings, "google_application_credentials_json", ""
        ):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS_JSON"] = (
                settings.google_application_credentials_json
            )
        setup_application_default_credentials()

        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            logger.warning(
                "STT stream: GOOGLE_APPLICATION_CREDENTIALS not set. "
                "Set GOOGLE_APPLICATION_CREDENTIALS_JSON on the api component and redeploy."
            )
            await websocket.send_json(
                {
                    "type": MSG_STT_ERROR,
                    "message": "Speech-to-text is not configured. Set GOOGLE_APPLICATION_CREDENTIALS_JSON on the api component (full JSON or base64) and redeploy.",
                }
            )
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="STT credentials not configured",
            )
            return (None, None)

        try:
            creds, project = google_auth_default()
            cred_identity = (
                getattr(creds, "service_account_email", None)
                or getattr(creds, "signer_email", None)
            )
            if cred_identity is None and hasattr(creds, "credentials"):
                cred_identity = getattr(
                    creds.credentials, "service_account_email", None
                )
            logger.info(
                "STT stream: credentials identity project=%s email=%s recognizer=%s",
                project,
                cred_identity,
                settings.stt_recognizer,
            )
        except Exception as e:
            logger.warning("STT stream: could not log credential identity: %s", e)

        client_options = {"api_endpoint": endpoint} if endpoint else None
        try:
            client = speech.SpeechClient(client_options=client_options)
        except google_auth_exceptions.DefaultCredentialsError as e:
            logger.warning(
                "STT stream: Google Application Default Credentials not set: %s", e
            )
            await websocket.send_json(
                {
                    "type": MSG_STT_ERROR,
                    "message": "Speech-to-text is not configured. Set GOOGLE_APPLICATION_CREDENTIALS_JSON on the api component (full JSON or base64) and redeploy.",
                }
            )
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="STT credentials not configured",
            )
            return (None, None)
        return (client, endpoint)
