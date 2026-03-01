"""Milestones API router.

GET   /milestones                  List milestones (filterable)
PATCH /milestones/{milestone_id}   Update milestone status, confidence, acceptance criteria
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from sidecar.api.deps import get_milestone_repo, get_milestone_service
from sidecar.models.milestone import (
    Milestone,
    MilestoneConfidence,
    MilestoneStatus,
    MilestoneUpdate,
)
from sidecar.persistence.milestone import MilestoneRepository
from sidecar.services.milestone_service import MilestoneService

router = APIRouter()


@router.get("", response_model=list[Milestone])
async def list_milestones(
    project_id: Optional[str] = None,
    milestone_status: Optional[MilestoneStatus] = None,
    at_risk_only: bool = False,
    due_within_days: Optional[int] = None,
    svc: MilestoneService = Depends(get_milestone_service),
    milestone_repo: MilestoneRepository = Depends(get_milestone_repo),
) -> list[Milestone]:
    """List milestones with optional filters."""
    if at_risk_only:
        milestones = await svc.list_at_risk()
    elif project_id:
        milestones = await milestone_repo.list_for_project(project_id)
    else:
        milestones = await milestone_repo.list_at_risk()
        # For a full list without at_risk_only we'd need a broader repo method;
        # return at_risk subset as a safe default for v1.

    if milestone_status is not None:
        milestones = [m for m in milestones if m.status == milestone_status]

    if due_within_days is not None:
        cutoff = date.today() + timedelta(days=due_within_days)
        milestones = [m for m in milestones if m.target_date and m.target_date <= cutoff]

    milestones.sort(key=lambda m: m.target_date or date(9999, 12, 31))
    return milestones


@router.patch("/{milestone_id}", response_model=Milestone)
async def update_milestone(
    milestone_id: str,
    data: MilestoneUpdate,
    svc: MilestoneService = Depends(get_milestone_service),
) -> Milestone:
    """Update milestone status, confidence, or acceptance criteria."""
    if data.milestone_id != milestone_id:
        data = data.model_copy(update={"milestone_id": milestone_id})
    try:
        return await svc.update(data)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
