"""Risks API router.

GET   /risks             List open risks/blockers (filterable)
POST  /risks             Create risk/blocker
PATCH /risks/{risk_id}   Update risk status or escalation
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from sidecar.api.deps import get_risk_service
from sidecar.models.risk import (
    RiskBlocker,
    RiskCreate,
    RiskSeverity,
    RiskStatus,
    RiskType,
    RiskUpdate,
)
from sidecar.services.risk_service import RiskService

router = APIRouter()


@router.get("", response_model=list[RiskBlocker])
async def list_risks(
    risk_type: RiskType | None = None,
    severity: RiskSeverity | None = None,
    risk_status: RiskStatus | None = None,
    pm_id: str | None = None,
    open_only: bool = True,
    older_than_days: int | None = None,
    svc: RiskService = Depends(get_risk_service),
) -> list[RiskBlocker]:
    """List risks and blockers with optional filters."""
    risks = await svc.list(
        pm_id=pm_id,
        severity=severity,
        status=risk_status,
        open_only=open_only,
    )
    if risk_type is not None:
        risks = [r for r in risks if r.risk_type == risk_type]
    if older_than_days is not None:
        risks = [r for r in risks if (r.age_days or 0) >= older_than_days]
    # Sort by severity desc, age desc
    severity_order = {
        RiskSeverity.CRITICAL: 0,
        RiskSeverity.HIGH: 1,
        RiskSeverity.MEDIUM: 2,
        RiskSeverity.LOW: 3,
    }
    risks.sort(key=lambda r: (severity_order.get(r.severity, 99), -(r.age_days or 0)))
    return risks


@router.post("", response_model=RiskBlocker, status_code=status.HTTP_201_CREATED)
async def create_risk(
    data: RiskCreate,
    svc: RiskService = Depends(get_risk_service),
) -> RiskBlocker:
    """Create a new risk or blocker."""
    return await svc.create(data)


@router.patch("/{risk_id}", response_model=RiskBlocker)
async def update_risk(
    risk_id: str,
    data: RiskUpdate,
    svc: RiskService = Depends(get_risk_service),
) -> RiskBlocker:
    """Update risk status, severity, or escalation state."""
    if data.risk_id != risk_id:
        data = data.model_copy(update={"risk_id": risk_id})
    try:
        return await svc.update(data)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
