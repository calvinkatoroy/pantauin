"""
Unit tests for subdomain enumeration.
DNS resolution and HTTP calls are mocked so no network access is needed.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSubdomainEnum:
    async def test_returns_live_subdomains(self):
        from app.scanner import subdomain_enum

        # Mock crt.sh to return two SANs
        mock_crt_response = MagicMock()
        mock_crt_response.status_code = 200
        mock_crt_response.json.return_value = [
            {"name_value": "mail.example.go.id"},
            {"name_value": "api.example.go.id"},
            {"name_value": "*.example.go.id"},
        ]

        # Mock DNS: mail resolves, api resolves, prefix probes all fail
        async def mock_resolve(hostname: str):
            mapping = {
                "mail.example.go.id": "1.2.3.4",
                "api.example.go.id": "1.2.3.5",
            }
            return mapping.get(hostname)

        with (
            patch.object(subdomain_enum, "_crtsh_subdomains", return_value={"mail.example.go.id", "api.example.go.id"}),
            patch.object(subdomain_enum, "_probe_common_prefixes", return_value=set()),
            patch.object(subdomain_enum, "_resolve", side_effect=mock_resolve),
        ):
            result = await subdomain_enum.run("example.go.id")

        assert result["status"] == "success"
        assert result["error"] is None
        urls = {f["url"] for f in result["findings"]}
        assert "https://mail.example.go.id" in urls
        assert "https://api.example.go.id" in urls

    async def test_dead_subdomains_excluded(self):
        from app.scanner import subdomain_enum

        async def mock_resolve(hostname: str):
            return None  # nothing resolves

        with (
            patch.object(subdomain_enum, "_crtsh_subdomains", return_value={"dead.example.go.id"}),
            patch.object(subdomain_enum, "_probe_common_prefixes", return_value=set()),
            patch.object(subdomain_enum, "_resolve", side_effect=mock_resolve),
        ):
            result = await subdomain_enum.run("example.go.id")

        assert result["status"] == "success"
        assert result["findings"] == []

    async def test_root_domain_excluded_from_results(self):
        from app.scanner import subdomain_enum

        async def mock_resolve(hostname: str):
            if hostname == "example.go.id":
                return "1.2.3.4"
            return None

        with (
            patch.object(subdomain_enum, "_crtsh_subdomains", return_value={"example.go.id"}),
            patch.object(subdomain_enum, "_probe_common_prefixes", return_value=set()),
            patch.object(subdomain_enum, "_resolve", side_effect=mock_resolve),
        ):
            result = await subdomain_enum.run("example.go.id")

        # Root domain itself should not appear as a finding
        assert result["findings"] == []

    async def test_respects_subdomain_max(self, monkeypatch):
        from app.scanner import subdomain_enum
        from app.core.config import settings

        monkeypatch.setattr(settings, "subdomain_max", 2)

        # Simulate 10 live subdomains from crt.sh
        subs = {f"sub{i}.example.go.id" for i in range(10)}

        async def mock_resolve(hostname: str):
            return "1.2.3.4"

        with (
            patch.object(subdomain_enum, "_crtsh_subdomains", return_value=subs),
            patch.object(subdomain_enum, "_probe_common_prefixes", return_value=set()),
            patch.object(subdomain_enum, "_resolve", side_effect=mock_resolve),
        ):
            result = await subdomain_enum.run("example.go.id")

        assert len(result["findings"]) == 2

    async def test_findings_are_info_severity(self):
        from app.scanner import subdomain_enum

        async def mock_resolve(hostname: str):
            return "1.2.3.4"

        with (
            patch.object(subdomain_enum, "_crtsh_subdomains", return_value={"mail.example.go.id"}),
            patch.object(subdomain_enum, "_probe_common_prefixes", return_value=set()),
            patch.object(subdomain_enum, "_resolve", side_effect=mock_resolve),
        ):
            result = await subdomain_enum.run("example.go.id")

        assert all(f["severity"] == "info" for f in result["findings"])

    async def test_crtsh_failure_does_not_crash(self):
        from app.scanner import subdomain_enum

        async def mock_resolve(hostname: str):
            return "1.2.3.4"

        with (
            # crt.sh raises an exception
            patch.object(subdomain_enum, "_crtsh_subdomains", side_effect=Exception("network error")),
            patch.object(subdomain_enum, "_probe_common_prefixes", return_value={"www.example.go.id"}),
            patch.object(subdomain_enum, "_resolve", side_effect=mock_resolve),
        ):
            result = await subdomain_enum.run("example.go.id")

        # Should still return error status from the outer exception handler
        assert result["module"] == "subdomain_enum"
        assert result["status"] == "error"

    async def test_www_root_excluded(self):
        from app.scanner import subdomain_enum

        async def mock_resolve(hostname: str):
            return "1.2.3.4"

        with (
            patch.object(subdomain_enum, "_crtsh_subdomains", return_value={"www.example.go.id"}),
            patch.object(subdomain_enum, "_probe_common_prefixes", return_value=set()),
            patch.object(subdomain_enum, "_resolve", side_effect=mock_resolve),
        ):
            result = await subdomain_enum.run("example.go.id")

        # www.root is excluded by design (not interesting)
        assert result["findings"] == []


class TestExtractRoot:
    def test_strips_www(self):
        from app.scanner.subdomain_enum import _extract_root
        assert _extract_root("www.bkn.go.id") == "bkn.go.id"

    def test_no_change_without_www(self):
        from app.scanner.subdomain_enum import _extract_root
        assert _extract_root("bkn.go.id") == "bkn.go.id"

    def test_lowercases(self):
        from app.scanner.subdomain_enum import _extract_root
        assert _extract_root("BKN.GO.ID") == "bkn.go.id"
