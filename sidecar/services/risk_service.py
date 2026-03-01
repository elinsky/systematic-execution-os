"""Service for Risk / Blocker / Issue operations."""

from __future__ import annotations

from typing import Optional

import structlog

from sidecar.models.risk import (
    EscalationStatus,
    RiskBlocker,
    RiskCreate,
    RiskSeverity,
    RiskStatus,
    RiskUpdate,
)
from sidecar.persistence.risk import RiskRepository

logger = structlog.get_logger(__name__)


class RiskService:
    def __init__(self, repo: RiskRepository) -> None:
        self._repo = repo

    async def get(self, risk_id: str) -> Optional[RiskBlocker]:
        return await self._repo.get(risk_id)

    async def list(
        self,
        pm_id: Optional[str] = None,
        severity: Optional[RiskSeverity] = None,
        status: Optional[RiskStatus] = None,
        open_only: bool = False,
    ) -> list[RiskBlocker]:
        return await self._repo.list(pm_id=pm_id, severity=severity, status=status, open_only=open_only)

    async def create(self, data: RiskCreate) -> RiskBlocker:
        risk = await self._repo.create(data)
        logger.info(
            "risk_created",
            risk_id=risk.risk_id,
            risk_type=risk.risk_type,
            severity=risk.severity,
        )
        return risk

    async def update(self, data: RiskUpdate) -> RiskBlocker:
        risk = await self._repo.update(data)
        if risk is None:
            raise KeyError(f"Risk not found: {data.risk_id}")
        logger.info("risk_updated", risk_id=risk.risk_id, status=risk.status)
        return risk

    async def escalate(self, risk_id: str) -> RiskBlocker:
        """Shortcut to mark a risk as escalated."""
        return await self.update(RiskUpdate(
            risk_id=risk_id,
            escalation_status=EscalationStatus.ESCALATED,
        ))

    async def resolve(self, risk_id: str) -> RiskBlocker:
        """Mark a risk as resolved."""
        return await self.update(RiskUpdate(
            risk_id=risk_id,
            status=RiskStatus.RESOLVED,
        ))

    async def list_aging(self, threshold_days: int) -> list[RiskBlocker]:
        """Return open risks older than threshold_days."""
        open_risks = await self._repo.list(open_only=True)
        return [r for r in open_risks if (r.age_days or 0) >= threshold_days]
