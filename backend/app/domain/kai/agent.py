"""Kai agent service: lounge conversation, activity generation, love map questions. Horizontal personalized service; consumes Compass profile/context."""
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

MODEL_ID = "gemini-2.0-flash"

# Base prompt (therapist/communication coach instructions) loaded once at startup
_KAI_BASE_PROMPT: Optional[str] = None
# Lounge prompt (Lounge conversation use cases) loaded once at startup
_KAI_LOUNGE_PROMPT: Optional[str] = None
# Intervention prompt (vetting and guidance use cases) loaded once at startup
_KAI_INTERVENTION_PROMPT: Optional[str] = None
# Single-user prompt (solo reply and private chat with Kai) loaded once at startup
_KAI_SINGLE_USER_PROMPT: Optional[str] = None


def _load_prompt_file(filename: str) -> str:
    """Load a prompt file from prompts/ dir (no caching; caller caches)."""
    prompt_dir = Path(__file__).resolve().parent / "prompts"
    path = prompt_dir / filename
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    logger.warning("Kai prompt file not found at %s; using empty.", path)
    return ""


def _get_base_prompt() -> str:
    """Load Kai base prompt from file once; used on server startup (first Kai use)."""
    global _KAI_BASE_PROMPT
    if _KAI_BASE_PROMPT is not None:
        return _KAI_BASE_PROMPT
    try:
        _KAI_BASE_PROMPT = _load_prompt_file("base_prompt.txt")
        if _KAI_BASE_PROMPT:
            logger.info("Kai base prompt loaded (%s chars)", len(_KAI_BASE_PROMPT))
    except Exception as e:
        logger.warning("Kai base prompt load failed: %s; using empty base prompt.", e)
        _KAI_BASE_PROMPT = ""
    return _KAI_BASE_PROMPT


def _get_lounge_prompt() -> str:
    """Load Kai lounge prompt from file once; used on server startup (first Lounge/Kai use)."""
    global _KAI_LOUNGE_PROMPT
    if _KAI_LOUNGE_PROMPT is not None:
        return _KAI_LOUNGE_PROMPT
    try:
        _KAI_LOUNGE_PROMPT = _load_prompt_file("lounge_prompt.txt")
        if _KAI_LOUNGE_PROMPT:
            logger.info("Kai lounge prompt loaded (%s chars)", len(_KAI_LOUNGE_PROMPT))
    except Exception as e:
        logger.warning("Kai lounge prompt load failed: %s; using empty lounge prompt.", e)
        _KAI_LOUNGE_PROMPT = ""
    return _KAI_LOUNGE_PROMPT


def _get_intervention_prompt() -> str:
    """Load Kai intervention prompt from file once; used for vetting and guidance use cases."""
    global _KAI_INTERVENTION_PROMPT
    if _KAI_INTERVENTION_PROMPT is not None:
        return _KAI_INTERVENTION_PROMPT
    try:
        _KAI_INTERVENTION_PROMPT = _load_prompt_file("intervention_prompt.txt")
        if _KAI_INTERVENTION_PROMPT:
            logger.info("Kai intervention prompt loaded (%s chars)", len(_KAI_INTERVENTION_PROMPT))
    except Exception as e:
        logger.warning("Kai intervention prompt load failed: %s; using empty intervention prompt.", e)
        _KAI_INTERVENTION_PROMPT = ""
    return _KAI_INTERVENTION_PROMPT


def _get_lounge_system_prompt() -> str:
    """Base of the prompt for Lounge use cases: base_prompt concatenated with lounge_prompt.
    Lounge tasks (vet, guidance, solo reply, private reply, extract preferences) use this
    as the system/instruction block, then append the task-specific prompt after '---'."""
    base = _get_base_prompt()
    lounge = _get_lounge_prompt()
    if not base and not lounge:
        return ""
    if not lounge:
        return base
    if not base:
        return lounge
    return f"{base}\n\n{lounge}"


def _message_sender_label(m: dict) -> str:
    """Return display label for message sender (for thread formatting)."""
    return m.get("sender_label") or m.get("sender_user_id") or "Kai"


def _parse_message_time(created_at: Any) -> Optional[datetime]:
    """Parse created_at from message dict (ISO string or datetime) to timezone-aware datetime."""
    if created_at is None:
        return None
    if isinstance(created_at, datetime):
        return created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    if isinstance(created_at, str):
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None
    return None


def _elapsed_str(reference: datetime, msg_time: datetime) -> str:
    """Format elapsed time from msg_time to reference (e.g. 'just now', '2m ago')."""
    delta = reference - msg_time
    total_seconds = max(0, int(delta.total_seconds()))
    if total_seconds < 60:
        return "just now"
    if total_seconds < 3600:
        m = total_seconds // 60
        return f"{m}m ago"
    if total_seconds < 86400:
        h = total_seconds // 3600
        return f"{h}h ago"
    d = total_seconds // 86400
    return f"{d}d ago"


def format_message_history(
    recent_messages: list[dict],
    *,
    limit: int = 15,
    include_elapsed: bool = True,
    reference_ts: Optional[datetime] = None,
) -> str:
    """Format message history for LLM context: sender, content, and optional elapsed time.
    Message dicts may include sender_label/sender_user_id, content, and optionally created_at (ISO string or datetime)."""
    messages = (recent_messages or [])[-limit:]
    if not messages:
        return ""

    ref = reference_ts
    if include_elapsed and ref is None:
        last_ts = _parse_message_time(messages[-1].get("created_at"))
        ref = last_ts or datetime.now(timezone.utc)

    lines: list[str] = []
    for m in messages:
        sender = _message_sender_label(m)
        content = m.get("content", "")
        if include_elapsed and ref is not None:
            msg_ts = _parse_message_time(m.get("created_at"))
            if msg_ts is not None:
                elapsed = _elapsed_str(ref, msg_ts)
                lines.append(f"[{sender}] ({elapsed}): {content}")
            else:
                lines.append(f"[{sender}]: {content}")
        else:
            lines.append(f"[{sender}]: {content}")
    return "\n".join(lines)


def _get_single_user_prompt() -> str:
    """Load Kai single-user prompt from file once; used when a single user is involved in Lounge (solo reply, private chat)."""
    global _KAI_SINGLE_USER_PROMPT
    if _KAI_SINGLE_USER_PROMPT is not None:
        return _KAI_SINGLE_USER_PROMPT
    try:
        _KAI_SINGLE_USER_PROMPT = _load_prompt_file("single_user_prompt.txt")
        if _KAI_SINGLE_USER_PROMPT:
            logger.info("Kai single-user prompt loaded (%s chars)", len(_KAI_SINGLE_USER_PROMPT))
    except Exception as e:
        logger.warning("Kai single-user prompt load failed: %s; using empty single-user prompt.", e)
        _KAI_SINGLE_USER_PROMPT = ""
    return _KAI_SINGLE_USER_PROMPT


def _get_lounge_with_intervention_system_prompt() -> str:
    """Base + lounge + intervention prompt. Use only for vetting and guidance use cases.
    Appends intervention_prompt to base_prompt and lounge_prompt."""
    base_lounge = _get_lounge_system_prompt()
    intervention = _get_intervention_prompt()
    if not intervention:
        return base_lounge
    return f"{base_lounge}\n\n{intervention}"


def _get_lounge_with_single_user_system_prompt() -> str:
    """Base + lounge + single_user prompt. Use when a single user is involved in Lounge (solo reply, private chat with Kai).
    Appends single_user_prompt to base_prompt and lounge_prompt."""
    base_lounge = _get_lounge_system_prompt()
    single_user = _get_single_user_prompt()
    if not single_user:
        return base_lounge
    return f"{base_lounge}\n\n{single_user}"


