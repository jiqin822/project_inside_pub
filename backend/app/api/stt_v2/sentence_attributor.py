"""Assign a single speaker label to each UI sentence based on timeline coverage."""
from __future__ import annotations

from collections import defaultdict
from typing import Callable, Dict, List, Optional, Tuple

from app.api.stt.audio_processor import AudioProcessor
from app.api.stt_v2.audio_ring_buffer import AudioRingBuffer
from app.api.stt_v2.speaker_timeline_store import SpeakerTimelineStore
from app.domain.stt_v2.contracts import (
    DiarLabel,
    OVERLAP_LABEL,
    UNCERTAIN_LABEL,
    SpeakerSentence,
    StreamId,
    TimeRangeSamples,
    TimeRangeMs,
    UiSentence,
    UiSentenceSegment,
)
from app.domain.voice.embeddings import cosine_similarity
from app.settings import settings


class SentenceSpeakerAttributor:
    def __init__(
        self,
        timeline_store: SpeakerTimelineStore,
        sample_rate: int,
        dominant_sentence_th: float = 0.75,
        overlap_sentence_th: float = 0.20,
        uncertain_sentence_th: float = 0.30,
    ) -> None:
        self.timeline_store = timeline_store
        self.sample_rate = sample_rate
        self.dominant_sentence_th = dominant_sentence_th
        self.overlap_sentence_th = overlap_sentence_th
        self.uncertain_sentence_th = uncertain_sentence_th

    def attribute(
        self, stream_id: StreamId, sentence: UiSentence, debug_enabled: bool = False
    ) -> SpeakerSentence:
        start_sample = int((sentence.range_ms.start_ms * self.sample_rate) / 1000)
        end_sample = int((sentence.range_ms.end_ms * self.sample_rate) / 1000)
        range_samples = TimeRangeSamples(start=start_sample, end=end_sample, sr=self.sample_rate)
        intervals = self.timeline_store.query(stream_id, range_samples)
        # Aggregate per-label coverage over the sentence span.
        coverage: Dict[DiarLabel, int] = defaultdict(int)
        conf_weighted: Dict[DiarLabel, float] = defaultdict(float)
        total = 0
        patched = False
        intervals_debug: List[Dict[str, float | str | bool]] = []

        for span, label, conf, is_patch in intervals:
            span_len = span.end - span.start
            if span_len <= 0:
                continue
            total += span_len
            coverage[label] += span_len
            conf_weighted[label] += conf * span_len
            patched = patched or is_patch
            if debug_enabled:
                intervals_debug.append(
                    {
                        "start_ms": int((span.start * 1000) / span.sr),
                        "end_ms": int((span.end * 1000) / span.sr),
                        "label": label,
                        "conf": float(conf),
                        "is_patch": bool(is_patch),
                    }
                )

        if debug_enabled and intervals_debug:
            intervals_debug = self._merge_debug_intervals(intervals_debug)

        def build_debug(
            decision: str,
            label: DiarLabel,
            label_conf: float,
            coverage_ratio: float,
            overlap_ratio: float,
            uncertain_ratio: float,
            dominant_label: DiarLabel | None,
            dominant_ratio: float,
        ) -> Dict:
            coverage_by_label = []
            if total > 0:
                for entry_label, cov in coverage.items():
                    conf_avg = conf_weighted.get(entry_label, 0.0) / max(1, cov)
                    coverage_by_label.append(
                        {
                            "label": entry_label,
                            "ratio": cov / total,
                            "conf_avg": conf_avg,
                            "duration_ms": int((cov * 1000) / self.sample_rate),
                        }
                    )
                coverage_by_label.sort(key=lambda item: item["ratio"], reverse=True)
            return {
                "decision": decision,
                "label": label,
                "label_conf": label_conf,
                "coverage_ratio": coverage_ratio,
                "overlap_ratio": overlap_ratio,
                "uncertain_ratio": uncertain_ratio,
                "dominant_label": dominant_label,
                "dominant_ratio": dominant_ratio,
                "thresholds": {
                    "overlap": self.overlap_sentence_th,
                    "uncertain": self.uncertain_sentence_th,
                    "dominant": self.dominant_sentence_th,
                },
                "coverage_by_label": coverage_by_label,
                "intervals": intervals_debug,
                "total_ms": int((total * 1000) / self.sample_rate) if total > 0 else 0,
                "patched": patched,
            }

        if total <= 0:
            # No diarization coverage -> mark as UNCERTAIN.
            label = UNCERTAIN_LABEL
            return SpeakerSentence(
                ui_sentence=sentence,
                label=label,
                label_conf=0.0,
                coverage=0.0,
                flags={"overlap": False, "uncertain": True, "patched": patched},
                debug=build_debug(
                    "no_coverage",
                    label,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    None,
                    0.0,
                )
                if debug_enabled
                else None,
            )

        overlap_ratio = coverage.get(OVERLAP_LABEL, 0) / total
        uncertain_ratio = coverage.get(UNCERTAIN_LABEL, 0) / total

        if overlap_ratio >= self.overlap_sentence_th:
            # If overlap dominates, emit OVERLAP for this sentence.
            label = OVERLAP_LABEL
            label_conf = conf_weighted.get(label, 0.0) / max(1, coverage.get(label, 1))
            return SpeakerSentence(
                ui_sentence=sentence,
                label=label,
                label_conf=label_conf,
                coverage=overlap_ratio,
                flags={"overlap": True, "uncertain": False, "patched": patched},
                debug=build_debug(
                    "overlap",
                    label,
                    label_conf,
                    overlap_ratio,
                    overlap_ratio,
                    uncertain_ratio,
                    None,
                    0.0,
                )
                if debug_enabled
                else None,
            )

        if uncertain_ratio >= self.uncertain_sentence_th:
            # If uncertain dominates, emit UNCERTAIN for this sentence.
            label = UNCERTAIN_LABEL
            label_conf = conf_weighted.get(label, 0.0) / max(1, coverage.get(label, 1))
            return SpeakerSentence(
                ui_sentence=sentence,
                label=label,
                label_conf=label_conf,
                coverage=uncertain_ratio,
                flags={"overlap": False, "uncertain": True, "patched": patched},
                debug=build_debug(
                    "uncertain_ratio",
                    label,
                    label_conf,
                    uncertain_ratio,
                    overlap_ratio,
                    uncertain_ratio,
                    None,
                    0.0,
                )
                if debug_enabled
                else None,
            )

        # Dominant speaker (excluding overlap/uncertain) drives the final label.
        dominant_label, dominant_coverage = self._dominant_label(coverage)
        dominant_ratio = dominant_coverage / total if total > 0 else 0.0
        if dominant_ratio < self.dominant_sentence_th:
            # Dominant label is too weak -> fall back to UNCERTAIN.
            label = UNCERTAIN_LABEL
            label_conf = conf_weighted.get(label, 0.0) / max(1, coverage.get(label, 1))
            return SpeakerSentence(
                ui_sentence=sentence,
                label=label,
                label_conf=label_conf,
                coverage=dominant_ratio,
                flags={"overlap": False, "uncertain": True, "patched": patched},
                debug=build_debug(
                    "low_dominant",
                    label,
                    label_conf,
                    dominant_ratio,
                    overlap_ratio,
                    uncertain_ratio,
                    dominant_label,
                    dominant_ratio,
                )
                if debug_enabled
                else None,
            )

        label = dominant_label or UNCERTAIN_LABEL
        label_conf = conf_weighted.get(label, 0.0) / max(1, coverage.get(label, 1))
        return SpeakerSentence(
            ui_sentence=sentence,
            label=label,
            label_conf=label_conf,
            coverage=dominant_ratio,
            flags={"overlap": False, "uncertain": False, "patched": patched},
            debug=build_debug(
                "dominant",
                label,
                label_conf,
                dominant_ratio,
                overlap_ratio,
                uncertain_ratio,
                dominant_label,
                dominant_ratio,
            )
            if debug_enabled
            else None,
        )

    @staticmethod
    def _merge_debug_intervals(
        intervals: List[Dict[str, float | str | bool]],
        max_gap_ms: int = 100,
    ) -> List[Dict[str, float | str | bool]]:
        if not intervals:
            return []
        ordered = sorted(intervals, key=lambda item: (item.get("start_ms", 0), item.get("end_ms", 0)))
        merged: List[Dict[str, float | str | bool]] = []
        for interval in ordered:
            if not merged:
                merged.append(dict(interval))
                continue
            last = merged[-1]
            if (
                interval.get("label") == last.get("label")
                and interval.get("is_patch") == last.get("is_patch")
            ):
                gap = (interval.get("start_ms", 0) or 0) - (last.get("end_ms", 0) or 0)
                if gap <= max_gap_ms:
                    last_start = last.get("start_ms", 0) or 0
                    last_end = last.get("end_ms", 0) or 0
                    next_start = interval.get("start_ms", 0) or 0
                    next_end = interval.get("end_ms", 0) or 0
                    last_dur = max(0, last_end - last_start)
                    next_dur = max(0, next_end - next_start)
                    total_dur = last_dur + next_dur
                    if total_dur > 0:
                        last_conf = float(last.get("conf", 0.0) or 0.0)
                        next_conf = float(interval.get("conf", 0.0) or 0.0)
                        last["conf"] = (last_conf * last_dur + next_conf * next_dur) / total_dur
                    last["end_ms"] = max(last_end, next_end)
                    last["start_ms"] = min(last_start, next_start)
                    continue
            merged.append(dict(interval))
        return merged

    def attribute_with_speaker_change(
        self,
        stream_id: StreamId,
        sentence: UiSentence,
        ring_buffer: AudioRingBuffer,
        audio_processor: AudioProcessor,
        *,
        debug_enabled: bool = False,
        min_side_ms: int = 400,
        similarity_th: Optional[float] = None,
        embedding_provider: Optional[Callable[[bytes], Optional[list[float]]]] = None,
    ) -> List[SpeakerSentence]:
        if not sentence.segments or len(sentence.segments) < 2:
            return [self.attribute(stream_id, sentence, debug_enabled=debug_enabled)]

        # Attempt to split long/compound sentences if diarization indicates a label change.
        boundary_ms = self._find_label_boundary(stream_id, sentence, min_side_ms)
        if boundary_ms is None:
            return [self.attribute(stream_id, sentence, debug_enabled=debug_enabled)]

        split = self._split_sentence_at_boundary(sentence, boundary_ms, debug_enabled)
        if split is None:
            return [self.attribute(stream_id, sentence, debug_enabled=debug_enabled)]
        left_sentence, right_sentence = split

        left_audio = self._read_audio_bytes(stream_id, left_sentence.range_ms, ring_buffer)
        right_audio = self._read_audio_bytes(stream_id, right_sentence.range_ms, ring_buffer)
        if not left_audio or not right_audio:
            return [self.attribute(stream_id, sentence, debug_enabled=debug_enabled)]

        left_emb = self._compute_embedding(
            left_audio, audio_processor, embedding_provider
        )
        right_emb = self._compute_embedding(
            right_audio, audio_processor, embedding_provider
        )
        if not left_emb or not right_emb:
            return [self.attribute(stream_id, sentence, debug_enabled=debug_enabled)]

        threshold = (
            similarity_th
            if similarity_th is not None
            else settings.stt_speaker_match_threshold
        )
        similarity = cosine_similarity(left_emb, right_emb)
        if similarity >= threshold:
            # Same speaker embedding -> keep as a single sentence.
            return [self.attribute(stream_id, sentence, debug_enabled=debug_enabled)]

        # Different embeddings -> treat as a speaker change and attribute both halves.
        return [
            self.attribute(stream_id, left_sentence, debug_enabled=debug_enabled),
            self.attribute(stream_id, right_sentence, debug_enabled=debug_enabled),
        ]

    def _find_label_boundary(
        self, stream_id: StreamId, sentence: UiSentence, min_side_ms: int
    ) -> Optional[int]:
        start_sample = int((sentence.range_ms.start_ms * self.sample_rate) / 1000)
        end_sample = int((sentence.range_ms.end_ms * self.sample_rate) / 1000)
        range_samples = TimeRangeSamples(
            start=start_sample, end=end_sample, sr=self.sample_rate
        )
        intervals = self.timeline_store.query(stream_id, range_samples)
        if len(intervals) < 2:
            return None

        best_boundary_ms: Optional[int] = None
        best_score = -1.0
        for left, right in zip(intervals, intervals[1:]):
            left_span, left_label, left_conf, _ = left
            right_span, right_label, right_conf, _ = right
            if left_label in (OVERLAP_LABEL, UNCERTAIN_LABEL):
                continue
            if right_label in (OVERLAP_LABEL, UNCERTAIN_LABEL):
                continue
            if left_label == right_label:
                continue
            # Candidate boundary is a confident label change with enough room on each side.
            boundary_ms = int((left_span.end * 1000) / left_span.sr)
            if boundary_ms - sentence.range_ms.start_ms < min_side_ms:
                continue
            if sentence.range_ms.end_ms - boundary_ms < min_side_ms:
                continue
            score = min(left_conf, right_conf)
            if score > best_score:
                best_score = score
                best_boundary_ms = boundary_ms
        return best_boundary_ms

    def _split_sentence_at_boundary(
        self, sentence: UiSentence, boundary_ms: int, debug_enabled: bool
    ) -> Optional[Tuple[UiSentence, UiSentence]]:
        segments = sentence.segments or []
        split_idx = None
        for idx, seg in enumerate(segments[:-1]):
            if seg.range_ms.end_ms <= boundary_ms:
                split_idx = idx
        if split_idx is None or split_idx >= len(segments) - 1:
            return None
        left_segments = segments[: split_idx + 1]
        right_segments = segments[split_idx + 1 :]
        left_text = self._join_segment_text(left_segments)
        right_text = self._join_segment_text(right_segments)
        if not left_text or not right_text:
            return None

        left_range = TimeRangeMs(
            start_ms=left_segments[0].range_ms.start_ms,
            end_ms=left_segments[-1].range_ms.end_ms,
        )
        right_range = TimeRangeMs(
            start_ms=right_segments[0].range_ms.start_ms,
            end_ms=right_segments[-1].range_ms.end_ms,
        )
        left_debug = self._split_debug(sentence.debug, boundary_ms, "left", debug_enabled)
        right_debug = self._split_debug(sentence.debug, boundary_ms, "right", debug_enabled)
        left_sentence = UiSentence(
            id=f"{sentence.id}_a",
            range_ms=left_range,
            text=left_text,
            is_final=sentence.is_final,
            segments=left_segments,
            debug=left_debug,
        )
        right_sentence = UiSentence(
            id=f"{sentence.id}_b",
            range_ms=right_range,
            text=right_text,
            is_final=sentence.is_final,
            segments=right_segments,
            debug=right_debug,
        )
        return left_sentence, right_sentence

    @staticmethod
    def _join_segment_text(segments: List[UiSentenceSegment]) -> str:
        parts = [seg.text.strip() for seg in segments if seg.text.strip()]
        return " ".join(parts).strip()

    @staticmethod
    def _split_debug(
        debug: Optional[Dict], boundary_ms: int, side: str, debug_enabled: bool
    ) -> Optional[Dict]:
        if not debug_enabled:
            return debug
        payload = dict(debug or {})
        payload["speaker_change_split"] = {"boundary_ms": boundary_ms, "side": side}
        return payload

    def _read_audio_bytes(
        self,
        stream_id: StreamId,
        range_ms: TimeRangeMs,
        ring_buffer: AudioRingBuffer,
    ) -> Optional[bytes]:
        start_sample = int((range_ms.start_ms * self.sample_rate) / 1000)
        end_sample = int((range_ms.end_ms * self.sample_rate) / 1000)
        if end_sample <= start_sample:
            return None
        samples = ring_buffer.read(
            stream_id,
            TimeRangeSamples(start=start_sample, end=end_sample, sr=self.sample_rate),
        )
        if samples is None or len(samples) == 0:
            return None
        return samples.tobytes()

    @staticmethod
    def _compute_embedding(
        pcm_bytes: bytes,
        audio_processor: AudioProcessor,
        embedding_provider: Optional[Callable[[bytes], Optional[list[float]]]] = None,
    ) -> Optional[list[float]]:
        if embedding_provider is not None:
            return embedding_provider(pcm_bytes)
        return audio_processor.compute_embedding_sync(pcm_bytes)

    @staticmethod
    def _dominant_label(coverage: Dict[DiarLabel, int]) -> Tuple[DiarLabel | None, int]:
        best_label = None
        best_coverage = 0
        for label, cov in coverage.items():
            if label in (OVERLAP_LABEL, UNCERTAIN_LABEL):
                continue
            if cov > best_coverage:
                best_label = label
                best_coverage = cov
        return best_label, best_coverage
