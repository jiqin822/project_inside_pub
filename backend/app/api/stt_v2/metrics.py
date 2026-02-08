"""Lightweight per-stream metrics collector for STT V2."""
from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass
class MetricsCollector:
    start_ts: float = field(default_factory=time.time)
    sentence_count: int = 0
    sentence_total_ms: int = 0
    coverage_sum: float = 0.0
    switch_count: int = 0
    last_label: str | None = None
    uncertain_count: int = 0
    overlap_count: int = 0
    patch_count: int = 0
    patch_sentence_updates: int = 0
    sentence_len_bins_ms: tuple[int, ...] = (250, 500, 1000, 2000, 4000, 8000, 12000)
    sentence_len_hist: dict[str, int] = field(default_factory=dict)

    def record_sentence(self, speaker_sentence) -> None:
        self.sentence_count += 1
        sentence_ms = speaker_sentence.ui_sentence.range_ms.duration_ms
        self.sentence_total_ms += sentence_ms
        self.coverage_sum += speaker_sentence.coverage
        if self.last_label is not None and speaker_sentence.label != self.last_label:
            self.switch_count += 1
        self.last_label = speaker_sentence.label
        if speaker_sentence.flags.get("uncertain", False):
            self.uncertain_count += 1
        if speaker_sentence.flags.get("overlap", False):
            self.overlap_count += 1
        self._record_sentence_len(sentence_ms)

    def record_patch(self, updated_sentence_count: int) -> None:
        self.patch_count += 1
        self.patch_sentence_updates += updated_sentence_count

    def _record_sentence_len(self, duration_ms: int) -> None:
        bucket = self._bucket_label(duration_ms)
        self.sentence_len_hist[bucket] = self.sentence_len_hist.get(bucket, 0) + 1

    def _bucket_label(self, duration_ms: int) -> str:
        for upper in self.sentence_len_bins_ms:
            if duration_ms <= upper:
                return f"<= {upper}ms"
        return f"> {self.sentence_len_bins_ms[-1]}ms"

    def snapshot(self) -> dict:
        elapsed_minutes = max(1e-6, (time.time() - self.start_ts) / 60)
        avg_sentence_ms = (
            self.sentence_total_ms / self.sentence_count
            if self.sentence_count
            else 0.0
        )
        avg_coverage = (
            self.coverage_sum / self.sentence_count
            if self.sentence_count
            else 0.0
        )
        return {
            "switch_rate_per_min": self.switch_count / elapsed_minutes,
            "uncertain_ratio": self.uncertain_count / self.sentence_count if self.sentence_count else 0.0,
            "overlap_ratio": self.overlap_count / self.sentence_count if self.sentence_count else 0.0,
            "avg_coverage": avg_coverage,
            "avg_sentence_ms": avg_sentence_ms,
            "sentence_len_hist": dict(self.sentence_len_hist),
            "patch_rate_per_min": self.patch_count / elapsed_minutes,
            "patch_sentence_updates": self.patch_sentence_updates,
        }
