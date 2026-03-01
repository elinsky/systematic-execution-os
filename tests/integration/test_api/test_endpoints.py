"""Integration tests for FastAPI endpoints.

Uses the test_client fixture (AsyncClient + in-memory SQLite).
Tests cover happy-path CRUD, query filtering, and error responses.
"""

from __future__ import annotations

import pytest
from datetime import date

from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    async def test_health_ok(self, test_client: AsyncClient):
        r = await test_client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# PM Coverage
# ---------------------------------------------------------------------------


class TestPMCoverageEndpoints:
    async def test_list_empty(self, test_client: AsyncClient):
        r = await test_client.get("/api/v1/pm-coverage")
        assert r.status_code == 200
        assert r.json() == []

    async def test_create_and_get(self, test_client: AsyncClient):
        payload = {"pm_id": "pm-test", "pm_name": "Test PM"}
        r = await test_client.post("/api/v1/pm-coverage", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert data["pm_id"] == "pm-test"
        assert data["pm_name"] == "Test PM"

        r2 = await test_client.get("/api/v1/pm-coverage/pm-test")
        assert r2.status_code == 200
        assert r2.json()["pm"]["pm_id"] == "pm-test"

    async def test_create_duplicate_returns_409(self, test_client: AsyncClient):
        payload = {"pm_id": "pm-dup", "pm_name": "Dup PM"}
        await test_client.post("/api/v1/pm-coverage", json=payload)
        r = await test_client.post("/api/v1/pm-coverage", json=payload)
        assert r.status_code == 409

    async def test_get_not_found_returns_404(self, test_client: AsyncClient):
        r = await test_client.get("/api/v1/pm-coverage/ghost")
        assert r.status_code == 404

    async def test_patch(self, test_client: AsyncClient):
        await test_client.post(
            "/api/v1/pm-coverage", json={"pm_id": "pm-patch", "pm_name": "Patch PM"}
        )
        r = await test_client.patch(
            "/api/v1/pm-coverage/pm-patch",
            json={"pm_id": "pm-patch", "health_status": "red"},
        )
        assert r.status_code == 200
        assert r.json()["health_status"] == "red"

    async def test_patch_not_found_returns_404(self, test_client: AsyncClient):
        r = await test_client.patch(
            "/api/v1/pm-coverage/ghost", json={"pm_id": "ghost"}
        )
        assert r.status_code == 404

    async def test_list_filter_by_health(self, test_client: AsyncClient):
        await test_client.post(
            "/api/v1/pm-coverage",
            json={"pm_id": "pm-red", "pm_name": "Red PM", "health_status": "red"},
        )
        await test_client.post(
            "/api/v1/pm-coverage",
            json={"pm_id": "pm-green", "pm_name": "Green PM", "health_status": "green"},
        )
        r = await test_client.get("/api/v1/pm-coverage?health=red")
        assert r.status_code == 200
        result = r.json()
        assert len(result) == 1
        assert result[0]["pm_id"] == "pm-red"


# ---------------------------------------------------------------------------
# PM Needs
# ---------------------------------------------------------------------------


class TestPMNeedEndpoints:
    async def _create_pm(self, client: AsyncClient, pm_id: str = "pm-jane") -> None:
        await client.post(
            "/api/v1/pm-coverage",
            json={"pm_id": pm_id, "pm_name": "Jane"},
        )

    async def test_create_and_get(self, test_client: AsyncClient):
        await self._create_pm(test_client)
        payload = {
            "pm_need_id": "n-1",
            "pm_id": "pm-jane",
            "title": "Market data feed",
            "requested_by": "Jane",
            "date_raised": "2026-01-01",
            "category": "market_data",
        }
        r = await test_client.post("/api/v1/pm-needs", json=payload)
        assert r.status_code == 201
        assert r.json()["pm_need_id"] == "n-1"
        assert r.json()["status"] == "new"

        r2 = await test_client.get("/api/v1/pm-needs/n-1")
        assert r2.status_code == 200
        assert r2.json()["pm_need_id"] == "n-1"

    async def test_get_not_found(self, test_client: AsyncClient):
        r = await test_client.get("/api/v1/pm-needs/ghost")
        assert r.status_code == 404

    async def test_list_unmet_only(self, test_client: AsyncClient):
        await self._create_pm(test_client)
        for i in range(2):
            await test_client.post(
                "/api/v1/pm-needs",
                json={
                    "pm_need_id": f"n-{i}",
                    "pm_id": "pm-jane",
                    "title": f"Need {i}",
                    "requested_by": "Jane",
                    "date_raised": "2026-01-01",
                    "category": "execution",
                },
            )
        r = await test_client.get("/api/v1/pm-needs?unmet_only=true")
        assert r.status_code == 200
        assert len(r.json()) == 2

    async def test_patch_does_not_change_status(self, test_client: AsyncClient):
        await self._create_pm(test_client)
        await test_client.post(
            "/api/v1/pm-needs",
            json={
                "pm_need_id": "n-patch",
                "pm_id": "pm-jane",
                "title": "T",
                "requested_by": "Jane",
                "date_raised": "2026-01-01",
                "category": "other",
            },
        )
        r = await test_client.patch(
            "/api/v1/pm-needs/n-patch",
            json={"pm_need_id": "n-patch", "urgency": "immediate"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["urgency"] == "immediate"
        assert body["status"] == "new"  # D1: status unchanged


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


class TestProjectEndpoints:
    async def test_list_empty(self, test_client: AsyncClient):
        r = await test_client.get("/api/v1/projects")
        assert r.status_code == 200
        assert r.json() == []

    async def test_get_not_found(self, test_client: AsyncClient):
        r = await test_client.get("/api/v1/projects/ghost")
        assert r.status_code == 404

    async def test_patch_not_found(self, test_client: AsyncClient):
        r = await test_client.patch(
            "/api/v1/projects/ghost", json={"project_id": "ghost"}
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Risks
# ---------------------------------------------------------------------------


class TestRiskEndpoints:
    async def test_create_and_list(self, test_client: AsyncClient):
        payload = {
            "risk_id": "r-1",
            "title": "Data feed delayed",
            "date_opened": "2026-01-01",
            "risk_type": "blocker",
            "severity": "high",
        }
        r = await test_client.post("/api/v1/risks", json=payload)
        assert r.status_code == 201
        assert r.json()["risk_id"] == "r-1"

        r2 = await test_client.get("/api/v1/risks?open_only=true")
        assert r2.status_code == 200
        assert any(risk["risk_id"] == "r-1" for risk in r2.json())

    async def test_patch_resolve(self, test_client: AsyncClient):
        await test_client.post(
            "/api/v1/risks",
            json={
                "risk_id": "r-resolve",
                "title": "T",
                "date_opened": "2026-01-01",
                "risk_type": "risk",
                "severity": "low",
            },
        )
        r = await test_client.patch(
            "/api/v1/risks/r-resolve",
            json={"risk_id": "r-resolve", "status": "resolved"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "resolved"

    async def test_patch_not_found(self, test_client: AsyncClient):
        r = await test_client.patch(
            "/api/v1/risks/ghost", json={"risk_id": "ghost"}
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------


class TestDecisionEndpoints:
    async def test_create_and_list(self, test_client: AsyncClient):
        payload = {"decision_id": "d-1", "title": "Choose broker"}
        r = await test_client.post("/api/v1/decisions", json=payload)
        assert r.status_code == 201
        assert r.json()["decision_id"] == "d-1"
        assert r.json()["status"] == "pending"

        r2 = await test_client.get("/api/v1/decisions?pending_only=true")
        assert r2.status_code == 200
        assert any(d["decision_id"] == "d-1" for d in r2.json())

    async def test_resolve(self, test_client: AsyncClient):
        await test_client.post(
            "/api/v1/decisions", json={"decision_id": "d-resolve", "title": "Pick infra"}
        )
        r = await test_client.post(
            "/api/v1/decisions/d-resolve/resolve",
            json={
                "decision_id": "d-resolve",
                "chosen_path": "AWS",
                "rationale": "Best SLA",
                "approvers": ["Alice"],
                "decision_date": "2026-03-01",
            },
        )
        assert r.status_code == 200
        assert r.json()["status"] == "decided"

    async def test_resolve_twice_returns_409(self, test_client: AsyncClient):
        await test_client.post(
            "/api/v1/decisions", json={"decision_id": "d-dup", "title": "T"}
        )
        resolve_payload = {
            "decision_id": "d-dup",
            "chosen_path": "A",
            "rationale": "R",
            "approvers": [],
            "decision_date": "2026-03-01",
        }
        await test_client.post("/api/v1/decisions/d-dup/resolve", json=resolve_payload)
        r = await test_client.post(
            "/api/v1/decisions/d-dup/resolve", json=resolve_payload
        )
        assert r.status_code == 409

    async def test_resolve_not_found_returns_404(self, test_client: AsyncClient):
        r = await test_client.post(
            "/api/v1/decisions/ghost/resolve",
            json={
                "decision_id": "ghost",
                "chosen_path": "X",
                "rationale": "Y",
                "approvers": [],
                "decision_date": "2026-03-01",
            },
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------


class TestMilestoneEndpoints:
    async def test_patch_not_found(self, test_client: AsyncClient):
        r = await test_client.patch(
            "/api/v1/milestones/ghost", json={"milestone_id": "ghost"}
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Operating Review
# ---------------------------------------------------------------------------


class TestOperatingReviewEndpoints:
    async def test_empty_agenda(self, test_client: AsyncClient):
        r = await test_client.get("/api/v1/operating-review/agenda")
        assert r.status_code == 200
        body = r.json()
        assert body["pms_at_risk"] == []
        assert body["aging_blockers"] == []
        assert body["pending_decisions"] == []

    async def test_at_risk_pms_empty(self, test_client: AsyncClient):
        r = await test_client.get("/api/v1/operating-review/at-risk-pms")
        assert r.status_code == 200
        assert r.json() == []

    async def test_pm_needs_summary_empty(self, test_client: AsyncClient):
        r = await test_client.get("/api/v1/operating-review/pm-needs-summary")
        assert r.status_code == 200
        body = r.json()
        assert body["by_category"] == {}
        assert body["unmet_by_pm"] == []

    async def test_milestone_calendar_empty(self, test_client: AsyncClient):
        r = await test_client.get("/api/v1/operating-review/milestone-calendar")
        assert r.status_code == 200
        assert r.json() == []

    async def test_agenda_includes_red_pm(self, test_client: AsyncClient):
        await test_client.post(
            "/api/v1/pm-coverage",
            json={"pm_id": "pm-red", "pm_name": "Red PM", "health_status": "red"},
        )
        r = await test_client.get("/api/v1/operating-review/agenda")
        assert r.status_code == 200
        at_risk = r.json()["pms_at_risk"]
        assert len(at_risk) == 1
        assert at_risk[0]["pm"]["pm_id"] == "pm-red"

    async def test_agenda_includes_pending_decision(self, test_client: AsyncClient):
        await test_client.post(
            "/api/v1/decisions",
            json={"decision_id": "d-pending", "title": "Choose vendor"},
        )
        r = await test_client.get("/api/v1/operating-review/agenda")
        assert r.status_code == 200
        assert len(r.json()["pending_decisions"]) == 1
