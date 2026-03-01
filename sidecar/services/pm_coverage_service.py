"""Service for PM Coverage Record operations.

Source of truth: Sidecar. Asana holds a summary task mirrored from sidecar.
This service owns all CRUD and business logic for PM records.
"""

from __future__ import annotations

import structlog

from sidecar.models.common import HealthStatus
from sidecar.models.pm_coverage import (
    OnboardingStage,
    PMCoverageCreate,
    PMCoverageRecord,
    PMCoverageUpdate,
)
from sidecar.persistence.pm_coverage import PMCoverageRepository

logger = structlog.get_logger(__name__)


class PMCoverageService:
    """Business logic for PM Coverage Records.

    Delegates persistence to PMCoverageRepository.
    Asana sync is handled separately by the sync layer (Task #13).
    """

    def __init__(self, repo: PMCoverageRepository) -> None:
        self._repo = repo

    async def get(self, pm_id: str) -> PMCoverageRecord | None:
        return await self._repo.get(pm_id)

    async def list(
        self,
        stage: OnboardingStage | None = None,
        health: HealthStatus | None = None,
    ) -> list[PMCoverageRecord]:
        return await self._repo.list(stage=stage, health=health)

    async def create(self, data: PMCoverageCreate) -> PMCoverageRecord:
        existing = await self._repo.get(data.pm_id)
        if existing:
            raise ValueError(f"PM Coverage record already exists: {data.pm_id}")
        record = await self._repo.create(data)
        logger.info("pm_coverage_created", pm_id=record.pm_id, pm_name=record.pm_name)
        return record

    async def update(self, data: PMCoverageUpdate) -> PMCoverageRecord:
        record = await self._repo.update(data)
        if record is None:
            raise KeyError(f"PM Coverage record not found: {data.pm_id}")
        logger.info(
            "pm_coverage_updated",
            pm_id=record.pm_id,
            stage=record.onboarding_stage,
            health=record.health_status,
        )
        return record

    async def archive(self, pm_id: str) -> None:
        found = await self._repo.archive(pm_id)
        if not found:
            raise KeyError(f"PM Coverage record not found: {pm_id}")
        logger.info("pm_coverage_archived", pm_id=pm_id)

    async def list_at_risk(self) -> list[PMCoverageRecord]:
        """Return PMs with RED health status."""
        return await self._repo.list(health=HealthStatus.RED)

    async def list_active_onboarding(self) -> list[PMCoverageRecord]:
        """Return PMs actively in onboarding (not yet live, not pipeline)."""
        all_records = await self._repo.list()
        active_stages = {
            OnboardingStage.REQUIREMENTS_DISCOVERY,
            OnboardingStage.ONBOARDING_IN_PROGRESS,
            OnboardingStage.UAT,
            OnboardingStage.GO_LIVE_READY,
        }
        return [r for r in all_records if r.onboarding_stage in active_stages]
