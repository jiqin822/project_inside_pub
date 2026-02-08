"""Relationship tests."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_list_relationships(client: AsyncClient):
    """Test create relationship -> list relationships flow."""
    # First, create a user and get token
    signup_response = await client.post(
        "/v1/auth/signup",
        json={
            "email": "user1@example.com",
            "password": "pass123",
        },
    )
    assert signup_response.status_code in [200, 201]
    token = signup_response.json()["access_token"]

    # Create relationship
    create_response = await client.post(
        "/v1/relationships",
        json={
            "rel_type": "romantic",
            "member_ids": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code in [200, 201]
    rel_data = create_response.json()
    assert "id" in rel_data
    assert rel_data["rel_type"] == "romantic"

    # List relationships
    list_response = await client.get(
        "/v1/relationships",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    relationships = list_response.json()
    assert isinstance(relationships, list)
    assert len(relationships) >= 1
