"""Milestone watch job.

Runs hourly.

Alerts when:
1. A milestone is due within MILESTONE_DUE_ALERT_DAYS and:
   - has no acceptance_criteria set, OR
   - confidence is low/blocked
2. A milestone is overdue (past target_date) and still not complete.

Each alert is logged as a structured log event with severity context.
In v3, these alerts will be posted to Slack/Teams.

Alert log events:
    milestone_missing_criteria — due soon but no acceptance criteria
    milestone_low_confidence   — due soon but confidence is low/blocked
    milestone_overdue          — past target date, not complete
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidecar.config import Settings
from sidecar.db.milestone import MilestoneTable

logger = structlog.get_logger(__name__)


async def run_milestone_watch(
    settings: Settings,
    session_factory: Any,
) -> dict[str, Any]:
    """Run milestone watch and return alert summary.

    Returns:
        Dict with lists of alert items per category.
    """
    async with session_factory() as session:
        alerts = await _check_milestones(session, settings)

    total = sum(len(v) for v in alerts.values())
    logger.info(
        "milestone_watch_complete",
        total_alerts=total,
        missing_criteria=len(alerts["missing_criteria"]),
        low_confidence=len(alerts["low_confidence"]),
        overdue=len(alerts["overdue"]),
    )
    return alerts


async def _check_milestones(
    session: AsyncSession, settings: Settings
) -> dict[str, list[dict[str, Any]]]:
    today = date.today()
    window = today + timedelta(days=settings.milestone_due_alert_days)

    # Active milestones within the alert window
    result = await session.execute(
        select(MilestoneTable).where(
            MilestoneTable.status.notin_(["complete", "missed"]),
        )
    )
    all_active = result.scalars().all()

    missing_criteria: list[dict[str, Any]] = []
    low_confidence: list[dict[str, Any]] = []
    overdue: list[dict[str, Any]] = []

    for ms in all_active:
        if not ms.target_date:
            continue
        target = date.fromisoformat(str(ms.target_date))
        is_near = today <= target <= window
        is_overdue = target < today

        base = {
            "milestone_id": ms.milestone_id,
            "name": ms.name,
            "project_id": ms.project_id,
            "target_date": str(ms.target_date),
            "status": ms.status,
            "confidence": ms.confidence,
        }

        if is_near and not ms.acceptance_criteria:
            logger.warning(
                "milestone_missing_criteria",
                milestone_id=ms.milestone_id,
                name=ms.name,
                target_date=str(ms.target_date),
                days_until_due=(target - today).days,
            )
            missing_criteria.append({**base, "days_until_due": (target - today).days})

        if is_near and ms.confidence in ("low", "blocked", "unknown"):
            logger.warning(
                "milestone_low_confidence",
                milestone_id=ms.milestone_id,
                name=ms.name,
                confidence=ms.confidence,
                target_date=str(ms.target_date),
            )
            low_confidence.append({**base, "days_until_due": (target - today).days})

        if is_overdue:
            days_over = (today - target).days
            logger.warning(
                "milestone_overdue",
                milestone_id=ms.milestone_id,
                name=ms.name,
                target_date=str(ms.target_date),
                days_overdue=days_over,
            )
            overdue.append({**base, "days_overdue": days_over})

    return {
        "missing_criteria": missing_criteria,
        "low_confidence": low_confidence,
        "overdue": overdue,
    }
