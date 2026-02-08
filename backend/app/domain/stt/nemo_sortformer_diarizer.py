from __future__ import annotations

import concurrent.futures
import logging
import math
import os
import tempfile
import threading
import time
import wave
from dataclasses import dataclass
from typing import Any, Optional

"""
NeMo Sortformer diarization (best-effort, optional dependency).

Uses the streaming Sortformer model per:
  https://huggingface.co/nvidia/diar_streaming_sortformer_4spk-v2.1

This module is intentionally import-safe when NeMo is not installed.
Callers should check `nemo_diarization_available()` and/or handle None/[] outputs.

Optional environment variables:
- NEMO_DIAR_MODEL_PATH: path to a local .nemo checkpoint; if set, load via restore_from instead of from_pretrained.
- HF_TOKEN: Hugging Face token for from_pretrained (e.g. gated models).
- NEMO_CACHE_DIR: directory for NeMo/HF cache (default: tempdir/nemo_cache).
- NEMO_DIAR_USE_CUDA: set to 1/true to enable CUDA (default: CPU).
"""
import numpy as np

logger = logging.getLogger(__name__)

# Expected sample rate for NeMo Sortformer (16 kHz mono).
_REQUIRED_SAMPLE_RATE = 16000
_MIN_DURATION_SAMPLES = _REQUIRED_SAMPLE_RATE * 1  # 1 second minimum
_MAX_SPEAKER_INDEX = 3  # 4spk model: 0..3


@dataclass(frozen=True)
class DiarSegment:
    start_s: float
    end_s: float
    speaker_id: str  # e.g. "spk_0"


_LOAD_ERROR: Optional[str] = None
_LOAD_LOCK: threading.Lock = threading.Lock()
_MODEL: Optional[Any] = None
# Removed global _STREAMING_DIARIZER - now created per-session
_STREAMING_LOCK: threading.Lock = threading.Lock()  # Keep for backward compat if needed


def nemo_diarization_available() -> tuple[bool, Optional[str]]:
    """
    Returns (available, error_message).
    - available=True means imports succeeded and model can be instantiated.
    - This does not guarantee the model files are already downloaded.
    """
    global _LOAD_ERROR
    if _LOAD_ERROR is not None:
        return False, _LOAD_ERROR
    try:
        # Lazy import probe only (do not instantiate model here).
        import nemo  # noqa: F401
        return True, None
    except Exception as e:  # pragma: no cover
        _LOAD_ERROR = f"NeMo not available: {e}"
        return False, _LOAD_ERROR


def _get_cache_dir() -> str:
    # Allow operator to control NeMo/HF cache location in ephemeral deployments.
    # Falling back to temp dir keeps containerized runs from writing into read-only paths.
    base = os.environ.get("NEMO_CACHE_DIR")
    if base:
        return base
    tmp = os.environ.get("TMPDIR") or os.environ.get("TEMP") or os.environ.get("TMP")
    if tmp:
        return os.path.join(tmp, "nemo_cache")
    return os.path.join("/tmp", "nemo_cache")


# Default Hugging Face model: streaming Sortformer 4spk v2.1 (see link in docstring).
_NEMO_DIAR_HF_MODEL_ID = "nvidia/diar_streaming_sortformer_4spk-v2.1"

# Streaming config: low latency (~1.04s input buffer). See HF model card for "low latency" row.
_NEMO_STREAMING_CHUNK_LEN = 6
_NEMO_STREAMING_CHUNK_RIGHT_CONTEXT = 7
_NEMO_STREAMING_FIFO_LEN = 188
_NEMO_STREAMING_SPKCACHE_UPDATE_PERIOD = 144
_NEMO_STREAMING_SPKCACHE_LEN = 188
_NEMO_STREAMING_CHUNK_LEFT_CONTEXT = 1
_STREAM_FRAME_LEN_S = 0.08  # 80ms frames (streaming model default)


def _cuda_enabled() -> bool:
    flag = os.environ.get("NEMO_DIAR_USE_CUDA", "").strip().lower()
    return flag in {"1", "true", "yes", "y", "on"}


