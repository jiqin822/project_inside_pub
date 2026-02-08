"""Live Coach: analyze a single turn (transcript) for sentiment, horseman, level, nudge, rephrasing."""
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_llm_service
from app.domain.admin.models import User
from app.services.llm_service import LLMRateLimitError, LLMService

logger = logging.getLogger(__name__)

router = APIRouter()


class HistoryTurn(BaseModel):
    """A single turn in recent conversation history."""
    speaker: str
    transcript: str


class AnalyzeTurnRequest(BaseModel):
    """Request body for POST /analyze-turn."""
    transcript: str = Field(..., description="Current turn transcript to analyze.")
    speaker: Optional[str] = Field(None, description="Detected speaker for the current turn (e.g. from STT).")
    segment_id: Optional[str] = Field(None, description="Client segment id for merging.")
    include_history: bool = Field(False, description="When true, send history for context.")
    history: Optional[list[HistoryTurn]] = Field(
        None,
        description="Recent turns (speaker, transcript). Used when include_history is true.",
    )
    debug: bool = Field(False, description="When true, include debug_prompt in response for debug UI.")


class AnalyzeTurnResponse(BaseModel):
    """Response: same schema as reportAnalysis + latency_ms."""
    sentiment: str  # Positive | Neutral | Negative | Hostile
    horseman: str  # None | Criticism | Contempt | Defensiveness | Stonewalling
    level: int  # -5 to 5
    nudgeText: Optional[str] = None
    suggestedRephrasing: Optional[str] = None
    latency_ms: int
    debug_prompt: Optional[str] = None  # LLM prompt when request.debug is True (for debug UI)


SYSTEM_PROMPT = """You are a communication coach, Kai. Figure out what is going on in the conversation. Analyze the **current turn** using the **recent turns** for context, and return **valid JSON only** (no markdown, no extra text).

Goal: **Don’t over-correct.** Assume good intent and only flag clear, meaningful issues (NVC + Gottman Four Horsemen). **Also show approval for positive actions that de-escalate conflict or push the conversation in a positive direction.**

## Output (exact keys only)
- "sentiment": "Positive" | "Neutral" | "Negative" | "Hostile"
- "horseman": "None" | "Criticism" | "Contempt" | "Defensiveness" | "Stonewalling"
- "level": integer -5..5
- "nudgeText": optional string (ONLY if level <= -4 or level >= 4)
- "suggestedRephrasing": optional string (ONLY if level <= -4)

Return a single JSON object.

## Quick calibration
- Default to "horseman": "None" if unsure.
- Use context: one sharp line may be a moment, not a pattern.
- **If the speaker de-escalates tension or makes a positive move, acknowledge and show approval for these positive actions. Positive actions include: taking responsibility; apologizing; showing appreciation; making an effort to understand the other person's perspective; expressing vulnerability; proposing a solution; expressing curiosity or asking clarifying questions; expressing care; making amends; de-escalating tension; engaging in teamwork; expressing empathy; explicitly acknowledging mistakes; giving recognition to the other person's feelings or actions; sharing hopes or intentions for a better interaction; validating the other person; offering support or encouragement; asking how to help; initiating a constructive topic shift; restating what the other person said to show understanding.**

## Horsemen 
- Criticism: attacks character/identity ("you are X") vs behavior ("when you did X").
- Contempt (very high bar): insults/mockery/disgust/belittling/superiority/humiliation.
- Defensiveness: dodges responsibility by excuses/counterattack ("yeah but you...").
- Stonewalling (high bar): shutdown/refusal to engage ("whatever", "I’m done", repeated silent/avoid).

## Sentiment anchors
- Positive: appreciation, repair, curiosity, teamwork.
- Neutral: factual/logistical, calm disagreement.
- Negative: frustration, blame-leaning, sarcasm-lite.
- Hostile: insults, contempt, threats, targeted profanity.

## Level anchors (-5..5)
- 5: strong warmth/repair
- 4: notable positive progress—clear de-escalation, significant empathy or responsibility, or a major constructive step
- 3: supportive/collaborative
- 2: clear effort toward positivity, such as direct validation, solution-seeking, or meaningful check-in
- 1: mildly positive
- 0: neutral
- -1: mild irritation
- -2: clear frustration, minor blame
- -3: sharp blame, "always/never", escalating
- -4: clearly escalatory attack or clear horseman with impact
- -5: contempt/humiliation/threats/aggressive verbal attack

Only set level <= -4 if likely to escalate if left unchecked.

## Nudges (ONLY when level <= -3 OR level >= 4)
- For negative escalations, keep warm and brief (not preachy).
- Rephrase with: observable facts + (optional feeling) + need/value + specific request.
- Keep it natural (not therapy-speak).
- For strong positive actions (level >= 4), offer brief encouragement or approval—acknowledge how the action helps de-escalate or build understanding.
"""


