"""Unit tests for agent tools — mock httpx to test tool logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(json_data, status_code=200):
    """Create a mock httpx.Response (sync methods like .json() and .raise_for_status())."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.is_success = 200 <= status_code < 300
    if status_code >= 400:
        from httpx import HTTPStatusError, Request, Response
        real_resp = Response(status_code, request=Request("GET", "http://test"))
        resp.raise_for_status.side_effect = HTTPStatusError(
            "error", request=real_resp.request, response=real_resp
        )
    return resp


def _mock_client(response):
    """Create a mock async httpx client context manager."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    client.post = AsyncMock(return_value=response)
    client.patch = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


async def _call(tool_obj, args):
    """Call an SdkMcpTool's underlying handler function."""
    return await tool_obj.handler(args)


# ---------------------------------------------------------------------------
# PM Coverage
# ---------------------------------------------------------------------------

class TestListPMCoverage:
    @pytest.mark.asyncio
    async def test_list_all(self):
        data = [{"pm_id": "pm-test", "pm_name": "Test PM"}]
        mock_resp = _mock_response(data)
        mock_cl = _mock_client(mock_resp)
        with patch("agent.tools._http._client", return_value=mock_cl):
            from agent.tools.pm_coverage import list_pm_coverage
            result = await _call(list_pm_coverage, {"stage": "", "health": ""})
        assert not result.get("isError")
        assert "pm-test" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_list_with_filter(self):
        data = [{"pm_id": "pm-filtered", "pm_name": "Filtered"}]
        mock_resp = _mock_response(data)
        mock_cl = _mock_client(mock_resp)
        with patch("agent.tools._http._client", return_value=mock_cl):
            from agent.tools.pm_coverage import list_pm_coverage
            result = await _call(list_pm_coverage, {"stage": "live", "health": "green"})
        assert not result.get("isError")
        mock_cl.get.assert_called_once()
        call_kwargs = mock_cl.get.call_args
        assert call_kwargs[1]["params"]["stage"] == "live"


class TestGetPMCoverage:
    @pytest.mark.asyncio
    async def test_get_existing(self):
        data = {
            "pm": {"pm_id": "pm-test", "pm_name": "Test"},
            "open_needs": [],
            "active_blockers": [],
            "upcoming_milestones": [],
        }
        mock_resp = _mock_response(data)
        mock_cl = _mock_client(mock_resp)
        with patch("agent.tools._http._client", return_value=mock_cl):
            from agent.tools.pm_coverage import get_pm_coverage
            result = await _call(get_pm_coverage, {"pm_id": "pm-test"})
        assert not result.get("isError")
        assert "pm-test" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_get_missing_id(self):
        from agent.tools.pm_coverage import get_pm_coverage
        result = await _call(get_pm_coverage, {})
        assert result.get("isError")


class TestCreatePMCoverage:
    @pytest.mark.asyncio
    async def test_create(self):
        data = {"pm_id": "pm-new", "pm_name": "New PM"}
        mock_resp = _mock_response(data, 201)
        mock_cl = _mock_client(mock_resp)
        with patch("agent.tools._http._client", return_value=mock_cl):
            from agent.tools.pm_coverage import create_pm_coverage
            result = await _call(create_pm_coverage, {
                "pm_id": "pm-new", "pm_name": "New PM",
            })
        assert not result.get("isError")
        assert "pm-new" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_create_missing_fields(self):
        from agent.tools.pm_coverage import create_pm_coverage
        result = await _call(create_pm_coverage, {"pm_id": "pm-test"})
        assert result.get("isError")


# ---------------------------------------------------------------------------
# PM Needs
# ---------------------------------------------------------------------------

