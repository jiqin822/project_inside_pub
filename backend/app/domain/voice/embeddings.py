"""Voice embedding utilities for speaker identification using ECAPA-TDNN (SpeechBrain)."""
from __future__ import annotations

import io
import logging
import os
import tempfile
import time
import wave
from typing import Optional, Sequence, Any

import numpy as np

# Device mode for enrollment: far-field (laptop/room) vs near-field (phone). Used to pick enrollment subset at scoring.
DEVICE_MODE_FAR_FIELD = "far_field"
DEVICE_MODE_NEAR_FIELD = "near_field"

logger = logging.getLogger(__name__)

# Speaker encoder (SpeechBrain ECAPA-TDNN) - lazy loaded (import deferred to avoid torchaudio API issues at startup)
_model: Optional[Any] = None
_encoder_classifier: Optional[Any] = None  # EncoderClassifier class, set on first successful import
_speechbrain_import_error: Optional[str] = None

# ECAPA-TDNN (spkrec-ecapa-voxceleb) outputs 192-dimensional embeddings
ECAPA_EMBEDDING_DIM = 192


def _get_model() -> Optional[Any]:
    """Get or initialize ECAPA-TDNN speaker encoder (lazy loading)."""
    global _model, _encoder_classifier, _speechbrain_import_error
    # Lazy-import SpeechBrain so app starts even if torchaudio/SpeechBrain are incompatible
    if _encoder_classifier is None and _speechbrain_import_error is None:
        try:
            from speechbrain.inference.classifiers import EncoderClassifier
            _encoder_classifier = EncoderClassifier
        except Exception as e:
            _speechbrain_import_error = str(e)
    if _encoder_classifier is None:
        return None
    if _model is None:
        try:
            # ECAPA-TDNN trained on VoxCeleb; 192-dim embeddings, 16 kHz
            _model = _encoder_classifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir=os.path.join(tempfile.gettempdir(), "speechbrain_spkrec_ecapa"),
            )
        except Exception as e:
            _speechbrain_import_error = _speechbrain_import_error or str(e)
            return None
    return _model


def ensure_speaker_encoder_loaded() -> tuple[bool, str]:
    """
    Load the speaker encoder (ECAPA-TDNN) at startup.
    Returns (True, message) on success, (False, error_message) on failure.
    """
    try:
        model = _get_model()
        if model is None:
            hint = (
                "SpeechBrain not available (speechbrain failed to import). "
                "Install: cd backend && poetry lock && poetry install   or: pip install speechbrain"
            )
            if _speechbrain_import_error:
                return False, f"{hint} Import error: {_speechbrain_import_error}"
            return False, hint
        return True, "Speaker encoder ready (SpeechBrain ECAPA-TDNN, spkrec-ecapa-voxceleb)"
    except Exception as e:
        return False, f"Speaker encoder load failed: {e}"


# ECAPA-TDNN expects 16 kHz; enrollment WAV may be 44.1 kHz etc. Resample to match STT segments.
ECAPA_SAMPLE_RATE = 16000


def _wav_to_16k_mono_tensor(tmp_path: str):
    """Read WAV, resample to 16 kHz if needed, return (batch=1, time) float tensor for ECAPA."""
    import scipy.io.wavfile as wavfile
    rate, data = wavfile.read(tmp_path)
    if data.ndim == 2:
        data = data.mean(axis=1)
    if data.dtype in (np.int16, np.int32):
        data = data.astype(np.float32) / (np.iinfo(data.dtype).max + 1)
    if rate != ECAPA_SAMPLE_RATE:
        from scipy.signal import resample
        n = int(round(len(data) * ECAPA_SAMPLE_RATE / rate))
        data = resample(data, n).astype(np.float32)
    import torch
    signal = torch.from_numpy(data).float().unsqueeze(0)
    return signal