def streaming_latency_s() -> float:
    """Return streaming latency window in seconds."""
    return (_NEMO_STREAMING_CHUNK_LEN + _NEMO_STREAMING_CHUNK_RIGHT_CONTEXT) * _STREAM_FRAME_LEN_S


def streaming_context_window_s() -> float:
    """Return streaming context window in seconds."""
    return (
        _NEMO_STREAMING_FIFO_LEN
        + _NEMO_STREAMING_CHUNK_LEN
        + _NEMO_STREAMING_CHUNK_RIGHT_CONTEXT
    ) * _STREAM_FRAME_LEN_S


def streaming_frame_len_s() -> float:
    """Return streaming frame length in seconds."""
    return _STREAM_FRAME_LEN_S


def get_frame_bytes() -> int:
    """Return frame size in bytes (80ms at 16kHz, 16-bit PCM)."""
    return int(_REQUIRED_SAMPLE_RATE * _STREAM_FRAME_LEN_S * 2)


def get_chunk_bytes() -> int:
    """Return chunk size in bytes (chunk_len frames at 16kHz, 16-bit PCM)."""
    return int(_REQUIRED_SAMPLE_RATE * _STREAM_FRAME_LEN_S * _NEMO_STREAMING_CHUNK_LEN * 2)


def _apply_streaming_config(model: Any) -> None:
    """Set streaming Sortformer params per HF model card (low latency)."""
    mod = getattr(model, "sortformer_modules", None)
    if mod is None:
        return
    # These values tune the model's internal streaming buffers and context windows.
    # Keep them aligned with the HF streaming model card to avoid degraded diarization quality.
    setattr(mod, "chunk_len", _NEMO_STREAMING_CHUNK_LEN)
    if hasattr(mod, "chunk_left_context"):
        setattr(mod, "chunk_left_context", _NEMO_STREAMING_CHUNK_LEFT_CONTEXT)
    setattr(mod, "chunk_right_context", _NEMO_STREAMING_CHUNK_RIGHT_CONTEXT)
    setattr(mod, "fifo_len", _NEMO_STREAMING_FIFO_LEN)
    if hasattr(mod, "spkcache_update_period"):
        setattr(mod, "spkcache_update_period", _NEMO_STREAMING_SPKCACHE_UPDATE_PERIOD)
    if hasattr(mod, "spkcache_refresh_rate"):
        setattr(mod, "spkcache_refresh_rate", _NEMO_STREAMING_SPKCACHE_UPDATE_PERIOD)
    setattr(mod, "spkcache_len", _NEMO_STREAMING_SPKCACHE_LEN)
    check = getattr(mod, "_check_streaming_parameters", None)
    if callable(check):
        check()


def _ensure_model_loaded() -> Any:
    """
    Load SortformerEncLabelModel (thread-safe, single load).
    Uses NEMO_DIAR_MODEL_PATH if set, else from_pretrained(nvidia/diar_streaming_sortformer_4spk-v2.1).
    Applies low-latency streaming config for the HF streaming model.
    """
    global _MODEL, _LOAD_ERROR
    # Single-flight load so multiple sessions don't race to instantiate the heavy model.
    # Any load error is cached to avoid repeated expensive failures.
    with _LOAD_LOCK:
        if _MODEL is not None:
            return _MODEL
        if _LOAD_ERROR is not None:
            raise RuntimeError(_LOAD_ERROR)

        try:
            from nemo.collections.asr.models import SortformerEncLabelModel
        except Exception as e:  # pragma: no cover
            _LOAD_ERROR = f"NeMo SortformerEncLabelModel import failed: {e}"
            raise RuntimeError(_LOAD_ERROR) from e

        try:
            import torch
            use_cuda = _cuda_enabled() and torch.cuda.is_available()
            map_location = "cuda" if use_cuda else "cpu"
        except Exception:  # pragma: no cover
            # Torch import failed; fall back to CPU load.
            map_location = "cpu"

        model_path = os.environ.get("NEMO_DIAR_MODEL_PATH")
        try:
            # Prefer a local checkpoint if provided (useful for offline or pinned models).
            if model_path and os.path.isfile(model_path):
                model = SortformerEncLabelModel.restore_from(
                    restore_path=model_path,
                    map_location=map_location,
                    strict=False,
                )
            else:
                # Use HF pre-trained model (optionally with token).
                hf_token = os.environ.get("HF_TOKEN")
                kwargs = {"token": hf_token} if hf_token else {}
                model = SortformerEncLabelModel.from_pretrained(
                    _NEMO_DIAR_HF_MODEL_ID,
                    **kwargs,
                )
            _apply_streaming_config(model)
            model.eval()
            _MODEL = model
            return _MODEL
        except Exception as e:  # pragma: no cover
            _LOAD_ERROR = f"NeMo diarization model load failed: {e}"
            raise RuntimeError(_LOAD_ERROR) from e