@dataclass
class VetResult:
    """Result of vetting an outbound message."""
    allowed: bool
    suggestion: Optional[str] = None
    revised_text: Optional[str] = None
    horseman: Optional[str] = None


@dataclass
class GuidanceResult:
    """Optional guidance after others' messages."""
    guidance_type: Optional[str] = None
    text: Optional[str] = None
    suggested_phrase: Optional[str] = None
    debug_prompt: Optional[str] = None
    debug_response: Optional[str] = None


@dataclass
class ReplyPublicSoloResult:
    """When user is alone in chat group: Kai's reply and optional invite suggestion."""
    reply: Optional[str] = None
    suggest_invite_display_name: Optional[str] = None
    debug_prompt: Optional[str] = None
    debug_response: Optional[str] = None


@dataclass
class ReplyPrivateResult:
    """Kai's reply to a private message plus debug."""
    reply: Optional[str] = None
    debug_prompt: Optional[str] = None
    debug_response: Optional[str] = None


@dataclass
class UnderstandScreenshotResult:
    """Understanding of a conversation extracted from screenshots (what's going on, who's who, who is the user)."""
    whats_going_on: Optional[str] = None
    participants_description: Optional[str] = None
    likely_user_in_conversation: Optional[str] = None
    questions_if_any: Optional[str] = None


@dataclass
class ScreenshotMessageAnalysis:
    """Per-message analysis: revision and/or guidance Kai would suggest for this message."""
    message_index: int
    sender_label: str
    content: str
    suggested_revision: Optional[str] = None  # rephrased version Kai would suggest (vet-style)
    guidance_type: Optional[str] = None  # validate_feelings, rephrase_that, breathing_break, analysis
    guidance_text: Optional[str] = None
    suggested_phrase: Optional[str] = None  # for rephrase_that


def _get_client(gemini_api_key: Optional[str]):
    if not gemini_api_key or not (gemini_api_key or "").strip():
        return None
    try:
        import google.genai as genai
        return genai.Client(api_key=gemini_api_key.strip())
    except (ImportError, ModuleNotFoundError) as e:
        logger.warning("Kai agent: google.genai not available: %s", e)
        return None


def _generate_text(
    prompt: str,
    model: str,
    llm_service: Optional[Any],
    gemini_api_key: Optional[str],
) -> Optional[str]:
    """Generate text via LLMService (preferred) or raw Gemini client. Returns response text or None."""
    if llm_service is not None:
        out = llm_service.generate_text(prompt, model=model)
        return (out or "").strip() or None
    client = _get_client(gemini_api_key)
    if not client:
        return None
    try:
        response = client.models.generate_content(model=model, contents=prompt)
        return (response.text or "").strip() or None
    except Exception as e:
        logger.warning("Kai _generate_text failed: %s", e)
        return None


def extract_chat_from_screenshots(
    image_base64_list: List[str],
    mime_types: Optional[List[str]] = None,
    gemini_api_key: Optional[str] = None,
    *,
    llm_service: Optional[Any] = None,
) -> List[dict]:
    """
    Extract a chat thread from one or more screenshot images using vision.
    Returns a list of message dicts compatible with format_message_history / get_guidance:
    each dict has sender_label and content; sender_user_id can be None.
    """
    if not image_base64_list:
        return []
    mimes = mime_types or []
    image_parts = []
    for i, b64 in enumerate(image_base64_list):
        if not b64 or not isinstance(b64, str):
            continue
        mime = (mimes[i] if i < len(mimes) else "image/png").strip() or "image/png"
        image_parts.append({"mime_type": mime, "data": b64})
    if not image_parts:
        return []
    n = len(image_parts)
    order_note = f" These {n} image(s) are in chronological order (oldest first)." if n > 1 else ""
    prompt = f"""These are screenshot(s) of a chat or messaging thread.{order_note}
Important: The name or label in the chat header/title is usually the OTHER person (the contact), not the person who took the screenshot. The person who took the screenshot is the "user"; their messages are often on one side (e.g. right) and may be labeled "You" or "Me" in the app.
Extract every message in order. For each message, identify who said it: use the exact label from the screen (e.g. the header name for the contact, "You" or "Me" for the person who took the screenshot, or "Person A" / "Person B" if unclear) and the exact message text.
Output a JSON array only. Each element must have "sender_label" and "content". Try your best even if the image is blurry or partial—extract whatever you can; use "[unreadable]" or "..." for text you cannot make out. Do not add any explanation: return only the JSON array.
Example: [{{"sender_label": "You", "content": "Hey, can we talk?"}}, {{"sender_label": "Mom", "content": "Sure."}}]
Do not include any other text before or after the JSON array."""

    raw_response: Optional[str] = None
    if llm_service is not None and hasattr(llm_service, "generate_text_with_images"):
        raw_response = llm_service.generate_text_with_images(prompt, image_parts, model=MODEL_ID)
    if not raw_response:
        client = _get_client(gemini_api_key)
        if client:
            try:
                import base64
                from google.genai import types
                parts: List[Any] = []
                use_types = hasattr(types, "Part") and hasattr(types, "Blob")
                for ip in image_parts:
                    mime = ip.get("mime_type", "image/png")
                    data = ip.get("data")
                    if isinstance(data, str):
                        data = base64.b64decode(data)
                    if use_types:
                        parts.append(types.Part(inline_data=types.Blob(mime_type=mime, data=data)))
                    else:
                        parts.append({"inline_data": {"mime_type": mime, "data": ip.get("data")}})
                if use_types:
                    parts.append(types.Part(text=prompt))
                else:
                    parts.append({"text": prompt})
                response = client.models.generate_content(model=MODEL_ID, contents=parts)
                raw_response = (response.text or "").strip() or None
            except Exception as e:
                logger.warning("Kai extract_chat_from_screenshots (client) failed: %s", e)
    if not raw_response:
        logger.info("Kai extract_chat_from_screenshots: no response from model (empty or API error)")
        return []
    text = raw_response.strip()
    if "```json" in text:
        text = text.split("```json")[-1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    def parse_array(arr: list) -> list:
        out = []
        for item in arr:
            if not isinstance(item, dict):
                continue
            sender = item.get("sender_label") or item.get("sender") or "Unknown"
            content = item.get("content") or item.get("text") or ""
            if not isinstance(content, str):
                content = str(content) if content is not None else ""
            content = content.strip() or "[message]"
            sender = sender.strip() if isinstance(sender, str) else str(sender)
            out.append({
                "sender_label": sender or "Unknown",
                "sender_user_id": None,
                "content": content,
                "created_at": None,
            })
        return out

    try:
        data = json.loads(text)
        if not isinstance(data, list):
            logger.info("Kai extract_chat_from_screenshots: model returned non-array JSON")
            return []
        out = parse_array(data)
        if not out:
            logger.info("Kai extract_chat_from_screenshots: parsed array had no valid message items")
            return []
        return out
    except json.JSONDecodeError:
        pass
    # Fallback: find first '[' and last ']' and parse that substring
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, list):
                out = parse_array(data)
                if out:
                    logger.info("Kai extract_chat_from_screenshots: parsed array from [ ] substring (%d messages)", len(out))
                    return out
        except json.JSONDecodeError as e:
            logger.warning("Kai extract_chat_from_screenshots parse failed (including [ ] fallback): %s", e)
    else:
        logger.warning("Kai extract_chat_from_screenshots parse failed: no JSON array in response (len=%d)", len(raw_response))
    return []


