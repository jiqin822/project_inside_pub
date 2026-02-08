"""
Audio processing for STT stream: WAV conversion, PCM extraction, and segment speaker/source resolution.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import time
import wave
from typing import Any, Optional

from app.domain.stt.diarization_utils import best_overlap_speaker_id
from app.domain.stt.session_registry import SttSessionContext, diarization_reliable_end_sample
from app.domain.stt.speaker_timeline_attribution import extract_clean_pcm_for_segment

from app.api.stt.constants import (
    LABEL_UNKNOWN,
    SPEAKER_SOURCE_NEMO,
    SPEAKER_SOURCE_NONE,
    STT_BYTES_PER_SAMPLE,
    STT_SAMPLE_RATE_HZ,
)
from app.settings import settings

logger = logging.getLogger(__name__)


class SpeakerMatcherProtocol:
    """Protocol for NeMo tag/label assignment used by resolve_final_segment_speaker_and_source."""

    def get_or_assign_nemo_tag(self, ctx: SttSessionContext, nemo_speaker_id: str) -> int: ...
    def get_or_assign_nemo_label(self, ctx: SttSessionContext, nemo_speaker_id: str) -> str: ...


class AudioProcessor:
    """
    Handles audio extraction, conversion, and segment speaker/source resolution.

    Uses constants for sample rate and WAV format. resolve_final_segment_speaker_and_source
    requires a SpeakerMatcher (or protocol) for NeMo tag/label assignment.
    """

    def __init__(self, sample_rate_hz: int = STT_SAMPLE_RATE_HZ):
        self.sample_rate_hz = sample_rate_hz
        self.bytes_per_sample = STT_BYTES_PER_SAMPLE

    def samples_to_wav_base64(self, samples: Any) -> Optional[str]:
        """Build a WAV file from int16 segment samples and return its base64 encoding.

        Uses STT_SAMPLE_RATE_HZ and WAV_MONO_CHANNELS. Returns None if samples are
        missing/empty or if WAV encoding fails.
        """
        from app.api.stt.constants import WAV_MONO_CHANNELS

        if samples is None or len(samples) == 0:
            return None
        try:
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wav_file:
                wav_file.setnchannels(WAV_MONO_CHANNELS)
                wav_file.setsampwidth(self.bytes_per_sample)
                wav_file.setframerate(self.sample_rate_hz)
                wav_file.writeframes(samples.tobytes())
            return base64.b64encode(wav_buffer.getvalue()).decode("utf-8")
        except Exception:
            return None

    def compute_embedding_sync(self, pcm_bytes: bytes) -> Optional[list[float]]:
        """
        CPU-bound: run in executor. Returns ECAPA segment embedding or None.
        PCM must be 16-bit mono at configured sample rate.
        """
        from app.domain.voice.embeddings import compute_embedding_from_pcm_bytes

        return compute_embedding_from_pcm_bytes(pcm_bytes, self.sample_rate_hz)

    async def get_pcm_for_embedding(
        self,
        deps: Any,
        pcm_copy: bytes,
        start_sample: Optional[int],
        end_sample: Optional[int],
        segment_id: int,
    ) -> bytes:
        """Choose PCM for embedding: clean (single-speaker) when possible, else full segment.

        When segment bounds and speaker_timeline exist and we're inside the reliable
        window, extracts clean PCM via extract_clean_pcm_for_segment. Otherwise returns
        pcm_copy.
        """
        if (
            start_sample is not None
            and end_sample is not None
            and deps.ctx.speaker_timeline
        ):
            # We need to retrieve the lag window for reliable diarization from settings, or default to 1000 ms.
            lag_ms = getattr(settings, "stt_diarization_reliable_lag_ms", 1000)
            reliable_end = diarization_reliable_end_sample(
                deps.ring_buffer.total_samples, lag_ms
            )
            if end_sample <= reliable_end:
                async with deps.ctx.timeline_lock:
                    timeline_snapshot = list(deps.ctx.speaker_timeline)
                clean_pcm = extract_clean_pcm_for_segment(
                    timeline_snapshot, start_sample, end_sample, pcm_copy
                )
                if clean_pcm is not None:
                    logger.debug(
                        "STT segment_id=%s using clean-only PCM for embedding clean_seconds=%.2f",
                        segment_id,
                        len(clean_pcm) / (self.sample_rate_hz * self.bytes_per_sample),
                    )
                    return clean_pcm
                logger.debug(
                    "STT segment_id=%s using full segment for embedding (clean duration < min or invalid)",
                    segment_id,
                )
            else:
                logger.debug(
                    "STT segment_id=%s using full segment for embedding (outside reliable window)",
                    segment_id,
                )
        elif (
            start_sample is None or end_sample is None or not deps.ctx.speaker_timeline
        ):
            logger.debug(
                "STT segment_id=%s using full segment for embedding (no timeline or no segment bounds)",
                segment_id,
            )
        return pcm_copy

    async def resolve_final_segment_speaker_and_source(
        self,
        deps: Any,
        seg_abs_start_s: Optional[float],
        seg_abs_end_s: Optional[float],
        seg_tag: Optional[int],
        seg_words: list,
        speaker_matcher: SpeakerMatcherProtocol,
    ) -> tuple[str, str, Optional[str], Optional[int]]:
        """Resolve speaker label, source, NeMo id, and effective tag for a final segment.

        When NeMo fallback is on, overlaps segment time with nemo_latest_segments to get
        nemo_speaker_id and assigns tag/label under nemo_label_lock. Google seg_tag is
        not used for speaker source.

        Returns:
            (seg_speaker_label, speaker_source, nemo_speaker_id, effective_seg_tag).
        """
        seg_speaker_label = LABEL_UNKNOWN
        nemo_speaker_id: Optional[str] = None
        if (
            deps.enable_nemo_fallback
            and seg_abs_start_s is not None
            and seg_abs_end_s is not None
        ):
            async with deps.ctx.nemo_history_lock:
                segments_for_overlap = list(
                    getattr(deps.ctx, "nemo_segments_history", None) or []
                )
            nemo_speaker_id = best_overlap_speaker_id(
                segments_for_overlap, seg_abs_start_s, seg_abs_end_s
            )
            if nemo_speaker_id:
                async with deps.ctx.nemo_label_lock:
                    seg_tag = speaker_matcher.get_or_assign_nemo_tag(
                        deps.ctx, nemo_speaker_id
                    )
                    seg_speaker_label = speaker_matcher.get_or_assign_nemo_label(
                        deps.ctx, nemo_speaker_id
                    )
        speaker_source = SPEAKER_SOURCE_NONE
        if deps.enable_nemo_fallback and nemo_speaker_id:
            speaker_source = SPEAKER_SOURCE_NEMO
        return (seg_speaker_label, speaker_source, nemo_speaker_id, seg_tag)