def create_streaming_diarizer() -> Optional[Any]:
    """
    Create a new per-session streaming diarizer instance.
    Returns None if streaming APIs are unavailable or model cannot be loaded.
    
    Each session should call this once and store the instance in session context.
    The returned instance maintains its own streaming state and should not be shared.
    """
    try:
        model = _ensure_model_loaded()
    except Exception:
        # Model load failures are handled upstream; returning None keeps callers resilient.
        return None
    
    if model is None:
        return None
    # Guard on streaming APIs; some model variants do not implement these methods.
    if not hasattr(model, "forward_streaming_step"):
        return None
    mod = getattr(model, "sortformer_modules", None)
    if mod is None or not hasattr(mod, "init_streaming_state"):
        return None

    try:
        import torch
        import nemo.collections.asr as nemo_asr
    except Exception as e:  # pragma: no cover
        logger.warning("NeMo streaming diarizer unavailable: %s", e)
        return None

    class _AudioBufferer:
        def __init__(self, sample_rate: int, buffer_size_in_secs: float) -> None:
            self.buffer_size = int(buffer_size_in_secs * sample_rate)
            self.sample_buffer = torch.zeros(self.buffer_size, dtype=torch.float32)

        def reset(self) -> None:
            self.sample_buffer.zero_()

        def update(self, audio: np.ndarray) -> None:
            if not isinstance(audio, torch.Tensor):
                audio = torch.from_numpy(audio)
            audio_size = audio.shape[0]
            if audio_size > self.buffer_size:
                raise ValueError(
                    f"Frame size ({audio_size}) exceeds buffer size ({self.buffer_size})"
                )
            # Shift buffer left and append new samples to keep a rolling window.
            shift = audio_size
            self.sample_buffer[:-shift] = self.sample_buffer[shift:].clone()
            self.sample_buffer[-shift:] = audio.clone()

        def get_buffer(self) -> torch.Tensor:
            return self.sample_buffer.clone()

        def is_buffer_empty(self) -> bool:
            return self.sample_buffer.sum() == 0

    class _CacheFeatureBufferer:
        def __init__(
            self,
            sample_rate: int,
            buffer_size_in_secs: float,
            chunk_size_in_secs: float,
            preprocessor_cfg: Any,
            device: str,
            fill_value: float = -16.635,
        ) -> None:
            # Feature buffer must be at least one chunk to support streaming windows.
            if buffer_size_in_secs < chunk_size_in_secs:
                raise ValueError(
                    "Buffer size must be >= chunk size for streaming features"
                )
            self.sample_rate = sample_rate
            self.buffer_size_in_secs = buffer_size_in_secs
            self.chunk_size_in_secs = chunk_size_in_secs
            self.device = device
            self.zero_level = (
                -16.635
                if getattr(preprocessor_cfg, "log", False)
                else fill_value
            )
            self.n_feat = preprocessor_cfg.features
            self.timestep_duration = preprocessor_cfg.window_stride
            self.n_chunk_look_back = int(self.timestep_duration * self.sample_rate)
            self.chunk_size = int(self.chunk_size_in_secs * self.sample_rate)
            self.sample_buffer = _AudioBufferer(sample_rate, buffer_size_in_secs)

            self.feature_buffer_len = int(buffer_size_in_secs / self.timestep_duration)
            self.feature_chunk_len = int(chunk_size_in_secs / self.timestep_duration)
            self.feature_buffer = torch.full(
                [self.n_feat, self.feature_buffer_len],
                self.zero_level,
                dtype=torch.float32,
                device=self.device,
            )

            # Build a feature extractor that matches the diarization model's config.
            self.preprocessor = nemo_asr.models.ASRModel.from_config_dict(
                preprocessor_cfg
            )
            self.preprocessor.to(self.device)

        def is_buffer_empty(self) -> bool:
            return self.sample_buffer.is_buffer_empty()

        def reset(self) -> None:
            self.sample_buffer.reset()
            self.feature_buffer.fill_(self.zero_level)

        def _update_feature_buffer(self, feat_chunk: torch.Tensor) -> None:
            # Maintain a rolling window of features aligned to streaming buffer length.
            self.feature_buffer[:, : -self.feature_chunk_len] = self.feature_buffer[
                :, self.feature_chunk_len :
            ].clone()
            self.feature_buffer[:, -self.feature_chunk_len :] = feat_chunk.clone()

        def preprocess(self, audio_signal: torch.Tensor) -> torch.Tensor:
            # Normalize audio to batch shape for the NeMo preprocessor.
            audio_signal = audio_signal.unsqueeze_(0).to(self.device)
            audio_signal_len = torch.tensor(
                [audio_signal.shape[1]], device=self.device
            )
            features, _ = self.preprocessor(
                input_signal=audio_signal,
                length=audio_signal_len,
            )
            return features.squeeze()

        def update(self, audio: np.ndarray) -> None:
            self.sample_buffer.update(audio)
            # Pull the most recent chunk (plus look-back) and compute features.
            if math.isclose(self.buffer_size_in_secs, self.chunk_size_in_secs):
                samples = self.sample_buffer.sample_buffer.clone()
            else:
                samples = self.sample_buffer.sample_buffer[
                    -(self.n_chunk_look_back + self.chunk_size) :
                ]
            features = self.preprocess(samples)
            # Trim extra frames produced by the preprocessor to fit the expected chunk size.
            if (diff := features.shape[1] - self.feature_chunk_len - 1) > 0:
                features = features[:, :-diff]
            self._update_feature_buffer(features[:, -self.feature_chunk_len :])

        def get_feature_buffer(self) -> torch.Tensor:
            return self.feature_buffer.clone()

    class _StreamingDiarizer:
        def __init__(self, diar_model: Any, device: str, max_num_speakers: int) -> None:
            self.model = diar_model
            self.device = device
            self.max_num_speakers = max_num_speakers
            self.chunk_size = getattr(
                diar_model.sortformer_modules, "chunk_len", _NEMO_STREAMING_CHUNK_LEN
            )
            self.frame_len_in_secs = _STREAM_FRAME_LEN_S
            # Offset frames control how much left/right context is included in streaming outputs.
            self.left_offset = 8
            self.right_offset = 8
            self.buffer_size_in_secs = (
                self.chunk_size * self.frame_len_in_secs
                + (self.left_offset + self.right_offset) * 0.01
            )
            self.feature_bufferer = _CacheFeatureBufferer(
                sample_rate=_REQUIRED_SAMPLE_RATE,
                buffer_size_in_secs=self.buffer_size_in_secs,
                chunk_size_in_secs=self.chunk_size * self.frame_len_in_secs,
                preprocessor_cfg=diar_model.cfg.preprocessor,
                device=self.device,
            )
            self.streaming_state = self._init_streaming_state(batch_size=1)
            self.total_preds = torch.zeros(
                (1, 0, self.max_num_speakers), device=self.device
            )

        def reset_state(self) -> None:
            # Clear cached features and model streaming state for a fresh session.
            self.feature_bufferer.reset()
            self.streaming_state = self._init_streaming_state(batch_size=1)
            self.total_preds = torch.zeros(
                (1, 0, self.max_num_speakers), device=self.device
            )

        def _init_streaming_state(self, batch_size: int = 1) -> Any:
            async_streaming = getattr(self.model, "async_streaming", False)
            try:
                return self.model.sortformer_modules.init_streaming_state(
                    batch_size=batch_size,
                    async_streaming=async_streaming,
                    device=self.device,
                )
            except TypeError:
                return self.model.sortformer_modules.init_streaming_state(
                    batch_size=batch_size,
                    async_streaming=async_streaming,
                )

        def diarize(self, audio: bytes) -> np.ndarray:
            """Process audio and return chunk predictions (legacy method)."""
            audio_array = (
                np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
            )
            # Update rolling feature buffer and run one streaming step.
            self.feature_bufferer.update(audio_array)
            features = self.feature_bufferer.get_feature_buffer()
            feature_buffers = features.unsqueeze(0).transpose(1, 2)
            feature_buffer_lens = torch.tensor(
                [feature_buffers.shape[1]], device=self.device
            )
            self.streaming_state, chunk_preds = self._stream_step(
                processed_signal=feature_buffers,
                processed_signal_length=feature_buffer_lens,
                streaming_state=self.streaming_state,
                total_preds=self.total_preds,
                left_offset=self.left_offset,
                right_offset=self.right_offset,
            )
            self.total_preds = chunk_preds
            diar_result = chunk_preds[:, -self.chunk_size :, :].clone().cpu().numpy()
            return diar_result[0]

        def step_chunk(self, pcm_bytes: bytes) -> list[np.ndarray]:
            """
            Process a full chunk (chunk_len frames) in a single streaming step.

            Args:
                pcm_bytes: PCM16 audio bytes, length must equal chunk_bytes.

            Returns:
                List of frame probability arrays (one per frame in the chunk).
            """
            frame_bytes = get_frame_bytes()
            chunk_bytes = frame_bytes * self.chunk_size
            if len(pcm_bytes) != chunk_bytes:
                raise ValueError(
                    f"pcm_bytes length ({len(pcm_bytes)}) must equal chunk_bytes ({chunk_bytes})"
                )
            if len(pcm_bytes) < frame_bytes:
                return []

            audio_array = (
                np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            )
            # Update features for the chunk and run one streaming step.
            self.feature_bufferer.update(audio_array)
            features = self.feature_bufferer.get_feature_buffer()
            feature_buffers = features.unsqueeze(0).transpose(1, 2)
            feature_buffer_lens = torch.tensor(
                [feature_buffers.shape[1]], device=self.device
            )
            self.streaming_state, chunk_preds = self._stream_step(
                processed_signal=feature_buffers,
                processed_signal_length=feature_buffer_lens,
                streaming_state=self.streaming_state,
                total_preds=self.total_preds,
                left_offset=self.left_offset,
                right_offset=self.right_offset,
            )
            self.total_preds = chunk_preds
            diar_result = chunk_preds[:, -self.chunk_size :, :].clone().cpu().numpy()
            # diar_result shape: (1, chunk_size, num_speakers)
            # it's a numpy array with probabilities per speaker for each frame in the chunk
            return [frame for frame in diar_result[0]]

        def step(self, pcm_bytes: bytes) -> list[np.ndarray]:
            """
            Process audio incrementally without resetting state.
            
            Args:
                pcm_bytes: PCM16 audio bytes, must be a multiple of frame_bytes.
                          Typically chunk_bytes (6 frames = 0.48s) for efficient processing.
            
            Returns:
                List of frame probability arrays (one per frame in the input).
                Each array has shape (max_num_speakers,).
            """
            frame_bytes = get_frame_bytes()
            chunk_bytes = frame_bytes * self.chunk_size
            if len(pcm_bytes) % frame_bytes != 0:
                raise ValueError(
                    f"pcm_bytes length ({len(pcm_bytes)}) must be a multiple of frame_bytes ({frame_bytes})"
                )
            if len(pcm_bytes) < frame_bytes:
                return []

            # If this is a full chunk, use the efficient single-step path.
            if len(pcm_bytes) == chunk_bytes:
                return self.step_chunk(pcm_bytes)
            
            num_frames = len(pcm_bytes) // frame_bytes
            frame_probs: list[np.ndarray] = []
            
            # Process frame by frame to maintain continuity.
            # We keep only the newest frame prediction to avoid duplicates.
            for offset in range(0, len(pcm_bytes), frame_bytes):
                frame_pcm = pcm_bytes[offset : offset + frame_bytes]
                audio_array = (
                    np.frombuffer(frame_pcm, dtype=np.int16).astype(np.float32) / 32768.0
                )
                self.feature_bufferer.update(audio_array)
                features = self.feature_bufferer.get_feature_buffer()
                feature_buffers = features.unsqueeze(0).transpose(1, 2)
                feature_buffer_lens = torch.tensor(
                    [feature_buffers.shape[1]], device=self.device
                )
                self.streaming_state, chunk_preds = self._stream_step(
                    processed_signal=feature_buffers,
                    processed_signal_length=feature_buffer_lens,
                    streaming_state=self.streaming_state,
                    total_preds=self.total_preds,
                    left_offset=self.left_offset,
                    right_offset=self.right_offset,
                )
                self.total_preds = chunk_preds
                # Extract only the newest frame prediction to avoid overlap duplication
                frame_pred = chunk_preds[:, -1, :].clone().cpu().numpy()
                frame_probs.append(frame_pred[0])
            
            return frame_probs

        def _stream_step(
            self,
            processed_signal: Any,
            processed_signal_length: Any,
            streaming_state: Any,
            total_preds: Any,
            left_offset: int = 0,
            right_offset: int = 0,
        ) -> tuple[Any, Any]:
            # Ensure tensors are on the correct device before forwarding.
            if processed_signal.device != self.device:
                processed_signal = processed_signal.to(self.device)
            if processed_signal_length.device != self.device:
                processed_signal_length = processed_signal_length.to(self.device)
            if total_preds is not None and total_preds.device != self.device:
                total_preds = total_preds.to(self.device)
            # Run inference without grad for performance.
            with torch.no_grad():
                return self.model.forward_streaming_step(
                    processed_signal=processed_signal,
                    processed_signal_length=processed_signal_length,
                    streaming_state=streaming_state,
                    total_preds=total_preds,
                    left_offset=left_offset,
                    right_offset=right_offset,
                )

    try:
        device = "cuda" if (_cuda_enabled() and torch.cuda.is_available()) else "cpu"
        max_num_speakers = _MAX_SPEAKER_INDEX + 1
        streaming_diarizer = _StreamingDiarizer(
            diar_model=model, device=device, max_num_speakers=max_num_speakers
        )
        return streaming_diarizer
    except Exception as e:  # pragma: no cover
        logger.warning("NeMo streaming diarizer init failed: %s", e)
        return None