def understand_screenshot_conversation(
    extracted_thread: list[dict],
    gemini_api_key: Optional[str] = None,
    *,
    llm_service: Optional[Any] = None,
) -> UnderstandScreenshotResult:
    """
    Make sense of what's going on in the conversation and who the user is in it.
    Do not assume participants are the user's loved ones; use only labels from the thread.
    """
    if not extracted_thread:
        return UnderstandScreenshotResult()
    thread = format_message_history(extracted_thread, limit=50, include_elapsed=False)
    prompt = f"""You are Kai, a supportive communication coach. You are looking at a conversation that was extracted from chat screenshots. The person using this app (the "user") is one of the participants in that conversation and is seeking your guidance.

Important: In chat screenshots, the name in the header/title is usually the OTHER person (the contact), not the user. The user is the person who took the screenshot; their messages are often on one side (e.g. right) and may be labeled "You" or "Me". So the header name = the contact; "You"/"Me" (or the side that isn't the header name) = the user.

Extracted conversation (participants are labeled as they appeared in the screenshots; do NOT assume they are the user's partner or family):
{thread or '(none)'}

Tasks:
1. Summarize what's going on in the conversation: topic, tone, conflict/support, tension, or cooperation.
2. Describe who the participants appear to be using only the labels from the thread (e.g. "You", "Mom", "Person A"). Do NOT assume they are the user's loved ones or family.
3. Infer which participant is most likely the person seeking guidance (the "user" in this app). Prefer: the one labeled "You" or "Me", or the participant whose messages are on the same side as "You"/"Me" in typical apps; the participant whose name appears in the header is usually the OTHER person (the contact), not the user.
4. If something is unclear (e.g. ambiguous who is who), list 1-2 short questions you could ask the user to clarify. Otherwise use null.

Output JSON only, no other text:
{{"whats_going_on": "1-3 sentences", "participants_description": "who appears in the chat (labels only)", "likely_user_in_conversation": "which participant and why", "questions_if_any": "1-2 short questions or null"}}"""

    raw = _generate_text(prompt, MODEL_ID, llm_service, gemini_api_key)
    if not raw:
        return UnderstandScreenshotResult()
    text = raw
    if "```json" in text:
        text = text.split("```json")[-1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    try:
        data = json.loads(text)
        return UnderstandScreenshotResult(
            whats_going_on=(data.get("whats_going_on") or "").strip() or None,
            participants_description=(data.get("participants_description") or "").strip() or None,
            likely_user_in_conversation=(data.get("likely_user_in_conversation") or "").strip() or None,
            questions_if_any=data.get("questions_if_any") if isinstance(data.get("questions_if_any"), str) and (data.get("questions_if_any") or "").strip() else None,
        )
    except Exception as e:
        logger.warning("Kai understand_screenshot_conversation parse failed: %s", e)
        return UnderstandScreenshotResult()


def analyze_screenshot_messages_for_revisions_and_guidance(
    extracted_thread: list[dict],
    understanding_text: str,
    likely_user_label: Optional[str],
    gemini_api_key: Optional[str] = None,
    *,
    llm_service: Optional[Any] = None,
) -> list[ScreenshotMessageAnalysis]:
    """
    Analyze the extracted conversation message by message. For each message, decide if Kai would
    suggest a revision (rephrase) and/or generate guidance for the user (the person seeking help).
    Uses the same intervention philosophy as vet_message and get_guidance.
    """
    if not extracted_thread:
        return []
    thread = format_message_history(extracted_thread, limit=50, include_elapsed=False)
    system = _get_lounge_with_intervention_system_prompt()
    user_line = (
        f'The person seeking guidance (the "user") in this conversation is likely **{likely_user_label}**. '
        if likely_user_label
        else "The person seeking guidance is one of the participants; infer who might want support.\n"
    )
    prompt = f"""{system}

---
Task: Screenshot analysis — message-by-message. A conversation was extracted from chat screenshots. The user (the person seeking Kai's help) is one of the participants. In chat screenshots, the name in the header is usually the OTHER person (the contact); the user is the one who took the screenshot (often labeled "You" or "Me").
Go through the conversation message by message and, for each message, decide:
1. **Revision**: Would Kai suggest a rephrase for this message? If the message is from the other person, consider whether the user's *reply* could be improved; if the message is from the user, consider whether this message could be rephrased.
2. **Guidance**: At this point in the thread, would Kai offer the user a gentle nudge? Write as if speaking TO the user (use "you"). Prefer no guidance unless there is clear benefit.

**What to flag (revision)** — same criteria as vetting. Suggest a revision when the message (or the user's reply to it) shows:
- **Four Horsemen:** criticism (attacking character instead of behavior), contempt (disrespect, eye-rolling, insults), defensiveness (excuses, counter-attack, not hearing the other), stonewalling (shutting down, refusing to engage).
- **Hostility:** threats, name-calling, "always/never" blame, intensity that escalates.
- **Clarity:** vague or accusatory wording that could be restated as a clear feeling or request (e.g. "You never listen" → "I don't feel heard when we talk over each other").
If the message is mild or already constructive, leave suggested_revision null.

**What to flag (guidance)** — when a nudge would clearly help the user:
- **validate_feelings:** User might need to hear that their feeling makes sense before replying (e.g. after a dismissive or harsh message from the other person).
- **rephrase_that:** User's next reply could be softened or clarified; offer suggested_phrase they could type.
- **breathing_break:** Tension is high; user might benefit from pausing, breathing, or stepping back before responding.
- **analysis:** Short note to the user about where the conversation could go (e.g. naming feelings, one small ask, hearing each other). Use "you"; never use the other participant's name.
Only output guidance when there is clear benefit; otherwise leave guidance_type, guidance_text, and suggested_phrase null.

**Language:** Use the same language as the conversation. If messages are in Spanish, write suggested_revision, guidance_text, and suggested_phrase in Spanish; if in Chinese, write in Chinese; if in English, write in English. Match the language of the messages.

{user_line}
Your earlier understanding of the conversation:
{understanding_text.strip()}

Extracted conversation (in order):
{thread or '(none)'}

Output a JSON array only. One object per message, in the same order as the conversation. Each object must have:
- "message_index": 0-based index
- "sender_label": who sent it (from the thread)
- "content": the message text (from the thread)
- "suggested_revision": null, or the EXACT rephrased sentence the user could have sent instead (only the sentence, no preamble)
- "guidance_type": null, or one of "validate_feelings", "rephrase_that", "breathing_break", "analysis"
- "guidance_text": null, or short suggestion for the user (use "you"; never use the other participant's name)
- "suggested_phrase": null, or for rephrase_that only, the EXACT words the user could type in the message box

Example (one message with revision + guidance): {{"message_index": 2, "sender_label": "Person A", "content": "You never listen!", "suggested_revision": "I don't feel heard when we talk over each other.", "guidance_type": "validate_feelings", "guidance_text": "You might name how you feel before asking for one thing you need.", "suggested_phrase": null}}
Example (no revision or guidance): {{"message_index": 0, "sender_label": "Person A", "content": "Hey.", "suggested_revision": null, "guidance_type": null, "guidance_text": null, "suggested_phrase": null}}

Output the full JSON array. No other text before or after."""

    raw = _generate_text(prompt, MODEL_ID, llm_service, gemini_api_key)
    if not raw:
        return []
    text = (raw or "").strip()
    if "```json" in text:
        text = text.split("```json")[-1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    try:
        data = json.loads(text)
        if not isinstance(data, list):
            return []
        out: list[ScreenshotMessageAnalysis] = []
        allowed_guidance = ("validate_feelings", "rephrase_that", "breathing_break", "analysis")
        for item in data:
            if not isinstance(item, dict):
                continue
            idx = item.get("message_index")
            if idx is None or not isinstance(idx, int):
                continue
            sender = (item.get("sender_label") or item.get("sender") or "Unknown")
            sender = sender if isinstance(sender, str) else "Unknown"
            content = (item.get("content") or "")
            content = content if isinstance(content, str) else ""
            suggested_revision = item.get("suggested_revision")
            if suggested_revision is not None and not isinstance(suggested_revision, str):
                suggested_revision = None
            if suggested_revision:
                suggested_revision = suggested_revision.strip() or None
            gtype = item.get("guidance_type")
            if gtype is not None and (not isinstance(gtype, str) or gtype not in allowed_guidance):
                gtype = None
            guidance_text = item.get("guidance_text")
            if guidance_text is not None and not isinstance(guidance_text, str):
                guidance_text = None
            if guidance_text:
                guidance_text = guidance_text.strip() or None
            suggested_phrase = item.get("suggested_phrase")
            if suggested_phrase is not None and not isinstance(suggested_phrase, str):
                suggested_phrase = None
            if suggested_phrase:
                suggested_phrase = suggested_phrase.strip() or None
            out.append(ScreenshotMessageAnalysis(
                message_index=idx,
                sender_label=sender,
                content=content,
                suggested_revision=suggested_revision,
                guidance_type=gtype,
                guidance_text=guidance_text,
                suggested_phrase=suggested_phrase,
            ))
        return out
    except Exception as e:
        logger.warning("Kai analyze_screenshot_messages_for_revisions_and_guidance parse failed: %s", e)
        return []


def analyze_screenshot_communication_and_suggest(
    extracted_thread: list[dict],
    understanding_text: str,
    user_message: str,
    gemini_api_key: Optional[str] = None,
    *,
    kai_summary: Optional[str] = None,
    user_preferences_text: Optional[str] = None,
    conversation_goal: Optional[str] = None,
    llm_service: Optional[Any] = None,
) -> Optional[str]:
    """
    After the user has confirmed or corrected the understanding, analyze the communication
    and interactions in the extracted conversation and suggest concrete next steps.
    Returns a single block of text suitable for posting as a Kai message.
    """
    if not extracted_thread or not (understanding_text or "").strip():
        return None
    thread = format_message_history(extracted_thread, limit=50, include_elapsed=False)
    system = _get_lounge_with_intervention_system_prompt()
    prompt = f"""{system}

---
Task: Screenshot analysis follow-up. The user previously shared chat screenshots. You shared your understanding and asked them to confirm. They have now replied with confirmation or correction.

Your earlier understanding:
{understanding_text.strip()}

Extracted conversation:
{thread or '(none)'}

User's reply (confirmation or correction or extra context): "{user_message}"

Kai context: {kai_summary or 'None'}
User's stated goal for this conversation: {conversation_goal or 'None'}
User's preferences/feedback: {user_preferences_text or 'None'}

Using only what's in the conversation and the user's clarification (do NOT assume participants are loved ones):
1. Briefly acknowledge their reply.
2. Analyze the communication and interactions in the conversation: what's working, what might be improved, tone, listening, any patterns or pitfalls.
3. Suggest 2-4 concrete, kind next steps for the user.

Write a single reply in plain text (2-5 short paragraphs). No JSON. Tone: supportive coach. Do not assume the other participant is the user's partner or family."""

    raw = _generate_text(prompt, MODEL_ID, llm_service, gemini_api_key)
    if not raw:
        return None
    return (raw or "").strip() or None


def update_context(
    recent_messages: list[dict],
    existing_summary: Optional[str],
    existing_facts: Optional[dict],
    gemini_api_key: Optional[str],
    *,
    llm_service: Optional[Any] = None,
) -> tuple[Optional[str], Optional[dict]]:
    """Summarize recent public messages and extract key facts for Kai's context."""
    thread = format_message_history(recent_messages, limit=30, include_elapsed=True)
    if not thread.strip():
        return existing_summary, existing_facts

    prompt = f"""You are Kai, an AI coach in a group chat (Lounge). Your job is to keep a concise context of the conversation.

Recent messages (newest at bottom):
{thread}

Existing summary (if any): {existing_summary or 'None'}
Existing extracted facts (if any): {json.dumps(existing_facts or {}, default=str)[:500]}

Output a short summary (2-4 sentences) of what has been discussed and any key facts (names, feelings, conflicts, agreements). Reply with JSON only:
{{"summary": "...", "facts": {{"key": "value", ...}}}}
Do not include any other text."""

    text = _generate_text(prompt, MODEL_ID, llm_service, gemini_api_key)
    if not text:
        return existing_summary, existing_facts
    try:
        if "```json" in text:
            text = text.split("```json")[-1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        data = json.loads(text)
        summary = data.get("summary") if isinstance(data.get("summary"), str) else existing_summary
        facts = data.get("facts") if isinstance(data.get("facts"), dict) else (existing_facts or {})
        return summary, facts
    except Exception as e:
        logger.warning("Kai update_context failed: %s", e)
        return existing_summary, existing_facts


def vet_message(
    draft: str,
    recent_messages: list[dict],
    kai_summary: Optional[str],
    gemini_api_key: Optional[str],
    *,
    sender_name: Optional[str] = None,
    other_sensitivity: Optional[str] = None,
    tension_level: Optional[str] = None,
    user_preferences_text: Optional[str] = None,
    compass_profile_text: Optional[str] = None,
    conversation_goal: Optional[str] = None,
    llm_service: Optional[Any] = None,
) -> VetResult:
    """Vet a draft message for Four Horsemen and communication risks."""

    thread = format_message_history(recent_messages, limit=20, include_elapsed=True)

    sensitivity = (other_sensitivity or "medium").lower()
    if sensitivity not in ("low", "medium", "high"):
        sensitivity = "medium"
    tension = (tension_level or "medium").lower()
    if tension not in ("low", "medium", "high"):
        tension = "medium"

    system = _get_lounge_with_intervention_system_prompt()
    sender_line = f"The person about to send this message is **{sender_name}**. " if sender_name else ""
    prompt = f"""{system}

---
Task: Vetting. A user is about to send a message to the Lounge group chat. Be a process facilitator: improve HOW they talk more than WHAT they decide. Intervene to protect safety, fairness, clarity, and forward progress.
{sender_line}Check the draft for communication risks (Four Horsemen, hostility). If allowed, they send as-is; if not, offer a short suggestion and the EXACT revised phrase they can type instead. Use the context below for sensitivity and tension.

**Language:** Use the same language as the draft and conversation. If the draft is in Spanish, write "suggestion" and "revised_text" in Spanish; if in Chinese, write in Chinese; if in English, write in English. Match the user's language.

Context for vetting:
- Other participants' sensitivity: **{sensitivity}** (by default assume medium; do not be overly strict).
- Current tension in the conversation: **{tension}**.
- User's stated goal for this conversation (if any): {conversation_goal or 'None'}
- User profile (from Compass): {compass_profile_text or 'None'}
- User's stated preferences and feedback (use these in how you respond): {user_preferences_text or 'None'}

Recent conversation:
{thread or '(none)'}

Kai context: {kai_summary or 'None'}

Draft message to send: "{draft}"

Output: Reply with JSON only, no other text.
- If the draft is fine (or only mildly strong): {{"allowed": true}}
- If the draft is clearly problematic: {{"allowed": false, "suggestion": "A short explanation for the user (e.g. A calmer way to say this:)", "revised_text": "The EXACT words the user should type—only the revised sentence, no preamble.", "horseman": "criticism" | "contempt" | "defensiveness" | "stonewalling" | null}}

Example: {{"allowed": false, "suggestion": "A calmer way to say this:", "revised_text": "I feel hurt when I'm interrupted.", "horseman": "defensiveness"}}"""

    text = _generate_text(prompt, MODEL_ID, llm_service, gemini_api_key)
    if not text:
        return VetResult(allowed=True)
    try:
        if "```json" in text:
            text = text.split("```json")[-1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        data = json.loads(text)
        allowed = data.get("allowed", True)
        suggestion = data.get("suggestion") if isinstance(data.get("suggestion"), str) else None
        revised_text = data.get("revised_text") if isinstance(data.get("revised_text"), str) else None
        if revised_text:
            revised_text = revised_text.strip()
        horseman_raw = data.get("horseman")
        horseman = None
        if isinstance(horseman_raw, str) and horseman_raw.strip().lower() in ("criticism", "contempt", "defensiveness", "stonewalling"):
            horseman = horseman_raw.strip().lower()
        return VetResult(allowed=allowed, suggestion=suggestion, revised_text=revised_text or None, horseman=horseman)
    except Exception as e:
        logger.warning("Kai vet_message failed: %s", e)
        return VetResult(allowed=True)


def get_guidance(
    recent_messages: list[dict],
    latest_from_other: Optional[str],
    kai_summary: Optional[str],
    gemini_api_key: Optional[str],
    *,
    user_preferences_text: Optional[str] = None,
    compass_profile_text: Optional[str] = None,
    conversation_goal: Optional[str] = None,
    viewer_display_name: Optional[str] = None,
    llm_service: Optional[Any] = None,
) -> GuidanceResult:
    """After someone else sent a message, optionally suggest guidance for the current user."""

    thread = format_message_history(recent_messages, limit=15, include_elapsed=True)

    viewer_line = f"The person who will read this guidance (the viewer) is **{viewer_display_name}**. " if viewer_display_name else ""

    system = _get_lounge_with_intervention_system_prompt()
    prompt = f"""{system}

---
Task: Guidance in group chat. Someone else in the Lounge just sent a message. Decide if the **viewer** (the current user, the person who will receive this guidance—NOT the message sender) would benefit from a gentle nudge—e.g. validate their feelings, rephrase their reply, take a breathing break, or consider mediation. Only when there is clear benefit; prefer no guidance otherwise.

**Critical — who reads the guidance:** {viewer_line}The "text" and "suggested_phrase" are for the VIEWER to read. Write as if speaking TO the viewer (use "you" for the viewer). Never use the message sender's name in the guidance text. The viewer is reading it; if you use a name, the viewer will think you're talking to someone else.
- WRONG: "It's understandable to feel ignored in that situation, Marcus." (addresses the sender; the viewer is not Marcus)
- RIGHT: "It's understandable to feel that way." or "You might say: It sounds like he felt ignored—acknowledging that can help."

**Language:** Use the same language the user and conversation are using. If the messages are in Spanish, write "text" and "suggested_phrase" in Spanish; if in Chinese, write in Chinese; if in English, write in English. Match the language of the recent messages.

Recent messages:
{thread or '(none)'}

Latest message from another person (the sender—do not use their name in your guidance): "{latest_from_other or ''}"

Kai context: {kai_summary or 'None'}
Viewer's stated goal for this conversation (if any): {conversation_goal or 'None'}
Viewer's profile (from Compass): {compass_profile_text or 'None'}
Viewer's stated preferences and feedback (use these in how you respond): {user_preferences_text or 'None'}

Output: Reply with JSON only. Prefer no guidance unless there is clear benefit.
- If no guidance needed: {{"guidance_type": null}}
- If validate feelings would help: {{"guidance_type": "validate_feelings", "text": "short suggestion for the viewer only—use 'you', never the sender's name"}}
- If rephrase would help: {{"guidance_type": "rephrase_that", "text": "short explanation for the viewer", "suggested_phrase": "the EXACT words the viewer could type in the message box (only the rephrased sentence, no preamble)"}}
- If breathing break would help: {{"guidance_type": "breathing_break", "text": "short suggestion for the viewer"}}
- If a general analysis would help: {{"guidance_type": "analysis", "text": "short note to the viewer about the direction Kai hopes the conversation can go (e.g. naming feelings, hearing each other, one small step)—use 'you', never the sender's name"}}"""

    raw_response = _generate_text(prompt, MODEL_ID, llm_service, gemini_api_key)
    if not raw_response:
        return GuidanceResult()
    try:
        text = raw_response
        if "```json" in text:
            text = text.split("```json")[-1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        data = json.loads(text)
        gtype = data.get("guidance_type")
        if gtype is None or gtype == "null":
            return GuidanceResult(debug_prompt=prompt, debug_response=raw_response)
        allowed = ("validate_feelings", "rephrase_that", "breathing_break", "analysis")
        if gtype not in allowed:
            return GuidanceResult(debug_prompt=prompt, debug_response=raw_response)
        suggested_phrase = data.get("suggested_phrase") if isinstance(data.get("suggested_phrase"), str) else None
        if suggested_phrase:
            suggested_phrase = suggested_phrase.strip() or None
        return GuidanceResult(
            guidance_type=gtype,
            text=data.get("text") if isinstance(data.get("text"), str) else None,
            suggested_phrase=suggested_phrase,
            debug_prompt=prompt,
            debug_response=raw_response,
        )
    except Exception as e:
        logger.warning("Kai get_guidance failed: %s", e)
        return GuidanceResult()


def reply_public_solo(
    user_message: str,
    recent_messages: list[dict],
    kai_summary: Optional[str],
    loved_ones: list[dict],
    gemini_api_key: Optional[str],
    debug: bool = False,
    *,
    user_preferences_text: Optional[str] = None,
    compass_profile_text: Optional[str] = None,
    conversation_goal: Optional[str] = None,
    llm_service: Optional[Any] = None,
) -> ReplyPublicSoloResult:
    """When the user is alone in the chat group, generate Kai's supportive reply in the public thread."""

    names_list = ", ".join((lo.get("display_name") or lo.get("user_id", "")) for lo in (loved_ones or []))
    thread = format_message_history(recent_messages, limit=15, include_elapsed=True)

    system = _get_lounge_with_single_user_system_prompt()
    prompt = f"""{system}

---
Task: Solo reply. The user is the only person in this Lounge group. You reply as their conversational partner in the **public** thread (visible to anyone who joins). Be supportive, warm, and brief (1-3 sentences). If they mentioned a loved one and it would make sense to bring them into the chat, you may suggest inviting that person; otherwise do not suggest an invite.

Recent messages (newest at bottom):
{thread or '(none)'}

Kai context: {kai_summary or 'None'}
User's stated goal for this conversation (if any): {conversation_goal or 'None'}
User profile (from Compass): {compass_profile_text or 'None'}
User's stated preferences and feedback (honor these): {user_preferences_text or 'None'}

User's latest message: "{user_message}"

Loved ones the user can invite (names only): {names_list or 'None'}

Output: Reply with JSON only, no other text.
{{"reply": "Your supportive reply (plain text, 1-3 sentences).", "suggest_invite_display_name": "Exact display name from the list above to suggest inviting, or null"}}"""

    raw_response = _generate_text(prompt, MODEL_ID, llm_service, gemini_api_key)
    if not raw_response:
        return ReplyPublicSoloResult()
    try:
        text = raw_response
        if "```json" in text:
            text = text.split("```json")[-1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        data = json.loads(text)
        reply = data.get("reply") if isinstance(data.get("reply"), str) else None
        suggest = data.get("suggest_invite_display_name")
        if suggest is not None and not isinstance(suggest, str):
            suggest = None
        elif suggest:
            suggest = suggest.strip() or None
        return ReplyPublicSoloResult(
            reply=reply,
            suggest_invite_display_name=suggest,
            debug_prompt=prompt,
            debug_response=raw_response,
        )
    except Exception as e:
        logger.warning("Kai reply_public_solo failed: %s", e)
        return ReplyPublicSoloResult()


def reply_private(
    user_message: str,
    room_context_summary: Optional[str],
    gemini_api_key: Optional[str],
    *,
    user_preferences_text: Optional[str] = None,
    compass_profile_text: Optional[str] = None,
    conversation_goal: Optional[str] = None,
    recent_private_messages: Optional[list[dict]] = None,
    recent_public_messages: Optional[list[dict]] = None,
    llm_service: Optional[Any] = None,
) -> ReplyPrivateResult:
    """Generate Kai's reply to a private message (therapist-style). Uses recent_private_messages and recent_public_messages for context."""

    group_thread = format_message_history(recent_public_messages or [], limit=15, include_elapsed=True)
    group_block = (
        "Recent messages in the group chat (for context only; do not repeat in your reply):\n" + group_thread
        if group_thread.strip()
        else ""
    )

    private_thread = format_message_history(recent_private_messages or [], limit=20, include_elapsed=False)
    private_block = (
        "Recent private conversation with you (newest at bottom):\n" + private_thread + f'\n\nUser\'s latest message: "{user_message}"'
        if private_thread.strip()
        else f'User\'s private message: "{user_message}"'
    )

    system = _get_lounge_with_single_user_system_prompt()
    prompt = f"""{system}

---
Task: Private reply (private chat with Kai). The user is talking to you in the **private** thread—only they and you see this. **Focus on the topic and situation from the group chat** (the original context): what is being discussed there, what the user is struggling with or wants to improve. Your job is to **help them improve their current situation in the current moment**—offer reflection, validation, or a concrete next step they can take right now (e.g. how to phrase something, how to calm down before replying, one small action). Use the group chat and their private thread for context; do not repeat group content verbatim. Keep replies brief (1-3 sentences). Do not diagnose; stay grounded in the here-and-now.

Optional summary of the group chat (for awareness): {room_context_summary or 'None'}
{group_block + chr(10) * 2 if group_block else ""}User's stated goal for this conversation (if any): {conversation_goal or 'None'}
User profile (from Compass): {compass_profile_text or 'None'}
User's stated preferences and feedback (honor these): {user_preferences_text or 'None'}

{private_block}

Output: Plain text only, no JSON. Your reply (1-3 sentences)."""

    raw_response = _generate_text(prompt, MODEL_ID, llm_service, gemini_api_key)
    return ReplyPrivateResult(
        reply=raw_response or None,
        debug_prompt=prompt,
        debug_response=raw_response or None,
    )


def extract_user_preferences(
    user_message: str,
    visibility: str,
    gemini_api_key: Optional[str],
    *,
    llm_service: Optional[Any] = None,
) -> list[dict[str, Any]]:
    """Detect if the message contains feedback for Kai, preference, or personal information."""
    system = _get_lounge_system_prompt()
    prompt = f"""{system}

---
Task: Extract preferences. The user sent this message in a {"private" if visibility == "private" else "public"} Lounge chat. Detect if it contains (1) feedback for Kai (e.g. how Kai should respond), (2) a preference about how the user wants Kai to assist them, or (3) personal information the user is sharing. If yes, extract each as a short phrase; if no, return an empty array.

User message: "{user_message}"

Output: Reply with JSON only—an array of objects, each with "kind" (exactly one of "feedback", "preference", "personal_info") and "content" (short extracted phrase). Example: [{{"kind": "preference", "content": "I prefer direct feedback"}}]. If nothing to extract: []"""

    text = _generate_text(prompt, MODEL_ID, llm_service, gemini_api_key)
    if not text:
        return []
    try:
        if "```json" in text:
            text = text.split("```json")[-1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        data = json.loads(text)
        if not isinstance(data, list):
            return []
        out: list[dict[str, Any]] = []
        allowed_kinds = ("feedback", "preference", "personal_info")
        for item in data:
            if not isinstance(item, dict):
                continue
            kind = item.get("kind")
            content = item.get("content")
            if kind in allowed_kinds and isinstance(content, str) and content.strip():
                out.append({"kind": kind, "content": content.strip()})
        return out
    except Exception as e:
        logger.warning("Kai extract_user_preferences failed: %s", e)
        return []


def generate_activity_recommendations(
    compass_context_text: str,
    member_list: List[dict],
    duration_max_minutes: Optional[int],
    limit: int,
    gemini_api_key: Optional[str],
    *,
    exclude_activity_titles: Optional[List[str]] = None,
    query: Optional[str] = None,
    llm_service: Optional[Any] = None,
) -> List[dict]:
    """
    Generate activity recommendations via Gemini using Compass context. Returns list of dicts with
    title, description, recommendation_rationale, estimated_minutes, recommended_location,
    recommended_invitee_name, vibe_tags (no id; caller persists).
    """
    if llm_service is None and (not gemini_api_key or not gemini_api_key.strip()):
        return []

    member_names = [m.get("name") or m.get("id", "") for m in (member_list or []) if m]
    first_member_name = member_names[0] if member_names else "Someone"
    from app.domain.activity.seed_examples import SEED_EXAMPLE_ACTIVITIES
    example_activities = []
    for ex in SEED_EXAMPLE_ACTIVITIES[:3]:
        ex_copy = dict(ex)
        if (ex_copy.get("recommended_invitee_name") or "").strip().lower() == "partner":
            ex_copy["recommended_invitee_name"] = first_member_name
        example_activities.append(ex_copy)
    examples_json = json.dumps(example_activities, indent=2)
    query_line = (
        f"The user is asking for activities that match: {query.strip()}. Focus suggestions on this theme while still being diverse."
        if query and (query or "").strip()
        else ""
    )

    prompt = f"""You are a creative relationship coach suggesting fun, memorable activities that look like they come from "the adventure challenge book". They need to be interesting, executable, creative for a user and their loved one(s). Be playful, warm, and a little surprising—avoid generic or boring ideas. Use the context below to personalize so activities feel tailored to their interests, personalities, and relationship.

Important: The people in this relationship might not know each other yet. Do not assume they have shared history, inside jokes, or that they have met before. Suggest activities that work for people who are getting to know each other as well as for established pairs.

Tone: Creative and fun. Mix cozy, silly, adventurous, and tender. Titles can be catchy or whimsical. Descriptions should make the activity sound appealing, doable and logical. Rationales should feel specific to one or more individuals mentioned, serve to bring them closer, solving their problems if any.

Context:
{compass_context_text}
{query_line}

Generate exactly {min(limit, 10)} activities. Be as diverse as possible: vary vibes (silly, nostalgic, intimate, calm, repair, creative, family), settings (indoor/outdoor, short/long), and energy (cozy, active, thoughtful). Include at least one cozy, one playful/silly, and one that gets them moving or out of the house when the context supports it. Return ONLY a valid JSON array, no markdown or extra text. Each object must have:
- title (string) — catchy, specific, inviting
- description (string, 2-3 sentences) — concrete steps and a bit of warmth
- recommendation_rationale (string, short "why we suggest this" for this user/loved one — specific to their interests or dynamic, not generic)
- estimated_minutes (number)
- recommended_location (string: specific places—e.g. kitchen, living room, backyard, park, cafe, bedroom—not just "indoor" or "outdoor")
- recommended_invitee_name (string, must be exactly one of: {json.dumps(member_names) if member_names else '["Someone"]'})
- vibe_tags (array of strings) — 2–4 tags for the mood/vibe. Use only these exact values: silly, nostalgic, intimate, calm, repair, creative, family

Examples of the desired format:
{examples_json}"""

    text = _generate_text(prompt, MODEL_ID, llm_service, gemini_api_key)
    if not text:
        return []
    try:
        if text.startswith("```json"):
            text = text.replace("```json", "").replace("```", "").strip()
        elif text.startswith("```"):
            text = text.replace("```", "").strip()
        data = json.loads(text)
        if not isinstance(data, list):
            return []
        out = []
        required = {"title", "description", "recommendation_rationale", "estimated_minutes", "recommended_location", "recommended_invitee_name"}
        allowed_vibes = {"silly", "nostalgic", "intimate", "calm", "repair", "creative", "family"}
        for item in data[:limit]:
            if not isinstance(item, dict):
                continue
            if not required.issubset(item.keys()):
                continue
            try:
                estimated_min = int(item["estimated_minutes"]) if item["estimated_minutes"] is not None else 30
                location = str(item["recommended_location"]).strip() or "any"
                invitee_name = str(item["recommended_invitee_name"]).strip() or (member_names[0] if member_names else "Someone")
                rationale = str(item["recommendation_rationale"]).strip() or "Recommended for your relationship."
                title = str(item["title"]).strip() or "Activity"
                description = str(item["description"]).strip() or ""
                raw_vibe = item.get("vibe_tags")
                if isinstance(raw_vibe, list) and raw_vibe:
                    vibe_tags = [str(t).strip().lower() for t in raw_vibe[:5] if t and str(t).strip().lower() in allowed_vibes]
                else:
                    vibe_tags = ["calm"]
                out.append({
                    "title": title,
                    "description": description,
                    "recommendation_rationale": rationale,
                    "estimated_minutes": estimated_min,
                    "recommended_location": location,
                    "recommended_invitee_name": invitee_name,
                    "vibe_tags": vibe_tags,
                })
            except (TypeError, ValueError):
                continue
        return out
    except Exception as e:
        logger.warning("Kai generate_activity_recommendations failed: %s", e)
        return []


def detect_lounge_intention(
    recent_messages: list[dict],
    latest_message: str,
    kai_summary: Optional[str],
    gemini_api_key: Optional[str],
    *,
    llm_service: Optional[Any] = None,
) -> dict:
    """
    Classify whether the sender is expressing (1) wanting to spend time together / do something together,
    or (2) wanting to repair or offer an amendment. Returns dict with suggest_activities, activity_query, suggest_vouchers.
    """
    if llm_service is None and (not gemini_api_key or not gemini_api_key.strip()):
        return {"suggest_activities": False, "activity_query": None, "suggest_vouchers": False}

    thread = format_message_history(recent_messages, limit=10, include_elapsed=False)
    prompt = f"""You are Kai, a relationship coach. Given the latest message in a group chat and recent context, classify the sender's intention.

Recent messages (newest at bottom):
{thread or '(none)'}

Latest message from the sender: "{latest_message or ''}"

Kai context (if any): {kai_summary or 'None'}

Reply with JSON only. No other text.
- suggest_activities: true if the sender is expressing wanting to spend time together, do something together, or similar (e.g. "we should do something", "let's hang out", "I want to do something with you"). Otherwise false.
- activity_query: if suggest_activities is true, a short query for what kind of activities (e.g. "something to do together", "date ideas", "reconnection"). Otherwise null.
- suggest_vouchers: true if the sender is expressing wanting to repair the relationship, offer an amendment, or make it up to the other person (e.g. "I want to make it up to you", "how can I fix this", "I'd like to offer something"). Otherwise false.

Example: {{"suggest_activities": true, "activity_query": "something to do together", "suggest_vouchers": false}}
Example: {{"suggest_activities": false, "activity_query": null, "suggest_vouchers": true}}"""

    text = _generate_text(prompt, MODEL_ID, llm_service, gemini_api_key)
    if not text:
        return {"suggest_activities": False, "activity_query": None, "suggest_vouchers": False}
    try:
        if "```json" in text:
            text = text.split("```json")[-1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        data = json.loads(text)
        suggest_activities = bool(data.get("suggest_activities"))
        activity_query = data.get("activity_query")
        if activity_query is not None and not isinstance(activity_query, str):
            activity_query = None
        if activity_query:
            activity_query = (activity_query or "").strip() or None
        suggest_vouchers = bool(data.get("suggest_vouchers"))
        return {
            "suggest_activities": suggest_activities,
            "activity_query": activity_query or ("something to do together" if suggest_activities else None),
            "suggest_vouchers": suggest_vouchers,
        }
    except Exception as e:
        logger.warning("Kai detect_lounge_intention failed: %s", e)
        return {"suggest_activities": False, "activity_query": None, "suggest_vouchers": False}


def generate_repair_vouchers(
    compass_context_text: str,
    member_list: List[dict],
    limit: int,
    gemini_api_key: Optional[str],
    *,
    llm_service: Optional[Any] = None,
) -> List[dict]:
    """
    Generate simple repair/amendment vouchers (promises one partner can offer the other).
    Returns list of dicts with title and description; no estimated_minutes or activity schema.
    """
    if llm_service is None and (not gemini_api_key or not gemini_api_key.strip()):
        return []

    member_names = [m.get("name") or m.get("id", "") for m in (member_list or []) if m]
    prompt = f"""You are a relationship coach. Suggest simple, concrete promises ("vouchers") that one person can offer to the other to repair the relationship or make an amendment—e.g. "I'll make dinner Tuesday", "I'll plan a surprise date", "I'll listen without interrupting for 10 minutes", "I'll take the kids so you can have an hour to yourself". Use the context below to personalize. Keep each voucher short and doable.

Context:
{compass_context_text}

The people in this relationship: {json.dumps(member_names) if member_names else "two partners"}

Generate exactly {min(limit, 8)} vouchers. Return ONLY a valid JSON array. Each object must have:
- title (string) — short label, e.g. "Make dinner"
- description (string) — the exact promise they could offer, 1 sentence

Example: [{{"title": "Make dinner", "description": "I'll make dinner on Tuesday so you can relax."}}, {{"title": "Plan a date", "description": "I'll plan a surprise date for us this weekend."}}]"""

    text = _generate_text(prompt, MODEL_ID, llm_service, gemini_api_key)
    if not text:
        return []
    try:
        if "```json" in text:
            text = text.split("```json")[-1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        data = json.loads(text)
        if not isinstance(data, list):
            return []
        out = []
        for item in data[:limit]:
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or "").strip() or None
            description = (item.get("description") or "").strip() or None
            if title and description:
                out.append({"title": title, "description": description})
        return out
    except Exception as e:
        logger.warning("Kai generate_repair_vouchers failed: %s", e)
        return []


def generate_love_map_questions_for_profile(
    observer_id: str,
    subject_id: str,
    compass_profile_subject_text: str,
    tier: int,
    gemini_api_key: Optional[str],
    *,
    existing_prompt_ids: Optional[List[str]] = None,
    subject_display_name: Optional[str] = None,
    llm_service: Optional[Any] = None,
) -> List[dict]:
    """
    Generate love map questions to confirm or fill gaps in the Compass profile for the subject.
    Returns list of dicts with question_template, input_prompt, category (and optionally prompt_id).
    """
    if llm_service is None and (not gemini_api_key or not gemini_api_key.strip()):
        return []

    name_placeholder = (subject_display_name or "your partner").strip() or "your partner"
    existing_note = ""
    if existing_prompt_ids:
        existing_note = f" Avoid suggesting questions that duplicate these prompt IDs: {', '.join(existing_prompt_ids[:20])}."

    prompt = f"""You are Kai, a relationship coach helping build a "love map" — knowledge about a person's inner world. We have a profile (from Compass) for the person we are asking about (the "subject"). Your job is to suggest 3–5 short question prompts that would help confirm or fill gaps in that profile. The observer (e.g. partner) will answer these questions about the subject, or the subject will answer about themselves.

Profile of the subject (from Compass):
{compass_profile_subject_text or 'None'}

Tier (depth): {tier}. Lower tiers = lighter questions; higher tiers = deeper.

Suggest questions that:
1. Confirm or correct what we think we know from the profile.
2. Fill clear gaps (e.g. we know hobbies but not what helps them feel safe when stressed).
3. Consider any "Unconfirmed hypotheses" and "Things we want to find out" listed in the profile when suggesting questions.
4. Use [NAME] as placeholder where the subject's name should go (we will substitute "{name_placeholder}").
5. Are one short sentence each, suitable as quiz/prompt text.{existing_note}

Return ONLY a valid JSON array. Each object must have:
- question_template (string) — e.g. "What helps [NAME] feel safe when stressed?"
- input_prompt (string) — optional longer prompt for the answerer; can be same as question_template.
- category (string) — e.g. "stress", "love_language", "values", "hobbies", "boundaries"

Example: [{{"question_template": "What helps [NAME] feel safe when stressed?", "input_prompt": "What helps [NAME] feel safe when stressed?", "category": "stress"}}]
No other text."""

    text = _generate_text(prompt, MODEL_ID, llm_service, gemini_api_key)
    if not text:
        return []
    try:
        if "```json" in text:
            text = text.split("```json")[-1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        data = json.loads(text)
        if not isinstance(data, list):
            return []
        out = []
        for item in data[:10]:
            if not isinstance(item, dict):
                continue
            qt = item.get("question_template")
            if not isinstance(qt, str) or not qt.strip():
                continue
            out.append({
                "question_template": qt.strip(),
                "input_prompt": (item.get("input_prompt") or qt).strip() if isinstance(item.get("input_prompt"), str) else qt.strip(),
                "category": str(item.get("category") or "general").strip()[:100],
            })
        return out
    except Exception as e:
        logger.warning("Kai generate_love_map_questions_for_profile failed: %s", e)
        return []


def generate_things_to_find_out(
    compass_profile_text: str,
    gemini_api_key: Optional[str],
    *,
    limit: int = 5,
    llm_service: Optional[Any] = None,
) -> List[str]:
    """
    Generate questions Kai wants to know (to save to Compass as things to find out).
    Returns list of short question strings. Caller can post each to Compass add_thing_to_find_out.
    """
    if llm_service is None and (not gemini_api_key or not gemini_api_key.strip()):
        return []
    prompt = f"""You are Kai, a relationship coach. Based on the current user/relationship profile, suggest 1–{min(limit, 5)} short questions you would like to learn the answer to (things to find out about this person or relationship). One question per line, concise. Do not use [NAME] placeholder.

Profile (from Compass):
{compass_profile_text or 'None'}

Return ONLY a JSON array of strings, e.g. ["What helps them feel safe when stressed?", "What is their love language?"]. No other text."""

    text = _generate_text(prompt, MODEL_ID, llm_service, gemini_api_key)
    if not text:
        return []
    try:
        if "```json" in text:
            text = text.split("```json")[-1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        data = json.loads(text)
        if not isinstance(data, list):
            return []
        out = []
        for item in data[:limit]:
            if isinstance(item, str) and item.strip():
                out.append(item.strip()[:500])
        return out
    except Exception as e:
        logger.warning("Kai generate_things_to_find_out failed: %s", e)
        return []


class KaiAgentService:
    """Thin orchestration over Kai agent functions (for dependency injection in routes)."""

    def __init__(
        self,
        llm_service: Optional[Any] = None,
        gemini_api_key: Optional[str] = None,
    ):
        self.llm_service = llm_service
        self.gemini_api_key = (gemini_api_key or "").strip() or None

    def update_context(
        self,
        recent_messages: list[dict],
        existing_summary: Optional[str],
        existing_facts: Optional[dict],
    ) -> tuple[Optional[str], Optional[dict]]:
        return update_context(
            recent_messages, existing_summary, existing_facts, self.gemini_api_key,
            llm_service=self.llm_service,
        )

    def vet_message(
        self,
        draft: str,
        recent_messages: list[dict],
        kai_summary: Optional[str],
        *,
        sender_name: Optional[str] = None,
        other_sensitivity: Optional[str] = None,
        tension_level: Optional[str] = None,
        user_preferences_text: Optional[str] = None,
        compass_profile_text: Optional[str] = None,
        conversation_goal: Optional[str] = None,
    ) -> VetResult:
        return vet_message(
            draft,
            recent_messages,
            kai_summary,
            self.gemini_api_key,
            sender_name=sender_name,
            other_sensitivity=other_sensitivity,
            tension_level=tension_level,
            user_preferences_text=user_preferences_text,
            compass_profile_text=compass_profile_text,
            conversation_goal=conversation_goal,
            llm_service=self.llm_service,
        )

    def get_guidance(
        self,
        recent_messages: list[dict],
        latest_from_other: Optional[str],
        kai_summary: Optional[str],
        *,
        user_preferences_text: Optional[str] = None,
        compass_profile_text: Optional[str] = None,
        conversation_goal: Optional[str] = None,
        viewer_display_name: Optional[str] = None,
    ) -> GuidanceResult:
        return get_guidance(
            recent_messages, latest_from_other, kai_summary, self.gemini_api_key,
            user_preferences_text=user_preferences_text,
            compass_profile_text=compass_profile_text,
            conversation_goal=conversation_goal,
            viewer_display_name=viewer_display_name,
            llm_service=self.llm_service,
        )

    def reply_public_solo(
        self,
        user_message: str,
        recent_messages: list[dict],
        kai_summary: Optional[str],
        loved_ones: list[dict],
        debug: bool = False,
        *,
        user_preferences_text: Optional[str] = None,
        compass_profile_text: Optional[str] = None,
        conversation_goal: Optional[str] = None,
    ) -> ReplyPublicSoloResult:
        return reply_public_solo(
            user_message, recent_messages, kai_summary, loved_ones, self.gemini_api_key, debug,
            user_preferences_text=user_preferences_text,
            compass_profile_text=compass_profile_text,
            conversation_goal=conversation_goal,
            llm_service=self.llm_service,
        )

    def reply_private(
        self,
        user_message: str,
        room_context_summary: Optional[str],
        *,
        user_preferences_text: Optional[str] = None,
        compass_profile_text: Optional[str] = None,
        conversation_goal: Optional[str] = None,
        recent_private_messages: Optional[list[dict]] = None,
        recent_public_messages: Optional[list[dict]] = None,
    ) -> ReplyPrivateResult:
        return reply_private(
            user_message, room_context_summary, self.gemini_api_key,
            user_preferences_text=user_preferences_text,
            compass_profile_text=compass_profile_text,
            conversation_goal=conversation_goal,
            recent_private_messages=recent_private_messages,
            recent_public_messages=recent_public_messages,
            llm_service=self.llm_service,
        )

    def extract_user_preferences(
        self,
        user_message: str,
        visibility: str,
    ) -> list[dict[str, Any]]:
        return extract_user_preferences(
            user_message, visibility, self.gemini_api_key,
            llm_service=self.llm_service,
        )
