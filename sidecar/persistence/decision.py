"""Repository for Decisions.

Source of truth: Sidecar-only. Append-only semantics:
- Decisions may not be deleted.
- Once status=DECIDED, the record is immutable via the update() path.
- To revise a decided decision, create a new one and set superseded_by_id.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidecar.db.decision import DecisionTable
from sidecar.models.decision import (
    ArtifactType,
    Decision,
    DecisionCreate,
    DecisionResolve,
    DecisionStatus,
    ImpactedArtifact,
)
from sidecar.persistence.base import decode_list, encode_list


def _decode_impacted_artifacts(value: str) -> list[ImpactedArtifact]:
    raw = json.loads(value) if value else []
    return [ImpactedArtifact(**item) for item in raw]


def _encode_impacted_artifacts(artifacts: list[ImpactedArtifact]) -> str:
    return json.dumps([a.model_dump(mode="json") for a in artifacts])


def _row_to_model(row: DecisionTable) -> Decision:
    return Decision(
        decision_id=row.decision_id,
        title=row.title,
        context=row.context,
        options_considered=row.options_considered,
        chosen_path=row.chosen_path,
        rationale=row.rationale,
        approvers=decode_list(row.approvers),
        decision_date=row.decision_date,
        status=DecisionStatus(row.status),
        superseded_by_id=None,  # stored in impacted_artifact_ids as convention; not in v1 schema
        impacted_artifacts=_decode_impacted_artifacts(row.impacted_artifact_ids),
        notes=None,
        # Decision.created_at is Optional[date]; extract date portion from ORM datetime
        created_at=row.created_at.date() if row.created_at else None,
    )


class DecisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, decision_id: str) -> Decision | None:
        result = await self._session.execute(
            select(DecisionTable).where(DecisionTable.decision_id == decision_id)
        )
        row = result.scalar_one_or_none()
        return _row_to_model(row) if row else None

    async def list(
        self,
        status: DecisionStatus | None = None,
        project_id: str | None = None,
    ) -> list[Decision]:
        stmt = select(DecisionTable)
        if status is not None:
            stmt = stmt.where(DecisionTable.status == status.value)
        stmt = stmt.order_by(DecisionTable.created_at.desc())
        result = await self._session.execute(stmt)
        decisions = [_row_to_model(r) for r in result.scalars().all()]
        # Filter by project_id in Python (stored in impacted_artifacts)
        if project_id is not None:
            decisions = [
                d
                for d in decisions
                if any(
                    a.artifact_type == ArtifactType.PROJECT and a.artifact_id == project_id
                    for a in d.impacted_artifacts
                )
            ]
        return decisions

    async def list_pending(self) -> list[Decision]:
        return await self.list(status=DecisionStatus.PENDING)

    async def create(self, data: DecisionCreate) -> Decision:
        row = DecisionTable(
            decision_id=data.decision_id,
            title=data.title,
            context=data.context,
            options_considered=data.options_considered,
            chosen_path=data.chosen_path,
            rationale=data.rationale,
            approvers=encode_list(data.approvers),
            decision_date=data.decision_date,
            status=data.status.value,
            impacted_artifact_ids=_encode_impacted_artifacts(data.impacted_artifacts),
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _row_to_model(row)

    async def resolve(self, data: DecisionResolve) -> Decision | None:
        """Record the outcome of a pending decision.

        Only PENDING decisions may be resolved (D3).
        Returns None if not found or if decision is not PENDING.
        """
        result = await self._session.execute(
            select(DecisionTable).where(DecisionTable.decision_id == data.decision_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        if row.status != DecisionStatus.PENDING.value:
            return None  # immutable once DECIDED; caller should check
        row.chosen_path = data.chosen_path
        row.rationale = data.rationale
        row.approvers = encode_list(data.approvers)
        row.decision_date = data.decision_date
        row.status = DecisionStatus.DECIDED.value
        await self._session.flush()
        await self._session.refresh(row)
        return _row_to_model(row)

    async def supersede(self, decision_id: str, superseded_by_id: str) -> Decision | None:
        """Mark a decision as superseded by a new one."""
        result = await self._session.execute(
            select(DecisionTable).where(DecisionTable.decision_id == decision_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.status = DecisionStatus.SUPERSEDED.value
        await self._session.flush()
        await self._session.refresh(row)
        return _row_to_model(row)
