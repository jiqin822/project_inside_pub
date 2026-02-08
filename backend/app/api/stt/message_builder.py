"""
WebSocket message payload builders for STT stream (transcript, speaker_resolved, escalation).
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import WebSocket

from app.domain.stt.anonymous_name import speaker_display_name
from app.domain.stt.speaker_timeline_attribution import OVERLAP_LABEL, UNCERTAIN_LABEL

from app.api.stt.constants import (
    MSG_STT_ESCALATION,
    MSG_STT_SPEAKER_RESOLVED,
    SPEAKER_SOURCE_NONE,
)
from app.settings import settings


def _safe_label_debug_info(label: Optional[str]) -> dict:
    if not label:
        return {"kind": "empty"}
    if label in (OVERLAP_LABEL, UNCERTAIN_LABEL):
        return {"kind": "special", "label": label}
    if label.startswith("Unknown_"):
        suffix = label[len("Unknown_"):]
        if suffix.isdigit():
            return {"kind": "unknown_n", "n": int(suffix)}
        return {"kind": "unknown_pref", "suffix": suffix[:32]}
    if label.startswith("Anon_") or label.startswith("ANON_"):
        suffix = label.split("_", 1)[1] if "_" in label else ""
        if suffix.isdigit():
            return {"kind": "anon_n", "n": int(suffix)}
        return {"kind": "anon_pref", "suffix": suffix[:32]}
    return {"kind": "other", "len": len(label)}


class MessageBuilder:
    """Builds WebSocket message payloads for STT transcript, speaker_resolved, and escalation."""

    def build_transcript_payload(
        self,
        session_id: str,
        *,
        seg_text: str,
        speaker_label: str,
        seg_tag: Optional[int],
        is_final: bool,
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
        confidence: Optional[float] = None,
        segment_id: Optional[int] = None,
        audio_segment_base64: Optional[str] = None,
        speaker_source: str = SPEAKER_SOURCE_NONE,
        nemo_speaker_id: Optional[str] = None,
    ) -> dict:
        """Build the stt.transcript WebSocket message payload.

        Maps internal speaker_label to display name (e.g. Unknown_1, user id) except for
        OVERLAP_LABEL/UNCERTAIN_LABEL which are sent as-is when is_final. Includes
        optional timing, confidence, base64 audio (final only), and attribution fields.
        """
        if is_final and speaker_label in (OVERLAP_LABEL, UNCERTAIN_LABEL):
            display_label = speaker_label
        else:
            display_label = speaker_display_name(
                session_id, speaker_label, nemo_speaker_id=nemo_speaker_id
            )
        payload = {
            "type": "stt.transcript",
            "text": seg_text,
            "speaker_label": display_label,
            "speaker_tag": seg_tag,
            "is_final": is_final,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "confidence": confidence,
            "audio_segment_base64": audio_segment_base64 if is_final else None,
            "best_score_pct": None,
            "second_score_pct": None,
            "score_margin_pct": None,
            "best_user_suffix": None,
            "second_user_suffix": None,
            "speaker_source": speaker_source,
            "nemo_speaker_id": nemo_speaker_id,
            "speaker_label_before": None,
            "speaker_label_after": None,
            "speaker_change_at_ms": None,
            "speaker_change_word_index": None,
        }
        if is_final and segment_id is not None:
            payload["segment_id"] = segment_id
            payload["bubble_id"] = str(segment_id)
        return payload

    def build_speaker_resolved_payload(
        self,
        session_id: str,
        *,
        segment_id: int,
        speaker_label: str,
        speaker_source: str,
        confidence: Optional[float] = None,
        is_overlap: bool = False,
        attribution_source: Optional[str] = None,
        best_score_pct: Optional[float] = None,
        second_score_pct: Optional[float] = None,
        score_margin_pct: Optional[float] = None,
        best_user_suffix: Optional[str] = None,
        second_user_suffix: Optional[str] = None,
        all_scores: Optional[list] = None,
        nemo_speaker_id: Optional[str] = None,
        speaker_label_before: Optional[str] = None,
        speaker_label_after: Optional[str] = None,
        speaker_change_at_ms: Optional[int] = None,
        speaker_change_word_index: Optional[int] = None,
    ) -> dict:
        """Build the stt.speaker_resolved WebSocket message payload.

        Used when a segment's speaker is resolved (voice-id match, timeline, or NeMo).
        Preserves OVERLAP_LABEL/UNCERTAIN_LABEL as display; otherwise maps to session
        display name.
        """
        display_label = speaker_label
        if speaker_label not in (OVERLAP_LABEL, UNCERTAIN_LABEL):
            display_label = speaker_display_name(
                session_id, speaker_label, nemo_speaker_id=nemo_speaker_id
            )
        return {
            "type": MSG_STT_SPEAKER_RESOLVED,
            "segment_id": segment_id,
            "bubble_id": str(segment_id),
            "speaker_label": display_label,
            "confidence": round(confidence, 3) if confidence is not None else None,
            "is_overlap": is_overlap,
            "attribution_source": attribution_source,
            "best_score_pct": best_score_pct,
            "second_score_pct": second_score_pct,
            "score_margin_pct": score_margin_pct,
            "best_user_suffix": best_user_suffix,
            "second_user_suffix": second_user_suffix,
            "all_scores": all_scores or [],
            "speaker_source": speaker_source,
            "nemo_speaker_id": nemo_speaker_id,
            "speaker_label_before": speaker_label_before,
            "speaker_label_after": speaker_label_after,
            "speaker_change_at_ms": speaker_change_at_ms,
            "speaker_change_word_index": speaker_change_word_index,
        }

    async def send_escalation_if_allowed(
        self,
        escalation: Any,
        websocket: WebSocket,
        last_escalation_at_ref: list[float],
    ) -> None:
        """Send escalation to client only if cooldown has elapsed.

        Updates last_escalation_at_ref[0] and sends a single stt.escalation message.
        """
        import asyncio

        now = asyncio.get_event_loop().time()
        if now - last_escalation_at_ref[0] >= settings.stt_escalation_cooldown_seconds:
            last_escalation_at_ref[0] = now
            await websocket.send_json({
                "type": MSG_STT_ESCALATION,
                "severity": escalation.severity,
                "reason": escalation.reason,
                "message": escalation.message,
            })
