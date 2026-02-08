"""LLM service: generic image and text generation with provider selection (OpenAI vs Gemini)."""
import base64
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LLMRateLimitError(Exception):
    """Raised when the LLM provider returns 429 / RESOURCE_EXHAUSTED (quota or rate limit)."""


async def _generate_text_gemini_async(api_key: str, prompt: str, model: str) -> Optional[str]:
    """Call Gemini async generate_content; returns response text or None."""
    try:
        import google.genai as genai
    except (ImportError, ModuleNotFoundError):
        return None
    try:
        client = genai.Client(api_key=api_key.strip())
        response = await client.aio.models.generate_content(
            model=model,
            contents=prompt,
        )
        text = (getattr(response, "text", None) or "").strip()
        return text or None
    except Exception as e:
        err_str = str(e).upper()
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            raise LLMRateLimitError(
                "Google Gemini (GenAI) rate limit exceeded (quota or requests per minute); try again shortly."
            ) from e
        logger.warning("generate_text_async (Gemini) failed: %s", e)
        return None


def _generate_image_gemini(client: Any, prompt: str, model: str = "gemini-2.5-flash-image") -> Optional[str]:
    """
    Generate an image using the given Gemini image model. Prompt is passed as-is.
    Returns base64-encoded PNG string or None.
    """
    try:
        from google.genai import types
    except (ImportError, ModuleNotFoundError):
        return None
    try:
        config_kw: Dict[str, Any] = {"response_modalities": ["IMAGE"]}
        if hasattr(types, "ImageConfig"):
            config_kw["image_config"] = types.ImageConfig(aspect_ratio="1:1")
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kw),
        )
        parts = getattr(response, "parts", None)
        if parts is None and getattr(response, "candidates", None):
            cand = response.candidates[0] if response.candidates else None
            if cand and getattr(cand, "content", None):
                parts = getattr(cand.content, "parts", None)
        if not parts:
            logger.debug("_generate_image_gemini: no parts in response for %r", prompt[:40])
            return None
        for part in parts:
            as_image_fn = getattr(part, "as_image", None)
            if callable(as_image_fn):
                try:
                    img = as_image_fn()
                    if img is not None:
                        import io
                        buf = io.BytesIO()
                        img.save(buf, format="PNG")
                        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                        if b64:
                            return b64
                except Exception as e:
                    logger.debug("_generate_image_gemini as_image() failed: %s", e)
            inline = getattr(part, "inline_data", None) or getattr(part, "inlineData", None)
            if inline is None:
                continue
            data = getattr(inline, "data", None) if not isinstance(inline, dict) else inline.get("data")
            if data is None:
                continue
            if isinstance(data, bytes):
                b64 = base64.b64encode(data).decode("ascii")
            else:
                b64 = str(data).strip()
            if not b64:
                continue
            return b64
        logger.debug("_generate_image_gemini: no image part in response for %r", prompt[:40])
        return None
    except Exception as e:
        logger.warning("_generate_image_gemini failed for prompt %r: %s", prompt[:50], e)
        return None


def _generate_image_openai(
    prompt: str,
    *,
    api_key: str,
    model: str = "gpt-image-1",
    size: str = "1024x1024",
    quality: str = "low",
    output_size: tuple[int, int] = (1024, 1024),
) -> Optional[str]:
    """
    Generate an image using OpenAI image model. Prompt is passed as-is.
    model, size, quality are configurable. Returns base64-encoded PNG.
    """
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key.strip())
        response = client.images.generate(
            model=model,
            prompt=prompt,
            size=size,
            quality=quality,
            output_format="png",
            background="transparent",
        )
        if response.data and len(response.data) > 0:
            b64 = getattr(response.data[0], "b64_json", None)
            if b64:
                return b64
        logger.debug("_generate_image_openai: no b64_json in response for %r", prompt[:40])
        return None
    except Exception as e:
        logger.warning("_generate_image_openai failed for prompt %r: %s", prompt[:50], e)
        return None


