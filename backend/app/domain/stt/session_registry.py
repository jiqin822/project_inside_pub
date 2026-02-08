from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple

# Overlap flag for diarization intervals: avoid over-triggering (only DEFINITE_OVERLAP blocks clean_buffer).
POSSIBLE_OVERLAP = "POSSIBLE_OVERLAP"
DEFINITE_OVERLAP = "DEFINITE_OVERLAP"
OVERLAP_NONE = "NONE"

# Diarization interval: (start_sample, end_sample, spk_id, spk_conf, overlap_flag).
# overlap_flag is POSSIBLE_OVERLAP | DEFINITE_OVERLAP | OVERLAP_NONE.
class DiarInterval(NamedTuple):
    start_sample: int
    end_sample: int
    speaker_id: str
    spk_conf: float
    overlap_flag: str


def diarization_reliable_end_sample(now_sample: int, lag_ms: int, sample_rate: int = 16000) -> int:
    """
    Sortformer output is reliable only up to now_sample - L.
    Only resolve speakers for transcript segments whose end_sample <= this value.
    """
    lag_samples = (lag_ms * sample_rate) // 1000
    return max(0, now_sample - lag_samples)


def _ring_append(buffer: bytearray, data: bytes, max_bytes: int) -> None:
    """Append data to buffer; evict from the start so len(buffer) <= max_bytes."""
    buffer.extend(data)
    if len(buffer) > max_bytes:
        del buffer[: len(buffer) - max_bytes]


@dataclass
class TrackState:
    """
    Per-spk_id state for timeline-based speaker identification.
    clean_buffer: ring of PCM bytes (non-overlap speech only); max size e.g. 6–10s.
    track_embedding: rolling centroid from clean speech; only set after warm-up (2–3 embeddings).
    """
    stable_label: str  # user_id or Unknown_spk{K}
    label_posterior: Dict[str, float] = field(default_factory=dict)
    last_seen_sample: int = 0
    clean_buffer: bytearray = field(default_factory=bytearray)  # ring: cap size when appending
    clean_buffer_max_bytes: int = 16000 * 2 * 10  # 10s at 16 kHz PCM16
    track_embedding: Optional[List[float]] = None
    embedding_count: int = 0  # number of clean-speech embeddings used; warm-up until >= 2
    current_best_label: Optional[str] = None  # non-sticky best candidate this update

    def append_clean_speech(self, pcm_chunk: bytes) -> None:
        """Append non-overlap PCM to clean_buffer with ring eviction."""
        _ring_append(self.clean_buffer, pcm_chunk, self.clean_buffer_max_bytes)


