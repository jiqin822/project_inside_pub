"""Activity domain: suggestions (LLM + seed), scrapbook layout/options/html, sticker generator."""
import json
import logging
import re
from io import BytesIO
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.domain.common.types import generate_id
from app.domain.compass.models import USE_CASE_ACTIVITIES
from app.domain.activity.seed_examples import SEED_EXAMPLE_ACTIVITIES

logger = logging.getLogger(__name__)


class ActivitySuggestionService:
    """
    Generate activity recommendations (LLM or seed fallback).
    Depends on a compass context provider for build_context_bundle and _build_llm_context_text.
    """

    def __init__(self, activity_template_repo: Any, context_provider: Any):
        self.activity_template_repo = activity_template_repo
        self.context_provider = context_provider

    async def generate_activities_llm(
        self,
        actor_user_id: str,
        relationship_id: str,
        limit: int,
        duration_max_minutes: Optional[int],
        partner_portrait: Optional[Any],
        member_list: List[Dict[str, str]],
        gemini_api_key: Optional[str],
        include_debug: bool = False,
        actor_profile: Optional[Dict[str, Any]] = None,
        partner_profiles: Optional[List[Dict[str, Any]]] = None,
        exclude_activity_titles: Optional[List[str]] = None,
        query: Optional[str] = None,
        llm_service: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Generate activity recommendations via Gemini. Returns list of dicts; empty on failure."""
        if llm_service is None and (not gemini_api_key or not gemini_api_key.strip()):
            return []
        try:
            bundle = await self.context_provider.build_context_bundle(
                actor_user_id, relationship_id, USE_CASE_ACTIVITIES
            )
            recent_activity_titles = []
            for aid in (bundle.recent_activity_ids or [])[:20]:
                t = await self.activity_template_repo.get(aid)
                if t and getattr(t, "title", None):
                    recent_activity_titles.append(t.title)
            context_text = self.context_provider._build_llm_context_text(
                bundle,
                partner_portrait,
                member_list,
                duration_max_minutes,
                recent_activity_titles,
                actor_profile=actor_profile,
                partner_profiles=partner_profiles,
                exclude_activity_titles=exclude_activity_titles,
            )
            member_names = [m.get("name") or m.get("id", "") for m in member_list if m]
            from app.domain.kai import generate_activity_recommendations
            data = generate_activity_recommendations(
                compass_context_text=context_text,
                member_list=member_list,
                duration_max_minutes=duration_max_minutes,
                limit=limit,
                gemini_api_key=gemini_api_key,
                exclude_activity_titles=exclude_activity_titles,
                query=query,
                llm_service=llm_service,
            )
            if not isinstance(data, list):
                return []
            out = []
            for i, item in enumerate(data[:limit]):
                if not isinstance(item, dict):
                    continue
                try:
                    activity_id = generate_id()
                    estimated_min = int(item["estimated_minutes"]) if item["estimated_minutes"] is not None else 30
                    location = str(item["recommended_location"]).strip() or "any"
                    invitee_name = str(item["recommended_invitee_name"]).strip() or (member_names[0] if member_names else "Someone")
                    rationale = str(item["recommendation_rationale"]).strip() or "Recommended for your relationship."
                    title = str(item["title"]).strip() or "Activity"
                    description = str(item["description"]).strip() or ""
                    allowed_vibes = {"silly", "nostalgic", "intimate", "calm", "repair", "creative", "family"}
                    raw_vibe = item.get("vibe_tags")
                    if isinstance(raw_vibe, list) and raw_vibe:
                        vibe_tags = [str(t).strip().lower() for t in raw_vibe[:5] if t and str(t).strip().lower() in allowed_vibes]
                    else:
                        vibe_tags = []
                    if not vibe_tags:
                        vibe_tags = ["calm"]

                    await self.activity_template_repo.create(
                        activity_id=activity_id,
                        title=title,
                        relationship_types=["partner"],
                        vibe_tags=vibe_tags,
                        constraints={"duration_min": estimated_min, "location": location},
                        steps_markdown_template=description,
                        personalization_slots={
                            "source": "llm",
                            "recommended_for_relationship_id": relationship_id,
                            "recommended_for_actor_user_id": actor_user_id,
                            "recommended_invitee_name": invitee_name,
                            "recommendation_rationale": rationale,
                        },
                        is_active=True,
                    )

                    item_out = {
                        "id": activity_id,
                        "title": title,
                        "description": description,
                        "recommendation_rationale": rationale,
                        "estimated_minutes": estimated_min,
                        "recommended_location": location,
                        "recommended_invitee_name": invitee_name,
                        "vibe_tags": vibe_tags,
                    }
                    if include_debug:
                        item_out["llm_prompt"] = None
                        item_out["llm_response"] = None
                    out.append(item_out)
                except (TypeError, ValueError):
                    continue
            return out
        except Exception as e:
            logger.warning("generate_activities_llm failed (seed fallback will be used): %s", e, exc_info=True)
            return []

    async def generate_activities_llm_stream(
        self,
        actor_user_id: str,
        relationship_id: str,
        limit: int,
        duration_max_minutes: Optional[int],
        partner_portrait: Optional[Any],
        member_list: List[Dict[str, str]],
        gemini_api_key: Optional[str],
        include_debug: bool = False,
        actor_profile: Optional[Dict[str, Any]] = None,
        partner_profiles: Optional[List[Dict[str, Any]]] = None,
        exclude_activity_titles: Optional[List[str]] = None,
        query: Optional[str] = None,
        llm_service: Optional[Any] = None,
    ):
        """Async generator: stream LLM-generated activities one-by-one (NDJSON)."""
        if llm_service is None and (not gemini_api_key or not gemini_api_key.strip()):
            return
        bundle = await self.context_provider.build_context_bundle(
            actor_user_id, relationship_id, USE_CASE_ACTIVITIES
        )
        recent_activity_titles = []
        for aid in (bundle.recent_activity_ids or [])[:20]:
            t = await self.activity_template_repo.get(aid)
            if t and getattr(t, "title", None):
                recent_activity_titles.append(t.title)
        context_text = self.context_provider._build_llm_context_text(
            bundle,
            partner_portrait,
            member_list,
            duration_max_minutes,
            recent_activity_titles,
            actor_profile=actor_profile,
            partner_profiles=partner_profiles,
            exclude_activity_titles=exclude_activity_titles,
        )
        member_names = [m.get("name") or m.get("id", "") for m in member_list if m]
        first_member_name = member_names[0] if member_names else "Someone"
        query_line = (
            f"The user is asking for activities that match: {query.strip()}. Focus suggestions on this theme while still being diverse.\n\n"
            if query and (query or "").strip()
            else ""
        )
        stream_prompt = f"""You are a creative relationship coach suggesting fun, memorable activities for a user and their loved one(s). Be playful, warm, and a little surprising. Use the context below to personalize.

Important: The people in this relationship might not know each other yet. Do not assume they have shared history, inside jokes, or that they have met before. Suggest activities that work for people who are getting to know each other as well as for established pairs.

Context:
{context_text}
{query_line}Generate exactly {min(limit, 10)} activities. Output one JSON object per line (newline-delimited JSON, NDJSON). Each line must be exactly one complete activity object—no outer array, no markdown, no commas between lines. Each object must have: title, description, recommendation_rationale, estimated_minutes, recommended_location, recommended_invitee_name (exactly one of {json.dumps(member_names) if member_names else '["Someone"]'}), vibe_tags (array, use only: silly, nostalgic, intimate, calm, repair, creative, family).

Example (one object per line):
{{"title": "Cooking blindfolded", "description": "...", "recommendation_rationale": "...", "estimated_minutes": 30, "recommended_location": "kitchen", "recommended_invitee_name": "{first_member_name}", "vibe_tags": ["silly", "creative"]}}
{{"title": "Blanket fort night", "description": "...", "recommendation_rationale": "...", "estimated_minutes": 60, "recommended_location": "living room", "recommended_invitee_name": "{first_member_name}", "vibe_tags": ["calm", "family"]}}
"""
        if llm_service is not None:
            text = (await llm_service.generate_text_async(stream_prompt, model="gemini-2.0-flash")) or ""
        else:
            try:
                import google.genai as genai
            except (ImportError, ModuleNotFoundError):
                return
            try:
                client = genai.Client(api_key=gemini_api_key)
                response = await client.aio.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=stream_prompt,
                )
                raw_text = (response.text or "") if response else ""
            except Exception as e:
                logger.warning("generate_activities_llm_stream: generate_content failed: %s", e)
                return
            text = raw_text.strip()
        text = (text or "").strip()
        if not text:
            return
        required = {"title", "description", "recommendation_rationale", "estimated_minutes", "recommended_location", "recommended_invitee_name"}
        allowed_vibes = {"silly", "nostalgic", "intimate", "calm", "repair", "creative", "family"}
        count = 0
        for line in text.split("\n"):
            line = line.strip()
            if not line or line in ("[", "]", ","):
                continue
            if line.endswith(","):
                line = line[:-1].strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict) or not required.issubset(item.keys()):
                continue
            if count >= limit:
                break
            try:
                activity_id = generate_id()
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
                    vibe_tags = []
                if not vibe_tags:
                    vibe_tags = ["calm"]
                await self.activity_template_repo.create(
                    activity_id=activity_id,
                    title=title,
                    relationship_types=["partner"],
                    vibe_tags=vibe_tags,
                    constraints={"duration_min": estimated_min, "location": location},
                    steps_markdown_template=description,
                    personalization_slots={
                        "source": "llm",
                        "recommended_for_relationship_id": relationship_id,
                        "recommended_for_actor_user_id": actor_user_id,
                        "recommended_invitee_name": invitee_name,
                        "recommendation_rationale": rationale,
                    },
                    is_active=True,
                )
                item_out = {
                    "id": activity_id,
                    "title": title,
                    "description": description,
                    "recommendation_rationale": rationale,
                    "estimated_minutes": estimated_min,
                    "recommended_location": location,
                    "recommended_invitee_name": invitee_name,
                    "vibe_tags": vibe_tags,
                }
                if include_debug:
                    item_out["llm_prompt"] = stream_prompt
                    item_out["llm_response"] = line
                count += 1
                yield item_out
            except (TypeError, ValueError):
                continue


# ---- Scrapbook (layout, options, html, sticker) ----

async def generate_scrapbook_layout(
    gemini_api_key: Optional[str],
    activity_title: str,
    note: str,
    feeling: Optional[str],
    image_count: int,
    *,
    llm_service: Optional[Any] = None,
) -> Dict[str, Any]:
    """Generate scrapbook layout dict (themeColor, headline, narrative, stickers, imageCaptions, style)."""
    fallback = {
        "themeColor": "#f8fafc",
        "secondaryColor": "#1e293b",
        "narrative": note or "A moment worth remembering.",
        "headline": activity_title or "Memory",
        "stickers": ["✨"],
        "imageCaptions": ["Lovely moment"] * max(0, image_count),
        "style": "classic",
    }
    if llm_service is None and (not gemini_api_key or not gemini_api_key.strip()):
        return fallback
    prompt = f"""Act as a creative Digital Scrapbook Artist.

**Task**: Design a stylish, chaotic, and aesthetic scrapbook page for a relationship memory. Output a structured layout (JSON) that can be rendered like a digital scrapbook.

**Content Context**:
- Note: "{note or 'No note'}"
- Activity: "{activity_title or 'Activity'}"
- Mood: "{feeling or 'Unknown'}"
- Number of User Photos: {image_count}

**Design Requirements (CSS-IRL style)**:
1. **Layout**: Use a grid-like composition (polaroid-style photos, overlapping elements, rotated items).
2. **Aesthetic**: Overlapping elements, paper textures, "taped" photos. Light, textured paper feel. Photos should feel like polaroids (white border, soft shadow).
3. **Typography**: Handwriting / playful fonts for headlines and captions.
4. **Stickers**: Include 3-5 emojis or small decorative elements matching the vibe.

Respond with a single JSON object (no markdown, no code block) with exactly these keys:
- themeColor: string (hex color for background, pastel or aesthetic paper tone)
- secondaryColor: string (hex for accents and text)
- narrative: string (2-3 sentence warm rewrite of the note, first person)
- headline: string (short catchy title)
- stickers: array of 3-5 strings (emojis matching the vibe)
- imageCaptions: array of {image_count} strings (3-5 word caption per image)
- style: string, one of "polaroid", "classic", "minimal"
"""
    if llm_service is not None:
        text = (llm_service.generate_text(prompt, model="gemini-2.0-flash") or "").strip()
    else:
        try:
            import google.genai as genai
        except (ImportError, ModuleNotFoundError):
            return fallback
        try:
            client = genai.Client(api_key=gemini_api_key)
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            text = (response.text or "").strip()
        except Exception as e:
            logger.warning("generate_scrapbook_layout failed: %s", e)
            return fallback
    if not text:
        return fallback
    try:
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        data = json.loads(text)
        if not isinstance(data, dict):
            return fallback
        theme_color = str(data.get("themeColor") or fallback["themeColor"]).strip() or fallback["themeColor"]
        secondary = str(data.get("secondaryColor") or fallback["secondaryColor"]).strip() or fallback["secondaryColor"]
        narrative = str(data.get("narrative") or fallback["narrative"]).strip() or fallback["narrative"]
        headline = str(data.get("headline") or fallback["headline"]).strip() or fallback["headline"]
        raw_stickers = data.get("stickers")
        stickers = [str(s).strip() for s in raw_stickers[:10] if s] if isinstance(raw_stickers, list) else fallback["stickers"]
        if not stickers:
            stickers = fallback["stickers"]
        raw_captions = data.get("imageCaptions")
        if isinstance(raw_captions, list) and len(raw_captions) >= image_count:
            image_captions = [str(c).strip() or "Lovely moment" for c in raw_captions[:image_count]]
        else:
            image_captions = ["Lovely moment"] * max(0, image_count)
        style = str(data.get("style") or "classic").strip().lower()
        if style not in ("polaroid", "classic", "minimal"):
            style = "classic"
        return {
            "themeColor": theme_color,
            "secondaryColor": secondary,
            "narrative": narrative,
            "headline": headline,
            "stickers": stickers,
            "imageCaptions": image_captions,
            "style": style,
        }
    except Exception as e:
        logger.warning("generate_scrapbook_layout failed: %s", e)
        return fallback


def _resize_sticker_b64(b64: str, width: int, height: int) -> Optional[str]:
    """Resize a base64 PNG to width x height; return base64 string or None."""
    import base64
    try:
        from PIL import Image
    except ImportError:
        return b64
    try:
        raw = base64.b64decode(b64)
        img = Image.open(BytesIO(raw)).convert("RGBA")
        img = img.resize((width, height), Image.Resampling.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as e:
        logger.debug("_resize_sticker_b64 failed: %s", e)
        return b64


def _sticker_prompt_for(description: str) -> str:
    """Build the die-cut sticker image prompt for scrapbook stickers."""
    return f"""Generate a die-cut sticker of: {description} on a transparent background.
REQUIREMENTS:
1. Subject must be surrounded by a THICK WHITE BORDER (die-cut style).
2. Background MUST be transparent. Do NOT render a checkerboard pattern.
3. Style: Vector art, cute, vibrant colors, high quality, sticker art.

**Sticker output requirements (critical)**:
- Generate each sticker as a **PNG with transparent background (alpha)**.
- No white/solid rectangle, no filled background, no border.
- Tightly cropped around the subject (minimal padding).
- No baked-in drop shadow (CSS will add shadows).
- If transparent background is not possible, output on a **pure chroma key background** `#00FF00` (solid, uniform), with the subject not touching the edges.
"""


def make_sticker_generator(
    image_generator: Callable[[str, Tuple[int, int]], Optional[str]],
) -> Callable[[str, Tuple[int, int]], Optional[str]]:
    """Wrap a generic image generator into a sticker generator (description, output_size) -> base64 PNG or None."""

    def sticker_generator(description: str, output_size: Tuple[int, int]) -> Optional[str]:
        prompt = _sticker_prompt_for(description)
        b64 = image_generator(prompt, output_size)
        if not b64:
            return None
        w, h = output_size
        if (w, h) != (1024, 1024):
            resized = _resize_sticker_b64(b64, w, h)
            if resized is not None:
                return resized
        return b64

    return sticker_generator


async def generate_scrapbook_html(
    activity_title: str,
    note: str,
    feeling: Optional[str],
    image_count: int,
    *,
    description: Optional[str] = None,
    vibe_tags: Optional[List[str]] = None,
    duration_min: Optional[int] = None,
    recommended_location: Optional[str] = None,
    include_debug: bool = False,
    disable_sticker_generation: bool = False,
    sticker_generator: Optional[Callable[[str, Tuple[int, int]], Optional[str]]] = None,
    layout_generator: Optional[Callable[[str, Optional[str]], Optional[str]]] = None,
) -> Dict[str, Any]:
    """Generate scrapbook layout as raw HTML via layout_generator (e.g. LLMService.generate_text). Optional sticker_generator inlines sticker images."""
    fallback_html = (
        "<div style='padding:1rem;background:#f8fafc;font-family:cursive;text-align:center;'>"
        "<h3 style='color:#1e293b;'>" + (activity_title or "Memory") + "</h3>"
        "<p style='color:#64748b;'>" + (note or "A moment worth remembering.") + "</p>"
        "</div>"
    )
    if not layout_generator or not callable(layout_generator):
        return {"htmlContent": fallback_html}

    activity_context_lines = []
    if description and description.strip():
        activity_context_lines.append(f"- Activity description / steps: \"{description.strip()[:400]}\"")
    if vibe_tags:
        tags_str = ", ".join(str(t) for t in vibe_tags[:10])
        activity_context_lines.append(f"- Vibe / tags: {tags_str}")
    if duration_min is not None:
        activity_context_lines.append(f"- Duration: {duration_min} minutes")
    if recommended_location and recommended_location.strip():
        activity_context_lines.append(f"- Suggested location: {recommended_location.strip()}")
    activity_context_block = "\n".join(activity_context_lines) if activity_context_lines else ""

    disable_sticker_block = '''2. **AI Stickers**: Do NOT include any sticker images (no <img data-sticker-prompt=...>). You may use emoji or simple text/circle decorations for small accents if desired.''' if disable_sticker_generation else r'''2. **AI Stickers**: Invent a few(2-5) cute stickers that match the context, activity description, mood, notes or photo captions (e.g. for a coffee making activity, add a coffee cup sticker).
   - To request a sticker, use this EXACT tag format:
     `<img data-sticker-prompt="cute watercolor coffee cup" class="sticker" style="..." />`
   - Optionally add `data-sticker-size="WxH"` to set the sticker pixel size (e.g. "100x100", "64x64", "128x128"). If omitted, 100x100 is used. Valid range: 32–256 per side.
   - I will parse this tag and generate the image, then inject the base64 src at the requested size.
    **Sticker output requirements (critical)**:
    - Generate each sticker as a **PNG with transparent background (alpha)**.
    - No white/solid rectangle, no filled background, no border.
    - Tightly cropped around the subject (minimal padding).
    - No baked-in drop shadow (CSS will add shadows).
    - If chroma key fallback is used, do NOT try to remove it with CSS.'''

    prompt = f"""Act as a creative and professional Digital Scrapbook Artist.

**Task**: Create a single HTML string (a `div` container) that represents a stylish, chaotic, and aesthetic scrapbook page for a relationship memory.

**Content Context**:
- Note: "{note or 'No note'}"
- Activity: "{activity_title or 'Activity'}"
- Mood: "{feeling or 'Unknown'}"
- Number of User Photos: {image_count}
{f'''
**Activity card context (use to match the scrapbook style and stickers to the activity type):**
{activity_context_block}
''' if activity_context_block else ''}

**Activity info block (required)**: Include a clearly visible block that displays the activity info (activity title, description, vibe tags, duration, suggested location) and style it **like an activity card in the app**:
- **Container**: White background, thick dark border (e.g. 2px solid #0f172a or similar dark slate), padding (e.g. 12–16px), offset box-shadow (e.g. 6px 6px 0 rgba(30,41,59,0.1)) so it looks like a card.
- **Title**: Bold, large (e.g. 1.1–1.25rem), dark color (#0f172a or #1e293b), UPPERCASE, tight letter-spacing.
- **Vibe tags**: If vibe tags are provided, show them as small pills/chips—rounded, uppercase, small font (e.g. 9px), with soft background colors (e.g. silly=amber, nostalgic=orange, intimate=rose, calm=sky, repair=emerald, creative=violet, family=teal).
- **Duration**: Small mono-style or sans text (e.g. 10px), muted color (e.g. #94a3b8), e.g. "30m" or "30 min".
- **Description**: If description is provided, show it with a left border accent (e.g. 2px solid #e2e8f0) and padding-left; text color #475569 or #64748b, small font.
- **Location**: If suggested location is provided, show it as small muted text (e.g. "Location: Kitchen").
- **Participants**: If participants are provided, show them as small muted text (e.g. "Participants: You, Partner").

**Design Requirements (CSS-IRL Style)**:
1. **Layout Engine**: Use **CSS Grid**. Create a grid (e.g., 12x12) and use `grid-column` / `grid-row` to place items.
2. **Tight fit (critical)**: Fit text and photos on the page **as tight as possible**. Use minimal padding and minimal gaps (e.g. gap: 4px–8px, padding: 6px–12px).
3. **Wrap content tightly (critical)**: Every container must **wrap its content tightly**. Use `width: max-content` or `fit-content` for text blocks; use minimal padding.
4. **Aesthetic**: Overlapping elements, rotated items (`transform: rotate()`), paper textures, and "taped" photos. Light, textured paper background.
5. **Typography**: Use Google Fonts (@import in a <style> tag). Suggested: 'Caveat', 'Gloria Hallelujah', or 'Shadows Into Light' for handwriting.
6. **Container sizing**: The outer container must SIZE TO ITS CONTENT. No fixed aspect ratio.
7. **Mobile-first, viewport-scaled (critical)**: Optimize for **vertical mobile** (portrait, ~360–430px wide). Outer container: `width: 100%; max-width: 100%; box-sizing: border-box; overflow-x: hidden;`. Prefer relative units (em, rem, %, clamp). All images: `max-width: 100%; height: auto;`.
8. **Styling**: Use inline CSS or a scoped <style> block. Give photos white border and box-shadow like polaroids. Add tape effects. **Stickers**: Use `mix-blend-mode: multiply` and `filter: drop-shadow(...)` on `.sticker`.

**Asset Placeholders**:
1. **User Photos**: You MUST include {image_count} `img` tags. Set their `src` to the exact placeholder strings (copy exactly): {{{{USER_IMAGE_0}}}}, {{{{USER_IMAGE_1}}}}, etc. (one per image; each placeholder has double curly braces on both sides).
{disable_sticker_block}

**Output**: Return ONLY the raw HTML string. Do not wrap in JSON. Do not use Markdown code blocks.
"""
    try:
        raw_text = layout_generator(prompt, "gemini-3-flash-preview") or ""
        text = raw_text.strip()
        if not text:
            return {"htmlContent": fallback_html}
        if "```" in text:
            text = text.replace("```html", "").replace("```", "").strip()

        sticker_regex_double = re.compile(
            r'<img[^>]+data-sticker-prompt="([^"]+)"[^>]*>', re.IGNORECASE
        )
        sticker_regex_single = re.compile(
            r"<img[^>]+data-sticker-prompt='([^']+)'[^>]*>", re.IGNORECASE
        )
        size_regex = re.compile(
            r'data-sticker-size=["\']?(\d+)\s*[x×]\s*(\d+)["\']?', re.IGNORECASE
        )
        def _parse_sticker_size(tag: str) -> tuple[int, int]:
            m = size_regex.search(tag)
            if not m:
                return (100, 100)
            w, h = int(m.group(1)), int(m.group(2))
            w = max(32, min(256, w))
            h = max(32, min(256, h))
            return (w, h)

        replacements = []
        seen_tags = set()
        for match in sticker_regex_double.finditer(text):
            full_tag = match.group(0)
            if full_tag not in seen_tags:
                seen_tags.add(full_tag)
                replacements.append((full_tag, match.group(1).strip(), _parse_sticker_size(full_tag)))
        for match in sticker_regex_single.finditer(text):
            full_tag = match.group(0)
            if full_tag not in seen_tags:
                seen_tags.add(full_tag)
                replacements.append((full_tag, match.group(1).strip(), _parse_sticker_size(full_tag)))

        num_found = len(replacements)
        num_injected = 0
        if disable_sticker_generation:
            for full_tag, _, _ in replacements:
                text = text.replace(full_tag, "", 1)
            if num_found:
                logger.info("Scrapbook stickers: disabled by user, %d placeholder(s) removed", num_found)
        else:
            for full_tag, sticker_prompt, output_size in replacements:
                b64 = sticker_generator(sticker_prompt, output_size) if sticker_generator else None
                if b64:
                    src_attr = f'src="data:image/png;base64,{b64}"'
                    new_tag = full_tag
                    if 'src=' in new_tag:
                        new_tag = re.sub(r'src="[^"]*"', src_attr, new_tag)
                        new_tag = re.sub(r"src='[^']*'", src_attr, new_tag)
                    else:
                        new_tag = new_tag.replace("<img ", f"<img {src_attr} ", 1)
                    new_tag = re.sub(r'data-sticker-prompt="[^"]*"', '', new_tag, flags=re.IGNORECASE)
                    new_tag = re.sub(r"data-sticker-prompt='[^']*'", '', new_tag, flags=re.IGNORECASE)
                    new_tag = re.sub(r'data-sticker-size=["\']?\d+\s*[x×]\s*\d+["\']?', '', new_tag, flags=re.IGNORECASE)
                    text = text.replace(full_tag, new_tag, 1)
                    num_injected += 1
                else:
                    text = text.replace(full_tag, "", 1)
                    logger.debug("Scrapbook sticker not inlined (generation failed): %r", sticker_prompt[:50])
            if num_found:
                logger.info("Scrapbook stickers: %d placeholders found, %d inlined", num_found, num_injected)

        out = {"htmlContent": text}
        if include_debug:
            out["prompt"] = prompt
            out["response"] = raw_text
        return out
    except Exception as e:
        logger.warning("generate_scrapbook_html failed: %s", e)
        return {"htmlContent": fallback_html}


async def generate_scrapbook_options(
    activity_title: str,
    note: str,
    feeling: Optional[str],
    image_count: int,
    limit: int = 3,
    layout_generator: Optional[Callable[[str], Optional[str]]] = None,
) -> List[Dict[str, Any]]:
    """Generate 1 or 3 scrapbook layout options (element-based: bgStyle, elements, styleName)."""
    fallback_options = _fallback_element_layouts(activity_title, note, image_count)
    if not layout_generator:
        return fallback_options
    num_layouts = max(1, min(3, limit))
    if num_layouts == 1:
        task_line = "Create 1 unique scrapbook layout that represents a stylish, chaotic, and aesthetic scrapbook page for a relationship memory."
        options_line = '"options" must be an array of exactly 1 layout object.'
        options_hint = "One layout: Collage/Chaotic or Minimal or Retro (your choice)."
    else:
        task_line = "Create 3 unique scrapbook layouts that represent a stylish, chaotic, and aesthetic scrapbook page for a relationship memory."
        options_line = '"options" must be an array of exactly 3 layout objects.'
        options_hint = "Option 1: Collage/Chaotic. Option 2: Minimal/Gallery. Option 3: Retro/Journal."
    prompt = f"""Act as a creative Frontend Developer and Digital Scrapbook Artist.

**Task**: {task_line} Each layout is a structured description (JSON) that can be rendered like a digital scrapbook with overlapping elements, rotated items, paper textures, and "taped" photos.

**Content Context**:
- Note: "{note or 'No note'}"
- Activity: "{activity_title or 'Activity'}"
- Mood: "{feeling or 'Unknown'}"
- Number of User Photos: {image_count}

**Design Requirements (CSS-IRL style)**:
1. **Layout Engine**: Use a grid-like composition; place elements with top/left/rotation so they overlap and feel hand-placed.
2. **Aesthetic**: Overlapping elements, rotated items (e.g. -5deg, 3deg), paper textures, "taped" photos. Light, textured paper background. Photos should have white border and box-shadow like polaroids. Add tape effects (small semi-transparent rectangles over corners).
3. **Typography**: Use handwriting-style or playful fonts for headlines and note snippets (e.g. Caveat, Gloria Hallelujah, Shadows Into Light feel).
4. **Stickers**: Include 2-3 cute stickers (emojis or small decorative elements) that match the context.
5. **Container**: Assume roughly 3:4 aspect ratio; elements use percentages for positioning.

Respond with a single JSON object (no markdown, no code block) with one key: "options".
{options_line} Each layout has:
- "bgStyle": {{ "color": "<hex>", "texture": "paper" | "dot-grid" | "crumpled" | "none" (optional), "pattern": "<string>" (optional) }}
- "elements": array of elements. Each element: {{ "type": "text" | "image" | "sticker" | "tape" | "doodle", "content": "<text or image index '0' '1' or emoji>", "style": {{ "top": "<e.g. 10%>", "left": "<e.g. 5%>", "width": "<% or auto>", "rotation": "<e.g. -5deg>", "zIndex": <int>, "fontSize": "<optional>", "color": "<optional>", "fontFamily": "handwritten"|"serif"|"sans"|"mono", "background": "<optional>", "borderRadius": "<optional>", "boxShadow": "<optional>", "textAlign": "left"|"center"|"right" }} }}
- "styleName": short display name (e.g. "Collage Chaos", "Minimal Gallery", "Retro Journal")

CRITICAL: Include exactly {image_count} elements of type "image" in each layout; content must be "0", "1", etc. for image indices.
Use type "text" for note snippets, "sticker" for emojis, "tape" for small colored rectangles.
{options_hint}
"""
    try:
        text = layout_generator(prompt)
        if not text:
            return fallback_options
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        data = json.loads(text)
        options = data.get("options")
        if not isinstance(options, list) or len(options) < num_layouts:
            return fallback_options[:num_layouts] if num_layouts == 1 else fallback_options
        out = []
        for opt in options[:num_layouts]:
            if not isinstance(opt, dict):
                continue
            bg = opt.get("bgStyle") or {}
            elems = opt.get("elements")
            name = str(opt.get("styleName") or "Style").strip() or "Style"
            if not isinstance(elems, list):
                continue
            out.append({
                "bgStyle": {"color": str(bg.get("color") or "#f8fafc"), "texture": bg.get("texture"), "pattern": bg.get("pattern")},
                "elements": _normalize_elements(elems),
                "styleName": name,
            })
        return out if len(out) >= num_layouts else (fallback_options[:num_layouts] if num_layouts == 1 else fallback_options)
    except Exception as e:
        logger.warning("generate_scrapbook_options failed: %s", e)
        return fallback_options


def _normalize_elements(elems: List[Any]) -> List[Dict[str, Any]]:
    normalized = []
    for el in elems:
        if not isinstance(el, dict):
            continue
        style = el.get("style") or {}
        normalized.append({
            "type": str(el.get("type") or "text").strip(),
            "content": str(el.get("content") or ""),
            "style": {
                "top": str(style.get("top") or "0%"),
                "left": str(style.get("left") or "0%"),
                "width": style.get("width"),
                "rotation": str(style.get("rotation") or "0deg"),
                "zIndex": int(style.get("zIndex", 0)),
                "fontSize": style.get("fontSize"),
                "color": style.get("color"),
                "fontFamily": style.get("fontFamily"),
                "background": style.get("background"),
                "borderRadius": style.get("borderRadius"),
                "boxShadow": style.get("boxShadow"),
                "textAlign": style.get("textAlign"),
            },
        })
    return normalized


def _fallback_element_layouts(activity_title: str, note: str, image_count: int) -> List[Dict[str, Any]]:
    """Return 3 minimal element-based layouts when LLM is unavailable."""
    base_narrative = (note or "A moment we shared.")[:80]
    layouts = []
    for name in ("Collage Chaos", "Minimal Gallery", "Retro Journal"):
        elements = [
            {"type": "text", "content": activity_title or "Memory", "style": {"top": "8%", "left": "10%", "rotation": "-2deg", "zIndex": 2, "fontSize": "1.25rem", "color": "#1e293b", "fontFamily": "serif"}},
            {"type": "text", "content": base_narrative, "style": {"top": "45%", "left": "10%", "width": "80%", "rotation": "0deg", "zIndex": 1, "fontSize": "0.875rem", "color": "#475569", "fontFamily": "handwritten"}},
        ]
        for i in range(max(0, image_count)):
            elements.append({
                "type": "image",
                "content": str(i),
                "style": {"top": f"{20 + i * 25}%", "left": "15%", "width": "35%", "rotation": "2deg" if i % 2 else "-2deg", "zIndex": 1},
            })
        elements.append({"type": "sticker", "content": "✨", "style": {"top": "5%", "left": "75%", "rotation": "0deg", "zIndex": 3}})
        layouts.append({
            "bgStyle": {"color": "#f8fafc", "texture": "none"},
            "elements": elements,
            "styleName": name,
        })
    return layouts
