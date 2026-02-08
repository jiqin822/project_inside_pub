"""
Google Application Default Credentials (ADC) setup for environments that cannot use a file path.

On DigitalOcean App Platform (and similar PaaS), you cannot upload a JSON key file. Instead:
1. Create a GCP service account and download its JSON key.
2. Set the **entire JSON content** in an env var: GOOGLE_APPLICATION_CREDENTIALS_JSON.
3. This module writes that JSON to a temp file at startup and sets GOOGLE_APPLICATION_CREDENTIALS
   so google.auth.default() and Speech-to-Text / Firebase work.

Call setup_application_default_credentials() as early as possible (e.g. in main.py before any
Google client is created).
"""
import json
import logging
import os
import tempfile

logger = logging.getLogger(__name__)


def setup_application_default_credentials() -> None:
    """
    If GOOGLE_APPLICATION_CREDENTIALS is not set but GOOGLE_APPLICATION_CREDENTIALS_JSON is,
    write the JSON to a temp file and set GOOGLE_APPLICATION_CREDENTIALS to that path.
    """
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        # Already set (e.g. path to key file on disk)
        return
    raw = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if not raw or not raw.strip():
        logger.debug("GOOGLE_APPLICATION_CREDENTIALS_JSON is empty or not set; skipping ADC setup")
        return
    raw = raw.strip()
    logger.info("GOOGLE_APPLICATION_CREDENTIALS_JSON present (%d chars), writing temp file for ADC", len(raw))
    try:
        # Support both raw JSON and base64-encoded JSON (for env vars with newlines)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            import base64
            decoded = base64.b64decode(raw).decode("utf-8")
            data = json.loads(decoded)
        if not isinstance(data, dict):
            logger.warning("GOOGLE_APPLICATION_CREDENTIALS_JSON is not a JSON object; skipping ADC setup")
            return
        fd, path = tempfile.mkstemp(suffix=".json", prefix="gcp-credentials-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path
            logger.info("Google Application Default Credentials set from GOOGLE_APPLICATION_CREDENTIALS_JSON")
        except Exception:
            try:
                os.unlink(path)
            except Exception:
                pass
            raise
    except Exception as e:
        logger.warning("Failed to setup Google ADC from GOOGLE_APPLICATION_CREDENTIALS_JSON: %s", e)