class LLMService:
    """
    Application-facing LLM service. Owns provider selection for image and text generation.
    Use OpenAI if openai_api_key is set, else Gemini if gemini_api_key is set.
    """

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        default_text_model: Optional[str] = None,
        backup_text_model: Optional[str] = None,
        default_image_model: Optional[str] = None,
        default_image_size: Optional[str] = None,
        default_image_quality: Optional[str] = None,
    ):
        self._openai_api_key = (openai_api_key or "").strip() or None
        self._gemini_api_key = (gemini_api_key or "").strip() or None
        self._default_text_model = (default_text_model or "").strip() or "gemini-2.0-flash"
        self._backup_text_model = (backup_text_model or "").strip() or None
        self._default_image_model = (default_image_model or "").strip() or "gemini-2.5-flash-image"
        self._default_image_size = (default_image_size or "").strip() or "1024x1024"
        self._default_image_quality = (default_image_quality or "").strip() or "low"

    def generate_image(
        self,
        prompt: str,
        output_size: tuple[int, int] = (1024, 1024),
        model: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generate an image from a prompt. Provider inferred from model name (gpt-* -> OpenAI, else Gemini).
        model: optional; when None uses default from config (llm_default_image_model).
        Returns base64-encoded PNG string or None. Caller may resize to output_size if needed.
        """
        model = (model or "").strip() or self._default_image_model
        is_openai_model = model.lower().startswith("gpt-")
        if self._openai_api_key and is_openai_model:
            return _generate_image_openai(
                prompt,
                api_key=self._openai_api_key,
                model=model,
                size=self._default_image_size,
                quality=self._default_image_quality,
                output_size=output_size,
            )
        if self._gemini_api_key and not is_openai_model:
            try:
                import google.genai as genai
            except (ImportError, ModuleNotFoundError):
                return None
            client = genai.Client(api_key=self._gemini_api_key)
            return _generate_image_gemini(client, prompt, model=model)
        # Fallback: use other provider if default model type does not match available key
        if self._openai_api_key:
            return _generate_image_openai(
                prompt,
                api_key=self._openai_api_key,
                model="gpt-image-1",
                size=self._default_image_size,
                quality=self._default_image_quality,
                output_size=output_size,
            )
        if self._gemini_api_key:
            try:
                import google.genai as genai
            except (ImportError, ModuleNotFoundError):
                return None
            client = genai.Client(api_key=self._gemini_api_key)
            return _generate_image_gemini(client, prompt, model="gemini-2.5-flash-image")
        return None

    def generate_text(
        self,
        prompt: str,
        model: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generate text from a prompt. Uses Gemini when gemini_api_key is set.
        model: optional; when None uses default from config (llm_default_text_model).
        On 429, retries once with backup model (llm_backup_text_model) if configured.
        Returns raw response text or None.
        """
        if not self._gemini_api_key:
            return None
        try:
            import google.genai as genai
        except (ImportError, ModuleNotFoundError):
            return None
        primary = (model or "").strip() or self._default_text_model
        try:
            client = genai.Client(api_key=self._gemini_api_key)
            response = client.models.generate_content(
                model=primary,
                contents=prompt,
            )
            text = (response.text or "").strip()
            return text or None
        except Exception as e:
            err_str = str(e).upper()
            if ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str) and self._backup_text_model and self._backup_text_model != primary:
                logger.info("generate_text 429, retrying with backup model %s", self._backup_text_model)
                try:
                    response = client.models.generate_content(
                        model=self._backup_text_model,
                        contents=prompt,
                    )
                    text = (response.text or "").strip()
                    return text or None
                except Exception as retry_e:
                    logger.warning("generate_text backup model failed: %s", retry_e)
                    return None
            logger.warning("generate_text failed: %s", e)
            return None

    def generate_text_with_images(
        self,
        prompt: str,
        image_parts: List[Dict[str, Any]],
        model: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generate text from a prompt and one or more images (multimodal). Uses Gemini when gemini_api_key is set.
        image_parts: list of dicts with "mime_type" (e.g. "image/png") and "data" (base64-encoded string).
        model: optional; when None uses default from config (llm_default_text_model).
        On 429, retries once with backup model (llm_backup_text_model) if configured.
        Returns raw response text or None.
        """
        if not self._gemini_api_key or not image_parts:
            return None
        try:
            import google.genai as genai
            from google.genai import types
        except (ImportError, ModuleNotFoundError):
            return None
        parts: List[Any] = []
        use_types = hasattr(types, "Part") and hasattr(types, "Blob")
        for ip in image_parts:
            mime = (ip.get("mime_type") or "image/png").strip()
            data = ip.get("data")
            if not data:
                continue
            if isinstance(data, str):
                data = base64.b64decode(data)
            if use_types:
                parts.append(types.Part(inline_data=types.Blob(mime_type=mime, data=data)))
            else:
                parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode("ascii")}})
        if not parts:
            return None
        if use_types:
            parts.append(types.Part(text=prompt))
        else:
            parts.append({"text": prompt})
        primary = (model or "").strip() or self._default_text_model
        client = genai.Client(api_key=self._gemini_api_key)
        try:
            response = client.models.generate_content(
                model=primary,
                contents=parts,
            )
            text = (response.text or "").strip()
            return text or None
        except Exception as e:
            err_str = str(e).upper()
            if ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str) and self._backup_text_model and self._backup_text_model != primary:
                logger.info("generate_text_with_images 429, retrying with backup model %s", self._backup_text_model)
                try:
                    response = client.models.generate_content(
                        model=self._backup_text_model,
                        contents=parts,
                    )
                    text = (response.text or "").strip()
                    return text or None
                except Exception as retry_e:
                    logger.warning("generate_text_with_images backup model failed: %s", retry_e)
                    return None
            logger.warning("generate_text_with_images failed: %s", e)
            return None

    async def generate_text_async(
        self,
        prompt: str,
        model: Optional[str] = None,
    ) -> Optional[str]:
        """
        Async: generate text from a prompt. Uses Gemini when gemini_api_key is set.
        model: optional; when None uses default from config (llm_default_text_model).
        On 429, retries once with backup model (llm_backup_text_model) if configured.
        Returns raw response text or None.
        """
        if not self._gemini_api_key:
            return None
        primary = (model or "").strip() or self._default_text_model
        try:
            return await _generate_text_gemini_async(
                self._gemini_api_key,
                prompt,
                primary,
            )
        except LLMRateLimitError:
            if self._backup_text_model and self._backup_text_model != primary:
                logger.info("generate_text_async 429, retrying with backup model %s", self._backup_text_model)
                try:
                    return await _generate_text_gemini_async(
                        self._gemini_api_key,
                        prompt,
                        self._backup_text_model,
                    )
                except LLMRateLimitError:
                    logger.warning("generate_text_async backup model also rate limited")
                    return None
            logger.warning("generate_text_async rate limited and no backup model configured")
            return None
