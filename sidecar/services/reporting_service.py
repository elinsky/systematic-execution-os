"""Reporting service for generating dashboard and status report views.

Aggregates data from all entity repositories to produce structured reports
aligned with the dashboard requirements in docs/workflows.md (Section 4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import structlog

from sidecar.models.common import HealthStatus
from sidecar.models.milestone import Milestone, MilestoneStatus
from sidecar.models.pm_coverage import PMCoverageRecord
from sidecar.models.pm_need import NeedStatus, PMNeed
from sidecar.models.project import Project
from sidecar.models.risk import RiskBlocker, RiskSeverity
from sidecar.persistence.decision import DecisionRepository
from sidecar.persistence.milestone import MilestoneRepository
from sidecar.persistence.pm_coverage import PMCoverageRepository
from sidecar.persistence.pm_need import PMNeedRepository
from sidecar.persistence.project import ProjectRepository
from sidecar.persistence.risk import RiskRepository

logger = structlog.get_logger(__name__)

TERMINAL_NEED_STATUSES = {NeedStatus.DELIVERED, NeedStatus.DEFERRED, NeedStatus.CANCELLED}


# ---------------------------------------------------------------------------
# Report dataclasses
# ---------------------------------------------------------------------------


@dataclass
class PMCoverageSummary:
    """PM pipeline counts by onboarding stage and health distribution."""

    total: int = 0
    by_stage: dict[str, int] = field(default_factory=dict)
    by_health: dict[str, int] = field(default_factory=dict)


@dataclass
class OpenNeedsSummary:
    """Aggregated view of open (non-terminal) PM needs."""

    total_open: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    by_urgency: dict[str, int] = field(default_factory=dict)
    oldest_open_days: int | None = None
    avg_age_days: float | None = None


@dataclass
class RiskBlockerSummary:
    """Aggregated view of open risks and blockers."""

    total_open: int = 0
    by_severity: dict[str, int] = field(default_factory=dict)
    aging_count: int = 0
    aging_blockers: list[RiskBlocker] = field(default_factory=list)


@dataclass
class MilestoneSummary:
    """Upcoming, overdue, and at-risk milestones."""

    upcoming_14d: list[Milestone] = field(default_factory=list)
    overdue: list[Milestone] = field(default_factory=list)
    at_risk: list[Milestone] = field(default_factory=list)


@dataclass
class DecisionSummary:
    """Summary of pending decisions."""

    pending_count: int = 0
    avg_days_pending: float | None = None


@dataclass
class WeeklyStatusReport:
    """Complete weekly status report combining all summary sections."""

    generated_on: date
    pm_coverage: PMCoverageSummary
    open_needs: OpenNeedsSummary
    risks: RiskBlockerSummary
    milestones: MilestoneSummary
    decisions: DecisionSummary


@dataclass
class PMDashboard:
    """PM-specific dashboard view (Section 4.1 of workflows.md)."""

    pm: PMCoverageRecord
    needs: list[PMNeed]
    open_need_count: int
    linked_projects: list[Project]
    milestones: list[Milestone]
    risks: list[RiskBlocker]
    days_since_touchpoint: int | None = None


@dataclass
class PortfolioHealth:
    """Aggregate portfolio health across all PMs (Section 4.3 / 4.5)."""

    generated_on: date
    total_pms: int = 0
    total_projects: int = 0
    projects_by_health: dict[str, int] = field(default_factory=dict)
    projects_by_status: dict[str, int] = field(default_factory=dict)
    pms_at_risk_count: int = 0
    open_risks_total: int = 0
    critical_risks: int = 0
    pending_decisions: int = 0
    overdue_milestones: int = 0
    upcoming_go_lives: list[PMCoverageRecord] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ReportingService:
    """Generates reports by querying existing repositories.

    Does not create new DB queries -- all data is fetched via existing
    repository list/filter methods and aggregated in Python.
    """

    def __init__(
        self,
        pm_repo: PMCoverageRepository,
        need_repo: PMNeedRepository,
        project_repo: ProjectRepository,
        milestone_repo: MilestoneRepository,
        risk_repo: RiskRepository,
        decision_repo: DecisionRepository,
        blocker_age_threshold_days: int = 7,
    ) -> None:
        self._pm_repo = pm_repo
        self._need_repo = need_repo
        self._project_repo = project_repo
        self._milestone_repo = milestone_repo
        self._risk_repo = risk_repo
        self._decision_repo = decision_repo
        self._blocker_age_threshold = blocker_age_threshold_days

    # -- Weekly Status Report ------------------------------------------------

    async def weekly_status_report(self) -> WeeklyStatusReport:
        """Generate a structured weekly status report."""
        today = date.today()

        pm_coverage = await self._pm_coverage_summary()
        open_needs = await self._open_needs_summary(today)
        risks = await self._risk_blocker_summary(today)
        milestones = await self._milestone_summary(today)
        decisions = await self._decision_summary(today)

        logger.info(
            "weekly_status_report_generated",
            total_pms=pm_coverage.total,
            open_needs=open_needs.total_open,
            open_risks=risks.total_open,
            pending_decisions=decisions.pending_count,
        )

        return WeeklyStatusReport(
            generated_on=today,
            pm_coverage=pm_coverage,
            open_needs=open_needs,
            risks=risks,
            milestones=milestones,
            decisions=decisions,
        )

    # -- PM Dashboard --------------------------------------------------------

    async def pm_dashboard(self, pm_id: str) -> PMDashboard | None:
        """Generate a PM-specific dashboard view.

        Returns None if the PM is not found.
        """
        pm = await self._pm_repo.get(pm_id)
        if pm is None:
            return None

        needs = await self._need_repo.list(pm_id=pm_id)
        open_needs = [n for n in needs if n.status not in TERMINAL_NEED_STATUSES]

        projects: list[Project] = []
        for pid in pm.linked_project_ids:
            proj = await self._project_repo.get(pid)
            if proj is not None:
                projects.append(proj)

        # Also include projects that reference this PM via primary_pm_ids
        all_pm_projects = await self._project_repo.list(pm_id=pm_id)
        seen = {p.project_id for p in projects}
        for p in all_pm_projects:
            if p.project_id not in seen:
                projects.append(p)
                seen.add(p.project_id)

        # Milestones from linked projects
        milestones: list[Milestone] = []
        for proj in projects:
            proj_milestones = await self._milestone_repo.list_for_project(proj.project_id)
            milestones.extend(proj_milestones)

        risks = await self._risk_repo.list(pm_id=pm_id, open_only=True)

        days_since_touchpoint: int | None = None
        if pm.last_touchpoint_date is not None:
            days_since_touchpoint = (date.today() - pm.last_touchpoint_date).days

        logger.info(
            "pm_dashboard_generated",
            pm_id=pm_id,
            open_needs=len(open_needs),
            projects=len(projects),
            risks=len(risks),
        )

        return PMDashboard(
            pm=pm,
            needs=needs,
            open_need_count=len(open_needs),
            linked_projects=projects,
            milestones=milestones,
            risks=risks,
            days_since_touchpoint=days_since_touchpoint,
        )

    # -- Portfolio Health ----------------------------------------------------

    async def portfolio_health(self) -> PortfolioHealth:
        """Generate aggregate health metrics across all PMs and projects."""
        today = date.today()

        all_pms = await self._pm_repo.list()
        all_projects = await self._project_repo.list()

        projects_by_health: dict[str, int] = {}
        for p in all_projects:
            key = p.health.value
            projects_by_health[key] = projects_by_health.get(key, 0) + 1

        projects_by_status: dict[str, int] = {}
        for p in all_projects:
            key = p.status.value
            projects_by_status[key] = projects_by_status.get(key, 0) + 1

        pms_at_risk_count = sum(
            1
            for pm in all_pms
            if pm.health_status in (HealthStatus.RED, HealthStatus.YELLOW)
        )

        open_risks = await self._risk_repo.list(open_only=True)
        critical_risks = sum(
            1 for r in open_risks if r.severity == RiskSeverity.CRITICAL
        )

        pending_decisions = await self._decision_repo.list_pending()

        at_risk_milestones = await self._milestone_repo.list_at_risk()
        overdue_milestones = sum(
            1
            for m in at_risk_milestones
            if m.target_date and m.target_date < today
        )

        # Upcoming go-lives: PMs with go_live_target_date in next 60 days
        cutoff = today + timedelta(days=60)
        upcoming_go_lives = [
            pm
            for pm in all_pms
            if pm.go_live_target_date
            and today <= pm.go_live_target_date <= cutoff
        ]
        upcoming_go_lives.sort(key=lambda pm: pm.go_live_target_date)  # type: ignore[arg-type]

        logger.info(
            "portfolio_health_generated",
            total_pms=len(all_pms),
            total_projects=len(all_projects),
            pms_at_risk=pms_at_risk_count,
        )

        return PortfolioHealth(
            generated_on=today,
            total_pms=len(all_pms),
            total_projects=len(all_projects),
            projects_by_health=projects_by_health,
            projects_by_status=projects_by_status,
            pms_at_risk_count=pms_at_risk_count,
            open_risks_total=len(open_risks),
            critical_risks=critical_risks,
            pending_decisions=len(pending_decisions),
            overdue_milestones=overdue_milestones,
            upcoming_go_lives=upcoming_go_lives,
        )

    # -- Private helpers -----------------------------------------------------

    async def _pm_coverage_summary(self) -> PMCoverageSummary:
        all_pms = await self._pm_repo.list()
        by_stage: dict[str, int] = {}
        by_health: dict[str, int] = {}
        for pm in all_pms:
            stage_key = pm.onboarding_stage.value
            by_stage[stage_key] = by_stage.get(stage_key, 0) + 1
            health_key = pm.health_status.value
            by_health[health_key] = by_health.get(health_key, 0) + 1
        return PMCoverageSummary(total=len(all_pms), by_stage=by_stage, by_health=by_health)

    async def _open_needs_summary(self, today: date) -> OpenNeedsSummary:
        all_needs = await self._need_repo.list()
        open_needs = [n for n in all_needs if n.status not in TERMINAL_NEED_STATUSES]
        by_category: dict[str, int] = {}
        by_urgency: dict[str, int] = {}
        ages: list[int] = []
        for n in open_needs:
            cat_key = n.category.value
            by_category[cat_key] = by_category.get(cat_key, 0) + 1
            urg_key = n.urgency.value
            by_urgency[urg_key] = by_urgency.get(urg_key, 0) + 1
            age = (today - n.date_raised).days
            ages.append(age)

        oldest = max(ages) if ages else None
        avg_age = sum(ages) / len(ages) if ages else None

        return OpenNeedsSummary(
            total_open=len(open_needs),
            by_category=by_category,
            by_urgency=by_urgency,
            oldest_open_days=oldest,
            avg_age_days=round(avg_age, 1) if avg_age is not None else None,
        )

    async def _risk_blocker_summary(self, today: date) -> RiskBlockerSummary:
        open_risks = await self._risk_repo.list(open_only=True)
        by_severity: dict[str, int] = {}
        aging: list[RiskBlocker] = []
        for r in open_risks:
            sev_key = r.severity.value
            by_severity[sev_key] = by_severity.get(sev_key, 0) + 1
            if (r.age_days or 0) >= self._blocker_age_threshold:
                aging.append(r)

        return RiskBlockerSummary(
            total_open=len(open_risks),
            by_severity=by_severity,
            aging_count=len(aging),
            aging_blockers=aging,
        )

    async def _milestone_summary(self, today: date) -> MilestoneSummary:
        at_risk_milestones = await self._milestone_repo.list_at_risk()

        cutoff_14d = today + timedelta(days=14)
        upcoming: list[Milestone] = []
        overdue: list[Milestone] = []
        at_risk: list[Milestone] = []

        for m in at_risk_milestones:
            if m.target_date and m.target_date < today:
                overdue.append(m)
            elif m.target_date and m.target_date <= cutoff_14d:
                upcoming.append(m)
            if m.status == MilestoneStatus.AT_RISK:
                at_risk.append(m)

        upcoming.sort(key=lambda m: m.target_date or today)
        overdue.sort(key=lambda m: m.target_date or today)

        return MilestoneSummary(
            upcoming_14d=upcoming,
            overdue=overdue,
            at_risk=at_risk,
        )

    async def _decision_summary(self, today: date) -> DecisionSummary:
        pending = await self._decision_repo.list_pending()
        if not pending:
            return DecisionSummary(pending_count=0, avg_days_pending=None)

        ages: list[int] = []
        for d in pending:
            if d.created_at is not None:
                age = (today - d.created_at).days
                ages.append(age)

        avg = round(sum(ages) / len(ages), 1) if ages else None
        return DecisionSummary(pending_count=len(pending), avg_days_pending=avg)
