"""Service for generating weekly operating review agendas and at-risk views.

Aggregates data from PM, Project, Milestone, and Risk repositories to produce
the structured views that drive weekly and monthly operating cadences.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import structlog

from sidecar.models.common import HealthStatus
from sidecar.models.decision import Decision
from sidecar.models.milestone import Milestone, MilestoneStatus
from sidecar.models.pm_coverage import PMCoverageRecord
from sidecar.models.pm_need import NeedStatus
from sidecar.models.project import Project, ProjectStatus
from sidecar.models.risk import RiskBlocker
from sidecar.persistence.decision import DecisionRepository
from sidecar.persistence.milestone import MilestoneRepository
from sidecar.persistence.pm_coverage import PMCoverageRepository
from sidecar.persistence.pm_need import PMNeedRepository
from sidecar.persistence.project import ProjectRepository
from sidecar.persistence.risk import RiskRepository

logger = structlog.get_logger(__name__)


@dataclass
class PMAtRisk:
    """A PM record flagged as at-risk for the operating review."""

    pm: PMCoverageRecord
    reasons: list[str] = field(default_factory=list)
    open_blockers: list[RiskBlocker] = field(default_factory=list)
    open_need_count: int = 0


@dataclass
class OperatingReviewAgenda:
    """Auto-generated weekly operating review agenda."""

    generated_on: date
    pms_at_risk: list[PMAtRisk]
    slipping_milestones: list[Milestone]
    aging_blockers: list[RiskBlocker]
    pending_decisions: list[Decision]
    at_risk_projects: list[Project]


class OperatingReviewService:
    """Generates operating review views by querying across all entity repositories."""

    def __init__(
        self,
        pm_repo: PMCoverageRepository,
        need_repo: PMNeedRepository,
        project_repo: ProjectRepository,
        milestone_repo: MilestoneRepository,
        risk_repo: RiskRepository,
        decision_repo: DecisionRepository,
        blocker_age_threshold_days: int = 7,
        milestone_due_threshold_days: int = 7,
        pm_open_needs_threshold: int = 3,
    ) -> None:
        self._pm_repo = pm_repo
        self._need_repo = need_repo
        self._project_repo = project_repo
        self._milestone_repo = milestone_repo
        self._risk_repo = risk_repo
        self._decision_repo = decision_repo
        self._blocker_age_threshold = blocker_age_threshold_days
        self._milestone_due_threshold = milestone_due_threshold_days
        self._pm_needs_threshold = pm_open_needs_threshold

    async def get_agenda(self) -> OperatingReviewAgenda:
        """Generate a complete weekly operating review agenda."""
        today = date.today()

        pms_at_risk = await self._get_pms_at_risk()
        slipping_milestones = await self._get_slipping_milestones(today)
        aging_blockers = await self._get_aging_blockers()
        pending_decisions = await self._decision_repo.list_pending()
        at_risk_projects = await self._get_at_risk_projects()

        logger.info(
            "operating_review_agenda_generated",
            pms_at_risk=len(pms_at_risk),
            slipping_milestones=len(slipping_milestones),
            aging_blockers=len(aging_blockers),
            pending_decisions=len(pending_decisions),
        )

        return OperatingReviewAgenda(
            generated_on=today,
            pms_at_risk=pms_at_risk,
            slipping_milestones=slipping_milestones,
            aging_blockers=aging_blockers,
            pending_decisions=pending_decisions,
            at_risk_projects=at_risk_projects,
        )

    async def get_pms_at_risk(self) -> list[PMAtRisk]:
        """Return PMs with active blockers, slipping milestones, or too many open needs."""
        return await self._get_pms_at_risk()

    async def _get_pms_at_risk(self) -> list[PMAtRisk]:
        all_pms = await self._pm_repo.list()
        result = []

        for pm in all_pms:
            reasons: list[str] = []

            # Reason 1: health is RED or YELLOW
            if pm.health_status == HealthStatus.RED:
                reasons.append("health=red")
            elif pm.health_status == HealthStatus.YELLOW:
                reasons.append("health=yellow")

            # Reason 2: too many open needs
            open_needs = await self._need_repo.list(pm_id=pm.pm_id)
            terminal = {NeedStatus.DELIVERED, NeedStatus.DEFERRED, NeedStatus.CANCELLED}
            unresolved_needs = [n for n in open_needs if n.status not in terminal]
            if len(unresolved_needs) >= self._pm_needs_threshold:
                reasons.append(f"open_needs={len(unresolved_needs)}")

            # Reason 3: open blockers
            open_blockers = await self._risk_repo.list(pm_id=pm.pm_id, open_only=True)
            if open_blockers:
                reasons.append(f"open_blockers={len(open_blockers)}")

            if reasons:
                result.append(
                    PMAtRisk(
                        pm=pm,
                        reasons=reasons,
                        open_blockers=open_blockers,
                        open_need_count=len(unresolved_needs),
                    )
                )

        return result

    async def _get_slipping_milestones(self, today: date) -> list[Milestone]:
        """Return milestones due within threshold days that are AT_RISK or have low confidence."""
        at_risk = await self._milestone_repo.list_at_risk()
        cutoff = today + timedelta(days=self._milestone_due_threshold)
        slipping = []
        for m in at_risk:
            if m.target_date and m.target_date <= cutoff or m.status == MilestoneStatus.MISSED:
                slipping.append(m)
        return slipping

    async def _get_aging_blockers(self) -> list[RiskBlocker]:
        """Return open blockers/risks older than threshold days."""
        open_risks = await self._risk_repo.list(open_only=True)
        return [r for r in open_risks if (r.age_days or 0) >= self._blocker_age_threshold]

    async def _get_at_risk_projects(self) -> list[Project]:
        """Return projects with AT_RISK status or RED health."""
        at_risk = await self._project_repo.list(status=ProjectStatus.AT_RISK)
        red = await self._project_repo.list(health=HealthStatus.RED)
        seen: set[str] = set()
        result = []
        for p in at_risk + red:
            if p.project_id not in seen:
                seen.add(p.project_id)
                result.append(p)
        return result
