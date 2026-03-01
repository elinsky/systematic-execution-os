"""Reporting and Dashboard API router.

GET /reports/weekly-status           Weekly status report
GET /reports/pm/{pm_id}/dashboard    PM-specific dashboard
GET /reports/portfolio-health        Portfolio health overview
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from sidecar.api.deps import get_reporting_service
from sidecar.models.milestone import Milestone
from sidecar.models.pm_coverage import PMCoverageRecord
from sidecar.models.pm_need import PMNeed
from sidecar.models.project import Project
from sidecar.models.risk import RiskBlocker
from sidecar.services.reporting_service import ReportingService

router = APIRouter()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class PMCoverageSummaryResponse(BaseModel):
    total: int
    by_stage: dict[str, int]
    by_health: dict[str, int]


class OpenNeedsSummaryResponse(BaseModel):
    total_open: int
    by_category: dict[str, int]
    by_urgency: dict[str, int]
    oldest_open_days: int | None
    avg_age_days: float | None


class RiskBlockerSummaryResponse(BaseModel):
    total_open: int
    by_severity: dict[str, int]
    aging_count: int
    aging_blockers: list[RiskBlocker]


class MilestoneSummaryResponse(BaseModel):
    upcoming_14d: list[Milestone]
    overdue: list[Milestone]
    at_risk: list[Milestone]


class DecisionSummaryResponse(BaseModel):
    pending_count: int
    avg_days_pending: float | None


class WeeklyStatusReportResponse(BaseModel):
    generated_on: date
    pm_coverage: PMCoverageSummaryResponse
    open_needs: OpenNeedsSummaryResponse
    risks: RiskBlockerSummaryResponse
    milestones: MilestoneSummaryResponse
    decisions: DecisionSummaryResponse


class PMDashboardResponse(BaseModel):
    pm: PMCoverageRecord
    needs: list[PMNeed]
    open_need_count: int
    linked_projects: list[Project]
    milestones: list[Milestone]
    risks: list[RiskBlocker]
    days_since_touchpoint: int | None


class PortfolioHealthResponse(BaseModel):
    generated_on: date
    total_pms: int
    total_projects: int
    projects_by_health: dict[str, int]
    projects_by_status: dict[str, int]
    pms_at_risk_count: int
    open_risks_total: int
    critical_risks: int
    pending_decisions: int
    overdue_milestones: int
    upcoming_go_lives: list[PMCoverageRecord]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/weekly-status", response_model=WeeklyStatusReportResponse)
async def get_weekly_status(
    svc: ReportingService = Depends(get_reporting_service),
) -> WeeklyStatusReportResponse:
    """Generate a structured weekly status report.

    Includes PM coverage, open needs, risk/blocker, milestone, and decision
    summaries across the full portfolio.
    """
    report = await svc.weekly_status_report()
    return WeeklyStatusReportResponse(
        generated_on=report.generated_on,
        pm_coverage=PMCoverageSummaryResponse(
            total=report.pm_coverage.total,
            by_stage=report.pm_coverage.by_stage,
            by_health=report.pm_coverage.by_health,
        ),
        open_needs=OpenNeedsSummaryResponse(
            total_open=report.open_needs.total_open,
            by_category=report.open_needs.by_category,
            by_urgency=report.open_needs.by_urgency,
            oldest_open_days=report.open_needs.oldest_open_days,
            avg_age_days=report.open_needs.avg_age_days,
        ),
        risks=RiskBlockerSummaryResponse(
            total_open=report.risks.total_open,
            by_severity=report.risks.by_severity,
            aging_count=report.risks.aging_count,
            aging_blockers=report.risks.aging_blockers,
        ),
        milestones=MilestoneSummaryResponse(
            upcoming_14d=report.milestones.upcoming_14d,
            overdue=report.milestones.overdue,
            at_risk=report.milestones.at_risk,
        ),
        decisions=DecisionSummaryResponse(
            pending_count=report.decisions.pending_count,
            avg_days_pending=report.decisions.avg_days_pending,
        ),
    )


@router.get("/pm/{pm_id}/dashboard", response_model=PMDashboardResponse)
async def get_pm_dashboard(
    pm_id: str,
    svc: ReportingService = Depends(get_reporting_service),
) -> PMDashboardResponse:
    """PM-specific dashboard view with needs, projects, milestones, and risks."""
    dashboard = await svc.pm_dashboard(pm_id)
    if dashboard is None:
        raise HTTPException(status_code=404, detail=f"PM '{pm_id}' not found")
    return PMDashboardResponse(
        pm=dashboard.pm,
        needs=dashboard.needs,
        open_need_count=dashboard.open_need_count,
        linked_projects=dashboard.linked_projects,
        milestones=dashboard.milestones,
        risks=dashboard.risks,
        days_since_touchpoint=dashboard.days_since_touchpoint,
    )


@router.get("/portfolio-health", response_model=PortfolioHealthResponse)
async def get_portfolio_health(
    svc: ReportingService = Depends(get_reporting_service),
) -> PortfolioHealthResponse:
    """Aggregate portfolio health metrics across all PMs and projects."""
    health = await svc.portfolio_health()
    return PortfolioHealthResponse(
        generated_on=health.generated_on,
        total_pms=health.total_pms,
        total_projects=health.total_projects,
        projects_by_health=health.projects_by_health,
        projects_by_status=health.projects_by_status,
        pms_at_risk_count=health.pms_at_risk_count,
        open_risks_total=health.open_risks_total,
        critical_risks=health.critical_risks,
        pending_decisions=health.pending_decisions,
        overdue_milestones=health.overdue_milestones,
        upcoming_go_lives=health.upcoming_go_lives,
    )