def _ensure_streaming_diarizer(model: Any) -> Optional[Any]:
    """
    Legacy function for backward compatibility.
    Creates a new streaming diarizer instance (no longer cached globally).
    """
    return create_streaming_diarizer()


def _segments_from_frame_probs(
    frame_probs: list[np.ndarray],
    frame_len_s: float,
    max_speakers: Optional[int],
) -> list[DiarSegment]:
    if not frame_probs:
        return []
    probs = np.vstack([p.reshape(1, -1) for p in frame_probs])
    num_speakers = probs.shape[1]
    if max_speakers is not None:
        num_speakers = max(1, min(num_speakers, max_speakers))
    segments: list[DiarSegment] = []
    current_spk: Optional[int] = None
    start_idx = 0
    # Collapse per-frame argmax into contiguous diarization segments.
    for idx in range(probs.shape[0]):
        spk_idx = int(np.argmax(probs[idx, :num_speakers]))
        if current_spk is None:
            current_spk = spk_idx
            start_idx = idx
            continue
        if spk_idx != current_spk:
            segments.append(
                DiarSegment(
                    start_s=start_idx * frame_len_s,
                    end_s=idx * frame_len_s,
                    speaker_id=f"spk_{current_spk}",
                )
            )
            current_spk = spk_idx
            start_idx = idx
    if current_spk is not None and start_idx < probs.shape[0]:
        segments.append(
            DiarSegment(
                start_s=start_idx * frame_len_s,
                end_s=probs.shape[0] * frame_len_s,
                speaker_id=f"spk_{current_spk}",
            )
        )
    return segments


