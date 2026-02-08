"""Insider Compass domain services: Event Ingest, Consolidation, Personalization (user profiling only)."""
import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)
from datetime import datetime
from typing import Optional, List, Any, Dict, Tuple, Callable

from app.domain.compass.models import (
    EventSource,
    PERSONALIZATION_USE_CASES,
    USE_CASE_ACTIVITIES,
)
from app.infra.db.models.compass import CompassEventModel


def _nth_weekday_of_month(year: int, month: int, n: int, weekday: int) -> datetime:
    """Return the nth weekday (0=Mon..6=Sun) in the given month. n is 1-based."""
    first = datetime(year, month, 1)
    # weekday(): Mon=0 .. Sun=6
    shift = (weekday - first.weekday()) % 7
    if shift and n == 1:
        shift += 7 * (n - 1)
    else:
        shift += 7 * (n - 1)
    return first.replace(day=1 + shift)


def get_world_context_snippet() -> str:
    """Return a short world context (date, season, time of day, upcoming holidays) for activity prompts."""
    now = datetime.utcnow()
    month = now.month

    if month in (12, 1, 2):
        season = "winter"
    elif month in (3, 4, 5):
        season = "spring"
    elif month in (6, 7, 8):
        season = "summer"
    else:
        season = "fall"

    hour = now.hour
    if 5 <= hour < 12:
        time_of_day = "morning"
    elif 12 <= hour < 17:
        time_of_day = "afternoon"
    elif 17 <= hour < 21:
        time_of_day = "evening"
    else:
        time_of_day = "night"

    # Build list of (date, name) for upcoming holidays (fixed + variable).
    current_year = now.year
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    holidays_with_dates: List[Tuple[datetime, str]] = []
    # Fixed-date holidays (month, day, name)
    fixed = [
        (1, 1, "New Year's Day"),
        (2, 14, "Valentine's Day"),
        (3, 17, "St. Patrick's Day"),
        (4, 1, "April Fool's Day"),
        (5, 5, "Cinco de Mayo"),
        (6, 19, "Juneteenth"),
        (7, 4, "Independence Day"),
        (10, 31, "Halloween"),
        (12, 24, "Christmas Eve"),
        (12, 25, "Christmas Day"),
        (12, 31, "New Year's Eve"),
    ]
    for m, d, name in fixed:
        d_this = datetime(current_year, m, d)
        if d_this < today:
            d_this = datetime(current_year + 1, m, d)
        holidays_with_dates.append((d_this, name))
    # US Thanksgiving: 4th Thursday of November
    try:
        thanksgiving = _nth_weekday_of_month(current_year, 11, 4, 3)
        if thanksgiving < today:
            thanksgiving = _nth_weekday_of_month(current_year + 1, 11, 4, 3)
        holidays_with_dates.append((thanksgiving, "Thanksgiving"))
    except Exception:
        pass
    # US Memorial Day: last Monday of May
    try:
        last_may = datetime(current_year, 5, 31)
        while last_may.weekday() != 0:
            last_may = last_may.replace(day=last_may.day - 1)
        if last_may < today:
            last_may = datetime(current_year + 1, 5, 31)
            while last_may.weekday() != 0:
                last_may = last_may.replace(day=last_may.day - 1)
        holidays_with_dates.append((last_may, "Memorial Day"))
    except Exception:
        pass
    # US Labor Day: 1st Monday of September
    try:
        labor = _nth_weekday_of_month(current_year, 9, 1, 0)
        if labor < today:
            labor = _nth_weekday_of_month(current_year + 1, 9, 1, 0)
        holidays_with_dates.append((labor, "Labor Day"))
    except Exception:
        pass

    upcoming = [(d, name, (d - now).days) for d, name in holidays_with_dates if d >= today]
    upcoming.sort(key=lambda x: x[0])

    if upcoming:
        next_d, next_name, days_until = upcoming[0]
        if days_until == 0:
            holiday_str = f"Today is {next_name}!"
        elif days_until == 1:
            holiday_str = f"Tomorrow is {next_name}."
        else:
            holiday_str = f"Upcoming holiday: {next_name} (in {days_until} days)."
        if len(upcoming) > 1:
            other = ", ".join(n for (_, n, _) in upcoming[1:4])
            holiday_str = f"{holiday_str} Other soon: {other}."
    else:
        holiday_str = "No upcoming holidays in the next few months."

    return (
        f"Current date: {now.strftime('%Y-%m-%d')}. "
        f"Season: {season}. "
        f"Time of day: {time_of_day}. "
        f"{holiday_str}"
    )


