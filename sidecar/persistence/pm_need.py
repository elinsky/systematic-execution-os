"""Repository for PM Needs.

Source of truth: Hybrid (Asana task + sidecar metadata).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidecar.db.pm_need import PMNeedTable
from sidecar.models.common import BusinessImpact, Urgency
from sidecar.models.pm_need import NeedCategory, NeedStatus, PMNeed, PMNeedCreate, PMNeedUpdate
from sidecar.persistence.base import decode_list, encode_list


def _row_to_model(row: PMNeedTable) -> PMNeed:
    return PMNeed(
        pm_need_id=row.need_id,
        pm_id=row.pm_id,
        title=row.title,
        problem_statement=row.problem_statement,
        business_rationale=row.business_rationale,
        requested_by=row.requested_by,
        date_raised=row.date_raised,
        category=NeedCategory(row.category),
        urgency=Urgency(row.urgency),
        business_impact=BusinessImpact(row.business_impact)
        if row.business_impact
        else BusinessImpact.MEDIUM,
        desired_by_date=row.desired_by_date,
        status=NeedStatus(row.status),
        mapped_capability_id=row.mapped_capability_id,
        linked_project_ids=decode_list(row.linked_project_ids),
        resolution_path=row.resolution_path,
        notes=row.notes,
        asana_gid=row.asana_gid,
        asana_synced_at=row.asana_synced_at,
    )


class PMNeedRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, need_id: str) -> PMNeed | None:
        result = await self._session.execute(
            select(PMNeedTable).where(PMNeedTable.need_id == need_id)
        )
        row = result.scalar_one_or_none()
        return _row_to_model(row) if row else None

    async def get_by_asana_gid(self, asana_gid: str) -> PMNeed | None:
        result = await self._session.execute(
            select(PMNeedTable).where(PMNeedTable.asana_gid == asana_gid)
        )
        row = result.scalar_one_or_none()
        return _row_to_model(row) if row else None

    async def list(
        self,
        pm_id: str | None = None,
        status: NeedStatus | None = None,
        category: NeedCategory | None = None,
        include_archived: bool = False,
    ) -> list[PMNeed]:
        stmt = select(PMNeedTable)
        if not include_archived:
            stmt = stmt.where(PMNeedTable.archived_at.is_(None))
        if pm_id is not None:
            stmt = stmt.where(PMNeedTable.pm_id == pm_id)
        if status is not None:
            stmt = stmt.where(PMNeedTable.status == status.value)
        if category is not None:
            stmt = stmt.where(PMNeedTable.category == category.value)
        stmt = stmt.order_by(PMNeedTable.date_raised.desc())
        result = await self._session.execute(stmt)
        return [_row_to_model(r) for r in result.scalars().all()]

    async def create(self, data: PMNeedCreate) -> PMNeed:
        row = PMNeedTable(
            need_id=data.pm_need_id,
            pm_id=data.pm_id,
            title=data.title,
            problem_statement=data.problem_statement,
            business_rationale=data.business_rationale,
            requested_by=data.requested_by,
            date_raised=data.date_raised,
            category=data.category.value,
            urgency=data.urgency.value,
            business_impact=data.business_impact.value
            if data.business_impact
            else BusinessImpact.MEDIUM.value,
            desired_by_date=data.desired_by_date,
            status=data.status.value,
            mapped_capability_id=data.mapped_capability_id,
            linked_project_ids=encode_list(data.linked_project_ids),
            resolution_path=data.resolution_path,
            notes=data.notes,
            asana_gid=data.asana_gid,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _row_to_model(row)

    async def update(self, data: PMNeedUpdate) -> PMNeed | None:
        result = await self._session.execute(
            select(PMNeedTable).where(PMNeedTable.need_id == data.pm_need_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        # NOTE: status is NOT updated here (D1 — Asana section is canonical).
        # status is synced separately by the webhook handler.
        if data.urgency is not None:
            row.urgency = data.urgency.value
        if data.business_impact is not None:
            row.business_impact = data.business_impact.value
        if data.mapped_capability_id is not None:
            row.mapped_capability_id = data.mapped_capability_id
        if data.linked_project_ids is not None:
            row.linked_project_ids = encode_list(data.linked_project_ids)
        if data.resolution_path is not None:
            row.resolution_path = data.resolution_path
        if data.notes is not None:
            row.notes = data.notes
        if data.asana_gid is not None:
            row.asana_gid = data.asana_gid
        if data.asana_synced_at is not None:
            row.asana_synced_at = data.asana_synced_at
        await self._session.flush()
        await self._session.refresh(row)
        return _row_to_model(row)

    async def sync_status_from_asana(self, need_id: str, status: NeedStatus) -> bool:
        """Update status from Asana section webhook. This is the ONLY path for status writes."""
        result = await self._session.execute(
            select(PMNeedTable).where(PMNeedTable.need_id == need_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        row.status = status.value
        await self._session.flush()
        return True

    async def upsert_by_asana_gid(self, data: PMNeedCreate) -> PMNeed:
        """Idempotent create-or-update keyed on asana_gid."""
        if data.asana_gid:
            existing = await self.get_by_asana_gid(data.asana_gid)
            if existing:
                update = PMNeedUpdate(
                    pm_need_id=existing.pm_need_id,
                    urgency=data.urgency,
                    business_impact=data.business_impact,
                    asana_gid=data.asana_gid,
                    asana_synced_at=data.asana_synced_at,
                )
                updated = await self.update(update)
                return updated  # type: ignore[return-value]
        return await self.create(data)
