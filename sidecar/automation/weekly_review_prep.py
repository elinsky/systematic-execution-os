"""Weekly review prep job.

Runs Monday 8am (configurable via WEEKLY_REVIEW_CRON in Settings).

Generates the operating review agenda — same data as the daily digest
but with expanded context and organized for presentation:

    - overdue_deliverable summary (milestone-level, not task-level)
    - milestone slips (at_risk or low confidence)
    - pms_at_risk with open needs context
    - open blockers sorted by severity + age
    - pending_decisions (Decision table, status = pending)

In v1 the agenda is logged as structured JSON. The same data is also
served by GET /operating-review/agenda for real-time access.

The output format mirrors api-design.md § Operating Review Endpoints.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidecar.config import Settings
from sidecar.db.decision import DecisionTable
from sidecar.db.milestone import MilestoneTable
from sidecar.db.pm_coverage import PMCoverageTable
from sidecar.db.pm_need import PMNeedTable
from sidecar.db.risk import RiskTable

logger = structlog.get_logger(__name__)


async def run_weekly_review_prep(
    settings: Settings,
    session_factory: Any,
) -> dict[str, Any]:
    """Generate and log the weekly operating review agenda.

    Returns:
        Agenda dict (also logged via structlog).
    """
    async with session_factory() as session:
        agenda = await _build_agenda(session, settings)

    logger.info(
        "weekly_review_agenda_generated",
        overdue_count=len(agenda["overdue_milestones"]),
        slip_count=len(agenda["milestone_slips"]),
        pms_at_risk_count=len(agenda["pms_at_risk"]),
        blocker_count=len(agenda["open_blockers"]),
        decision_count=len(agenda["pending_decisions"]),
        agenda=agenda,
    )
    return agenda


async def _build_agenda(session: AsyncSession, settings: Settings) -> dict[str, Any]:
    today = date.today()
    lookahead = today + timedelta(days=30)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overdue_milestones": await _overdue_milestones(session, today),
        "milestone_slips": await _milestone_slips(session, today, lookahead),
        "pms_at_risk": await _pms_at_risk_with_needs(session),
        "open_blockers": await _open_blockers_ranked(session, today),
        "pending_decisions": await _pending_decisions(session, today),
    }


async def _overdue_milestones(
    session: AsyncSession, today: date
) -> list[dict[str, Any]]:
    result = await session.execute(
        select(MilestoneTable).where(
            MilestoneTable.target_date < today.isoformat(),
            MilestoneTable.status.notin_(["complete", "missed"]),
        ).order_by(MilestoneTable.target_date)
    )
    rows = result.scalars().all()
    return [
        {
            "milestone_id": r.milestone_id,
            "name": r.name,
            "project_id": r.project_id,
            "target_date": str(r.target_date),
            "status": r.status,
            "confidence": r.confidence,
            "owner": r.owner,
            "days_overdue": (today - date.fromisoformat(str(r.target_date))).days,
            "has_acceptance_criteria": bool(r.acceptance_criteria),
        }
        for r in rows
    ]


async def _milestone_slips(
    session: AsyncSession, today: date, lookahead: date
) -> list[dict[str, Any]]:
    """Milestones within the lookahead window that are at_risk or low confidence."""
    result = await session.execute(
        select(MilestoneTable).where(
            MilestoneTable.target_date >= today.isoformat(),
            MilestoneTable.target_date <= lookahead.isoformat(),
            MilestoneTable.status.notin_(["complete"]),
            # at_risk status OR low/blocked confidence
            (
                MilestoneTable.status.in_(["at_risk"]) |
                MilestoneTable.confidence.in_(["low", "blocked"])
            ),
        ).order_by(MilestoneTable.target_date)
    )
    rows = result.scalars().all()
    return [
        {
            "milestone_id": r.milestone_id,
            "name": r.name,
            "project_id": r.project_id,
            "target_date": str(r.target_date),
            "status": r.status,
            "confidence": r.confidence,
            "owner": r.owner,
            "days_until_due": (date.fromisoformat(str(r.target_date)) - today).days,
        }
        for r in rows
    ]


async def _pms_at_risk_with_needs(session: AsyncSession) -> list[dict[str, Any]]:
    """PM Coverage records with red/yellow health, plus their open need count."""
    pm_result = await session.execute(
        select(PMCoverageTable).where(
            PMCoverageTable.health_status.in_(["red", "yellow"]),
            PMCoverageTable.archived_at.is_(None),
        )
    )
    pms = pm_result.scalars().all()

    output = []
    for pm in pms:
        need_result = await session.execute(
            select(PMNeedTable).where(
                PMNeedTable.pm_id == pm.pm_id,
                PMNeedTable.status.notin_(["delivered", "cancelled", "deferred"]),
                PMNeedTable.archived_at.is_(None),
            )
        )
        open_needs = need_result.scalars().all()
        output.append({
            "pm_id": pm.pm_id,
            "pm_name": pm.pm_name,
            "onboarding_stage": pm.onboarding_stage,
            "health_status": pm.health_status,
            "coverage_owner": pm.coverage_owner,
            "go_live_target_date": str(pm.go_live_target_date) if pm.go_live_target_date else None,
            "open_needs_count": len(open_needs),
            "top_open_needs": [
                {"need_id": n.need_id, "title": n.title, "urgency": n.urgency}
                for n in open_needs[:3]
            ],
        })
    return output


async def _open_blockers_ranked(
    session: AsyncSession, today: date
) -> list[dict[str, Any]]:
    """Open blockers ranked by severity (critical first) then age (oldest first)."""
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    result = await session.execute(
        select(RiskTable).where(
            RiskTable.status.in_(["open", "in_mitigation"]),
        )
    )
    rows = result.scalars().all()

    items = []
    for r in rows:
        age = (today - date.fromisoformat(str(r.date_opened))).days
        items.append({
            "risk_id": r.risk_id,
            "title": r.title,
            "risk_type": r.risk_type,
            "severity": r.severity,
            "escalation_status": r.escalation_status,
            "owner": r.owner,
            "age_days": age,
            "_sort_key": (severity_order.get(r.severity, 9), -age),
        })

    items.sort(key=lambda x: x["_sort_key"])
    # Remove sort key from output
    for item in items:
        item.pop("_sort_key")
    return items


async def _pending_decisions(
    session: AsyncSession, today: date
) -> list[dict[str, Any]]:
    """Pending decisions, oldest first."""
    result = await session.execute(
        select(DecisionTable).where(
            DecisionTable.status == "pending",
        ).order_by(DecisionTable.created_at)
    )
    rows = result.scalars().all()
    return [
        {
            "decision_id": r.decision_id,
            "title": r.title,
            "approvers": r.approvers or "[]",
            "age_days": (today - date.fromisoformat(str(r.created_at)[:10])).days
            if r.created_at else None,
        }
        for r in rows
    ]