def compute_embedding_from_wav_bytes(audio_bytes: bytes) -> Optional[list[float]]:
    """
    Compute speaker embedding from WAV bytes using ECAPA-TDNN (SpeechBrain).
    Resamples to 16 kHz so enrollment matches STT segment pipeline; returns 192-dim vector or None.
    """
    model = _get_model()
    if model is None:
        logger.warning("Voice embedding: speaker encoder unavailable (compute_wav)")
        return None

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp.flush()
            tmp_path = tmp.name

        try:
            signal = _wav_to_16k_mono_tensor(tmp_path)
        except Exception:
            from speechbrain.dataio.dataio import read_audio
            signal = read_audio(tmp_path)
            if signal.dim() == 1:
                signal = signal.unsqueeze(0)
            elif signal.dim() == 2:
                signal = signal.mean(dim=1, keepdim=False).unsqueeze(0)
            # Resample to 16 kHz so enrollment matches STT segment space (ECAPA expects 16 kHz)
            with wave.open(tmp_path, "rb") as wav_f:
                file_rate = wav_f.getframerate()
            if file_rate != ECAPA_SAMPLE_RATE:
                try:
                    import torchaudio.transforms as T
                    resampler = T.Resample(file_rate, ECAPA_SAMPLE_RATE)
                    signal = resampler(signal)
                except Exception as resample_err:
                    raise
        emb = model.encode_batch(signal)
        result = np.array(emb.squeeze().cpu()).flatten().tolist()
        if len(result) != ECAPA_EMBEDDING_DIM:
            logger.warning("Voice embedding: bad dim %s (expected %s)", len(result), ECAPA_EMBEDDING_DIM)
            return None
        return result
    except Exception as e:
        logger.warning("Voice embedding (wav) failed: %s", str(e)[:120])
        return None
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def compute_embedding_from_pcm_bytes(
    pcm_bytes: bytes,
    sample_rate: int = 16000,
) -> Optional[list[float]]:
    """
    Compute speaker embedding from PCM16 bytes (little-endian) using ECAPA-TDNN.
    Returns 192-dimensional embedding vector, or None if the encoder is unavailable or errors.
    """
    model = _get_model()
    pcm = np.frombuffer(pcm_bytes, dtype=np.int16)

    if model is None:
        logger.warning("Voice embedding: speaker encoder unavailable (compute_pcm)")
        return None

    if pcm.size == 0:
        return None

    tmp_path: Optional[str] = None
    try:
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm.tobytes())

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_buffer.getvalue())
            tmp.flush()
            tmp_path = tmp.name

        from speechbrain.dataio.dataio import read_audio
        signal = read_audio(tmp_path)
        if signal.dim() == 1:
            signal = signal.unsqueeze(0)
        elif signal.dim() == 2:
            signal = signal.mean(dim=1, keepdim=False).unsqueeze(0)
        emb = model.encode_batch(signal)
        result = np.array(emb.squeeze().cpu()).flatten().tolist()
        if len(result) != ECAPA_EMBEDDING_DIM:
            logger.warning("Voice embedding (pcm): bad dim %s (expected %s)", len(result), ECAPA_EMBEDDING_DIM)
            return None
        return result
    except Exception as e:
        logger.warning("Voice embedding (pcm) failed: %s", str(e)[:120])
        return None
    finally:
        try:
            if tmp_path:
                os.unlink(tmp_path)
        except Exception:
            pass


def l2_normalize(x: Sequence[float]) -> np.ndarray:
    """L2-normalize embedding to unit length for stable cosine comparison."""
    arr = np.asarray(x, dtype=np.float32)
    n = np.linalg.norm(arr)
    if n < 1e-8:
        return arr
    return arr / n