def _build_prompt(transcript: str, history: Optional[list[HistoryTurn]], speaker: Optional[str] = None) -> str:
    parts = [SYSTEM_PROMPT, "\n\n"]
    if history:
        parts.append("Recent turns:\n")
        for t in history:
            parts.append(f"- {t.speaker}: {t.transcript}\n")
        parts.append("\n")
    # When no known speaker is sent, use a generated anonymous name so the prompt always identifies who is speaking.
    speaker_label = (speaker or "").strip() or "Unknown speaker"
    parts.append(f"Current turn to analyze (speaker: {speaker_label}):\n")
    if speaker_label in ("OVERLAP", "UNCERTAIN"):
        parts.append("(Don't over-attribute blame; acknowledge interruptions and overlapping speech.)\n")
    parts.append(transcript)
    return "".join(parts)


def _parse_response(text: str) -> dict:
    """Parse LLM response into dict; normalize keys and values."""
    text = (text or "").strip()
    # Strip markdown code block if present
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("analyze-turn: JSON parse failed: %s", e)
        return {
            "sentiment": "Neutral",
            "horseman": "None",
            "level": 0,
            "nudgeText": None,
            "suggestedRephrasing": None,
        }
    sentiment = (data.get("sentiment") or "Neutral").strip()
    if sentiment not in ("Positive", "Neutral", "Negative", "Hostile"):
        sentiment = "Neutral"
    horseman = (data.get("horseman") or "None").strip()
    if horseman not in ("None", "Criticism", "Contempt", "Defensiveness", "Stonewalling"):
        horseman = "None"
    try:
        level = int(data.get("level", 0))
    except (TypeError, ValueError):
        level = 0
    level = max(-5, min(5, level))
    nudge = data.get("nudgeText") or data.get("nudge_text")
    if isinstance(nudge, str):
        nudge = nudge.strip() or None
    else:
        nudge = None
    rephrasing = data.get("suggestedRephrasing") or data.get("suggested_rephrasing")
    if isinstance(rephrasing, str):
        rephrasing = rephrasing.strip() or None
    else:
        rephrasing = None
    # Only show rephrasing when negativity <= -4, regardless of horseman
    if level > -4 and rephrasing:
        rephrasing = None
    return {
        "sentiment": sentiment,
        "horseman": horseman,
        "level": level,
        "nudgeText": nudge,
        "suggestedRephrasing": rephrasing,
    }


@router.post("/analyze-turn", response_model=AnalyzeTurnResponse)
async def post_analyze_turn(
    request: AnalyzeTurnRequest,
    current_user: User = Depends(get_current_user),
    llm_service: LLMService = Depends(get_llm_service),
) -> AnalyzeTurnResponse:
    """
    Analyze a single conversation turn (transcript) for sentiment, horseman, level, nudge, rephrasing.
    Used by Live Coach when STT final arrives; analysis is merged into the transcript row by segment_id.
    """
    t0 = time.perf_counter()
    history = request.history if request.include_history and request.history else None
    prompt = _build_prompt(request.transcript, history, speaker=request.speaker)
    try:
        text = await llm_service.generate_text_async(prompt)
    except LLMRateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail=e.args[0] if e.args else "LLM rate limit exceeded; try again shortly.",
        ) from None
    if not text:
        raise HTTPException(
            status_code=503,
            detail="Analysis unavailable (LLM not configured or failed).",
        )
    out = _parse_response(text)
    latency_ms = int((time.perf_counter() - t0) * 1000)
    return AnalyzeTurnResponse(
        sentiment=out["sentiment"],
        horseman=out["horseman"],
        level=out["level"],
        nudgeText=out["nudgeText"],
        suggestedRephrasing=out["suggestedRephrasing"],
        latency_ms=latency_ms,
        debug_prompt=prompt if request.debug else None,
    )