@dataclass
class ContextBundle:
    """Context bundle for personalization (memories, portraits, loops, recent activity)."""
    memories: List[Any] = field(default_factory=list)
    person_portrait_actor: Optional[Any] = None
    person_portrait_partner: Optional[Any] = None
    dyad_portrait: Optional[Any] = None
    loops: List[Any] = field(default_factory=list)
    recent_activity_ids: List[str] = field(default_factory=list)
    constraints: dict = field(default_factory=dict)
    context_summary: Optional[str] = None


class ConsolidationService:
    """Re-reason over events and existing portraits; write back portraits and per-use-case context summaries."""

    def __init__(
        self,
        event_repo: Any,
        person_portrait_repo: Any,
        dyad_portrait_repo: Any,
        context_summary_repo: Any,
        memory_repo: Optional[Any] = None,
    ):
        self.event_repo = event_repo
        self.person_portrait_repo = person_portrait_repo
        self.dyad_portrait_repo = dyad_portrait_repo
        self.context_summary_repo = context_summary_repo
        self.memory_repo = memory_repo

    async def _get_other_member_user_id(self, db: Any, relationship_id: str, actor_user_id: str) -> Optional[str]:
        """Resolve the other member's user_id in the relationship (loved one)."""
        from sqlalchemy import select
        from app.infra.db.models.relationship import relationship_members

        result = await db.execute(
            select(relationship_members.c.user_id).where(
                relationship_members.c.relationship_id == relationship_id,
            )
        )
        user_ids = [row[0] for row in result.all()]
        for uid in user_ids:
            if uid != actor_user_id:
                return uid
        return None

    def _apply_event_to_state(
        self,
        payload: dict,
        source: str,
        portrait_text_actor: str,
        portrait_facets_actor: dict,
        dyad_text: str,
        dyad_facets: dict,
    ) -> Tuple[str, dict, str, dict]:
        """Apply a single event payload to in-memory portrait state. Returns updated (actor_text, actor_facets, dyad_text, dyad_facets)."""
        if source == EventSource.LOVE_MAP.value and isinstance(payload, dict):
            answer = payload.get("answer_text") or payload.get("answer") or ""
            if answer:
                portrait_text_actor = (portrait_text_actor + "\n\n" + answer.strip())[:2000]
            for key in ["preference", "boundary", "value", "play_style", "meaning_markers"]:
                if key in payload and payload[key]:
                    portrait_facets_actor[key] = str(payload[key])[:200]
        if source == EventSource.THERAPIST.value and isinstance(payload, dict):
            msg = payload.get("message") or payload.get("summary") or ""
            if msg:
                portrait_text_actor = (portrait_text_actor + "\n\n" + msg.strip())[:2000]
        if source == EventSource.ACTIVITY.value and isinstance(payload, dict):
            outcome = payload.get("outcome_tags") or payload.get("rating")
            if outcome is not None:
                dyad_facets["recent_activity_outcome"] = str(outcome)[:100]
        return portrait_text_actor, portrait_facets_actor, dyad_text, dyad_facets

    async def consolidate(self, new_event: CompassEventModel, db: Any) -> None:
        """Load existing state, re-reason, write back portraits and context summaries (single event)."""
        await self.consolidate_batch([new_event], db)

    async def consolidate_batch(self, events: List[CompassEventModel], db: Any) -> None:
        """Consolidate a batch of events into portraits and context summaries. Caller should mark_processed(event_ids) after."""
        if not events:
            return
        # Group by (actor_user_id, relationship_id) so we update each (actor, rel) once
        groups: Dict[Tuple[str, Optional[str]], List[CompassEventModel]] = {}
        for e in events:
            key = (e.actor_user_id, e.relationship_id)
            groups.setdefault(key, []).append(e)
        for (actor_user_id, relationship_id), group_events in groups.items():
            group_events_sorted = sorted(
                group_events,
                key=lambda x: x.created_at if x.created_at else datetime.min,
            )
            contributing_event_ids = [e.event_id for e in group_events_sorted]
            existing_actor_portrait = await self.person_portrait_repo.get_by_owner(actor_user_id, relationship_id)
            other_user_id = await self._get_other_member_user_id(db, relationship_id, actor_user_id) if relationship_id else None
            existing_partner_portrait = (
                await self.person_portrait_repo.get_by_owner(other_user_id, relationship_id)
                if other_user_id else None
            )
            existing_dyad = (
                await self.dyad_portrait_repo.get_by_relationship(relationship_id)
                if relationship_id else None
            )

            portrait_text_actor = (existing_actor_portrait.portrait_text or "") if existing_actor_portrait else ""
            portrait_facets_actor = dict((existing_actor_portrait.portrait_facets_json or {}) if existing_actor_portrait else {})
            portrait_text_partner = (existing_partner_portrait.portrait_text or "") if existing_partner_portrait else ""
            portrait_facets_partner = dict((existing_partner_portrait.portrait_facets_json or {}) if existing_partner_portrait else {})
            dyad_text = (existing_dyad.portrait_text or "") if existing_dyad else ""
            dyad_facets = dict((existing_dyad.facets_json or {}) if existing_dyad else {})

            for ev in group_events_sorted:
                payload = ev.payload_json or {}
                portrait_text_actor, portrait_facets_actor, dyad_text, dyad_facets = self._apply_event_to_state(
                    payload, ev.source, portrait_text_actor, portrait_facets_actor, dyad_text, dyad_facets
                )

            source = group_events_sorted[-1].source if group_events_sorted else "activity"
            await self.person_portrait_repo.upsert(
                owner_user_id=actor_user_id,
                relationship_id=relationship_id,
                portrait_text=portrait_text_actor or None,
                portrait_facets_json=portrait_facets_actor or None,
                evidence_event_ids=contributing_event_ids,
                confidence=0.6,
            )
            if other_user_id and (portrait_text_partner or portrait_facets_partner):
                await self.person_portrait_repo.upsert(
                    owner_user_id=other_user_id,
                    relationship_id=relationship_id,
                    portrait_text=portrait_text_partner or None,
                    portrait_facets_json=portrait_facets_partner or None,
                    evidence_event_ids=contributing_event_ids,
                    confidence=0.5,
                )
            if relationship_id:
                if not dyad_text:
                    dyad_text = f"Relationship context (source: {source})."
                await self.dyad_portrait_repo.upsert(
                    relationship_id=relationship_id,
                    portrait_text=dyad_text or None,
                    facets_json=dyad_facets or None,
                    evidence_event_ids=contributing_event_ids,
                    confidence=0.5,
                )

            for use_case in PERSONALIZATION_USE_CASES:
                summary_parts = []
                if portrait_text_actor:
                    summary_parts.append(f"Actor: {portrait_text_actor[:300]}.")
                if dyad_text:
                    summary_parts.append(f"Dyad: {dyad_text[:200]}.")
                if portrait_facets_actor:
                    summary_parts.append(f"Facets: {str(portrait_facets_actor)[:200]}.")
                summary_parts.append(f"Use case: {use_case}. Source: {source}.")
                summary_text = " ".join(summary_parts) or f"Context for {use_case} (no portraits yet)."
                await self.context_summary_repo.upsert(
                    relationship_id=relationship_id,
                    actor_user_id=actor_user_id,
                    use_case=use_case,
                    scenario=None,
                    summary_text=summary_text,
                    evidence_event_ids=contributing_event_ids,
                )


