"""Repository for Risks / Blockers / Issues.

Source of truth: Hybrid (Asana task + sidecar severity/impact metadata).
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidecar.db.risk import RiskTable
from sidecar.models.risk import (
    EscalationStatus,
    RiskBlocker,
    RiskCreate,
    RiskSeverity,
    RiskStatus,
    RiskType,
    RiskUpdate,
)
from sidecar.persistence.base import decode_list, encode_list


def _row_to_model(row: RiskTable) -> RiskBlocker:
    return RiskBlocker(
        risk_id=row.risk_id,
        title=row.title,
        risk_type=RiskType(row.risk_type),
        severity=RiskSeverity(row.severity),
        status=RiskStatus(row.status),
        owner=row.owner,
        date_opened=row.date_opened,
        resolution_date=row.resolution_date,
        impacted_pm_ids=decode_list(row.impacted_pm_ids),
        impacted_project_ids=decode_list(row.impacted_project_ids),
        impacted_milestone_ids=decode_list(row.impacted_milestone_ids),
        escalation_status=EscalationStatus(row.escalation_status),
        mitigation_plan=row.mitigation_plan,
        notes=None,
        asana_gid=row.asana_gid,
        asana_synced_at=row.asana_synced_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class RiskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, risk_id: str) -> Optional[RiskBlocker]:
        result = await self._session.execute(
            select(RiskTable).where(RiskTable.risk_id == risk_id)
        )
        row = result.scalar_one_or_none()
        return _row_to_model(row) if row else None

    async def get_by_asana_gid(self, asana_gid: str) -> Optional[RiskBlocker]:
        result = await self._session.execute(
            select(RiskTable).where(RiskTable.asana_gid == asana_gid)
        )
        row = result.scalar_one_or_none()
        return _row_to_model(row) if row else None

    async def list(
        self,
        pm_id: Optional[str] = None,
        severity: Optional[RiskSeverity] = None,
        status: Optional[RiskStatus] = None,
        open_only: bool = False,
    ) -> list[RiskBlocker]:
        stmt = select(RiskTable)
        if open_only:
            stmt = stmt.where(RiskTable.status == RiskStatus.OPEN.value)
        elif status is not None:
            stmt = stmt.where(RiskTable.status == status.value)
        if severity is not None:
            stmt = stmt.where(RiskTable.severity == severity.value)
        stmt = stmt.order_by(RiskTable.date_opened.desc())
        result = await self._session.execute(stmt)
        risks = [_row_to_model(r) for r in result.scalars().all()]
        if pm_id is not None:
            risks = [r for r in risks if pm_id in r.impacted_pm_ids]
        return risks

    async def list_for_project(self, project_id: str) -> list[RiskBlocker]:
        result = await self._session.execute(
            select(RiskTable).order_by(RiskTable.date_opened.desc())
        )
        risks = [_row_to_model(r) for r in result.scalars().all()]
        return [r for r in risks if project_id in r.impacted_project_ids]

    async def create(self, data: RiskCreate) -> RiskBlocker:
        row = RiskTable(
            risk_id=data.risk_id,
            title=data.title,
            risk_type=data.risk_type.value,
            severity=data.severity.value,
            status=data.status.value,
            owner=data.owner,
            date_opened=data.date_opened,
            resolution_date=data.resolution_date,
            impacted_pm_ids=encode_list(data.impacted_pm_ids),
            impacted_project_ids=encode_list(data.impacted_project_ids),
            impacted_milestone_ids=encode_list(data.impacted_milestone_ids),
            escalation_status=data.escalation_status.value,
            mitigation_plan=data.mitigation_plan,
            asana_gid=data.asana_gid,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _row_to_model(row)

    async def update(self, data: RiskUpdate) -> Optional[RiskBlocker]:
        result = await self._session.execute(
            select(RiskTable).where(RiskTable.risk_id == data.risk_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        if data.status is not None:
            row.status = data.status.value
        if data.severity is not None:
            row.severity = data.severity.value
        if data.escalation_status is not None:
            row.escalation_status = data.escalation_status.value
        if data.owner is not None:
            row.owner = data.owner
        if data.mitigation_plan is not None:
            row.mitigation_plan = data.mitigation_plan
        if data.resolution_date is not None:
            row.resolution_date = data.resolution_date
        if data.asana_gid is not None:
            row.asana_gid = data.asana_gid
        if data.asana_synced_at is not None:
            row.asana_synced_at = data.asana_synced_at
        await self._session.flush()
        await self._session.refresh(row)
        return _row_to_model(row)

    async def upsert_by_asana_gid(self, data: RiskCreate) -> RiskBlocker:
        if data.asana_gid:
            existing = await self.get_by_asana_gid(data.asana_gid)
            if existing:
                update = RiskUpdate(
                    risk_id=existing.risk_id,
                    status=data.status,
                    severity=data.severity,
                    owner=data.owner,
                    asana_gid=data.asana_gid,
                    asana_synced_at=data.asana_synced_at,
                )
                updated = await self.update(update)
                return updated  # type: ignore[return-value]
        return await self.create(data)
