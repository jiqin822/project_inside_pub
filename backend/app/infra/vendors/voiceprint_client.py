"""Voiceprint API client."""
import httpx
import logging
from typing import Optional, Tuple
from app.settings import settings

logger = logging.getLogger(__name__)


def _log_connection_error(operation: str, url: str, e: Exception) -> None:
    """Log a clear message when voiceprint-api is unreachable."""
    if isinstance(e, httpx.ConnectError):
        logger.error(
            "Voiceprint API unreachable at %s (%s). "
            "Start the voiceprint-api service (see voiceprint-api/QUICK_START.md or VOICEPRINT_INTEGRATION.md).",
            url,
            e,
        )
    else:
        logger.error(f"Voiceprint API {operation} failed: {e}")


class VoiceprintClient:
    """Client for voiceprint-api service."""

    def __init__(self, base_url: str = None, api_token: str = None):
        self.base_url = (base_url or settings.voiceprint_api_url).rstrip("/")
        self.api_token = api_token or settings.voiceprint_api_token
        self.timeout = 60.0  # 60 seconds timeout for voice processing

    async def register_voiceprint(
        self, speaker_id: str, audio_bytes: bytes
    ) -> bool:
        """
        Register a voiceprint.

        Args:
            speaker_id: Unique speaker identifier (typically user_id)
            audio_bytes: WAV audio file bytes

        Returns:
            bool: True if registration successful
        """
        url = f"{self.base_url}/voiceprint/register"
        # voiceprint-api uses HTTPBearer which expects "Bearer {token}"
        headers = {"Authorization": f"Bearer {self.api_token}"} if self.api_token else {}

        files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
        data = {"speaker_id": speaker_id}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, files=files, data=data)
                response.raise_for_status()
                result = response.json()
                logger.info(f"Voiceprint registered: {speaker_id}")
                return result.get("success", False)
        except httpx.ConnectError as e:
            _log_connection_error("registration", url, e)
            raise
        except httpx.HTTPError as e:
            logger.error(f"Voiceprint registration failed for {speaker_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Voiceprint registration error for {speaker_id}: {e}")
            raise

    async def identify_voiceprint(
        self, speaker_ids: list[str], audio_bytes: bytes
    ) -> Tuple[Optional[str], float]:
        """
        Identify a speaker from audio.

        Args:
            speaker_ids: List of candidate speaker IDs
            audio_bytes: WAV audio file bytes

        Returns:
            Tuple[Optional[str], float]: (speaker_id if match found, similarity score)
        """
        url = f"{self.base_url}/voiceprint/identify"
        # voiceprint-api uses HTTPBearer which expects "Bearer {token}"
        headers = {"Authorization": f"Bearer {self.api_token}"} if self.api_token else {}

        files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
        data = {"speaker_ids": ",".join(speaker_ids)}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, files=files, data=data)
                response.raise_for_status()
                result = response.json()
                speaker_id = result.get("speaker_id")
                score = result.get("score", 0.0)
                
                if speaker_id:
                    logger.info(f"Voiceprint identified: {speaker_id} (score: {score:.4f})")
                else:
                    logger.info(f"No voiceprint match found (best score: {score:.4f})")
                
                return speaker_id, score
        except httpx.ConnectError as e:
            _log_connection_error("identification", url, e)
            raise
        except httpx.HTTPError as e:
            logger.error(f"Voiceprint identification failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Voiceprint identification error: {e}")
            raise

    async def delete_voiceprint(self, speaker_id: str) -> bool:
        """
        Delete a voiceprint.

        Args:
            speaker_id: Speaker ID to delete

        Returns:
            bool: True if deletion successful
        """
        url = f"{self.base_url}/voiceprint/{speaker_id}"
        # voiceprint-api uses HTTPBearer which expects "Bearer {token}"
        headers = {"Authorization": f"Bearer {self.api_token}"} if self.api_token else {}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.delete(url, headers=headers)
                response.raise_for_status()
                result = response.json()
                logger.info(f"Voiceprint deleted: {speaker_id}")
                return result.get("success", False)
        except httpx.ConnectError as e:
            _log_connection_error("deletion", url, e)
            raise
        except httpx.HTTPError as e:
            if e.response and e.response.status_code == 404:
                logger.warning(f"Voiceprint not found for deletion: {speaker_id}")
                return False
            logger.error(f"Voiceprint deletion failed for {speaker_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Voiceprint deletion error for {speaker_id}: {e}")
            raise
