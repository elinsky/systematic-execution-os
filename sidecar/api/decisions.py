"""Decisions API router.

GET  /decisions                      List decisions (filterable)
POST /decisions                      Create decision record (starts PENDING)
POST /decisions/{decision_id}/resolve  Record the outcome of a pending decision
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from sidecar.api.deps import get_decision_service
from sidecar.models.decision import Decision, DecisionCreate, DecisionResolve, DecisionStatus
from sidecar.services.decision_service import DecisionService

router = APIRouter()


@router.get("", response_model=list[Decision])
async def list_decisions(
    decision_status: Optional[DecisionStatus] = None,
    project_id: Optional[str] = None,
    pending_only: bool = False,
    older_than_days: Optional[int] = None,
    svc: DecisionService = Depends(get_decision_service),
) -> list[Decision]:
    """List decisions with optional filters."""
    if pending_only:
        decisions = await svc.list_pending()
    else:
        decisions = await svc.list(status=decision_status, project_id=project_id)

    if older_than_days is not None:
        cutoff = date.today() - timedelta(days=older_than_days)
        decisions = [
            d for d in decisions
            if d.created_at and d.created_at <= cutoff
        ]

    return decisions


@router.post("", response_model=Decision, status_code=status.HTTP_201_CREATED)
async def create_decision(
    data: DecisionCreate,
    svc: DecisionService = Depends(get_decision_service),
) -> Decision:
    """Create a new decision record (initially PENDING)."""
    return await svc.create(data)


@router.post("/{decision_id}/resolve", response_model=Decision)
async def resolve_decision(
    decision_id: str,
    data: DecisionResolve,
    svc: DecisionService = Depends(get_decision_service),
) -> Decision:
    """Record the outcome of a pending decision (D3: immutable once DECIDED)."""
    if data.decision_id != decision_id:
        data = data.model_copy(update={"decision_id": decision_id})
    try:
        return await svc.resolve(data)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
