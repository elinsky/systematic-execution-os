"""PM Needs API router.

GET  /pm-needs                List PM Needs
GET  /pm-needs/{pm_need_id}   Get single PM Need
POST /pm-needs                Create new PM Need
PATCH /pm-needs/{pm_need_id}  Update PM Need metadata (not status)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from sidecar.api.deps import get_pm_need_service
from sidecar.models.common import Urgency
from sidecar.models.pm_need import (
    NeedCategory,
    NeedStatus,
    PMNeed,
    PMNeedCreate,
    PMNeedUpdate,
)
from sidecar.services.pm_need_service import PMNeedService

router = APIRouter()


@router.get("", response_model=list[PMNeed])
async def list_pm_needs(
    pm_id: str | None = None,
    need_status: NeedStatus | None = None,
    category: NeedCategory | None = None,
    urgency: Urgency | None = None,
    unmet_only: bool = False,
    svc: PMNeedService = Depends(get_pm_need_service),
) -> list[PMNeed]:
    """List PM Needs, optionally filtered."""
    needs = await svc.list(pm_id=pm_id, status=need_status, category=category)
    if unmet_only:
        terminal = {NeedStatus.DELIVERED, NeedStatus.DEFERRED, NeedStatus.CANCELLED}
        needs = [n for n in needs if n.status not in terminal]
    if urgency is not None:
        needs = [n for n in needs if n.urgency == urgency]
    return needs


@router.get("/{pm_need_id}", response_model=PMNeed)
async def get_pm_need(
    pm_need_id: str,
    svc: PMNeedService = Depends(get_pm_need_service),
) -> PMNeed:
    need = await svc.get(pm_need_id)
    if need is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PM Need not found: {pm_need_id}",
        )
    return need


@router.post("", response_model=PMNeed, status_code=status.HTTP_201_CREATED)
async def create_pm_need(
    data: PMNeedCreate,
    svc: PMNeedService = Depends(get_pm_need_service),
) -> PMNeed:
    """Create a new PM Need."""
    return await svc.create(data)


@router.patch("/{pm_need_id}", response_model=PMNeed)
async def update_pm_need(
    pm_need_id: str,
    data: PMNeedUpdate,
    svc: PMNeedService = Depends(get_pm_need_service),
) -> PMNeed:
    """Update PM Need metadata. Note: status is not writable via API (D1)."""
    if data.pm_need_id != pm_need_id:
        data = data.model_copy(update={"pm_need_id": pm_need_id})
    try:
        return await svc.update(data)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
