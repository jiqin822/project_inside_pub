"""
Segment building from Google STT results and audio extraction from ring buffer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from app.domain.stt.speaker_matching import AudioRingBuffer
from app.domain.stt.script_boundary import (
    assign_text_to_sub_spans,
    derive_and_segment,
    intervals_in_sub_span,
)
from app.domain.stt.speaker_timeline_attribution import extract_clean_pcm_for_segment

from app.api.stt.constants import (
    MIN_SEGMENT_DURATION_S,
    STT_SAMPLE_RATE_HZ,
)

@dataclass
class SttSegment:
    """One STT segment: text, words, speaker tag, timing, and whether it came from diarization."""

    text: str
    words: list
    speaker_tag: Optional[int]
    raw_start_s: Optional[float]
    raw_end_s: Optional[float]
    from_diarization: bool


class SegmentBuilder:
    """Builds segments from Google STT results and extracts segment audio from ring buffer."""

    def __init__(self, sample_rate_hz: int = STT_SAMPLE_RATE_HZ):
        self.sample_rate_hz = sample_rate_hz

    @staticmethod
    def _duration_to_seconds(duration: Any) -> float:
        """Convert a protobuf-style duration (seconds + nanos) to float seconds."""
        if duration is None:
            return 0.0
        seconds = getattr(duration, "seconds", 0) or 0
        nanos = getattr(duration, "nanos", 0) or 0
        return seconds + nanos / 1_000_000_000

    @staticmethod
    def _resolve_speaker_tag(words: list) -> Optional[int]:
        """
        We use the most frequent speaker_tag among word-like objects because within a segment, 
        there may be occasional misattributions or minor fluctuations in speaker tags.
        Selecting the most common tag helps assign the segment to the dominant speaker, 
        improving accuracy and consistency, rather than relying on the first or last tag or splitting the segment.
        Returns None if no word has a speaker_tag.
        """
        if not words:
            return None
        counts: dict[int, int] = {}
        for word in words:
            tag = getattr(word, "speaker_tag", None)
            if tag is None:
                continue
            counts[tag] = counts.get(tag, 0) + 1
        if not counts:
            return None
        return max(counts.items(), key=lambda item: item[1])[0]

    @staticmethod
    def _group_words_by_speaker(words: list) -> list[list]:
        """Group consecutive words by speaker_tag so each segment has one speaker."""
        if not words:
            return []
        groups: list[list] = []
        current: list = []
        current_tag = None
        for w in words:
            tag = getattr(w, "speaker_tag", None)
            if current and tag != current_tag:
                groups.append(current)
                current = []
            current.append(w)
            current_tag = tag
        if current:
            groups.append(current)
        return groups

    async def build_segments_from_result(
        self,
        result: Any,
        d: Any,
        stream_base: int,
    ) -> tuple[list[SttSegment], Optional[list], Optional[list]]:
        """
        Build list of segments from one StreamingRecognize result.

        Returns:
            (segments_to_send, diarization_script_intervals, timeline_snapshot).
        """
        from app.settings import settings

        # "alternatives" is a list of possible recognition results provided by the STT API, 
        # typically ordered by confidence (best guess first). We pick the top (best) one.
        alternative = result.alternatives[0] if result.alternatives else None
        if not alternative:
            return [], None, None
        text = (alternative.transcript or "").strip()
        if not text:
            return [], None, None
        words = list(getattr(alternative, "words", []))
        # We do not use Google speaker_tag; NeMo timeline is the only diarization source.
        speaker_tag: Optional[int] = None

        segments_to_send: list[SttSegment] = []
        diarization_script_intervals: Optional[list] = None
        timeline_snapshot: Optional[list] = None

        # Prefer NeMo timeline segmentation when available (result.is_final and we have timeline).
        if result.is_final and text and d.ctx.speaker_timeline:
            max_end_s = max(
                0.0,
                (d.ring_buffer.total_samples - stream_base) / self.sample_rate_hz,
            )
            lag_ms = getattr(settings, "stt_diarization_reliable_lag_ms", 1000)
            async with d.ctx.timeline_lock:
                timeline_snapshot = list(d.ctx.speaker_timeline)
            nemo_snapshot = (
                d.ctx.nemo_latest_segments if d.ctx.nemo_latest_segments else None
            )
            sub_spans, intervals = derive_and_segment(
                stream_base,
                d.ring_buffer.total_samples,
                max_end_s,
                timeline_snapshot,
                nemo_snapshot,
                lag_ms=lag_ms,
            )
            if sub_spans and intervals:
                diarization_script_intervals = intervals
                for text_chunk, start_s, end_s in assign_text_to_sub_spans(
                    text, sub_spans
                ):
                    segments_to_send.append(
                        SttSegment(
                            text=text_chunk,
                            words=[],
                            speaker_tag=None,
                            raw_start_s=start_s,
                            raw_end_s=end_s,
                            from_diarization=True,
                        )
                    )

        # Fallback: single segment from transcript (no grouping by Google speaker_tag).
        if not segments_to_send:
            if result.is_final and words:
                segments_to_send.append(
                    SttSegment(
                        text=text,
                        words=words,
                        speaker_tag=None,
                        raw_start_s=self._duration_to_seconds(words[0].start_offset),
                        raw_end_s=self._duration_to_seconds(words[-1].end_offset),
                        from_diarization=False,
                    )
                )
            else:
                segments_to_send.append(
                    SttSegment(
                        text=text,
                        words=words,
                        speaker_tag=None,
                        raw_start_s=None,
                        raw_end_s=None,
                        from_diarization=False,
                    )
                )

        return segments_to_send, diarization_script_intervals, timeline_snapshot

    def extract_segment_audio(
        self,
        segment: SttSegment,
        ring_buffer: AudioRingBuffer,
        stream_base: int,
        timeline_snapshot: Optional[list],
        diarization_script_intervals: Optional[list],
        result_is_final: bool,
        has_voice_embeddings: bool,
    ) -> tuple[
        Optional[Any],
        Optional[int],
        Optional[int],
        Optional[float],
        Optional[float],
    ]:
        """Extract audio for one STT segment from the ring buffer for embedding or playback.

        Returns:
            (samples, start_sample, end_sample, seg_abs_start_s, seg_abs_end_s); any may be None.
        """
        raw_start_s = segment.raw_start_s
        raw_end_s = segment.raw_end_s
        from_diarization = segment.from_diarization
        seg_text = segment.text
        samples = None
        start_sample: Optional[int] = None
        end_sample: Optional[int] = None
        seg_abs_start_s: Optional[float] = None
        seg_abs_end_s: Optional[float] = None

        if result_is_final and raw_start_s is not None and raw_end_s is not None:
            max_end_s_val = max(
                0.0,
                (ring_buffer.total_samples - stream_base) / self.sample_rate_hz,
            )
            if from_diarization and diarization_script_intervals:
                sub_intervals = intervals_in_sub_span(
                    (raw_start_s, raw_end_s), diarization_script_intervals
                )
                if sub_intervals:
                    start_s = min(a for a, _ in sub_intervals)
                    end_s = max(b for _, b in sub_intervals)
                    if (end_s - start_s) < MIN_SEGMENT_DURATION_S:
                        end_s = min(
                            start_s + MIN_SEGMENT_DURATION_S, max_end_s_val
                        )
                    start_s = max(0.0, start_s)
                    end_s = min(end_s, max_end_s_val)
                else:
                    start_s = max(0.0, raw_start_s - 0.05)
                    end_s = min(raw_end_s + 0.05, max_end_s_val)
            else:
                start_s = max(0.0, raw_start_s - MIN_SEGMENT_DURATION_S)
                end_s = raw_end_s + MIN_SEGMENT_DURATION_S
                min_window_s = 3.0
                if (end_s - start_s) < min_window_s:
                    end_s = start_s + min_window_s
                if end_s > max_end_s_val:
                    end_s = max_end_s_val
            start_sample = stream_base + int(start_s * self.sample_rate_hz)
            end_sample = stream_base + int(end_s * self.sample_rate_hz)
            samples = ring_buffer.slice(start_sample, end_sample)
            seg_abs_start_s = start_sample / float(self.sample_rate_hz)
            seg_abs_end_s = end_sample / float(self.sample_rate_hz)
            if (
                from_diarization
                and timeline_snapshot
                and samples is not None
                and len(samples) > 0
            ):
                segment_pcm = bytes(samples.tobytes())
                clean_pcm = extract_clean_pcm_for_segment(
                    timeline_snapshot,
                    start_sample,
                    end_sample,
                    segment_pcm,
                    sample_rate=self.sample_rate_hz,
                    min_clean_seconds=MIN_SEGMENT_DURATION_S,
                )
                if clean_pcm and len(clean_pcm) >= self.sample_rate_hz:
                    samples = np.frombuffer(clean_pcm, dtype=np.int16)
        elif (
            result_is_final
            and seg_text
            and raw_start_s is None
            and has_voice_embeddings
        ):
            fallback_seconds = 4.0
            max_end_s = max(
                0.0,
                (ring_buffer.total_samples - stream_base) / self.sample_rate_hz,
            )
            end_s = max_end_s
            start_s = max(0.0, end_s - fallback_seconds)
            start_sample = stream_base + int(start_s * self.sample_rate_hz)
            end_sample = stream_base + int(end_s * self.sample_rate_hz)
            samples = ring_buffer.slice(start_sample, end_sample)
            seg_abs_start_s = start_sample / float(self.sample_rate_hz)
            seg_abs_end_s = end_sample / float(self.sample_rate_hz)


        return (samples, start_sample, end_sample, seg_abs_start_s, seg_abs_end_s)
