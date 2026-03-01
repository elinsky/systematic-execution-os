"""Service for PM Need operations.

Hybrid source of truth: Asana task is the operational store;
sidecar holds relational links and enrichment metadata.
Status is read-only from the API (D1) — only synced from Asana.
"""

from __future__ import annotations

from typing import Optional

import structlog

from sidecar.models.common import BusinessImpact, Urgency
from sidecar.models.pm_need import NeedCategory, NeedStatus, PMNeed, PMNeedCreate, PMNeedUpdate
from sidecar.persistence.pm_need import PMNeedRepository

logger = structlog.get_logger(__name__)


class PMNeedService:
    def __init__(self, repo: PMNeedRepository) -> None:
        self._repo = repo

    async def get(self, need_id: str) -> Optional[PMNeed]:
        return await self._repo.get(need_id)

    async def list(
        self,
        pm_id: Optional[str] = None,
        status: Optional[NeedStatus] = None,
        category: Optional[NeedCategory] = None,
    ) -> list[PMNeed]:
        return await self._repo.list(pm_id=pm_id, status=status, category=category)

    async def create(self, data: PMNeedCreate) -> PMNeed:
        """Create a PM Need sidecar record.

        The caller (API router or sync layer) is responsible for creating
        the corresponding Asana task before calling this method and setting
        asana_gid on the create payload.
        """
        need = await self._repo.create(data)
        logger.info(
            "pm_need_created",
            need_id=need.pm_need_id,
            pm_id=need.pm_id,
            category=need.category,
        )
        return need

    async def update(self, data: PMNeedUpdate) -> PMNeed:
        """Update enrichment metadata. Status is NOT writable here (D1)."""
        need = await self._repo.update(data)
        if need is None:
            raise KeyError(f"PM Need not found: {data.pm_need_id}")
        logger.info("pm_need_updated", need_id=need.pm_need_id)
        return need

    async def sync_status(self, need_id: str, status: NeedStatus) -> PMNeed:
        """Sync status from Asana section. This is the only write path for status (D1)."""
        ok = await self._repo.sync_status_from_asana(need_id, status)
        if not ok:
            raise KeyError(f"PM Need not found: {need_id}")
        need = await self._repo.get(need_id)
        logger.info("pm_need_status_synced", need_id=need_id, status=status)
        return need  # type: ignore[return-value]

    async def list_unresolved_for_pm(self, pm_id: str) -> list[PMNeed]:
        """Return open needs for a PM (new, triaged, in_progress, blocked)."""
        needs = await self._repo.list(pm_id=pm_id)
        terminal = {NeedStatus.DELIVERED, NeedStatus.DEFERRED, NeedStatus.CANCELLED}
        return [n for n in needs if n.status not in terminal]