def segments_from_frame_probs(
    frame_probs: list[np.ndarray],
    *,
    frame_len_s: Optional[float] = None,
    max_speakers: Optional[int] = None,
) -> list[DiarSegment]:
    """Public wrapper for converting frame probabilities to diar segments."""
    return _segments_from_frame_probs(
        frame_probs,
        frame_len_s if frame_len_s is not None else _STREAM_FRAME_LEN_S,
        max_speakers,
    )


def _streaming_diarize_pcm16(
    streaming: Any,
    audio_pcm16: bytes,
    max_speakers: Optional[int],
    timeout_s: Optional[float] = None,
) -> list[DiarSegment]:
    frame_bytes = int(_REQUIRED_SAMPLE_RATE * _STREAM_FRAME_LEN_S * 2)
    if frame_bytes <= 0:
        return []
    frame_probs: list[np.ndarray] = []
    num_skipped = 0
    num_iterations = 0
    first_probs_shape: Optional[tuple] = None
    start_ts = time.monotonic()
    # Streaming diarizer is stateful; lock to avoid interleaved calls from multiple threads.
    with _STREAMING_LOCK:
        streaming.reset_state()
        for offset in range(0, len(audio_pcm16) - frame_bytes + 1, frame_bytes):
            if timeout_s is not None and timeout_s > 0:
                if (time.monotonic() - start_ts) > timeout_s:
                    break
            num_iterations += 1
            chunk = audio_pcm16[offset : offset + frame_bytes]
            probs = streaming.diarize(chunk)
            if probs is None or len(probs) == 0:
                num_skipped += 1
                continue
            if first_probs_shape is None:
                first_probs_shape = getattr(probs, "shape", None)
            # Keep only the newest frame prediction to avoid overlap duplication.
            frame_probs.append(probs[-1])
    segments = _segments_from_frame_probs(
        frame_probs, frame_len_s=_STREAM_FRAME_LEN_S, max_speakers=max_speakers
    )
    return segments