class EventIngestService:
    """Append event to stream; run consolidation when unprocessed count exceeds threshold."""

    def __init__(
        self,
        event_repo: Any,
        consolidation_service: ConsolidationService,
        consolidation_threshold: int = 5,
    ):
        self.event_repo = event_repo
        self.consolidation_service = consolidation_service
        self.consolidation_threshold = consolidation_threshold

    async def ingest(
        self,
        type: str,
        actor_user_id: str,
        payload: dict,
        source: str,
        relationship_id: Optional[str] = None,
        privacy_scope: str = "private",
        db: Optional[Any] = None,
    ) -> CompassEventModel:
        """Validate source, append event. If unprocessed count >= threshold, consolidate batch and mark processed."""
        valid_sources = [e.value for e in EventSource]
        if source not in valid_sources:
            raise ValueError(f"source must be one of {valid_sources}")
        event = await self.event_repo.append(
            type=type,
            actor_user_id=actor_user_id,
            payload=payload,
            source=source,
            relationship_id=relationship_id,
            privacy_scope=privacy_scope,
        )
        if db is not None and self.consolidation_threshold > 0:
            count = await self.event_repo.count_unprocessed_by_actor(actor_user_id)
            if count >= self.consolidation_threshold:
                unprocessed = await self.event_repo.list_unprocessed_by_actor(actor_user_id, limit=100)
                if unprocessed:
                    await self.consolidation_service.consolidate_batch(unprocessed, db)
                    await self.event_repo.mark_processed([e.event_id for e in unprocessed])
        return event


