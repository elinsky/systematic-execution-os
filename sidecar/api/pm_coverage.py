"""PM Coverage API router.

GET  /pm-coverage          List all PM Coverage records
GET  /pm-coverage/{pm_id}  PM status summary
POST /pm-coverage          Create a new PM Coverage record
PATCH /pm-coverage/{pm_id} Partial update
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from sidecar.api.deps import (
    get_milestone_repo,
    get_pm_coverage_service,
    get_pm_need_repo,
    get_risk_repo,
)
from sidecar.models.common import HealthStatus
from sidecar.models.milestone import Milestone
from sidecar.models.pm_coverage import (
    OnboardingStage,
    PMCoverageCreate,
    PMCoverageRecord,
    PMCoverageUpdate,
)
from sidecar.models.pm_need import PMNeed, NeedStatus
from sidecar.models.risk import RiskBlocker, RiskSeverity
from sidecar.persistence.milestone import MilestoneRepository
from sidecar.persistence.pm_need import PMNeedRepository
from sidecar.persistence.risk import RiskRepository
from sidecar.services.pm_coverage_service import PMCoverageService
from pydantic import BaseModel

router = APIRouter()


class PMStatusSummary(BaseModel):
    """Full PM status summary returned by GET /pm-coverage/{pm_id}."""

    pm: PMCoverageRecord
    open_needs: list[PMNeed]
    active_blockers: list[RiskBlocker]
    upcoming_milestones: list[Milestone]

    model_config = {"from_attributes": True}


@router.get("", response_model=list[PMCoverageRecord])
async def list_pm_coverage(
    stage: Optional[OnboardingStage] = None,
    health: Optional[HealthStatus] = None,
    svc: PMCoverageService = Depends(get_pm_coverage_service),
) -> list[PMCoverageRecord]:
    """List all PM Coverage records, optionally filtered by stage or health."""
    return await svc.list(stage=stage, health=health)


@router.get("/{pm_id}", response_model=PMStatusSummary)
async def get_pm_status(
    pm_id: str,
    svc: PMCoverageService = Depends(get_pm_coverage_service),
    need_repo: PMNeedRepository = Depends(get_pm_need_repo),
    risk_repo: RiskRepository = Depends(get_risk_repo),
    milestone_repo: MilestoneRepository = Depends(get_milestone_repo),
) -> PMStatusSummary:
    """Full PM status summary — answers 'What is the status of PM X?'"""
    pm = await svc.get(pm_id)
    if pm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PM Coverage record not found: {pm_id}",
        )

    terminal = {NeedStatus.DELIVERED, NeedStatus.DEFERRED, NeedStatus.CANCELLED}
    all_needs = await need_repo.list(pm_id=pm_id)
    open_needs = sorted(
        [n for n in all_needs if n.status not in terminal],
        key=lambda n: (n.urgency, n.date_raised),
    )[:5]

    active_blockers = await risk_repo.list(pm_id=pm_id, open_only=True)
    severity_order = {
        RiskSeverity.CRITICAL: 0,
        RiskSeverity.HIGH: 1,
        RiskSeverity.MEDIUM: 2,
        RiskSeverity.LOW: 3,
    }
    active_blockers.sort(key=lambda r: severity_order.get(r.severity, 99))

    all_milestones = await milestone_repo.list_for_project(pm_id)
    upcoming = sorted(
        [m for m in all_milestones if m.target_date is not None],
        key=lambda m: m.target_date,  # type: ignore[arg-type]
    )[:3]

    return PMStatusSummary(
        pm=pm,
        open_needs=open_needs,
        active_blockers=active_blockers,
        upcoming_milestones=upcoming,
    )


@router.post("", response_model=PMCoverageRecord, status_code=status.HTTP_201_CREATED)
async def create_pm_coverage(
    data: PMCoverageCreate,
    svc: PMCoverageService = Depends(get_pm_coverage_service),
) -> PMCoverageRecord:
    """Create a new PM Coverage record."""
    try:
        return await svc.create(data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.patch("/{pm_id}", response_model=PMCoverageRecord)
async def update_pm_coverage(
    pm_id: str,
    data: PMCoverageUpdate,
    svc: PMCoverageService = Depends(get_pm_coverage_service),
) -> PMCoverageRecord:
    """Partial update to a PM Coverage record."""
    if data.pm_id != pm_id:
        data = data.model_copy(update={"pm_id": pm_id})
    try:
        return await svc.update(data)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