def _diarize_via_tempfile(model: Any, audio_pcm16: bytes) -> Any:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
        # Write a temporary WAV because NeMo diarize() expects a file path.
        with wave.open(tmp, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(_REQUIRED_SAMPLE_RATE)
            wf.writeframes(audio_pcm16)
        tmp.flush()
        return model.diarize(audio=[tmp.name], batch_size=1)


def _run_diarize_once(
    model: Any,
    audio_pcm16: bytes,
) -> Any:
    """
    Call model.diarize(audio=[/path/to/audio.wav], batch_size=1).

    Returns:
        The raw return value from the model's .diarize() method.
        This is typically a list (or nested list) of diarization segments, but the exact
        structure depends on the NeMo model version and configuration:
            - Commonly: list of (start_s, end_s, speaker_idx) tuples/lists
            - Sometimes: list of dicts with keys like 'start', 'end', and 'speaker'
            - In some cases, a list with a single element which is itself a list of segments
        Raises:
            Any exception raised by model.diarize(), e.g., if input is invalid.
    """
    return _diarize_via_tempfile(model, audio_pcm16)


def _parse_diarize_result(
    raw: Any,
    duration_s: float,
    max_speakers: Optional[int],
) -> list[DiarSegment]:
    """
    Parse NeMo diarize() return into list[DiarSegment].
    Accepts list of (start_s, end_s, speaker_idx), list of lists, or list of dicts;
    per-file nested list (length 1 for single file) is unwrapped.
    """
    out: list[DiarSegment] = []
    items: list[Any] = []
    if isinstance(raw, list) and len(raw) == 1 and isinstance(raw[0], list):
        items = raw[0]
    elif isinstance(raw, list):
        items = raw
    else:
        return out

    # Normalize all supported return shapes into DiarSegment entries.
    for item in items:
        start_s: float
        end_s: float
        spk_idx: int
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            try:
                start_s = float(item[0])
                end_s = float(item[1])
                spk_idx = int(item[2])
            except (TypeError, ValueError):
                logger.debug("nemo diarize: skip unparseable segment %r", item)
                continue
        elif isinstance(item, dict):
            start_s = item.get("start") if "start" in item else item.get("begin")
            end_s = item.get("end")
            spk_idx = item.get("speaker") if "speaker" in item else item.get("speaker_index")
            if start_s is None or end_s is None or spk_idx is None:
                logger.debug("nemo diarize: skip dict segment missing keys %r", item)
                continue
            try:
                start_s = float(start_s)
                end_s = float(end_s)
                spk_idx = int(spk_idx)
            except (TypeError, ValueError):
                logger.debug("nemo diarize: skip unparseable dict segment %r", item)
                continue
        else:
            logger.debug("nemo diarize: skip unknown segment type %r", type(item))
            continue

        # Clamp to the audio duration to avoid out-of-bounds intervals.
        start_s = max(0.0, min(start_s, duration_s))
        end_s = max(0.0, min(end_s, duration_s))
        if start_s >= end_s:
            continue
        spk_idx = max(0, min(spk_idx, _MAX_SPEAKER_INDEX))
        if max_speakers is not None and spk_idx >= max_speakers:
            continue
        out.append(
            DiarSegment(start_s=start_s, end_s=end_s, speaker_id=f"spk_{spk_idx}")
        )
    return out


def diarize_pcm16(
    audio_pcm16: bytes,
    sample_rate: int,
    *,
    timeout_s: float = 10.0,
    max_speakers: Optional[int] = None,
) -> list[DiarSegment]:
    """
    Best-effort diarization for a short audio window using NeMo Sortformer.
    Prefers the streaming API if available; otherwise falls back to file-based diarize().

    Expects 16 kHz mono PCM. Returns [] when NeMo is missing, sample rate is wrong,
    audio is too short (< 1 s), inference times out, or on any error so streaming continues.
    GPU is recommended for real-time use; CPU inference may exceed timeout for long windows.
    """
    if not audio_pcm16:
        return []
    if sample_rate != _REQUIRED_SAMPLE_RATE:
        logger.warning(
            "Nemo diarization failed: sample_rate=%r is not required sample rate %r",
            sample_rate,
            _REQUIRED_SAMPLE_RATE,
        )
        return []
    ok, _err = nemo_diarization_available()
    if not ok:
        logger.warning("Nemo diarization not available")
        return []

    try:
        model = _ensure_model_loaded()
    except Exception:
        return []

    # This function is a non-streaming, windowed diarization path (offline/debug).
    # For live streaming diarization, use per-session streaming_diarizer in SortformerStreamingWorker.
    if len(audio_pcm16) < _MIN_DURATION_SAMPLES * 2:  # 16-bit = 2 bytes per sample
        logger.warning(
            "Nemo diarization failed: audio too short, len(audio_pcm16)=%d, required>=%d",
            len(audio_pcm16),
            _MIN_DURATION_SAMPLES * 2,
        )
        return []

    duration_s = len(audio_pcm16) / (2.0 * _REQUIRED_SAMPLE_RATE)
    try:
        timeout_s = max(0.0, timeout_s)
        # Run diarization in a separate thread so we can enforce a hard timeout.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                _run_diarize_once,
                model,
                audio_pcm16,
            )
            try:
                result = future.result(timeout=timeout_s)
            except (concurrent.futures.TimeoutError, TimeoutError):
                logger.warning("nemo diarize: timeout after %.1fs", timeout_s)
                return []
        raw = result
        parsed = _parse_diarize_result(raw, duration_s, max_speakers)
        return parsed
    except Exception as e:
        logger.warning("nemo diarize failed: %s", e)
        return []

