"""Authentication tests."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestSignup:
    """Test user signup functionality."""

    async def test_signup_success(self, client: AsyncClient):
        """Test successful user signup."""
        response = await client.post(
            "/v1/auth/signup",
            json={
                "email": "newuser@example.com",
                "password": "securepass123",
                "display_name": "New User",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert isinstance(data["access_token"], str)
        assert isinstance(data["refresh_token"], str)
        assert len(data["access_token"]) > 0
        assert len(data["refresh_token"]) > 0

    async def test_signup_without_display_name(self, client: AsyncClient):
        """Test signup without optional display_name."""
        response = await client.post(
            "/v1/auth/signup",
            json={
                "email": "nodisplay@example.com",
                "password": "securepass123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_signup_duplicate_email(self, client: AsyncClient):
        """Test signup with duplicate email should fail."""
        # First signup
        await client.post(
            "/v1/auth/signup",
            json={
                "email": "duplicate@example.com",
                "password": "securepass123",
            },
        )

        # Second signup with same email
        response = await client.post(
            "/v1/auth/signup",
            json={
                "email": "duplicate@example.com",
                "password": "anotherpass123",
            },
        )
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    async def test_signup_invalid_email(self, client: AsyncClient):
        """Test signup with invalid email format."""
        response = await client.post(
            "/v1/auth/signup",
            json={
                "email": "not-an-email",
                "password": "securepass123",
            },
        )
        assert response.status_code == 422  # Validation error

    async def test_signup_missing_fields(self, client: AsyncClient):
        """Test signup with missing required fields."""
        # Missing email
        response = await client.post(
            "/v1/auth/signup",
            json={
                "password": "securepass123",
            },
        )
        assert response.status_code == 422

        # Missing password
        response = await client.post(
            "/v1/auth/signup",
            json={
                "email": "test@example.com",
            },
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestLogin:
    """Test user login functionality."""

    async def test_login_success(self, client: AsyncClient):
        """Test successful login."""
        # First create a user
        await client.post(
            "/v1/auth/signup",
            json={
                "email": "loginuser@example.com",
                "password": "testpass123",
                "display_name": "Login User",
            },
        )

        # Then login
        response = await client.post(
            "/v1/auth/login",
            json={
                "email": "loginuser@example.com",
                "password": "testpass123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert isinstance(data["access_token"], str)
        assert isinstance(data["refresh_token"], str)

    async def test_login_wrong_password(self, client: AsyncClient):
        """Test login with incorrect password."""
        # Create user first
        await client.post(
            "/v1/auth/signup",
            json={
                "email": "wrongpass@example.com",
                "password": "correctpass123",
            },
        )

        # Try login with wrong password
        response = await client.post(
            "/v1/auth/login",
            json={
                "email": "wrongpass@example.com",
                "password": "wrongpassword",
            },
        )
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with non-existent email."""
        response = await client.post(
            "/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "somepassword",
            },
        )
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    async def test_login_missing_fields(self, client: AsyncClient):
        """Test login with missing required fields."""
        # Missing email
        response = await client.post(
            "/v1/auth/login",
            json={
                "password": "testpass123",
            },
        )
        assert response.status_code == 422

        # Missing password
        response = await client.post(
            "/v1/auth/login",
            json={
                "email": "loginuser@example.com",
            },
        )
        assert response.status_code == 422

    async def test_login_invalid_email_format(self, client: AsyncClient):
        """Test login with invalid email format."""
        response = await client.post(
            "/v1/auth/login",
            json={
                "email": "not-an-email",
                "password": "testpass123",
            },
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestTokenRefresh:
    """Test token refresh functionality."""

    async def test_refresh_token_success(self, client: AsyncClient):
        """Test successful token refresh."""
        # Get refresh token from signup
        signup_response = await client.post(
            "/v1/auth/signup",
            json={
                "email": "refreshtest2@example.com",
                "password": "testpass123",
            },
        )
        original_refresh_token = signup_response.json()["refresh_token"]

        # Refresh tokens
        response = await client.post(
            "/v1/auth/refresh",
            json={
                "refresh_token": original_refresh_token,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert isinstance(data["access_token"], str)
        assert isinstance(data["refresh_token"], str)
        assert len(data["access_token"]) > 0
        assert len(data["refresh_token"]) > 0
        
        # New access token should be valid (can use it to get user info)
        me_response = await client.get(
            "/v1/users/me",
            headers={"Authorization": f"Bearer {data['access_token']}"},
        )
        assert me_response.status_code == 200
        
        # New refresh token should also work for another refresh
        refresh_response2 = await client.post(
            "/v1/auth/refresh",
            json={
                "refresh_token": data["refresh_token"],
            },
        )
        assert refresh_response2.status_code == 200

    async def test_refresh_invalid_token(self, client: AsyncClient):
        """Test refresh with invalid token."""
        response = await client.post(
            "/v1/auth/refresh",
            json={
                "refresh_token": "invalid.token.here",
            },
        )
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    async def test_refresh_missing_token(self, client: AsyncClient):
        """Test refresh without token."""
        response = await client.post(
            "/v1/auth/refresh",
            json={},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestAuthenticatedEndpoints:
    """Test endpoints that require authentication."""

    async def test_get_me_success(self, client: AsyncClient):
        """Test getting current user info with valid token."""
        # Create user and get token
        signup_response = await client.post(
            "/v1/auth/signup",
            json={
                "email": "authtest@example.com",
                "password": "testpass123",
                "display_name": "Auth Test User",
            },
        )
        access_token = signup_response.json()["access_token"]

        # Get user info
        response = await client.get(
            "/v1/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "authtest@example.com"
        assert data["display_name"] == "Auth Test User"
        assert "id" in data

    async def test_get_me_without_token(self, client: AsyncClient):
        """Test getting user info without token."""
        response = await client.get("/v1/users/me")
        assert response.status_code == 401  # Unauthorized

    async def test_get_me_with_invalid_token(self, client: AsyncClient):
        """Test getting user info with invalid token."""
        response = await client.get(
            "/v1/users/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestSignupLoginFlow:
    """Test complete signup -> login -> use token flow."""

    async def test_complete_flow(self, client: AsyncClient):
        """Test complete authentication flow."""
        # 1. Signup
        signup_response = await client.post(
            "/v1/auth/signup",
            json={
                "email": "flowtest@example.com",
                "password": "testpass123",
                "display_name": "Flow Test User",
            },
        )
        assert signup_response.status_code == 200
        signup_data = signup_response.json()
        signup_access_token = signup_data["access_token"]
        signup_refresh_token = signup_data["refresh_token"]

        # 2. Use signup token to get user info
        me_response = await client.get(
            "/v1/users/me",
            headers={"Authorization": f"Bearer {signup_access_token}"},
        )
        assert me_response.status_code == 200
        assert me_response.json()["email"] == "flowtest@example.com"

        # 3. Login with same credentials
        login_response = await client.post(
            "/v1/auth/login",
            json={
                "email": "flowtest@example.com",
                "password": "testpass123",
            },
        )
        assert login_response.status_code == 200
        login_data = login_response.json()
        login_access_token = login_data["access_token"]
        login_refresh_token = login_data["refresh_token"]

        # 4. Use login token to get user info
        me_response2 = await client.get(
            "/v1/users/me",
            headers={"Authorization": f"Bearer {login_access_token}"},
        )
        assert me_response2.status_code == 200
        assert me_response2.json()["email"] == "flowtest@example.com"

        # 5. Refresh token
        refresh_response = await client.post(
            "/v1/auth/refresh",
            json={
                "refresh_token": login_refresh_token,
            },
        )
        assert refresh_response.status_code == 200
        refresh_data = refresh_response.json()
        assert "access_token" in refresh_data
        assert "refresh_token" in refresh_data

        # 6. Use refreshed token
        me_response3 = await client.get(
            "/v1/users/me",
            headers={"Authorization": f"Bearer {refresh_data['access_token']}"},
        )
        assert me_response3.status_code == 200
        assert me_response3.json()["email"] == "flowtest@example.com"
