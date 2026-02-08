"""
STT (Speech-to-Text) API constants.

Centralizes sample rate, message types, speaker sources, labels, and thresholds
used across the STT stream handler and related modules.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Audio / sample rate
# ---------------------------------------------------------------------------
STT_SAMPLE_RATE_HZ = 16000  # 16 kHz mono; used for ring buffer, WAV, and Google/NeMo APIs
STT_BYTES_PER_SAMPLE = 2   # 16-bit linear PCM
STT_MIN_PCM_BYTES_2S = STT_SAMPLE_RATE_HZ * STT_BYTES_PER_SAMPLE * 2  # min bytes for 2s window
STT_SPEAKER_TIMELINE_MAX_SAMPLES_DEFAULT = STT_SAMPLE_RATE_HZ * 60  # retain last 60s of timeline

# ---------------------------------------------------------------------------
# WebSocket message type values (payload["type"])
# ---------------------------------------------------------------------------
MSG_STT_TRANSCRIPT = "stt.transcript"
MSG_STT_SPEAKER_RESOLVED = "stt.speaker_resolved"
MSG_STT_ESCALATION = "stt.escalation"
MSG_STT_ERROR = "stt.error"
MSG_STT_NEMO_DIAR_SEGMENTS = "stt.nemo_diar_segments"

# ---------------------------------------------------------------------------
# speaker_source values sent to client for attribution origin
# ---------------------------------------------------------------------------
SPEAKER_SOURCE_NONE = "none"      # no diarization used
SPEAKER_SOURCE_NEMO = "nemo"     # NeMo fallback diarization
SPEAKER_SOURCE_GOOGLE = "google"  # Google SpeakerDiarizationConfig
SPEAKER_SOURCE_VOICE_ID = "voice_id"  # embedding/timeline match

# ---------------------------------------------------------------------------
# Labels for unresolved or anonymous speakers
# ---------------------------------------------------------------------------
LABEL_UNKNOWN = "UNKNOWN"        # initial segment label before resolution
LABEL_UNKNOWN_PREFIX = "Unknown_"  # prefix for session-scoped unknown speakers (Unknown_1, ...)
LABEL_ANON_PREFIX = "Anon_"       # prefix for NeMo anonymous speakers (Anon_1, ...)

# ---------------------------------------------------------------------------
# Match thresholds and defaults
# ---------------------------------------------------------------------------
DEFAULT_MATCH_MARGIN = 0.03   # min score gap between best and second to accept best
DEFAULT_LARGE_MARGIN = 0.25   # clear-winner margin when below match threshold
DEFAULT_STT_EXECUTOR_WORKERS = 4  # ThreadPoolExecutor for embedding/diarization
WAV_MONO_CHANNELS = 1
SESSION_END_SLEEP_BEFORE_CENTROID_S = 0.5  # brief wait before session-end centroid update
MIN_SEGMENT_DURATION_S = 0.5   # minimum segment/clean-PCM duration in seconds
