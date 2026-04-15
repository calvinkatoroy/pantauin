"""
Integration tests for auth endpoints:
  GET  /api/auth/setup-required
  POST /api/auth/setup
  POST /api/auth/login
  GET  /api/auth/me
  GET  /api/auth/users
  POST /api/auth/users
  PATCH /api/auth/users/{id}
  DELETE /api/auth/users/{id}
"""
import pytest
from httpx import AsyncClient
from tests.conftest import create_admin, create_analyst


class TestSetupRequired:
    async def test_setup_required_when_no_users(self, client: AsyncClient):
        resp = await client.get("/api/auth/setup-required")
        assert resp.status_code == 200
        assert resp.json()["setup_required"] is True

    async def test_setup_not_required_after_first_admin(self, client: AsyncClient):
        await create_admin(client)
        resp = await client.get("/api/auth/setup-required")
        assert resp.status_code == 200
        assert resp.json()["setup_required"] is False


class TestSetup:
    async def test_creates_admin_with_api_key(self, client: AsyncClient):
        resp = await client.post(
            "/api/auth/setup",
            json={"username": "firstadmin", "password": "securepass1"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "firstadmin"
        assert data["role"] == "admin"
        assert len(data["api_key"]) == 32

    async def test_setup_rejects_short_password(self, client: AsyncClient):
        resp = await client.post(
            "/api/auth/setup",
            json={"username": "admin", "password": "short"},
        )
        assert resp.status_code == 422

    async def test_setup_conflicts_when_users_exist(self, client: AsyncClient):
        await create_admin(client)
        resp = await client.post(
            "/api/auth/setup",
            json={"username": "second", "password": "secondpass"},
        )
        assert resp.status_code == 409


class TestLogin:
    async def test_valid_credentials_return_api_key(self, client: AsyncClient):
        await create_admin(client)
        resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "adminpass123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "admin"
        assert len(data["api_key"]) == 32

    async def test_wrong_password_returns_401(self, client: AsyncClient):
        await create_admin(client)
        resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrongpass"},
        )
        assert resp.status_code == 401

    async def test_unknown_user_returns_401(self, client: AsyncClient):
        await create_admin(client)
        resp = await client.post(
            "/api/auth/login",
            json={"username": "nobody", "password": "adminpass123"},
        )
        assert resp.status_code == 401

    async def test_login_before_setup_returns_503(self, client: AsyncClient):
        resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "adminpass123"},
        )
        assert resp.status_code == 503


class TestMe:
    async def test_returns_own_profile(self, client: AsyncClient):
        creds = await create_admin(client)
        resp = await client.get("/api/auth/me", headers={"X-API-Key": creds["api_key"]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "admin"
        assert data["role"] == "admin"

    async def test_invalid_key_returns_401(self, client: AsyncClient):
        await create_admin(client)
        resp = await client.get("/api/auth/me", headers={"X-API-Key": "badbadbadbadbadbadbadbadbadbadba"})
        assert resp.status_code == 401


class TestUserManagement:
    async def test_admin_can_list_users(self, client: AsyncClient):
        creds = await create_admin(client)
        resp = await client.get("/api/auth/users", headers={"X-API-Key": creds["api_key"]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["users"][0]["username"] == "admin"

    async def test_analyst_cannot_list_users(self, client: AsyncClient):
        admin_creds = await create_admin(client)
        analyst = await create_analyst(client, admin_creds["api_key"])
        # Get analyst api_key via login
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "analyst1", "password": "analystpass1"},
        )
        analyst_key = login_resp.json()["api_key"]
        resp = await client.get("/api/auth/users", headers={"X-API-Key": analyst_key})
        assert resp.status_code == 403

    async def test_create_user_duplicate_username(self, client: AsyncClient):
        creds = await create_admin(client)
        await client.post(
            "/api/auth/users",
            json={"username": "dupuser", "password": "password123", "role": "analyst"},
            headers={"X-API-Key": creds["api_key"]},
        )
        resp = await client.post(
            "/api/auth/users",
            json={"username": "dupuser", "password": "password123", "role": "analyst"},
            headers={"X-API-Key": creds["api_key"]},
        )
        assert resp.status_code == 409

    async def test_create_user_invalid_role(self, client: AsyncClient):
        creds = await create_admin(client)
        resp = await client.post(
            "/api/auth/users",
            json={"username": "baduser", "password": "password123", "role": "superadmin"},
            headers={"X-API-Key": creds["api_key"]},
        )
        assert resp.status_code == 400

    async def test_patch_user_role(self, client: AsyncClient):
        creds = await create_admin(client)
        analyst = await create_analyst(client, creds["api_key"])
        resp = await client.patch(
            f"/api/auth/users/{analyst['id']}",
            json={"role": "read-only"},
            headers={"X-API-Key": creds["api_key"]},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "read-only"

    async def test_admin_cannot_demote_themselves(self, client: AsyncClient):
        creds = await create_admin(client)
        # Get admin user id
        users_resp = await client.get("/api/auth/users", headers={"X-API-Key": creds["api_key"]})
        admin_id = users_resp.json()["users"][0]["id"]
        resp = await client.patch(
            f"/api/auth/users/{admin_id}",
            json={"role": "analyst"},
            headers={"X-API-Key": creds["api_key"]},
        )
        assert resp.status_code == 400

    async def test_deactivate_user(self, client: AsyncClient):
        creds = await create_admin(client)
        analyst = await create_analyst(client, creds["api_key"])
        resp = await client.delete(
            f"/api/auth/users/{analyst['id']}",
            headers={"X-API-Key": creds["api_key"]},
        )
        assert resp.status_code == 204

        # Deactivated user should not be able to login
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "analyst1", "password": "analystpass1"},
        )
        assert login_resp.status_code == 401

    async def test_admin_cannot_delete_themselves(self, client: AsyncClient):
        creds = await create_admin(client)
        users_resp = await client.get("/api/auth/users", headers={"X-API-Key": creds["api_key"]})
        admin_id = users_resp.json()["users"][0]["id"]
        resp = await client.delete(
            f"/api/auth/users/{admin_id}",
            headers={"X-API-Key": creds["api_key"]},
        )
        assert resp.status_code == 400
