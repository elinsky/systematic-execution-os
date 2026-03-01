"""Service for Decision registry operations.

Decisions are append-only — they are never deleted, only superseded (D3).
Once status=DECIDED, the record is immutable via update.
"""

from __future__ import annotations

import structlog

from sidecar.models.decision import Decision, DecisionCreate, DecisionResolve, DecisionStatus
from sidecar.persistence.decision import DecisionRepository

logger = structlog.get_logger(__name__)


class DecisionService:
    def __init__(self, repo: DecisionRepository) -> None:
        self._repo = repo

    async def get(self, decision_id: str) -> Decision | None:
        return await self._repo.get(decision_id)

    async def list(
        self,
        status: DecisionStatus | None = None,
        project_id: str | None = None,
    ) -> list[Decision]:
        return await self._repo.list(status=status, project_id=project_id)

    async def list_pending(self) -> list[Decision]:
        return await self._repo.list_pending()

    async def create(self, data: DecisionCreate) -> Decision:
        decision = await self._repo.create(data)
        logger.info("decision_created", decision_id=decision.decision_id, title=decision.title)
        return decision

    async def resolve(self, data: DecisionResolve) -> Decision:
        """Record the outcome of a pending decision (D3: immutable once decided)."""
        decision = await self._repo.resolve(data)
        if decision is None:
            # Could be not found OR already decided
            existing = await self._repo.get(data.decision_id)
            if existing is None:
                raise KeyError(f"Decision not found: {data.decision_id}")
            raise ValueError(
                f"Decision {data.decision_id} is already {existing.status} and cannot be re-resolved. "
                "Create a new decision and use supersede() to replace it."
            )
        logger.info(
            "decision_resolved",
            decision_id=decision.decision_id,
            chosen_path=decision.chosen_path,
        )
        return decision

    async def supersede(
        self, decision_id: str, new_decision: DecisionCreate
    ) -> tuple[Decision, Decision]:
        """Create a new decision and mark the old one as superseded.

        Returns (new_decision, superseded_decision).
        """
        existing = await self._repo.get(decision_id)
        if existing is None:
            raise KeyError(f"Decision not found: {decision_id}")
        new = await self._repo.create(new_decision)
        superseded = await self._repo.supersede(decision_id, superseded_by_id=new.decision_id)
        logger.info(
            "decision_superseded",
            old_id=decision_id,
            new_id=new.decision_id,
        )
        return new, superseded  # type: ignore[return-value]
