"""Operating Review API router.

GET /operating-review/agenda           Auto-generate weekly review agenda
GET /operating-review/at-risk-pms      PMs with active blockers or red/yellow health
GET /operating-review/pm-needs-summary Cross-PM view of PM needs
GET /operating-review/milestone-calendar Upcoming milestones across all projects
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends

from sidecar.api.deps import get_milestone_repo, get_operating_review_service, get_pm_need_repo
from sidecar.models.milestone import Milestone
from sidecar.models.pm_need import NeedCategory, NeedStatus
from sidecar.persistence.milestone import MilestoneRepository
from sidecar.persistence.pm_need import PMNeedRepository
from sidecar.services.operating_review_service import (
    OperatingReviewAgenda,
    OperatingReviewService,
    PMAtRisk,
)
from pydantic import BaseModel

router = APIRouter()


class NeedsByCategoryItem(BaseModel):
    category: str
    count: int


class UnmetByPMItem(BaseModel):
    pm_id: str
    open_count: int


class PMNeedsSummary(BaseModel):
    by_category: dict[str, int]
    unmet_by_pm: list[UnmetByPMItem]


@router.get("/agenda", response_model=OperatingReviewAgenda)
async def get_agenda(
    svc: OperatingReviewService = Depends(get_operating_review_service),
) -> OperatingReviewAgenda:
    """Auto-generate the weekly operating review agenda."""
    return await svc.get_agenda()


@router.get("/at-risk-pms", response_model=list[PMAtRisk])
async def get_at_risk_pms(
    svc: OperatingReviewService = Depends(get_operating_review_service),
) -> list[PMAtRisk]:
    """PMs with active blockers, slipping milestones, or red/yellow health."""
    return await svc.get_pms_at_risk()


@router.get("/pm-needs-summary", response_model=PMNeedsSummary)
async def get_pm_needs_summary(
    need_repo: PMNeedRepository = Depends(get_pm_need_repo),
) -> PMNeedsSummary:
    """Cross-PM view of PM needs — answers 'What are the top PM needs across the business?'"""
    terminal = {NeedStatus.DELIVERED, NeedStatus.DEFERRED, NeedStatus.CANCELLED}
    all_needs = await need_repo.list()
    open_needs = [n for n in all_needs if n.status not in terminal]

    by_category: dict[str, int] = {}
    for n in open_needs:
        key = n.category.value
        by_category[key] = by_category.get(key, 0) + 1

    pm_counts: dict[str, int] = {}
    for n in open_needs:
        pm_counts[n.pm_id] = pm_counts.get(n.pm_id, 0) + 1

    unmet_by_pm = [
        UnmetByPMItem(pm_id=pm_id, open_count=count)
        for pm_id, count in sorted(pm_counts.items(), key=lambda x: -x[1])
    ]

    return PMNeedsSummary(by_category=by_category, unmet_by_pm=unmet_by_pm)


@router.get("/milestone-calendar", response_model=list[Milestone])
async def get_milestone_calendar(
    days_ahead: int = 30,
    milestone_repo: MilestoneRepository = Depends(get_milestone_repo),
) -> list[Milestone]:
    """Upcoming milestones across all active projects, sorted by target_date."""
    cutoff = date.today() + timedelta(days=days_ahead)
    at_risk = await milestone_repo.list_at_risk()
    upcoming = [
        m for m in at_risk
        if m.target_date and date.today() <= m.target_date <= cutoff
    ]
    upcoming.sort(key=lambda m: m.target_date)  # type: ignore[arg-type]
    return upcoming
