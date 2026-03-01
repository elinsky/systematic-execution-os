"""FastAPI dependency providers for repositories and services."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from sidecar.config import Settings, get_settings
from sidecar.database import get_db_session
from sidecar.persistence.decision import DecisionRepository
from sidecar.persistence.milestone import MilestoneRepository
from sidecar.persistence.pm_coverage import PMCoverageRepository
from sidecar.persistence.pm_need import PMNeedRepository
from sidecar.persistence.project import ProjectRepository
from sidecar.persistence.risk import RiskRepository
from sidecar.services.decision_service import DecisionService
from sidecar.services.milestone_service import MilestoneService
from sidecar.services.operating_review_service import OperatingReviewService
from sidecar.services.reporting_service import ReportingService
from sidecar.services.pm_coverage_service import PMCoverageService
from sidecar.services.pm_need_service import PMNeedService
from sidecar.services.project_service import ProjectService
from sidecar.services.risk_service import RiskService

# ── Repository dependencies ────────────────────────────────────────────────


def get_pm_coverage_repo(
    session: AsyncSession = Depends(get_db_session),
) -> PMCoverageRepository:
    return PMCoverageRepository(session)


def get_pm_need_repo(
    session: AsyncSession = Depends(get_db_session),
) -> PMNeedRepository:
    return PMNeedRepository(session)


def get_project_repo(
    session: AsyncSession = Depends(get_db_session),
) -> ProjectRepository:
    return ProjectRepository(session)


def get_milestone_repo(
    session: AsyncSession = Depends(get_db_session),
) -> MilestoneRepository:
    return MilestoneRepository(session)


def get_risk_repo(
    session: AsyncSession = Depends(get_db_session),
) -> RiskRepository:
    return RiskRepository(session)


def get_decision_repo(
    session: AsyncSession = Depends(get_db_session),
) -> DecisionRepository:
    return DecisionRepository(session)


# ── Service dependencies ───────────────────────────────────────────────────


def get_pm_coverage_service(
    repo: PMCoverageRepository = Depends(get_pm_coverage_repo),
) -> PMCoverageService:
    return PMCoverageService(repo)


def get_pm_need_service(
    repo: PMNeedRepository = Depends(get_pm_need_repo),
) -> PMNeedService:
    return PMNeedService(repo)


def get_project_service(
    repo: ProjectRepository = Depends(get_project_repo),
) -> ProjectService:
    return ProjectService(repo)


def get_milestone_service(
    repo: MilestoneRepository = Depends(get_milestone_repo),
) -> MilestoneService:
    return MilestoneService(repo)


def get_risk_service(
    repo: RiskRepository = Depends(get_risk_repo),
) -> RiskService:
    return RiskService(repo)


def get_decision_service(
    repo: DecisionRepository = Depends(get_decision_repo),
) -> DecisionService:
    return DecisionService(repo)


def get_operating_review_service(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> OperatingReviewService:
    return OperatingReviewService(
        pm_repo=PMCoverageRepository(session),
        need_repo=PMNeedRepository(session),
        project_repo=ProjectRepository(session),
        milestone_repo=MilestoneRepository(session),
        risk_repo=RiskRepository(session),
        decision_repo=DecisionRepository(session),
        blocker_age_threshold_days=settings.blocker_age_alert_days,
        milestone_due_threshold_days=settings.milestone_due_alert_days,
        pm_open_needs_threshold=settings.pm_open_needs_alert_count,
    )


def get_reporting_service(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> ReportingService:
    return ReportingService(
        pm_repo=PMCoverageRepository(session),
        need_repo=PMNeedRepository(session),
        project_repo=ProjectRepository(session),
        milestone_repo=MilestoneRepository(session),
        risk_repo=RiskRepository(session),
        decision_repo=DecisionRepository(session),
        blocker_age_threshold_days=settings.blocker_age_alert_days,
    )
