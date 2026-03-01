"""Daily digest job.

Runs at 7am daily (configurable via DAILY_DIGEST_CRON in Settings).

Produces a structured digest dict containing:
    - overdue_tasks:     milestones with target_date < today and status != complete
    - near_milestones:   milestones due within MILESTONE_DUE_ALERT_DAYS
    - pms_at_risk:       PM Coverage records with health = red or yellow
    - aging_blockers:    risks with status = open and age > BLOCKER_AGE_ALERT_DAYS

In v1 the digest is logged as structured JSON (structlog). In v3 it will be
posted to Slack/Teams via the bot adapter.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidecar.config import Settings
from sidecar.db.milestone import MilestoneTable
from sidecar.db.pm_coverage import PMCoverageTable
from sidecar.db.risk import RiskTable

logger = structlog.get_logger(__name__)


async def run_daily_digest(
    settings: Settings,
    session_factory: Any,
) -> dict[str, Any]:
    """Generate and log the daily digest.

    Args:
        settings:        Application settings (thresholds).
        session_factory: SQLAlchemy async_sessionmaker.

    Returns:
        The digest dict (also logged via structlog).
    """
    async with session_factory() as session:
        digest = await _build_digest(session, settings)

    logger.info(
        "daily_digest_generated",
        overdue_count=len(digest["overdue_milestones"]),
        near_milestone_count=len(digest["near_milestones"]),
        pms_at_risk_count=len(digest["pms_at_risk"]),
        aging_blocker_count=len(digest["aging_blockers"]),
        digest=digest,
    )
    return digest


async def _build_digest(session: AsyncSession, settings: Settings) -> dict[str, Any]:
    today = date.today()
    alert_window = today + timedelta(days=settings.milestone_due_alert_days)
    blocker_cutoff = today - timedelta(days=settings.blocker_age_alert_days)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "overdue_milestones": await _overdue_milestones(session, today),
        "near_milestones": await _near_milestones(session, today, alert_window),
        "pms_at_risk": await _pms_at_risk(session),
        "aging_blockers": await _aging_blockers(session, blocker_cutoff),
    }


async def _overdue_milestones(session: AsyncSession, today: date) -> list[dict[str, Any]]:
    """Milestones past their target date and not yet complete."""
    result = await session.execute(
        select(MilestoneTable).where(
            MilestoneTable.target_date < today.isoformat(),
            MilestoneTable.status.notin_(["complete", "missed"]),
        )
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
            "days_overdue": (today - date.fromisoformat(str(r.target_date))).days,
        }
        for r in rows
    ]


async def _near_milestones(
    session: AsyncSession, today: date, window: date
) -> list[dict[str, Any]]:
    """Milestones due within the alert window and not yet complete."""
    result = await session.execute(
        select(MilestoneTable).where(
            MilestoneTable.target_date >= today.isoformat(),
            MilestoneTable.target_date <= window.isoformat(),
            MilestoneTable.status.notin_(["complete"]),
        )
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
            "days_until_due": (date.fromisoformat(str(r.target_date)) - today).days,
            "has_acceptance_criteria": bool(r.acceptance_criteria),
        }
        for r in rows
    ]


async def _pms_at_risk(session: AsyncSession) -> list[dict[str, Any]]:
    """PM Coverage records with red or yellow health, not archived."""
    result = await session.execute(
        select(PMCoverageTable).where(
            PMCoverageTable.health_status.in_(["red", "yellow"]),
            PMCoverageTable.archived_at.is_(None),
        )
    )
    rows = result.scalars().all()
    return [
        {
            "pm_id": r.pm_id,
            "pm_name": r.pm_name,
            "onboarding_stage": r.onboarding_stage,
            "health_status": r.health_status,
            "coverage_owner": r.coverage_owner,
            "go_live_target_date": str(r.go_live_target_date) if r.go_live_target_date else None,
        }
        for r in rows
    ]


async def _aging_blockers(session: AsyncSession, cutoff: date) -> list[dict[str, Any]]:
    """Open risks/blockers opened before the cutoff date (too old)."""
    result = await session.execute(
        select(RiskTable).where(
            RiskTable.status.in_(["open", "in_mitigation"]),
            RiskTable.date_opened <= cutoff.isoformat(),
        )
    )
    rows = result.scalars().all()
    today = date.today()
    return [
        {
            "risk_id": r.risk_id,
            "title": r.title,
            "risk_type": r.risk_type,
            "severity": r.severity,
            "escalation_status": r.escalation_status,
            "owner": r.owner,
            "date_opened": str(r.date_opened),
            "age_days": (today - date.fromisoformat(str(r.date_opened))).days,
        }
        for r in rows
    ]
