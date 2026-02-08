from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class EscalationResult:
    severity: str
    reason: str
    message: str


_AGGRESSIVE_PATTERNS = [
    r"\bshut up\b",
    r"\bi hate you\b",
    r"\byou (?:always|never)\b",
    r"\bdivorce\b",
    r"\bkill\b",
    r"\bthreaten\b",
]

_PROFANITY = [
    r"\bfuck\b",
    r"\bshit\b",
    r"\bbitch\b",
    r"\basshole\b",
]


def detect_escalation(text: str) -> EscalationResult | None:
    if not text:
        return None
    lowered = text.lower()
    for pattern in _AGGRESSIVE_PATTERNS:
        if re.search(pattern, lowered):
            return EscalationResult(
                severity="high",
                reason="aggressive_language",
                message="Pause. This is escalating. Try a reset: slow breath, soften tone, and speak needs not blame.",
            )
    for pattern in _PROFANITY:
        if re.search(pattern, lowered):
            return EscalationResult(
                severity="medium",
                reason="profanity",
                message="That language increases heat. Try rephrasing with an 'I feel / I need' statement.",
            )
    return None
