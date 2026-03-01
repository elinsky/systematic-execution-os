"""Repository for Projects.

Source of truth: Asana. Sidecar stores asana_gid + enrichment fields.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidecar.db.project import ProjectTable
from sidecar.models.common import HealthStatus, Priority
from sidecar.models.project import Project, ProjectCreate, ProjectStatus, ProjectType, ProjectUpdate
from sidecar.persistence.base import decode_list, encode_list


def _row_to_model(row: ProjectTable) -> Project:
    return Project(
        project_id=row.project_id,
        name=row.name,
        project_type=ProjectType(row.project_type),
        business_objective=row.business_objective,
        success_criteria=row.success_criteria,
        primary_pm_ids=decode_list(row.primary_pm_ids),
        owner=row.owner,
        status=ProjectStatus(row.status),
        priority=Priority(row.priority) if row.priority else Priority.MEDIUM,
        health=HealthStatus(row.health_status),
        start_date=row.start_date,
        target_date=row.target_date,
        linked_pm_need_ids=decode_list(row.linked_pm_need_ids),
        linked_capability_ids=decode_list(row.linked_capability_ids),
        linked_milestone_ids=[],  # resolved at query time via MilestoneRepository
        linked_risk_ids=[],  # resolved at query time via RiskRepository
        linked_decision_ids=[],  # resolved at query time via DecisionRepository
        asana_gid=row.asana_gid,
        asana_synced_at=row.asana_synced_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        archived_at=row.archived_at,
    )


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, project_id: str) -> Project | None:
        result = await self._session.execute(
            select(ProjectTable).where(ProjectTable.project_id == project_id)
        )
        row = result.scalar_one_or_none()
        return _row_to_model(row) if row else None

    async def get_by_asana_gid(self, asana_gid: str) -> Project | None:
        result = await self._session.execute(
            select(ProjectTable).where(ProjectTable.asana_gid == asana_gid)
        )
        row = result.scalar_one_or_none()
        return _row_to_model(row) if row else None

    async def list(
        self,
        pm_id: str | None = None,
        health: HealthStatus | None = None,
        status: ProjectStatus | None = None,
        include_archived: bool = False,
    ) -> list[Project]:
        stmt = select(ProjectTable)
        if not include_archived:
            stmt = stmt.where(ProjectTable.archived_at.is_(None))
        if health is not None:
            stmt = stmt.where(ProjectTable.health_status == health.value)
        if status is not None:
            stmt = stmt.where(ProjectTable.status == status.value)
        stmt = stmt.order_by(ProjectTable.name)
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        projects = [_row_to_model(r) for r in rows]
        # Filter by pm_id in Python (stored as JSON array)
        if pm_id is not None:
            projects = [p for p in projects if pm_id in p.primary_pm_ids]
        return projects

    async def create(self, data: ProjectCreate) -> Project:
        row = ProjectTable(
            project_id=data.project_id,
            name=data.name,
            project_type=data.project_type.value,
            business_objective=data.business_objective,
            success_criteria=data.success_criteria,
            primary_pm_ids=encode_list(data.primary_pm_ids),
            owner=data.owner,
            status=data.status.value,
            priority=data.priority.value,
            health_status=data.health.value,
            start_date=data.start_date,
            target_date=data.target_date,
            linked_pm_need_ids=encode_list(data.linked_pm_need_ids),
            linked_capability_ids=encode_list(data.linked_capability_ids),
            asana_gid=data.asana_gid,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _row_to_model(row)

    async def update(self, data: ProjectUpdate) -> Project | None:
        result = await self._session.execute(
            select(ProjectTable).where(ProjectTable.project_id == data.project_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        if data.status is not None:
            row.status = data.status.value
        if data.health is not None:
            row.health_status = data.health.value
        if data.priority is not None:
            row.priority = data.priority.value
        if data.owner is not None:
            row.owner = data.owner
        if data.target_date is not None:
            row.target_date = data.target_date
        if data.success_criteria is not None:
            row.success_criteria = data.success_criteria
        if data.asana_gid is not None:
            row.asana_gid = data.asana_gid
        if data.asana_synced_at is not None:
            row.asana_synced_at = data.asana_synced_at
        await self._session.flush()
        await self._session.refresh(row)
        return _row_to_model(row)

    async def upsert_by_asana_gid(self, data: ProjectCreate) -> Project:
        """Idempotent create-or-update keyed on asana_gid."""
        if data.asana_gid:
            existing = await self.get_by_asana_gid(data.asana_gid)
            if existing:
                update = ProjectUpdate(
                    project_id=existing.project_id,
                    status=data.status,
                    health=data.health,
                    owner=data.owner,
                    target_date=data.target_date,
                    asana_gid=data.asana_gid,
                    asana_synced_at=data.asana_synced_at,
                )
                updated = await self.update(update)
                return updated  # type: ignore[return-value]
        return await self.create(data)
