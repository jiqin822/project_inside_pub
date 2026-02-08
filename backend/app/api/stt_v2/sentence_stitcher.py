"""Merge adjacent speaker sentences when safe to reduce fragmentation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from app.domain.stt_v2.contracts import SpeakerSentence, StreamId, TimeRangeMs, UiSentence


@dataclass
class _StitchState:
    last_sentence: SpeakerSentence | None = None


class SentenceStitcher:
    def __init__(self, stitch_gap_ms: int = 300, max_stitched_ms: int = 9000) -> None:
        self.stitch_gap_ms = stitch_gap_ms
        self.max_stitched_ms = max_stitched_ms
        self._states: Dict[StreamId, _StitchState] = {}

    def _state(self, stream_id: StreamId) -> _StitchState:
        if stream_id not in self._states:
            self._states[stream_id] = _StitchState()
        return self._states[stream_id]

    def on_speaker_sentence(self, stream_id: StreamId, ss: SpeakerSentence) -> List[SpeakerSentence]:
        state = self._state(stream_id)
        if state.last_sentence is None:
            state.last_sentence = ss
            return []

        prev = state.last_sentence
        gap = ss.ui_sentence.range_ms.start_ms - prev.ui_sentence.range_ms.end_ms
        merged_duration = ss.ui_sentence.range_ms.end_ms - prev.ui_sentence.range_ms.start_ms
        if (
            prev.label == ss.label
            and gap >= 0
            and gap <= self.stitch_gap_ms
            and merged_duration <= self.max_stitched_ms
        ):
            merged_text = f"{prev.ui_sentence.text} {ss.ui_sentence.text}".strip()
            merged_range = TimeRangeMs(
                start_ms=prev.ui_sentence.range_ms.start_ms,
                end_ms=ss.ui_sentence.range_ms.end_ms,
            )
            merged_debug = None
            if prev.ui_sentence.debug or ss.ui_sentence.debug:
                parts = [part for part in [prev.ui_sentence.debug, ss.ui_sentence.debug] if part]
                merged_debug = {
                    "merged": True,
                    "parts": parts,
                    "start_ms": merged_range.start_ms,
                    "end_ms": merged_range.end_ms,
                    "duration_ms": max(0, merged_range.end_ms - merged_range.start_ms),
                    "text_len": len(merged_text),
                }
            merged_ui = UiSentence(
                id=prev.ui_sentence.id,
                range_ms=merged_range,
                text=merged_text,
                is_final=True,
                debug=merged_debug,
            )
            merged_ss = SpeakerSentence(
                ui_sentence=merged_ui,
                label=prev.label,
                label_conf=max(prev.label_conf, ss.label_conf),
                coverage=min(1.0, (prev.coverage + ss.coverage) / 2),
                flags=prev.flags,
                audio_segment_base64=None,
                debug=prev.debug,
            )
            state.last_sentence = merged_ss
            return []

        # Emit previous and store current.
        output = [prev]
        state.last_sentence = ss
        return output

    def flush(self, stream_id: StreamId) -> List[SpeakerSentence]:
        state = self._state(stream_id)
        if state.last_sentence is None:
            return []
        last = state.last_sentence
        state.last_sentence = None
        return [last]
