"""Coach engine for generating safe nudges from speaker sentences."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.domain.stt_v2.contracts import SpeakerSentence


@dataclass(frozen=True)
class NudgeEvent:
    type: str
    label: str | None
    text: str


class CoachEngine:
    def __init__(
        self,
        dominant_sentence_th: float = 0.75,
        min_nudge_sentence_ms: int = 800,
    ) -> None:
        self.dominant_sentence_th = dominant_sentence_th
        self.min_nudge_sentence_ms = min_nudge_sentence_ms

    def on_speaker_sentence(self, ss: SpeakerSentence) -> List[NudgeEvent]:
        duration_ms = ss.ui_sentence.range_ms.duration_ms
        if (
            (ss.label.startswith("spk") or ss.flags.get("voice_id", False))
            and ss.coverage >= self.dominant_sentence_th
            and not ss.flags.get("overlap", False)
            and not ss.flags.get("uncertain", False)
            and duration_ms >= self.min_nudge_sentence_ms
        ):
            # Placeholder: actual nudge generation is external.
            return []
        return []
