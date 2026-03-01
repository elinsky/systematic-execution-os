"""Service for Project operations.

Asana is source of truth for projects. The sidecar syncs and enriches.
Projects are created/updated via Asana; sidecar records are upserted by sync.
"""

from __future__ import annotations

from typing import Optional

import structlog

from sidecar.models.common import HealthStatus
from sidecar.models.project import Project, ProjectCreate, ProjectStatus, ProjectUpdate
from sidecar.persistence.project import ProjectRepository

logger = structlog.get_logger(__name__)


class ProjectService:
    def __init__(self, repo: ProjectRepository) -> None:
        self._repo = repo

    async def get(self, project_id: str) -> Optional[Project]:
        return await self._repo.get(project_id)

    async def list(
        self,
        pm_id: Optional[str] = None,
        health: Optional[HealthStatus] = None,
        status: Optional[ProjectStatus] = None,
    ) -> list[Project]:
        return await self._repo.list(pm_id=pm_id, health=health, status=status)

    async def upsert_from_asana(self, data: ProjectCreate) -> Project:
        """Idempotent upsert triggered by Asana sync. Keyed on asana_gid."""
        project = await self._repo.upsert_by_asana_gid(data)
        logger.info("project_upserted", project_id=project.project_id, asana_gid=project.asana_gid)
        return project

    async def update(self, data: ProjectUpdate) -> Project:
        project = await self._repo.update(data)
        if project is None:
            raise KeyError(f"Project not found: {data.project_id}")
        return project

    async def list_at_risk(self) -> list[Project]:
        """Return projects with AT_RISK status or RED health."""
        at_risk_status = await self._repo.list(status=ProjectStatus.AT_RISK)
        red_health = await self._repo.list(health=HealthStatus.RED)
        # Deduplicate by project_id
        seen: set[str] = set()
        result = []
        for p in at_risk_status + red_health:
            if p.project_id not in seen:
                seen.add(p.project_id)
                result.append(p)
        return result
