"""Service for Milestone operations.

Source of truth: Asana. Sidecar stores GID + confidence/acceptance enrichment.
"""

from __future__ import annotations

import structlog

from sidecar.models.milestone import (
    Milestone,
    MilestoneCreate,
    MilestoneUpdate,
)
from sidecar.persistence.milestone import MilestoneRepository

logger = structlog.get_logger(__name__)


class MilestoneService:
    def __init__(self, repo: MilestoneRepository) -> None:
        self._repo = repo

    async def get(self, milestone_id: str) -> Milestone | None:
        return await self._repo.get(milestone_id)

    async def list_for_project(self, project_id: str) -> list[Milestone]:
        return await self._repo.list_for_project(project_id)

    async def list_at_risk(self) -> list[Milestone]:
        return await self._repo.list_at_risk()

    async def upsert_from_asana(self, data: MilestoneCreate) -> Milestone:
        milestone = await self._repo.upsert_by_asana_gid(data)
        logger.info(
            "milestone_upserted",
            milestone_id=milestone.milestone_id,
            asana_gid=milestone.asana_gid,
        )
        return milestone

    async def update(self, data: MilestoneUpdate) -> Milestone:
        milestone = await self._repo.update(data)
        if milestone is None:
            raise KeyError(f"Milestone not found: {data.milestone_id}")
        return milestone

    async def list_missing_acceptance_criteria(self) -> list[Milestone]:
        """Return milestones that have no acceptance criteria — a data quality signal."""
        at_risk = await self._repo.list_at_risk()
        # Also check not-started and in-progress milestones
        # We query at_risk for now; a broader query would require a new repo method
        # For v1, surface milestones that are AT_RISK or near without criteria
        return [m for m in at_risk if not m.acceptance_criteria]