class TestCreatePMNeed:
    @pytest.mark.asyncio
    async def test_create_auto_generates_id(self):
        data = {"pm_need_id": "need-12345678", "title": "Test need"}
        mock_resp = _mock_response(data, 201)
        mock_cl = _mock_client(mock_resp)
        with patch("agent.tools._http._client", return_value=mock_cl):
            from agent.tools.pm_needs import create_pm_need
            result = await _call(create_pm_need, {
                "pm_id": "pm-test",
                "title": "Test need",
                "category": "market_data",
                "requested_by": "Tester",
            })
        assert not result.get("isError")
        # Verify the posted payload includes auto-generated ID
        posted = mock_cl.post.call_args[1]["json"]
        assert posted["pm_need_id"].startswith("need-")
        assert posted["date_raised"]  # auto-set

    @pytest.mark.asyncio
    async def test_create_missing_required(self):
        from agent.tools.pm_needs import create_pm_need
        result = await _call(create_pm_need, {"pm_id": "pm-test"})
        assert result.get("isError")


# ---------------------------------------------------------------------------
# Risks
# ---------------------------------------------------------------------------

class TestCreateRisk:
    @pytest.mark.asyncio
    async def test_create_auto_generates_id(self):
        data = {"risk_id": "risk-12345678", "title": "Test risk"}
        mock_resp = _mock_response(data, 201)
        mock_cl = _mock_client(mock_resp)
        with patch("agent.tools._http._client", return_value=mock_cl):
            from agent.tools.risks import create_risk
            result = await _call(create_risk, {
                "title": "Data feed delayed",
                "risk_type": "blocker",
                "severity": "high",
            })
        assert not result.get("isError")
        posted = mock_cl.post.call_args[1]["json"]
        assert posted["risk_id"].startswith("risk-")
        assert posted["date_opened"]

    @pytest.mark.asyncio
    async def test_create_with_impacted_ids(self):
        data = {"risk_id": "risk-12345678", "title": "Test"}
        mock_resp = _mock_response(data, 201)
        mock_cl = _mock_client(mock_resp)
        with patch("agent.tools._http._client", return_value=mock_cl):
            from agent.tools.risks import create_risk
            result = await _call(create_risk, {
                "title": "Test",
                "risk_type": "risk",
                "severity": "medium",
                "impacted_pm_ids": "pm-a, pm-b",
            })
        assert not result.get("isError")
        posted = mock_cl.post.call_args[1]["json"]
        assert posted["impacted_pm_ids"] == ["pm-a", "pm-b"]


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------

class TestResolveDecision:
    @pytest.mark.asyncio
    async def test_resolve(self):
        data = {"decision_id": "dec-test", "status": "decided"}
        mock_resp = _mock_response(data)
        mock_cl = _mock_client(mock_resp)
        with patch("agent.tools._http._client", return_value=mock_cl):
            from agent.tools.decisions import resolve_decision
            result = await _call(resolve_decision, {
                "decision_id": "dec-test",
                "chosen_path": "Option A",
                "rationale": "Best fit",
                "approvers": "Alice, Bob",
            })
        assert not result.get("isError")
        posted = mock_cl.post.call_args[1]["json"]
        assert posted["approvers"] == ["Alice", "Bob"]
        assert posted["decision_date"]  # auto-set

    @pytest.mark.asyncio
    async def test_resolve_missing_required(self):
        from agent.tools.decisions import resolve_decision
        result = await _call(resolve_decision, {"decision_id": "dec-test"})
        assert result.get("isError")


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

class TestReports:
    @pytest.mark.asyncio
    async def test_get_agenda(self):
        data = {"generated_on": "2026-03-01", "pms_at_risk": []}
        mock_resp = _mock_response(data)
        mock_cl = _mock_client(mock_resp)
        with patch("agent.tools._http._client", return_value=mock_cl):
            from agent.tools.reports import get_operating_review_agenda
            result = await _call(get_operating_review_agenda, {})
        assert not result.get("isError")

    @pytest.mark.asyncio
    async def test_pm_dashboard_requires_id(self):
        from agent.tools.reports import get_pm_dashboard
        result = await _call(get_pm_dashboard, {})
        assert result.get("isError")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class TestHealth:
    @pytest.mark.asyncio
    async def test_check_health(self):
        data = {"status": "ok"}
        mock_resp = _mock_response(data)
        mock_cl = _mock_client(mock_resp)
        with patch("agent.tools._http._health_client", return_value=mock_cl):
            from agent.tools.health import check_health
            result = await _call(check_health, {})
        assert not result.get("isError")
        assert "ok" in result["content"][0]["text"]
