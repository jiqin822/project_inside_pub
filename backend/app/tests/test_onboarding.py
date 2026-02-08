"""Tests for onboarding endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestOnboardingFlow:
    """Test onboarding workflow."""

    async def test_signup_then_get_status_returns_profile_step(self, client: AsyncClient):
        """Test that after signup, onboarding status returns PROFILE step."""
        # Signup
        signup_response = await client.post(
            "/v1/auth/signup",
            json={
                "email": "onboarding@example.com",
                "password": "testpass123",
                "display_name": None,
            },
        )
        assert signup_response.status_code == 200
        token = signup_response.json()["access_token"]

        # Get onboarding status
        status_response = await client.get(
            "/v1/onboarding/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status_response.status_code == 200
        data = status_response.json()
        assert data["next_step"] == "PROFILE"
        assert data["has_profile"] is False
        assert data["has_voiceprint"] is False

    async def test_update_profile_then_complete_advances_step(self, client: AsyncClient):
        """Test updating profile and completing step advances to next step."""
        # Signup
        signup_response = await client.post(
            "/v1/auth/signup",
            json={
                "email": "profile@example.com",
                "password": "testpass123",
            },
        )
        token = signup_response.json()["access_token"]

        # Update profile
        update_response = await client.patch(
            "/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "display_name": "Test User",
                "privacy_tier": "STANDARD",
            },
        )
        assert update_response.status_code == 200

        # Complete profile step
        complete_response = await client.post(
            "/v1/onboarding/complete",
            headers={"Authorization": f"Bearer {token}"},
            json={"step": "PROFILE"},
        )
        assert complete_response.status_code == 200
        assert complete_response.json()["ok"] is True

        # Check status advances
        status_response = await client.get(
            "/v1/onboarding/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status_response.status_code == 200
        data = status_response.json()
        assert data["next_step"] == "VOICEPRINT"
        assert data["has_profile"] is True

    async def test_skip_voiceprint_advances_to_relationships(self, client: AsyncClient):
        """Test skipping voiceprint advances to relationships step."""
        # Signup and complete profile
        signup_response = await client.post(
            "/v1/auth/signup",
            json={
                "email": "skipvoice@example.com",
                "password": "testpass123",
            },
        )
        token = signup_response.json()["access_token"]

        await client.patch(
            "/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"display_name": "Test", "privacy_tier": "PRIVATE"},
        )
        await client.post(
            "/v1/onboarding/complete",
            headers={"Authorization": f"Bearer {token}"},
            json={"step": "PROFILE"},
        )

        # Skip voiceprint
        await client.post(
            "/v1/onboarding/complete",
            headers={"Authorization": f"Bearer {token}"},
            json={"step": "VOICEPRINT_SKIPPED"},
        )

        # Check status
        status_response = await client.get(
            "/v1/onboarding/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status_response.status_code == 200
        data = status_response.json()
        assert data["next_step"] == "RELATIONSHIPS"

    async def test_create_relationship_then_list(self, client: AsyncClient):
        """Test creating a relationship and listing relationships."""
        # Signup
        signup_response = await client.post(
            "/v1/auth/signup",
            json={
                "email": "reltest@example.com",
                "password": "testpass123",
            },
        )
        token = signup_response.json()["access_token"]
        user_id = signup_response.json().get("user_id")  # May not be in response, get from /me
        me_response = await client.get(
            "/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        user_id = me_response.json()["id"]

        # Create relationship
        create_response = await client.post(
            "/v1/relationships",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "type": "romantic",
                "member_ids": [user_id],
            },
        )
        assert create_response.status_code == 200
        rel_data = create_response.json()
        assert "id" in rel_data
        assert rel_data["type"] == "romantic"

        # List relationships
        list_response = await client.get(
            "/v1/relationships",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert list_response.status_code == 200
        relationships = list_response.json()
        assert isinstance(relationships, list)
        assert len(relationships) >= 1

    async def test_contact_lookup_not_found_then_create_invite(self, client: AsyncClient):
        """Test contact lookup NOT_FOUND then creating invite."""
        # Signup
        signup_response = await client.post(
            "/v1/auth/signup",
            json={
                "email": "invitetest@example.com",
                "password": "testpass123",
            },
        )
        token = signup_response.json()["access_token"]
        me_response = await client.get(
            "/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        user_id = me_response.json()["id"]

        # Create relationship first
        rel_response = await client.post(
            "/v1/relationships",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "type": "friend",
                "member_ids": [user_id],
            },
        )
        relationship_id = rel_response.json()["id"]

        # Lookup contact (not found)
        lookup_response = await client.post(
            "/v1/contacts/lookup",
            headers={"Authorization": f"Bearer {token}"},
            json={"email": "nonexistent@example.com"},
        )
        assert lookup_response.status_code == 200
        assert lookup_response.json()["status"] == "NOT_FOUND"

        # Create invite
        invite_response = await client.post(
            f"/v1/relationships/{relationship_id}/invites",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": "nonexistent@example.com",
                "role": "FRIEND",
            },
        )
        assert invite_response.status_code == 200
        invite_data = invite_response.json()
        assert invite_data["status"] == "SENT"
        assert "invite_id" in invite_data
        assert "expires_at" in invite_data

        # Get invites
        invites_response = await client.get(
            f"/v1/relationships/{relationship_id}/invites",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert invites_response.status_code == 200
        invites = invites_response.json()
        assert isinstance(invites, list)
        assert len(invites) >= 1
        assert invites[0]["email"] == "nonexistent@example.com"

    async def test_consent_templates_and_set_consent(self, client: AsyncClient):
        """Test getting consent templates and setting consent."""
        # Signup and create relationship
        signup_response = await client.post(
            "/v1/auth/signup",
            json={
                "email": "consenttest@example.com",
                "password": "testpass123",
            },
        )
        token = signup_response.json()["access_token"]
        me_response = await client.get(
            "/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        user_id = me_response.json()["id"]

        rel_response = await client.post(
            "/v1/relationships",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "type": "romantic",
                "member_ids": [user_id],
            },
        )
        relationship_id = rel_response.json()["id"]

        # Get templates
        templates_response = await client.get(
            f"/v1/relationships/{relationship_id}/consent/templates",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert templates_response.status_code == 200
        templates = templates_response.json()
        assert isinstance(templates, list)
        assert len(templates) > 0
        assert "scopes" in templates[0]

        # Set consent
        consent_response = await client.put(
            f"/v1/relationships/{relationship_id}/consent/me",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "scopes": ["REALTIME_FEATURES_ONLY", "SUMMARY_SHARED"],
                "status": "ACTIVE",
            },
        )
        assert consent_response.status_code == 200
        consent_data = consent_response.json()
        assert consent_data["ok"] is True
        assert consent_data["version"] == 1

        # Set consent again (version should increment)
        consent_response2 = await client.put(
            f"/v1/relationships/{relationship_id}/consent/me",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "scopes": ["REALTIME_FEATURES_ONLY"],
                "status": "ACTIVE",
            },
        )
        assert consent_response2.status_code == 200
        consent_data2 = consent_response2.json()
        assert consent_data2["version"] == 2
