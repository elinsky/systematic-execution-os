"""Repository for PM Coverage Records.

Source of truth: Sidecar.
Provides async CRUD + filtered list queries.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidecar.db.pm_coverage import PMCoverageTable
from sidecar.models.common import HealthStatus
from sidecar.models.pm_coverage import (
    OnboardingStage,
    PMCoverageCreate,
    PMCoverageRecord,
    PMCoverageUpdate,
)
from sidecar.persistence.base import decode_list, encode_list


def _row_to_model(row: PMCoverageTable) -> PMCoverageRecord:
    return PMCoverageRecord(
        pm_id=row.pm_id,
        pm_name=row.pm_name,
        team_or_pod=row.team_or_pod,
        strategy_type=row.strategy_type,
        region=row.region,
        coverage_owner=row.coverage_owner,
        onboarding_stage=OnboardingStage(row.onboarding_stage),
        go_live_target_date=row.go_live_target_date,
        health_status=HealthStatus(row.health_status),
        last_touchpoint_date=row.last_touchpoint_date,
        notes=row.notes,
        linked_project_ids=decode_list(row.linked_project_ids),
        asana_gid=row.asana_gid,
        asana_synced_at=row.asana_synced_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        archived_at=row.archived_at,
    )


class PMCoverageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, pm_id: str) -> PMCoverageRecord | None:
        result = await self._session.execute(
            select(PMCoverageTable).where(PMCoverageTable.pm_id == pm_id)
        )
        row = result.scalar_one_or_none()
        return _row_to_model(row) if row else None

    async def get_by_asana_gid(self, asana_gid: str) -> PMCoverageRecord | None:
        result = await self._session.execute(
            select(PMCoverageTable).where(PMCoverageTable.asana_gid == asana_gid)
        )
        row = result.scalar_one_or_none()
        return _row_to_model(row) if row else None

    async def list(
        self,
        stage: OnboardingStage | None = None,
        health: HealthStatus | None = None,
        include_archived: bool = False,
    ) -> list[PMCoverageRecord]:
        stmt = select(PMCoverageTable)
        if not include_archived:
            stmt = stmt.where(PMCoverageTable.archived_at.is_(None))
        if stage is not None:
            stmt = stmt.where(PMCoverageTable.onboarding_stage == stage.value)
        if health is not None:
            stmt = stmt.where(PMCoverageTable.health_status == health.value)
        stmt = stmt.order_by(PMCoverageTable.pm_name)
        result = await self._session.execute(stmt)
        return [_row_to_model(r) for r in result.scalars().all()]

    async def create(self, data: PMCoverageCreate) -> PMCoverageRecord:
        row = PMCoverageTable(
            pm_id=data.pm_id,
            pm_name=data.pm_name,
            team_or_pod=data.team_or_pod,
            strategy_type=data.strategy_type,
            region=data.region,
            coverage_owner=data.coverage_owner,
            onboarding_stage=data.onboarding_stage.value,
            go_live_target_date=data.go_live_target_date,
            health_status=data.health_status.value,
            last_touchpoint_date=data.last_touchpoint_date,
            notes=data.notes,
            linked_project_ids=encode_list(data.linked_project_ids),
            asana_gid=data.asana_gid,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _row_to_model(row)

    async def update(self, data: PMCoverageUpdate) -> PMCoverageRecord | None:
        result = await self._session.execute(
            select(PMCoverageTable).where(PMCoverageTable.pm_id == data.pm_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        if data.onboarding_stage is not None:
            row.onboarding_stage = data.onboarding_stage.value
        if data.health_status is not None:
            row.health_status = data.health_status.value
        if data.go_live_target_date is not None:
            row.go_live_target_date = data.go_live_target_date
        if data.coverage_owner is not None:
            row.coverage_owner = data.coverage_owner
        if data.last_touchpoint_date is not None:
            row.last_touchpoint_date = data.last_touchpoint_date
        if data.notes is not None:
            row.notes = data.notes
        if data.asana_gid is not None:
            row.asana_gid = data.asana_gid
        if data.asana_synced_at is not None:
            row.asana_synced_at = data.asana_synced_at
        await self._session.flush()
        await self._session.refresh(row)
        return _row_to_model(row)

    async def archive(self, pm_id: str) -> bool:
        result = await self._session.execute(
            select(PMCoverageTable).where(PMCoverageTable.pm_id == pm_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        row.archived_at = datetime.now(UTC)
        await self._session.flush()
        return True

    async def upsert_by_asana_gid(self, data: PMCoverageCreate) -> PMCoverageRecord:
        """Idempotent create-or-update keyed on asana_gid."""
        if data.asana_gid:
            existing = await self.get_by_asana_gid(data.asana_gid)
            if existing:
                update = PMCoverageUpdate(
                    pm_id=existing.pm_id,
                    onboarding_stage=data.onboarding_stage,
                    health_status=data.health_status,
                    coverage_owner=data.coverage_owner,
                    asana_gid=data.asana_gid,
                    asana_synced_at=data.asana_synced_at,
                )
                updated = await self.update(update)
                return updated  # type: ignore[return-value]
        return await self.create(data)
