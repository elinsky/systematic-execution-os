"""Integration tests for the Reports API endpoints.

Uses the test_client fixture (AsyncClient + in-memory SQLite).
Tests cover empty-state responses, populated data aggregation,
PM dashboard 404, and portfolio health metrics.
"""

from __future__ import annotations

from datetime import date, timedelta

from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Weekly Status Report
# ---------------------------------------------------------------------------


class TestWeeklyStatusReport:
    async def test_empty_weekly_status(self, test_client: AsyncClient):
        """Weekly status report with no data returns zeroed summaries."""
        r = await test_client.get("/api/v1/reports/weekly-status")
        assert r.status_code == 200
        body = r.json()
        assert body["pm_coverage"]["total"] == 0
        assert body["open_needs"]["total_open"] == 0
        assert body["risks"]["total_open"] == 0
        assert body["milestones"]["upcoming_14d"] == []
        assert body["milestones"]["overdue"] == []
        assert body["decisions"]["pending_count"] == 0
        assert body["decisions"]["avg_days_pending"] is None
        assert "generated_on" in body

    async def test_weekly_status_with_data(self, test_client: AsyncClient):
        """Weekly status report aggregates PM, need, risk, and decision data."""
        # Create 2 PMs with different health/stage
        await test_client.post(
            "/api/v1/pm-coverage",
            json={
                "pm_id": "pm-alice",
                "pm_name": "Alice",
                "health_status": "green",
                "onboarding_stage": "live",
            },
        )
        await test_client.post(
            "/api/v1/pm-coverage",
            json={
                "pm_id": "pm-bob",
                "pm_name": "Bob",
                "health_status": "red",
                "onboarding_stage": "uat",
            },
        )

        # Create open need
        await test_client.post(
            "/api/v1/pm-needs",
            json={
                "pm_need_id": "n-1",
                "pm_id": "pm-alice",
                "title": "Market data",
                "requested_by": "Alice",
                "date_raised": "2026-02-01",
                "category": "market_data",
                "urgency": "this_week",
            },
        )

        # Create open risk
        await test_client.post(
            "/api/v1/risks",
            json={
                "risk_id": "r-1",
                "title": "Feed delay",
                "date_opened": str(date.today() - timedelta(days=10)),
                "risk_type": "blocker",
                "severity": "high",
            },
        )

        # Create pending decision
        await test_client.post(
            "/api/v1/decisions",
            json={"decision_id": "d-1", "title": "Pick vendor"},
        )

        r = await test_client.get("/api/v1/reports/weekly-status")
        assert r.status_code == 200
        body = r.json()

        # PM coverage
        assert body["pm_coverage"]["total"] == 2
        assert body["pm_coverage"]["by_stage"]["live"] == 1
        assert body["pm_coverage"]["by_stage"]["uat"] == 1
        assert body["pm_coverage"]["by_health"]["green"] == 1
        assert body["pm_coverage"]["by_health"]["red"] == 1

        # Open needs
        assert body["open_needs"]["total_open"] == 1
        assert body["open_needs"]["by_category"]["market_data"] == 1
        assert body["open_needs"]["by_urgency"]["this_week"] == 1
        assert body["open_needs"]["oldest_open_days"] is not None

        # Risks
        assert body["risks"]["total_open"] == 1
        assert body["risks"]["by_severity"]["high"] == 1
        assert body["risks"]["aging_count"] == 1  # > 7 days old

        # Decisions
        assert body["decisions"]["pending_count"] == 1


# ---------------------------------------------------------------------------
# PM Dashboard
# ---------------------------------------------------------------------------


class TestPMDashboard:
    async def test_pm_not_found_returns_404(self, test_client: AsyncClient):
        """PM dashboard for non-existent PM returns 404."""
        r = await test_client.get("/api/v1/reports/pm/pm-ghost/dashboard")
        assert r.status_code == 404

    async def test_pm_dashboard_with_data(self, test_client: AsyncClient):
        """PM dashboard returns the PM record, their needs, and risks."""
        # Create PM
        await test_client.post(
            "/api/v1/pm-coverage",
            json={
                "pm_id": "pm-jane",
                "pm_name": "Jane",
                "health_status": "yellow",
                "last_touchpoint_date": str(date.today() - timedelta(days=5)),
            },
        )

        # Create an open need for this PM
        await test_client.post(
            "/api/v1/pm-needs",
            json={
                "pm_need_id": "n-jane-1",
                "pm_id": "pm-jane",
                "title": "Historical data",
                "requested_by": "Jane",
                "date_raised": "2026-01-15",
                "category": "historical_data",
            },
        )

        # Create risk impacting this PM
        await test_client.post(
            "/api/v1/risks",
            json={
                "risk_id": "r-jane-1",
                "title": "Data feed down",
                "date_opened": "2026-02-20",
                "risk_type": "blocker",
                "severity": "critical",
                "impacted_pm_ids": ["pm-jane"],
            },
        )

        r = await test_client.get("/api/v1/reports/pm/pm-jane/dashboard")
        assert r.status_code == 200
        body = r.json()

        assert body["pm"]["pm_id"] == "pm-jane"
        assert body["pm"]["health_status"] == "yellow"
        assert len(body["needs"]) == 1
        assert body["open_need_count"] == 1
        assert body["days_since_touchpoint"] == 5
        assert len(body["risks"]) == 1
        assert body["risks"][0]["risk_id"] == "r-jane-1"


# ---------------------------------------------------------------------------
# Portfolio Health
# ---------------------------------------------------------------------------


class TestPortfolioHealth:
    async def test_empty_portfolio_health(self, test_client: AsyncClient):
        """Portfolio health with no data returns zeroed metrics."""
        r = await test_client.get("/api/v1/reports/portfolio-health")
        assert r.status_code == 200
        body = r.json()
        assert body["total_pms"] == 0
        assert body["total_projects"] == 0
        assert body["pms_at_risk_count"] == 0
        assert body["open_risks_total"] == 0
        assert body["critical_risks"] == 0
        assert body["pending_decisions"] == 0
        assert body["overdue_milestones"] == 0
        assert body["upcoming_go_lives"] == []
        assert "generated_on" in body

    async def test_portfolio_health_counts(self, test_client: AsyncClient):
        """Portfolio health correctly counts PMs at risk and pending decisions."""
        # Create PMs: 1 green, 1 red
        await test_client.post(
            "/api/v1/pm-coverage",
            json={"pm_id": "pm-ok", "pm_name": "OK PM", "health_status": "green"},
        )
        await test_client.post(
            "/api/v1/pm-coverage",
            json={"pm_id": "pm-bad", "pm_name": "Bad PM", "health_status": "red"},
        )

        # Create a pending decision
        await test_client.post(
            "/api/v1/decisions",
            json={"decision_id": "d-port-1", "title": "Infra choice"},
        )

        # Create a critical open risk
        await test_client.post(
            "/api/v1/risks",
            json={
                "risk_id": "r-crit",
                "title": "Critical issue",
                "date_opened": "2026-02-01",
                "risk_type": "risk",
                "severity": "critical",
            },
        )

        r = await test_client.get("/api/v1/reports/portfolio-health")
        assert r.status_code == 200
        body = r.json()
        assert body["total_pms"] == 2
        assert body["pms_at_risk_count"] == 1  # only red PM
        assert body["pending_decisions"] == 1
        assert body["open_risks_total"] == 1
        assert body["critical_risks"] == 1
