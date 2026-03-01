"""Projects API router.

GET  /projects               List projects (filterable by health, PM, status)
GET  /projects/{project_id}  Project detail (milestones, blockers, decisions)
GET  /projects/{project_id}/milestones  List milestones for a project
PATCH /projects/{project_id}  Update project status or health
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from sidecar.api.deps import (
    get_decision_repo,
    get_milestone_repo,
    get_project_service,
    get_risk_repo,
)
from sidecar.models.common import HealthStatus
from sidecar.models.decision import Decision, DecisionStatus
from sidecar.models.milestone import Milestone
from sidecar.models.project import Project, ProjectStatus, ProjectType, ProjectUpdate
from sidecar.models.risk import RiskBlocker
from sidecar.persistence.decision import DecisionRepository
from sidecar.persistence.milestone import MilestoneRepository
from sidecar.persistence.risk import RiskRepository
from sidecar.services.project_service import ProjectService

router = APIRouter()


class ProjectDetail(BaseModel):
    """Full project detail with related entities."""

    project: Project
    milestones: list[Milestone]
    open_risks: list[RiskBlocker]
    pending_decisions: list[Decision]

    model_config = {"from_attributes": True}


@router.get("", response_model=list[Project])
async def list_projects(
    pm_id: str | None = None,
    project_status: ProjectStatus | None = None,
    health: HealthStatus | None = None,
    project_type: ProjectType | None = None,
    at_risk_only: bool = False,
    svc: ProjectService = Depends(get_project_service),
) -> list[Project]:
    """List projects with optional filters."""
    if at_risk_only:
        return await svc.list_at_risk()
    return await svc.list(pm_id=pm_id, health=health, status=project_status)


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project_detail(
    project_id: str,
    svc: ProjectService = Depends(get_project_service),
    milestone_repo: MilestoneRepository = Depends(get_milestone_repo),
    risk_repo: RiskRepository = Depends(get_risk_repo),
    decision_repo: DecisionRepository = Depends(get_decision_repo),
) -> ProjectDetail:
    """Project detail including milestones, open risks, and pending decisions."""
    project = await svc.get(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )
    milestones = await milestone_repo.list_for_project(project_id)
    milestones.sort(key=lambda m: m.target_date or "9999-12-31")
    open_risks = await risk_repo.list(open_only=True)
    project_risks = [r for r in open_risks if project_id in r.impacted_project_ids]
    decisions = await decision_repo.list(project_id=project_id)
    pending_decisions = [d for d in decisions if d.status == DecisionStatus.PENDING]

    return ProjectDetail(
        project=project,
        milestones=milestones,
        open_risks=project_risks,
        pending_decisions=pending_decisions,
    )


@router.get("/{project_id}/milestones", response_model=list[Milestone])
async def list_project_milestones(
    project_id: str,
    milestone_repo: MilestoneRepository = Depends(get_milestone_repo),
) -> list[Milestone]:
    """List milestones for a project, sorted by target_date."""
    milestones = await milestone_repo.list_for_project(project_id)
    milestones.sort(key=lambda m: m.target_date or "9999-12-31")
    return milestones


@router.patch("/{project_id}", response_model=Project)
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    svc: ProjectService = Depends(get_project_service),
) -> Project:
    """Update project status, health, priority, or owner."""
    if data.project_id != project_id:
        data = data.model_copy(update={"project_id": project_id})
    try:
        return await svc.update(data)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