@dataclass
class SttSessionContext:
    session_id: str
    user_id: str
    candidate_user_ids: list[str]
    language_code: str
    min_speaker_count: int
    max_speaker_count: int
    disable_speaker_union_join: bool = False
    debug: bool = False
    skip_diarization: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    speaker_tag_to_label: Dict[int, str] = field(default_factory=dict)
    unknown_counter: int = 0
    voice_embeddings: Dict[str, list[float]] = field(default_factory=dict)  # one centroid per user (backward compat)
    # Multi-embedding per user: (embeddings_list, metadata_list). Used for percentile_90 scoring when set.
    voice_embeddings_multi: Dict[str, Tuple[List[List[float]], List[dict]]] = field(default_factory=dict)
    unknown_voice_embeddings: Dict[str, list[float]] = field(default_factory=dict)
    # Union-find for unknown labels: canonical root = smallest N in Unknown_N; only current/future segments affected
    unknown_label_parent: Dict[str, str] = field(default_factory=dict)
    voice_id_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    segment_index: int = 0  # monotonic per session for segment_id
    pending_voice_id_tasks: Set[Any] = field(default_factory=set)  # asyncio.Task refs; cancel on disconnect
    # Session-end centroid: segment embeddings attributed to each known user (capped when appending)
    user_segment_embeddings: Dict[str, list[list[float]]] = field(default_factory=dict)

    # --- NeMo fallback diarization state (optional) ---
    # Latest diarization segments (stream time seconds) for the rolling window.
    # Tuple = (start_s, end_s, nemo_speaker_id)
    nemo_latest_segments: list[Tuple[float, float, str]] = field(default_factory=list)
    # Rolling history of NeMo segments (absolute stream seconds) for overlap; pruned by retention_s.
    nemo_segments_history: list[Tuple[float, float, str]] = field(default_factory=list)
    nemo_history_retention_s: float = 60.0
    nemo_history_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # Bounded deferral: segments waiting for NeMo overlap; set when NeMo window updates.
    nemo_updated_event: asyncio.Event = field(default_factory=asyncio.Event)
    # Pending final segments: list of dicts with segment_id, seg_abs_start_s, seg_abs_end_s, payload, created_ts, ttl_s.
    pending_final_segments: list = field(default_factory=list)
    # Stable mapping of NeMo speaker ids -> session-scoped numeric speaker_tag (for WS contract).
    nemo_speaker_id_to_tag: Dict[str, int] = field(default_factory=dict)
    nemo_next_tag: int = 1
    # Map NeMo speaker ids -> label (known user_id or Anon_N).
    nemo_speaker_id_to_label: Dict[str, str] = field(default_factory=dict)
    nemo_anon_counter: int = 0
    nemo_label_attempted: Set[str] = field(default_factory=set)
    # Per NeMo speaker labeling status/locks.
    nemo_label_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # Track in-flight labeling tasks so we can cancel on disconnect.
    pending_nemo_label_tasks: Set[Any] = field(default_factory=set)

    # --- Voice-matching redesign: speaker timeline and tracks (sample-index timebase) ---
    # Lock for speaker_timeline and spk_tracks (Sortformer worker vs STT attribution).
    timeline_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # Rolling diarization intervals: (start_sample, end_sample, spk_id, spk_conf, overlap_flag).
    # Retain last ~60s; prune by start_sample.
    speaker_timeline: List[DiarInterval] = field(default_factory=list)
    speaker_timeline_max_samples: int = 16000 * 60  # 60s at 16 kHz
    # Per spk_id (e.g. "0", "1", "spk_0") -> TrackState.
    spk_tracks: Dict[str, TrackState] = field(default_factory=dict)
    # All attribution and intervals use sample indices; never exceed ring buffer retention.
    # stream_base / ring_buffer.total_samples define audio_timebase (set when stream starts).

    # Segment audio backing store: segment_id -> raw PCM bytes. Kept for segments not yet resolved
    # so speaker_resolved can attach audio if needed; pruned when over max or when resolved.
    segment_audio_backing: Dict[int, bytes] = field(default_factory=dict)
    segment_audio_backing_max: int = 30

    # Guardrails / metrics (optional): counts for evaluation and drift detection.
    segments_resolved_count: int = 0
    overlap_resolved_count: int = 0
    uncertain_resolved_count: int = 0

    # --- Streaming NeMo diarization state (per-session) ---
    streaming_diarizer: Optional[Any] = None  # Per-session streaming diarizer instance
    streaming_diar_lock: asyncio.Lock = field(default_factory=asyncio.Lock)  # Lock for step() calls
    diar_abs_cursor_sample: Optional[int] = None  # Absolute sample index for next consumed diar chunk
    diar_last_end_sample: Optional[int] = None  # Last end_sample seen from queue (for gap detection)
    diar_pending_base_sample: Optional[int] = None  # Sample index for first byte in pending_pcm
    # Open segment continuity state (for cross-step merging)
    diar_open_segment: Optional[Tuple[int, str, str, float, int]] = None
    # (start_sample, speaker_id, overlap_flag, conf_sum, frame_count)


class SttSessionRegistry:
    def __init__(self) -> None:
        self._sessions: Dict[str, SttSessionContext] = {}
        self._lock = asyncio.Lock()

    async def create(self, ctx: SttSessionContext) -> None:
        async with self._lock:
            self._sessions[ctx.session_id] = ctx

    async def get(self, session_id: str) -> Optional[SttSessionContext]:
        async with self._lock:
            return self._sessions.get(session_id)

    async def delete(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)


stt_registry = SttSessionRegistry()
