"""
Integration tests for scan endpoints:
  POST   /api/scan
  GET    /api/scan/{id}
  DELETE /api/scan/{id}
  GET    /api/scans
  PATCH  /api/finding/{id}/lifecycle
  GET    /api/health
"""
import json
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
from tests.conftest import create_admin


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class TestHealth:
    async def test_health_ok(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Scan start (no users = legacy mode, auth disabled)
# ---------------------------------------------------------------------------

class TestStartScan:
    async def test_start_single_domain_scan(self, client: AsyncClient):
        resp = await client.post("/api/scan", json={"domain": "bkn.go.id"})
        assert resp.status_code == 202
        data = resp.json()
        assert "scan_id" in data
        assert len(data["scan_id"]) == 36  # UUID

    async def test_start_scan_creates_module_statuses(self, client: AsyncClient):
        resp = await client.post("/api/scan", json={"domain": "bkn.go.id"})
        scan_id = resp.json()["scan_id"]

        status_resp = await client.get(f"/api/scan/{scan_id}")
        assert status_resp.status_code == 200
        data = status_resp.json()
        modules = {m["module"] for m in data["modules"]}
        # Core modules always present
        assert "dork_sweep" in modules
        assert "header_probe" in modules
        assert "subdomain_enum" in modules
        # shodan_probe absent when no SHODAN_API_KEY
        assert "shodan_probe" not in modules

    async def test_start_tld_sweep(self, client: AsyncClient):
        resp = await client.post("/api/scan", json={"domain": ".go.id"})
        assert resp.status_code == 202

    async def test_missing_domain_field_rejected(self, client: AsyncClient):
        resp = await client.post("/api/scan", json={})
        assert resp.status_code == 422

    async def test_analyst_can_start_scan(self, client: AsyncClient):
        admin_creds = await create_admin(client)
        # Create analyst
        analyst_resp = await client.post(
            "/api/auth/users",
            json={"username": "analyst1", "password": "analystpass1", "role": "analyst"},
            headers={"X-API-Key": admin_creds["api_key"]},
        )
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "analyst1", "password": "analystpass1"},
        )
        analyst_key = login_resp.json()["api_key"]
        resp = await client.post(
            "/api/scan",
            json={"domain": "bkn.go.id"},
            headers={"X-API-Key": analyst_key},
        )
        assert resp.status_code == 202

    async def test_read_only_cannot_start_scan(self, client: AsyncClient):
        admin_creds = await create_admin(client)
        await client.post(
            "/api/auth/users",
            json={"username": "viewer", "password": "viewerpass1", "role": "read-only"},
            headers={"X-API-Key": admin_creds["api_key"]},
        )
        login_resp = await client.post(
            "/api/auth/login",
            json={"username": "viewer", "password": "viewerpass1"},
        )
        viewer_key = login_resp.json()["api_key"]
        resp = await client.post(
            "/api/scan",
            json={"domain": "bkn.go.id"},
            headers={"X-API-Key": viewer_key},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Scan status
# ---------------------------------------------------------------------------

class TestGetScan:
    async def test_get_pending_scan(self, client: AsyncClient):
        start_resp = await client.post("/api/scan", json={"domain": "bkn.go.id"})
        scan_id = start_resp.json()["scan_id"]

        resp = await client.get(f"/api/scan/{scan_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scan_id"] == scan_id
        assert data["domain"] == "bkn.go.id"
        assert data["status"] == "pending"
        assert isinstance(data["findings"], list)
        assert isinstance(data["modules"], list)

    async def test_get_nonexistent_scan_returns_404(self, client: AsyncClient):
        resp = await client.get("/api/scan/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Scan history
# ---------------------------------------------------------------------------

class TestScanHistory:
    async def test_empty_history(self, client: AsyncClient):
        resp = await client.get("/api/scans")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["scans"] == []

    async def test_history_shows_created_scans(self, client: AsyncClient):
        await client.post("/api/scan", json={"domain": "bkn.go.id"})
        await client.post("/api/scan", json={"domain": "kpu.go.id"})

        resp = await client.get("/api/scans")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    async def test_history_filter_by_domain(self, client: AsyncClient):
        await client.post("/api/scan", json={"domain": "bkn.go.id"})
        await client.post("/api/scan", json={"domain": "kpu.go.id"})

        resp = await client.get("/api/scans?domain=bkn.go.id")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["scans"][0]["domain"] == "bkn.go.id"

    async def test_history_pagination(self, client: AsyncClient):
        for i in range(5):
            await client.post("/api/scan", json={"domain": f"domain{i}.go.id"})

        resp = await client.get("/api/scans?limit=2&page=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["scans"]) == 2
        assert data["total"] == 5


# ---------------------------------------------------------------------------
# Scan cancellation
# ---------------------------------------------------------------------------

class TestCancelScan:
    async def test_cancel_pending_scan(self, client: AsyncClient):
        start_resp = await client.post("/api/scan", json={"domain": "bkn.go.id"})
        scan_id = start_resp.json()["scan_id"]

        with patch("app.worker.celery_app") as mock_celery:
            mock_celery.control.revoke = MagicMock()
            resp = await client.delete(f"/api/scan/{scan_id}")
        assert resp.status_code == 200

        # Verify status updated
        status_resp = await client.get(f"/api/scan/{scan_id}")
        assert status_resp.json()["status"] == "cancelled"

    async def test_cancel_nonexistent_scan(self, client: AsyncClient):
        with patch("app.worker.celery_app"):
            resp = await client.delete("/api/scan/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Finding lifecycle
# ---------------------------------------------------------------------------

class TestFindingLifecycle:
    async def _create_scan_with_finding(self, client: AsyncClient) -> tuple[str, str]:
        """Start a scan and manually inject a finding; return (scan_id, finding_id)."""
        start_resp = await client.post("/api/scan", json={"domain": "bkn.go.id"})
        scan_id = start_resp.json()["scan_id"]

        # Directly insert a finding via DB
        from tests.conftest import TestSession
        from app.models.scan import Finding
        async with TestSession() as db:
            f = Finding(
                scan_job_id=scan_id,
                module="header_probe",
                severity="medium",
                url="https://bkn.go.id",
                title="Missing CSP header",
                lifecycle_status="open",
            )
            db.add(f)
            await db.commit()
            await db.refresh(f)
            return scan_id, f.id

    async def test_update_lifecycle_to_resolved(self, client: AsyncClient):
        _scan_id, finding_id = await self._create_scan_with_finding(client)
        resp = await client.patch(
            f"/api/finding/{finding_id}/lifecycle",
            json={"lifecycle_status": "resolved"},
        )
        assert resp.status_code == 200
        assert resp.json()["lifecycle_status"] == "resolved"

    async def test_invalid_lifecycle_status(self, client: AsyncClient):
        _scan_id, finding_id = await self._create_scan_with_finding(client)
        resp = await client.patch(
            f"/api/finding/{finding_id}/lifecycle",
            json={"lifecycle_status": "nonexistent"},
        )
        assert resp.status_code == 422

    async def test_patch_nonexistent_finding(self, client: AsyncClient):
        resp = await client.patch(
            "/api/finding/00000000-0000-0000-0000-000000000000/lifecycle",
            json={"lifecycle_status": "resolved"},
        )
        assert resp.status_code == 404
