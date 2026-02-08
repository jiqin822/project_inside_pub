"""Assemble UI sentences from STT segments and pause events."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from app.domain.stt_v2.contracts import (
    PauseEvent,
    SttSegment,
    StreamId,
    TimeRangeMs,
    UiSentence,
    UiSentenceSegment,
)


@dataclass
class _SentenceState:
    current_text: str = ""
    start_ms: int | None = None
    end_ms: int | None = None
    sentence_counter: int = 0
    debug_enabled: bool = False
    debug_segments: List[Dict[str, Any]] = field(default_factory=list)
    segments: List[UiSentenceSegment] = field(default_factory=list)


class SentenceAssembler:
    def __init__(
        self,
        sample_rate: int,
        pause_split_ms: int = 600,
        max_sentence_ms: int = 8000,
        max_chars: int = 220,
        min_chars: int = 12,
        stt_jitter_buffer_ms: int = 300,
    ) -> None:
        self.sample_rate = sample_rate
        self.pause_split_ms = pause_split_ms
        self.max_sentence_ms = max_sentence_ms
        self.max_chars = max_chars
        self.min_chars = min_chars
        self.stt_jitter_buffer_ms = stt_jitter_buffer_ms
        self._states: Dict[StreamId, _SentenceState] = {}

    def _state(self, stream_id: StreamId) -> _SentenceState:
        if stream_id not in self._states:
            self._states[stream_id] = _SentenceState()
        return self._states[stream_id]

    def set_debug(self, stream_id: StreamId, enabled: bool) -> None:
        state = self._state(stream_id)
        state.debug_enabled = bool(enabled)
        if not state.debug_enabled:
            state.debug_segments = []

    def on_stt_segment(self, stream_id: StreamId, seg: SttSegment) -> List[UiSentence]:
        state = self._state(stream_id)
        output: List[UiSentence] = []

        if not seg.text:
            return output

        if state.start_ms is None:
            state.start_ms = seg.range_ms.start_ms
        if state.current_text and not state.current_text.endswith(" "):
            state.current_text += " "
        state.current_text += seg.text.strip()
        state.end_ms = seg.range_ms.end_ms

        if state.debug_enabled:
            state.debug_segments.append(
                {
                    "start_ms": seg.range_ms.start_ms,
                    "end_ms": seg.range_ms.end_ms,
                    "text": seg.text,
                    "conf": seg.stt_conf,
                    "is_final": seg.is_final,
                }
            )
        state.segments.append(
            UiSentenceSegment(
                range_ms=seg.range_ms,
                text=seg.text,
                stt_conf=seg.stt_conf,
                is_final=seg.is_final,
            )
        )

        if self._ends_with_strong_punct(seg.text) and len(state.current_text) >= self.min_chars:
            output.append(
                self._finalize(
                    stream_id,
                    reason="punctuation",
                    reason_data={
                        "punct": self._terminal_punct(seg.text),
                        "min_chars": self.min_chars,
                    },
                )
            )
            return output

        # Soft punctuation (comma, semicolon, colon) → break more aggressively when enough text
        min_chars_soft = max(4, self.min_chars - 1)
        if self._ends_with_soft_punct(seg.text) and len(state.current_text) >= min_chars_soft:
            output.append(
                self._finalize(
                    stream_id,
                    reason="soft_punctuation",
                    reason_data={
                        "punct": self._soft_punct(seg.text),
                        "min_chars_soft": min_chars_soft,
                    },
                )
            )
            return output

        if state.start_ms is not None and state.end_ms is not None:
            if (state.end_ms - state.start_ms) >= self.max_sentence_ms:
                output.append(
                    self._finalize(
                        stream_id,
                        reason="max_duration",
                        reason_data={
                            "max_sentence_ms": self.max_sentence_ms,
                            "duration_ms": state.end_ms - state.start_ms,
                        },
                    )
                )
                return output

        if len(state.current_text) >= self.max_chars:
            head, tail = self._split_at_best_boundary(state.current_text)
            debug_segments = list(state.debug_segments) if state.debug_enabled else None
            if head:
                output.append(
                    self._finalize(
                        stream_id,
                        override_text=head,
                        reason="max_chars",
                        reason_data={
                            "max_chars": self.max_chars,
                            "current_chars": len(state.current_text),
                            "split_head_chars": len(head),
                            "split_tail_chars": len(tail),
                        },
                        debug_segments_override=debug_segments,
                        segments_override=[],
                    )
                )
            if tail:
                state.current_text = tail
                state.start_ms = seg.range_ms.start_ms
                state.end_ms = seg.range_ms.end_ms
                state.segments = []
                if state.debug_enabled and debug_segments is not None:
                    state.debug_segments = debug_segments
        return output

    def on_pause_event(self, stream_id: StreamId, pause: PauseEvent) -> List[UiSentence]:
        if pause.pause_ms < self.pause_split_ms:
            return []
        state = self._state(stream_id)
        if not state.current_text or len(state.current_text) < self.min_chars:
            return []
        pause_start_ms = int((pause.range_samples.start * 1000) / pause.range_samples.sr)
        state.end_ms = pause_start_ms
        return [
            self._finalize(
                stream_id,
                reason="pause",
                reason_data={
                    "pause_ms": pause.pause_ms,
                    "pause_conf": pause.conf,
                    "pause_split_ms": self.pause_split_ms,
                    "pause_start_ms": pause_start_ms,
                    "pause_end_ms": int((pause.range_samples.end * 1000) / pause.range_samples.sr),
                },
            )
        ]

    def _finalize(
        self,
        stream_id: StreamId,
        override_text: str | None = None,
        reason: str | None = None,
        reason_data: Dict[str, Any] | None = None,
        debug_segments_override: List[Dict[str, Any]] | None = None,
        segments_override: List[UiSentenceSegment] | None = None,
    ) -> UiSentence:
        state = self._state(stream_id)
        text = (override_text or state.current_text).strip()
        if state.start_ms is None:
            start_ms = 0
        else:
            start_ms = state.start_ms
        end_ms = state.end_ms or start_ms
        debug = None
        if state.debug_enabled:
            segments = debug_segments_override or state.debug_segments
            debug = {
                "policy": reason or "unknown",
                "details": reason_data or {},
                "start_ms": start_ms,
                "end_ms": end_ms,
                "duration_ms": max(0, end_ms - start_ms),
                "text_len": len(text),
                "segments": segments,
            }
        state.sentence_counter += 1
        sentence_id = f"sent_{state.sentence_counter}"
        segments = segments_override if segments_override is not None else list(state.segments)
        ui_sentence = UiSentence(
            id=sentence_id,
            range_ms=TimeRangeMs(start_ms=start_ms, end_ms=end_ms),
            text=text,
            is_final=True,
            segments=segments or None,
            debug=debug,
        )
        state.current_text = ""
        state.start_ms = None
        state.end_ms = None
        state.segments = []
        if state.debug_enabled:
            state.debug_segments = []
        return ui_sentence

    @staticmethod
    def _ends_with_strong_punct(text: str) -> bool:
        return text.strip().endswith((".", "!", "?"))

    @staticmethod
    def _terminal_punct(text: str) -> str | None:
        stripped = text.strip()
        if not stripped:
            return None
        last = stripped[-1]
        if last in (".", "!", "?"):
            return last
        return None

    @staticmethod
    def _ends_with_soft_punct(text: str) -> bool:
        return text.strip().endswith((",", ";", ":"))

    @staticmethod
    def _soft_punct(text: str) -> str | None:
        stripped = text.strip()
        if not stripped:
            return None
        last = stripped[-1]
        if last in (",", ";", ":"):
            return last
        return None

    @staticmethod
    def _split_at_best_boundary(text: str) -> Tuple[str, str]:
        # Prefer soft punctuation, then whitespace nearest to target.
        for punct in [",", ";", ":"]:
            idx = text.rfind(punct, 0, len(text))
            if idx != -1 and idx + 1 < len(text):
                return text[: idx + 1].strip(), text[idx + 1 :].strip()
        # Fallback: nearest whitespace to the max length.
        idx = text.rfind(" ")
        if idx != -1:
            return text[:idx].strip(), text[idx + 1 :].strip()
        return text.strip(), ""
