"""Repository for Milestones.

Source of truth: Asana. Sidecar stores asana_gid + confidence/acceptance enrichment.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidecar.db.milestone import MilestoneTable
from sidecar.models.milestone import (
    Milestone,
    MilestoneConfidence,
    MilestoneCreate,
    MilestoneStatus,
    MilestoneUpdate,
)


def _row_to_model(row: MilestoneTable) -> Milestone:
    return Milestone(
        milestone_id=row.milestone_id,
        project_id=row.project_id,
        name=row.name,
        target_date=row.target_date,
        owner=row.owner,
        status=MilestoneStatus(row.status),
        confidence=MilestoneConfidence(row.confidence),
        gating_conditions=row.gating_conditions,
        acceptance_criteria=row.acceptance_criteria,
        notes=None,
        asana_gid=row.asana_gid,
        asana_synced_at=row.asana_synced_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class MilestoneRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, milestone_id: str) -> Optional[Milestone]:
        result = await self._session.execute(
            select(MilestoneTable).where(MilestoneTable.milestone_id == milestone_id)
        )
        row = result.scalar_one_or_none()
        return _row_to_model(row) if row else None

    async def get_by_asana_gid(self, asana_gid: str) -> Optional[Milestone]:
        result = await self._session.execute(
            select(MilestoneTable).where(MilestoneTable.asana_gid == asana_gid)
        )
        row = result.scalar_one_or_none()
        return _row_to_model(row) if row else None

    async def list_for_project(self, project_id: str) -> list[Milestone]:
        result = await self._session.execute(
            select(MilestoneTable)
            .where(MilestoneTable.project_id == project_id)
            .order_by(MilestoneTable.target_date)
        )
        return [_row_to_model(r) for r in result.scalars().all()]

    async def list_at_risk(self) -> list[Milestone]:
        """Return milestones with AT_RISK or MISSED status."""
        result = await self._session.execute(
            select(MilestoneTable).where(
                MilestoneTable.status.in_([MilestoneStatus.AT_RISK.value, MilestoneStatus.MISSED.value])
            )
        )
        return [_row_to_model(r) for r in result.scalars().all()]

    async def create(self, data: MilestoneCreate) -> Milestone:
        row = MilestoneTable(
            milestone_id=data.milestone_id,
            project_id=data.project_id,
            name=data.name,
            target_date=data.target_date,
            owner=data.owner,
            status=data.status.value,
            confidence=data.confidence.value,
            gating_conditions=data.gating_conditions,
            acceptance_criteria=data.acceptance_criteria,
            asana_gid=data.asana_gid,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _row_to_model(row)

    async def update(self, data: MilestoneUpdate) -> Optional[Milestone]:
        result = await self._session.execute(
            select(MilestoneTable).where(MilestoneTable.milestone_id == data.milestone_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        if data.status is not None:
            row.status = data.status.value
        if data.confidence is not None:
            row.confidence = data.confidence.value
        if data.target_date is not None:
            row.target_date = data.target_date
        if data.owner is not None:
            row.owner = data.owner
        if data.acceptance_criteria is not None:
            row.acceptance_criteria = data.acceptance_criteria
        if data.asana_gid is not None:
            row.asana_gid = data.asana_gid
        if data.asana_synced_at is not None:
            row.asana_synced_at = data.asana_synced_at
        await self._session.flush()
        await self._session.refresh(row)
        return _row_to_model(row)

    async def upsert_by_asana_gid(self, data: MilestoneCreate) -> Milestone:
        if data.asana_gid:
            existing = await self.get_by_asana_gid(data.asana_gid)
            if existing:
                update = MilestoneUpdate(
                    milestone_id=existing.milestone_id,
                    status=data.status,
                    target_date=data.target_date,
                    owner=data.owner,
                    asana_gid=data.asana_gid,
                    asana_synced_at=data.asana_synced_at,
                )
                updated = await self.update(update)
                return updated  # type: ignore[return-value]
        return await self.create(data)