class PersonalizationService:
    """Build context bundle, get dyad insights, ingest Kai insights (profile or unstructured memory)."""

    def __init__(
        self,
        event_repo: Any,
        memory_repo: Any,
        person_portrait_repo: Any,
        dyad_portrait_repo: Any,
        loop_repo: Any,
        activity_template_repo: Any,
        dyad_activity_repo: Any,
        context_summary_repo: Any,
        unstructured_memory_repo: Optional[Any] = None,
        things_to_find_out_repo: Optional[Any] = None,
    ):
        self.event_repo = event_repo
        self.memory_repo = memory_repo
        self.person_portrait_repo = person_portrait_repo
        self.dyad_portrait_repo = dyad_portrait_repo
        self.loop_repo = loop_repo
        self.activity_template_repo = activity_template_repo
        self.dyad_activity_repo = dyad_activity_repo
        self.context_summary_repo = context_summary_repo
        self.unstructured_memory_repo = unstructured_memory_repo
        self.things_to_find_out_repo = things_to_find_out_repo

    async def build_context_bundle(
        self,
        actor_user_id: str,
        relationship_id: str,
        mode: str,
        scenario: Optional[str] = None,
    ) -> ContextBundle:
        """Load memories, portraits, loops, recent activity; optionally read pre-computed context summary."""
        memories = await self.memory_repo.list_by_owner(
            actor_user_id, relationship_id=relationship_id, status="confirmed", limit=100
        )
        person_portrait_actor = await self.person_portrait_repo.get_by_owner(actor_user_id, relationship_id)
        dyad_portrait = await self.dyad_portrait_repo.get_by_relationship(relationship_id)
        loops = await self.loop_repo.list_by_relationship(relationship_id, limit=20)
        history = await self.dyad_activity_repo.list_by_relationship(relationship_id, limit=50)
        recent_activity_ids = [h.activity_template_id for h in history]

        context_summary = None
        cs = await self.context_summary_repo.get(relationship_id, mode, scenario)
        if cs:
            context_summary = cs.summary_text

        constraints = {}
        for m in memories:
            if m.canonical_key and m.value_json:
                constraints[m.canonical_key] = m.value_json

        return ContextBundle(
            memories=memories,
            person_portrait_actor=person_portrait_actor,
            person_portrait_partner=None,
            dyad_portrait=dyad_portrait,
            loops=loops,
            recent_activity_ids=recent_activity_ids,
            constraints=constraints,
            context_summary=context_summary,
        )

    def _build_llm_context_text(
        self,
        bundle: ContextBundle,
        partner_portrait: Optional[Any],
        member_list: List[Dict[str, str]],
        duration_max_minutes: Optional[int],
        recent_activity_titles: List[str],
        actor_profile: Optional[Dict[str, Any]] = None,
        partner_profiles: Optional[List[Dict[str, Any]]] = None,
        exclude_activity_titles: Optional[List[str]] = None,
    ) -> str:
        """Build a single text block for Gemini from actor, dyad, partner portraits, user profiles, and members."""
        parts = []
        # User (actor) profile: interests, personal description, personality (from profile, not only compass portraits)
        if actor_profile:
            actor_parts = []
            if actor_profile.get("personal_description"):
                actor_parts.append(f"Personal description: {str(actor_profile['personal_description'])[:400]}")
            if actor_profile.get("hobbies"):
                h = actor_profile["hobbies"]
                hobbies_str = ", ".join(h[:15]) if isinstance(h, list) else str(h)[:200]
                if hobbies_str:
                    actor_parts.append(f"Interests/hobbies: {hobbies_str}")
            if actor_profile.get("personality_type") and isinstance(actor_profile["personality_type"], dict):
                pt = actor_profile["personality_type"]
                ptype = pt.get("type") if isinstance(pt.get("type"), str) else None
                if ptype and (ptype or "").strip().lower() not in ("prefer not to say", ""):
                    actor_parts.append(f"Personality: {ptype}")
            if actor_parts:
                parts.append("User (actor) profile:\n" + "\n".join(actor_parts))
        if bundle.person_portrait_actor:
            p = bundle.person_portrait_actor
            text = getattr(p, "portrait_text", None) or ""
            facets = getattr(p, "portrait_facets_json", None) or {}
            if text:
                parts.append(f"User (actor) portrait from app usage: {text[:500]}")
            if facets:
                parts.append(f"User facets: {json.dumps(facets)[:300]}")
        if bundle.dyad_portrait:
            d = bundle.dyad_portrait
            text = getattr(d, "portrait_text", None) or ""
            facets = getattr(d, "facets_json", None) or {}
            if text:
                parts.append(f"Relationship (dyad): {text[:400]}")
            if facets:
                parts.append(f"Dyad facets: {json.dumps(facets)[:300]}")
        # Loved one(s) profiles: personal description, interests, personality (order matches member_list)
        if partner_profiles and member_list:
            for i, prof in enumerate(partner_profiles[: len(member_list)]):
                if not isinstance(prof, dict):
                    continue
                name = (member_list[i].get("name") or member_list[i].get("id") or f"Partner {i+1}") if i < len(member_list) else f"Partner {i+1}"
                pp = []
                if prof.get("personal_description"):
                    pp.append(f"Personal description: {str(prof['personal_description'])[:400]}")
                if prof.get("hobbies"):
                    h = prof["hobbies"]
                    hobbies_str = ", ".join(h[:15]) if isinstance(h, list) else str(h)[:200]
                    if hobbies_str:
                        pp.append(f"Interests/hobbies: {hobbies_str}")
                if prof.get("personality_type") and isinstance(prof["personality_type"], dict):
                    pt = prof["personality_type"]
                    ptype = pt.get("type") if isinstance(pt.get("type"), str) else None
                    if ptype and (ptype or "").strip().lower() not in ("prefer not to say", ""):
                        pp.append(f"Personality: {ptype}")
                if pp:
                    parts.append(f"Loved one ({name}) profile:\n" + "\n".join(pp))
        if partner_portrait:
            p = partner_portrait
            text = getattr(p, "portrait_text", None) or ""
            facets = getattr(p, "portrait_facets_json", None) or {}
            if text:
                parts.append(f"Loved one portrait from app usage: {text[:500]}")
            if facets:
                parts.append(f"Partner facets: {json.dumps(facets)[:300]}")
        member_names = [m.get("name") or m.get("id", "") for m in member_list if m]
        if member_names:
            parts.append(f"Relationship members (use exactly these names for recommended_invitee_name): {', '.join(member_names)}")
        if recent_activity_titles:
            parts.append(f"Recently done activities (avoid suggesting these): {', '.join(recent_activity_titles[:15])}")
        if exclude_activity_titles:
            parts.append(f"Activities already shown to user (do not suggest these—suggest different ones): {', '.join(exclude_activity_titles[:20])}")
        if duration_max_minutes is not None:
            parts.append(f"Prefer activities under {duration_max_minutes} minutes.")
        if bundle.context_summary:
            parts.append(f"Context summary: {bundle.context_summary[:400]}")
        parts.append(f"World context: {get_world_context_snippet()}")
        return "\n\n".join(parts) if parts else "No specific context; suggest varied relationship-building activities."

    async def get_user_profile_text_for_kai(
        self,
        user_id: str,
        relationship_id: Optional[str] = None,
        actor_profile: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build a single text string combining user profile (from user table), Compass portrait,
        dyad portrait if relationship_id, and context summary. Used by Kai callers (lounge, activity, love map)
        to pass into Kai prompts as "Compass user profile".
        """
        parts = []
        if actor_profile:
            actor_parts = []
            if actor_profile.get("personal_description"):
                actor_parts.append(f"Personal description: {str(actor_profile['personal_description'])[:400]}")
            if actor_profile.get("hobbies"):
                h = actor_profile["hobbies"]
                hobbies_str = ", ".join(h[:15]) if isinstance(h, list) else str(h)[:200]
                if hobbies_str:
                    actor_parts.append(f"Interests/hobbies: {hobbies_str}")
            if actor_profile.get("personality_type") and isinstance(actor_profile["personality_type"], dict):
                pt = actor_profile["personality_type"]
                ptype = pt.get("type") if isinstance(pt.get("type"), str) else None
                if ptype and (ptype or "").strip().lower() not in ("prefer not to say", ""):
                    actor_parts.append(f"Personality: {ptype}")
            if actor_parts:
                parts.append("User profile:\n" + "\n".join(actor_parts))
        person_portrait = await self.person_portrait_repo.get_by_owner(user_id, relationship_id)
        if person_portrait:
            text = getattr(person_portrait, "portrait_text", None) or ""
            facets = getattr(person_portrait, "portrait_facets_json", None) or {}
            if text:
                parts.append(f"Portrait from app usage: {text[:500]}")
            if facets:
                parts.append(f"Facets: {json.dumps(facets)[:300]}")
        if relationship_id:
            dyad_portrait = await self.dyad_portrait_repo.get_by_relationship(relationship_id)
            if dyad_portrait:
                text = getattr(dyad_portrait, "portrait_text", None) or ""
                facets = getattr(dyad_portrait, "facets_json", None) or {}
                if text:
                    parts.append(f"Relationship (dyad): {text[:400]}")
                if facets:
                    parts.append(f"Dyad facets: {json.dumps(facets)[:300]}")
        context_summary = None
        if relationship_id:
            cs = await self.context_summary_repo.get(relationship_id, USE_CASE_ACTIVITIES, None)
            if cs:
                context_summary = cs.summary_text
            else:
                cs = await self.context_summary_repo.get_by_actor(user_id, USE_CASE_ACTIVITIES, None)
                if cs:
                    context_summary = cs.summary_text
        if context_summary:
            parts.append(f"Context summary: {context_summary[:400]}")
        return "\n\n".join(parts) if parts else "None"

    async def get_dyad_insights(
        self,
        relationship_id: str,
        actor_user_id: str,
    ) -> dict:
        """Return person portraits, dyad portrait, loops, memories summary for dyad insights API."""
        portraits_actor = await self.person_portrait_repo.get_by_owner(actor_user_id, relationship_id)
        dyad = await self.dyad_portrait_repo.get_by_relationship(relationship_id)
        loops = await self.loop_repo.list_by_relationship(relationship_id, limit=50)
        memories = await self.memory_repo.list_by_owner(
            actor_user_id, relationship_id=relationship_id, status="confirmed", limit=100
        )
        memories_summary = [{"canonical_key": m.canonical_key, "value": m.value_json} for m in memories]
        return {
            "person_portraits": [portraits_actor] if portraits_actor else [],
            "dyad_portrait": dyad,
            "loops": loops,
            "memories_summary": memories_summary,
        }

    async def ingest_kai_insight(
        self,
        actor_user_id: str,
        insight_text: str,
        relationship_id: Optional[str] = None,
        source: str = "kai_insight",
    ) -> Optional[str]:
        """
        Store a Kai-generated insight. When unstructured_memory_repo is set, appends to unstructured memory.
        Returns the created memory id or None if not stored.
        """
        if not (insight_text or "").strip():
            return None
        if not self.unstructured_memory_repo:
            return None
        rec = await self.unstructured_memory_repo.create(
            owner_user_id=actor_user_id,
            content_text=(insight_text or "").strip()[:10000],
            source=source,
            relationship_id=relationship_id,
        )
        return rec.id

    async def get_context_for_query(
        self,
        user_id: str,
        question: Optional[str],
        relationship_id: Optional[str] = None,
        actor_profile: Optional[Dict[str, Any]] = None,
        llm_generate_text: Optional[Callable[[str], Optional[str]]] = None,
    ) -> str:
        """
        Return context for Kai: full bundle text if question is empty; otherwise LLM answer over context+unstructured memories.
        If question is set but llm_generate_text is None, returns full bundle text (no Q&A).
        """
        full_text = await self.get_user_profile_text_for_kai(
            user_id, relationship_id=relationship_id, actor_profile=actor_profile
        )
        unstructured_parts: List[str] = []
        if self.unstructured_memory_repo:
            recs = await self.unstructured_memory_repo.list_by_owner(
                owner_user_id=user_id,
                relationship_id=relationship_id,
                limit=50,
            )
            for r in recs:
                text = getattr(r, "content_text", None) or ""
                if text:
                    unstructured_parts.append(text[:500])
        if unstructured_parts:
            full_text = full_text + "\n\nUnstructured notes (from past insights):\n" + "\n".join(unstructured_parts)

        if not (question or "").strip():
            return full_text
        if not llm_generate_text or not callable(llm_generate_text):
            return full_text
        prompt = f"""You are a helpful assistant. Answer the question based ONLY on the following context. If the context does not contain enough information, say so briefly.

Context:
{full_text[:8000]}

Question: {question.strip()}

Answer (concise, based only on context):"""
        try:
            answer = llm_generate_text(prompt)
            if answer and answer.strip():
                return answer.strip()
        except Exception as e:
            logger.warning("get_context_for_query LLM failed: %s", e)
        return full_text

    async def add_thing_to_find_out(
        self,
        owner_user_id: str,
        question_text: str,
        relationship_id: Optional[str] = None,
        source: str = "kai",
        priority: Optional[int] = None,
    ) -> Optional[str]:
        """Store a question Kai wants to find out. Returns created id or None if repo not set."""
        if not (question_text or "").strip():
            return None
        if not self.things_to_find_out_repo:
            return None
        rec = await self.things_to_find_out_repo.create(
            owner_user_id=owner_user_id,
            question_text=(question_text or "").strip()[:2000],
            source=source,
            relationship_id=relationship_id,
            priority=priority,
        )
        return rec.id

    async def list_things_to_find_out(
        self,
        owner_user_id: str,
        relationship_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Any]:
        """List things to find out for owner/relationship. Returns [] if repo not set."""
        if not self.things_to_find_out_repo:
            return []
        return await self.things_to_find_out_repo.list_by_owner(
            owner_user_id=owner_user_id,
            relationship_id=relationship_id,
            limit=limit,
        )

    async def get_love_map_design_context(
        self,
        relationship_id: Optional[str],
        actor_user_id: str,
        subject_id: str,
        actor_profile: Optional[Dict[str, Any]] = None,
        subject_profile: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build context for love map level design: dyad importance, person portraits,
        unconfirmed hypotheses (memories with status=hypothesis), and things to find out.
        Returns a single text block for Kai prompts.
        """
        parts = []
        person_portrait_subject = await self.person_portrait_repo.get_by_owner(subject_id, relationship_id)
        if person_portrait_subject:
            text = getattr(person_portrait_subject, "portrait_text", None) or ""
            facets = getattr(person_portrait_subject, "portrait_facets_json", None) or {}
            if text:
                parts.append(f"Subject portrait (from Compass): {text[:500]}")
            if facets:
                parts.append(f"Subject facets: {json.dumps(facets)[:300]}")
        if subject_profile:
            sp = []
            if subject_profile.get("personal_description"):
                sp.append(f"Personal description: {str(subject_profile['personal_description'])[:400]}")
            if subject_profile.get("hobbies"):
                h = subject_profile["hobbies"]
                hobbies_str = ", ".join(h[:15]) if isinstance(h, list) else str(h)[:200]
                if hobbies_str:
                    sp.append(f"Interests/hobbies: {hobbies_str}")
            if sp:
                parts.append("Subject profile:\n" + "\n".join(sp))
        if relationship_id:
            dyad = await self.dyad_portrait_repo.get_by_relationship(relationship_id)
            if dyad:
                text = getattr(dyad, "portrait_text", None) or ""
                facets = getattr(dyad, "facets_json", None) or {}
                if text:
                    parts.append(f"Dyad (relationship): {text[:400]}")
                if facets:
                    parts.append(f"Dyad facets: {json.dumps(facets)[:300]}")
        memories_hypothesis = await self.memory_repo.list_by_owner(
            actor_user_id, relationship_id=relationship_id, status="hypothesis", limit=30
        )
        if memories_hypothesis:
            parts.append("Unconfirmed hypotheses (to confirm or correct):")
            for m in memories_hypothesis[:15]:
                key = getattr(m, "canonical_key", None) or "unknown"
                val = getattr(m, "value_json", None)
                parts.append(f"  - {key}: {json.dumps(val)[:150]}")
        things = await self.list_things_to_find_out(owner_user_id=actor_user_id, relationship_id=relationship_id, limit=20)
        if things:
            parts.append("Things we want to find out:")
            for t in things[:15]:
                q = getattr(t, "question_text", None) or ""
                if q:
                    parts.append(f"  - {q[:200]}")
        return "\n\n".join(parts) if parts else "None"