def compute_embedding_centroid(
    embeddings: list[list[float]],
    normalize: bool = True,
) -> Optional[list[float]]:
    """
    Compute element-wise mean of embeddings; optionally L2-normalize.
    Stored embeddings are unit length for consistent cosine similarity.
    Returns None if embeddings is empty.
    """
    if not embeddings:
        return None
    arr = np.asarray(embeddings, dtype=np.float32)
    mean = np.mean(arr, axis=0)
    if normalize:
        mean = l2_normalize(mean)
    return mean.tolist()


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity for embedding vectors. Normalizes so comparison is on unit sphere."""
    a_vec = l2_normalize(a)
    b_vec = l2_normalize(b)
    return float(np.dot(a_vec, b_vec))


def best_match(
    embedding: Sequence[float],
    candidates: dict[str, Sequence[float]],
    threshold: float,
) -> tuple[Optional[str], float]:
    """Return (user_id, score) for best match above threshold."""
    best_id = None
    best_score = 0.0
    for user_id, cand in candidates.items():
        score = cosine_similarity(embedding, cand)
        if score > best_score:
            best_score = score
            best_id = user_id
    if best_score >= threshold:
        return best_id, best_score
    return None, best_score


def _percentile_90(values: Sequence[float]) -> float:
    """90th percentile of values (for robust multi-embedding scoring)."""
    if not values:
        return 0.0
    arr = np.asarray(values, dtype=np.float64)
    return float(np.percentile(arr, 90))


def score_user_multi_embedding(
    track_embedding: Sequence[float],
    user_embeddings: Sequence[Sequence[float]],
    *,
    percentile: float = 90.0,
    device_filter: Optional[str] = None,
    embeddings_meta: Optional[Sequence[dict]] = None,
) -> float:
    """
    Score one user against a track embedding when the user has N embeddings (multi-embedding enrollment).
    score(user) = percentile_90( cos(track_emb, e) for e in E_user ).
    Returns 0.0 if user_embeddings is empty.
    Optionally filter by device_filter (e.g. DEVICE_MODE_FAR_FIELD) using embeddings_meta[i].get("device").
    """
    if not user_embeddings:
        return 0.0
    scores: list[float] = []
    for i, emb in enumerate(user_embeddings):
        if device_filter is not None and embeddings_meta is not None and i < len(embeddings_meta):
            if embeddings_meta[i].get("device") != device_filter:
                continue
        scores.append(cosine_similarity(track_embedding, emb))
    if not scores:
        return 0.0
    if percentile >= 100:
        return float(max(scores))
    if percentile <= 0:
        return float(min(scores))
    return float(np.percentile(np.asarray(scores, dtype=np.float64), percentile))


def parse_voice_embedding_json(
    voice_embedding_json: Optional[str],
    expected_dim: int = ECAPA_EMBEDDING_DIM,
) -> tuple[list[list[float]], list[dict]]:
    """
    Parse voice_embedding_json into list of embeddings and optional metadata per embedding.
    Backward-compatible:
    - If JSON is a single array of 192 numbers -> one embedding, no metadata.
    - If JSON is a list of {embedding: number[], device?, snr?, ts?} -> multiple embeddings + metadata.
    Returns (embeddings_list, metadata_list). metadata_list[i] is {} for legacy single embedding.
    """
    if not voice_embedding_json or not voice_embedding_json.strip():
        return [], []
    try:
        import json as _json
        data = _json.loads(voice_embedding_json)
    except Exception:
        return [], []
    if isinstance(data, list):
        if not data:
            return [], []
        first = data[0]
        if isinstance(first, (int, float)):
            # Legacy: single flat array of 192 numbers
            if len(data) == expected_dim:
                return [data], [{}]
            return [], []
        if isinstance(first, dict) and "embedding" in first:
            embeddings = []
            meta = []
            for item in data:
                emb = item.get("embedding")
                if isinstance(emb, list) and len(emb) == expected_dim:
                    embeddings.append(emb)
                    meta.append({k: v for k, v in item.items() if k != "embedding"})
            return embeddings, meta
    return [], []


# Backward compatibility: old name pointed at TitaNet, now points at ECAPA-TDNN
def ensure_titanet_loaded() -> tuple[bool, str]:
    """Alias for ensure_speaker_encoder_loaded (ECAPA-TDNN)."""
    return ensure_speaker_encoder_loaded()
