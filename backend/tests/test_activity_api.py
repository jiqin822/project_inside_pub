"""
Integration tests for Game Room 4-Tab Flow and Activity API (/v1/activity/*).
Covers: invite, invites/pending, invites/sent, respond, planned, complete (with memory_entries),
history, history/all, memories, recommendations (including similar_to_activity_id), log-interaction.

Requires a running Postgres DB and activity_templates seeded (or fixture seeds one template).
"""
import sys
from pathlib import Path
from datetime import datetime

backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from httpx import ASGITransport, AsyncClient

from app.infra.db.base import AsyncSessionLocal as _BaseSessionLocal
from app.infra.db.models.user import UserModel
from app.infra.db.models.relationship import (
    RelationshipModel,
    RelationshipType,
    RelationshipStatus,
    relationship_members,
    MemberStatus,
    MemberRole,
)
from app.infra.db.models.compass import ActivityTemplateModel
from app.infra.security.password import get_password_hash
from app.domain.common.types import generate_id

if _BaseSessionLocal is None:
    from app.settings import settings

    _integration_engine = create_async_engine(
        settings.database_url, echo=False, poolclass=NullPool
    )
    AsyncSessionLocal = async_sessionmaker(
        _integration_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
else:
    AsyncSessionLocal = _BaseSessionLocal

# Activity template to insert if not present
TEST_TEMPLATE = {
    "activity_id": "test-partner-teach-me",
    "title": "Teach me something",
    "relationship_types": ["partner"],
    "vibe_tags": ["creative", "calm", "intimate"],
    "risk_tags": [],
    "constraints": {"duration_min": 20, "budget": "low", "location": "any"},
    "personalization_slots": {},
    "steps_markdown_template": "1. Teach. 2. Swap.",
    "variants": {},
    "safety_rules": {},
    "is_active": True,
}


@pytest.fixture
async def activity_test_data():
    """Create two users, one COUPLE relationship, one activity template. Return ids and user entities."""
    unique = generate_id()[:8]
    async with AsyncSessionLocal() as session:
        now = datetime.utcnow()
        user_a_id = generate_id()
        user_b_id = generate_id()
        rel_id = generate_id()

        for uid, email, name in [
            (user_a_id, f"activity_test_a_{unique}@test.inside.app", "Test User A"),
            (user_b_id, f"activity_test_b_{unique}@test.inside.app", "Test User B"),
        ]:
            session.add(
                UserModel(
                    id=uid,
                    email=email,
                    password_hash=get_password_hash("test-pass"),
                    display_name=name,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
        await session.flush()

        session.add(
            RelationshipModel(
                id=rel_id,
                type=RelationshipType.COUPLE,
                status=RelationshipStatus.ACTIVE,
                created_by_user_id=user_a_id,
                created_at=now,
                updated_at=now,
            )
        )
        await session.flush()

        for j, uid in enumerate([user_a_id, user_b_id]):
            await session.execute(
                relationship_members.insert().values(
                    relationship_id=rel_id,
                    user_id=uid,
                    role=MemberRole.OWNER if j == 0 else MemberRole.MEMBER,
                    member_status=MemberStatus.ACCEPTED,
                    added_at=now,
                )
            )

        existing = await session.execute(
            select(ActivityTemplateModel).where(
                ActivityTemplateModel.activity_id == TEST_TEMPLATE["activity_id"]
            )
        )
        if existing.scalar_one_or_none() is None:
            session.add(
                ActivityTemplateModel(
                    activity_id=TEST_TEMPLATE["activity_id"],
                    title=TEST_TEMPLATE["title"],
                    relationship_types=TEST_TEMPLATE["relationship_types"],
                    vibe_tags=TEST_TEMPLATE["vibe_tags"],
                    risk_tags=TEST_TEMPLATE["risk_tags"],
                    constraints=TEST_TEMPLATE["constraints"],
                    personalization_slots=TEST_TEMPLATE["personalization_slots"],
                    steps_markdown_template=TEST_TEMPLATE["steps_markdown_template"],
                    variants=TEST_TEMPLATE["variants"],
                    safety_rules=TEST_TEMPLATE["safety_rules"],
                    is_active=TEST_TEMPLATE["is_active"],
                )
            )
        await session.commit()

        # Load user entities for dependency override
        ra = await session.execute(select(UserModel).where(UserModel.id == user_a_id))
        rb = await session.execute(select(UserModel).where(UserModel.id == user_b_id))
        user_a_model = ra.scalar_one_or_none()
        user_b_model = rb.scalar_one_or_none()
        assert user_a_model and user_b_model
        user_a_entity = user_a_model.to_entity()
        user_b_entity = user_b_model.to_entity()

    return {
        "user_a_id": user_a_id,
        "user_b_id": user_b_id,
        "relationship_id": rel_id,
        "template_id": TEST_TEMPLATE["activity_id"],
        "user_a_entity": user_a_entity,
        "user_b_entity": user_b_entity,
    }


@pytest.fixture
async def activity_client(activity_test_data):
    """HTTP client for /v1/activity with get_current_user and get_db overridden."""
    from app.main import app
    from app.api.deps import get_current_user, get_db

    data = activity_test_data

    async def override_user_a():
        return data["user_a_entity"]

    async def override_get_db():
        """Provide a DB session from the test AsyncSessionLocal (app's may be None under pytest)."""
        async with AsyncSessionLocal() as session:
            yield session

    app.dependency_overrides[get_current_user] = override_user_a
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield {"client": client, "app": app, "data": data}
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


# ---- Invite ----

@pytest.mark.asyncio
@pytest.mark.integration
async def test_activity_invite_success(activity_client):
    """POST /v1/activity/invite creates invite and returns invite_id."""
    client = activity_client["client"]
    data = activity_client["data"]
    r = await client.post(
        "/v1/activity/invite",
        json={
            "relationship_id": data["relationship_id"],
            "activity_template_id": data["template_id"],
            "invitee_user_id": data["user_b_id"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert "invite_id" in body


@pytest.mark.asyncio
@pytest.mark.integration
async def test_activity_invite_cannot_invite_self(activity_client):
    """POST /v1/activity/invite with invitee=self returns 400."""
    client = activity_client["client"]
    data = activity_client["data"]
    r = await client.post(
        "/v1/activity/invite",
        json={
            "relationship_id": data["relationship_id"],
            "activity_template_id": data["template_id"],
            "invitee_user_id": data["user_a_id"],
        },
    )
    assert r.status_code == 400
    assert "yourself" in r.json().get("detail", "").lower() or "invite" in r.json().get("detail", "").lower()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_activity_invites_pending_and_sent(activity_client):
    """After sending invite: GET invites/sent shows it for sender; GET invites/pending shows it for invitee (as user_b)."""
    client = activity_client["client"]
    app = activity_client["app"]
    data = activity_client["data"]
    from app.api.deps import get_current_user

    # Send invite as user_a
    r = await client.post(
        "/v1/activity/invite",
        json={
            "relationship_id": data["relationship_id"],
            "activity_template_id": data["template_id"],
            "invitee_user_id": data["user_b_id"],
        },
    )
    assert r.status_code == 200
    invite_id = r.json()["invite_id"]

    # Sent invites (as user_a)
    r_sent = await client.get("/v1/activity/invites/sent")
    assert r_sent.status_code == 200
    sent_list = r_sent.json()
    assert isinstance(sent_list, list)
    assert any(i.get("invite_id") == invite_id for i in sent_list)
    assert any(i.get("item_type") == "sent_pending" for i in sent_list)

    # Pending invites as user_b
    async def override_user_b():
        return data["user_b_entity"]

    app.dependency_overrides[get_current_user] = override_user_b
    r_pending = await client.get("/v1/activity/invites/pending")
    async def override_user_a():
        return data["user_a_entity"]
    app.dependency_overrides[get_current_user] = override_user_a
    assert r_pending.status_code == 200
    pending_list = r_pending.json()
    assert any(i.get("invite_id") == invite_id for i in pending_list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_activity_respond_accept_creates_planned(activity_client):
    """Accepting an invite creates a planned activity and returns planned_id."""
    client = activity_client["client"]
    app = activity_client["app"]
    data = activity_client["data"]
    from app.api.deps import get_current_user

    # User A sends invite
    r = await client.post(
        "/v1/activity/invite",
        json={
            "relationship_id": data["relationship_id"],
            "activity_template_id": data["template_id"],
            "invitee_user_id": data["user_b_id"],
        },
    )
    assert r.status_code == 200
    invite_id = r.json()["invite_id"]

    # User B accepts
    async def _as_b():
        return data["user_b_entity"]
    app.dependency_overrides[get_current_user] = _as_b
    r_accept = await client.post(
        f"/v1/activity/invite/{invite_id}/respond",
        json={"accept": True},
    )
    async def _as_a():
        return data["user_a_entity"]
    app.dependency_overrides[get_current_user] = _as_a
    assert r_accept.status_code == 200
    body = r_accept.json()
    assert body.get("ok") is True
    assert "planned_id" in body


@pytest.mark.asyncio
@pytest.mark.integration
async def test_activity_respond_decline(activity_client):
    """Declining an invite returns ok and does not create planned."""
    client = activity_client["client"]
    app = activity_client["app"]
    data = activity_client["data"]
    from app.api.deps import get_current_user

    r = await client.post(
        "/v1/activity/invite",
        json={
            "relationship_id": data["relationship_id"],
            "activity_template_id": data["template_id"],
            "invitee_user_id": data["user_b_id"],
        },
    )
    assert r.status_code == 200
    invite_id = r.json()["invite_id"]

    async def _as_b():
        return data["user_b_entity"]
    app.dependency_overrides[get_current_user] = _as_b
    r_decline = await client.post(
        f"/v1/activity/invite/{invite_id}/respond",
        json={"accept": False},
    )
    async def _as_a():
        return data["user_a_entity"]
    app.dependency_overrides[get_current_user] = _as_a
    assert r_decline.status_code == 200
    assert r_decline.json().get("ok") is True
    assert "planned_id" not in r_decline.json()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_activity_planned_list(activity_client):
    """GET /v1/activity/planned returns agreed planned activities for the user."""
    client = activity_client["client"]
    app = activity_client["app"]
    data = activity_client["data"]
    from app.api.deps import get_current_user

    # Create invite and accept
    r = await client.post(
        "/v1/activity/invite",
        json={
            "relationship_id": data["relationship_id"],
            "activity_template_id": data["template_id"],
            "invitee_user_id": data["user_b_id"],
        },
    )
    invite_id = r.json()["invite_id"]
    async def _as_b():
        return data["user_b_entity"]
    app.dependency_overrides[get_current_user] = _as_b
    await client.post(f"/v1/activity/invite/{invite_id}/respond", json={"accept": True})
    async def _as_a():
        return data["user_a_entity"]
    app.dependency_overrides[get_current_user] = _as_a

    r_planned = await client.get("/v1/activity/planned")
    assert r_planned.status_code == 200
    planned_list = r_planned.json()
    assert isinstance(planned_list, list)
    assert len(planned_list) >= 1
    one = next((p for p in planned_list if p.get("activity_template_id") == data["template_id"]), None)
    assert one is not None
    assert one.get("status") == "planned"
    assert "activity_title" in one


@pytest.mark.asyncio
@pytest.mark.integration
async def test_activity_complete_with_memory_entries(activity_client):
    """POST /v1/activity/planned/{id}/complete with notes and memory_entries succeeds."""
    client = activity_client["client"]
    app = activity_client["app"]
    data = activity_client["data"]
    from app.api.deps import get_current_user

    # Create planned
    r = await client.post(
        "/v1/activity/invite",
        json={
            "relationship_id": data["relationship_id"],
            "activity_template_id": data["template_id"],
            "invitee_user_id": data["user_b_id"],
        },
    )
    invite_id = r.json()["invite_id"]
    async def _as_b():
        return data["user_b_entity"]
    app.dependency_overrides[get_current_user] = _as_b
    r_accept = await client.post(
        f"/v1/activity/invite/{invite_id}/respond",
        json={"accept": True},
    )
    planned_id = r_accept.json()["planned_id"]
    async def _as_a():
        return data["user_a_entity"]
    app.dependency_overrides[get_current_user] = _as_a

    r_complete = await client.post(
        f"/v1/activity/planned/{planned_id}/complete",
        json={
            "notes": "We had a great time.",
            "memory_entries": [
                {"url": "storage/activity_memories/fake1.jpg", "caption": "First pic"},
                {"url": "storage/activity_memories/fake2.jpg", "caption": "Second pic"},
            ],
        },
    )
    assert r_complete.status_code == 200
    assert r_complete.json().get("ok") is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_activity_history_and_history_all(activity_client):
    """GET /v1/activity/history and GET /v1/activity/history/all return correct shapes."""
    client = activity_client["client"]
    data = activity_client["data"]

    r_history = await client.get(
        "/v1/activity/history",
        params={"relationship_id": data["relationship_id"], "limit": 10},
    )
    assert r_history.status_code == 200
    assert isinstance(r_history.json(), list)

    r_all = await client.get(
        "/v1/activity/history/all",
        params={"relationship_id": data["relationship_id"], "limit": 10},
    )
    assert r_all.status_code == 200
    items = r_all.json()
    assert isinstance(items, list)
    for item in items:
        assert item.get("item_type") in ("completed", "declined")
        assert "activity_title" in item
        assert "date" in item


@pytest.mark.asyncio
@pytest.mark.integration
async def test_activity_memories(activity_client):
    """GET /v1/activity/memories returns list with contributions (aggregated by activity)."""
    client = activity_client["client"]
    data = activity_client["data"]

    r = await client.get(
        "/v1/activity/memories",
        params={"relationship_id": data["relationship_id"], "limit": 10},
    )
    assert r.status_code == 200
    memories = r.json()
    assert isinstance(memories, list)
    for m in memories:
        assert "activity_title" in m
        assert "contributions" in m
        assert "completed_at" in m


@pytest.mark.asyncio
@pytest.mark.integration
async def test_activity_recommendations_and_similar_to(activity_client):
    """GET /v1/activity/recommendations with mode=activities and optional similar_to_activity_id."""
    client = activity_client["client"]
    data = activity_client["data"]

    r = await client.get(
        "/v1/activity/recommendations",
        params={
            "mode": "activities",
            "relationship_id": data["relationship_id"],
            "limit": 5,
        },
    )
    assert r.status_code == 200
    recs = r.json()
    assert isinstance(recs, list)
    if recs:
        one = recs[0]
        assert "id" in one
        assert "title" in one
        assert "vibe_tags" in one
        assert "suggested_invitees" in one

    # With similar_to_activity_id (generate more like this)
    r2 = await client.get(
        "/v1/activity/recommendations",
        params={
            "mode": "activities",
            "relationship_id": data["relationship_id"],
            "limit": 5,
            "similar_to_activity_id": data["template_id"],
        },
    )
    assert r2.status_code == 200
    assert isinstance(r2.json(), list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_activity_log_interaction(activity_client):
    """POST /v1/activity/log-interaction records event."""
    client = activity_client["client"]
    data = activity_client["data"]

    r = await client.post(
        "/v1/activity/log-interaction",
        json={
            "relationship_id": data["relationship_id"],
            "suggestion_id": data["template_id"],
            "action": "viewed",
        },
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True

    r_invite = await client.post(
        "/v1/activity/log-interaction",
        json={
            "relationship_id": data["relationship_id"],
            "suggestion_id": data["template_id"],
            "action": "invite_sent",
        },
    )
    assert r_invite.status_code == 200


@pytest.mark.asyncio
@pytest.mark.integration
async def test_activity_log_interaction_invalid_action(activity_client):
    """POST /v1/activity/log-interaction with invalid action returns 400."""
    client = activity_client["client"]
    data = activity_client["data"]
    r = await client.post(
        "/v1/activity/log-interaction",
        json={
            "relationship_id": data["relationship_id"],
            "suggestion_id": data["template_id"],
            "action": "invalid_action",
        },
    )
    assert r.status_code == 400
    assert "invalid" in r.json().get("detail", "").lower() or "action" in r.json().get("detail", "").lower()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_activity_recommendations_requires_relationship_id(activity_client):
    """GET /v1/activity/recommendations without relationship_id returns 400."""
    client = activity_client["client"]
    r = await client.get(
        "/v1/activity/recommendations",
        params={"mode": "activities", "limit": 5},
    )
    assert r.status_code == 400
    assert "relationship" in r.json().get("detail", "").lower()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_activity_respond_404_not_found(activity_client):
    """POST /v1/activity/invite/{id}/respond with unknown invite_id returns 404."""
    client = activity_client["client"]
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = await client.post(
        f"/v1/activity/invite/{fake_id}/respond",
        json={"accept": True},
    )
    assert r.status_code == 404
    assert "not found" in r.json().get("detail", "").lower()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_activity_complete_404_not_found(activity_client):
    """POST /v1/activity/planned/{id}/complete with unknown planned_id returns 404."""
    client = activity_client["client"]
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = await client.post(
        f"/v1/activity/planned/{fake_id}/complete",
        json={"notes": "test"},
    )
    assert r.status_code == 404
    assert "not found" in r.json().get("detail", "").lower()
