"""PM health watch job.

Runs hourly (offset 15 min from milestone_watch).

Alerts when (configurable thresholds from Settings):
1. A PM has >= PM_OPEN_NEEDS_ALERT_COUNT unresolved needs.
2. A blocker has been open >= BLOCKER_AGE_ALERT_DAYS.
3. A critical blocker has been open >= 3 days (hardcoded severity escalation).

Alert log events:
    pm_too_many_open_needs  — PM has too many unresolved needs
    blocker_aging           — blocker has been open too long
    blocker_critical_aging  — critical blocker older than 3 days
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidecar.config import Settings
from sidecar.db.pm_coverage import PMCoverageTable
from sidecar.db.pm_need import PMNeedTable
from sidecar.db.risk import RiskTable

logger = structlog.get_logger(__name__)

_CRITICAL_BLOCKER_AGE_DAYS = 3  # escalate critical blockers faster than general threshold


async def run_pm_health_watch(
    settings: Settings,
    session_factory: Any,
) -> dict[str, Any]:
    """Run PM health watch and return alert summary."""
    async with session_factory() as session:
        alerts = await _check_pm_health(session, settings)

    total = sum(len(v) for v in alerts.values())
    logger.info(
        "pm_health_watch_complete",
        total_alerts=total,
        pm_need_alerts=len(alerts["pms_with_too_many_needs"]),
        aging_blockers=len(alerts["aging_blockers"]),
        critical_blockers=len(alerts["critical_aging_blockers"]),
    )
    return alerts


async def _check_pm_health(
    session: AsyncSession, settings: Settings
) -> dict[str, Any]:
    today = date.today()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pms_with_too_many_needs": await _check_pm_open_needs(session, settings),
        "aging_blockers": await _check_aging_blockers(session, today, settings),
        "critical_aging_blockers": await _check_critical_blockers(session, today),
    }


async def _check_pm_open_needs(
    session: AsyncSession, settings: Settings
) -> list[dict[str, Any]]:
    """Find PMs with >= pm_open_needs_alert_count unresolved needs."""
    pm_result = await session.execute(
        select(PMCoverageTable).where(
            PMCoverageTable.archived_at.is_(None),
        )
    )
    pms = pm_result.scalars().all()

    flagged = []
    for pm in pms:
        need_result = await session.execute(
            select(PMNeedTable).where(
                PMNeedTable.pm_id == pm.pm_id,
                PMNeedTable.status.notin_(["delivered", "cancelled", "deferred"]),
                PMNeedTable.archived_at.is_(None),
            )
        )
        open_needs = need_result.scalars().all()
        count = len(open_needs)

        if count >= settings.pm_open_needs_alert_count:
            logger.warning(
                "pm_too_many_open_needs",
                pm_id=pm.pm_id,
                pm_name=pm.pm_name,
                open_needs_count=count,
                threshold=settings.pm_open_needs_alert_count,
            )
            flagged.append({
                "pm_id": pm.pm_id,
                "pm_name": pm.pm_name,
                "onboarding_stage": pm.onboarding_stage,
                "open_needs_count": count,
                "threshold": settings.pm_open_needs_alert_count,
                "top_needs": [
                    {"need_id": n.need_id, "title": n.title, "urgency": n.urgency}
                    for n in open_needs[:5]
                ],
            })

    return flagged


async def _check_aging_blockers(
    session: AsyncSession, today: date, settings: Settings
) -> list[dict[str, Any]]:
    """Find open blockers older than blocker_age_alert_days."""
    cutoff = today - timedelta(days=settings.blocker_age_alert_days)

    result = await session.execute(
        select(RiskTable).where(
            RiskTable.risk_type == "blocker",
            RiskTable.status.in_(["open", "in_mitigation"]),
            RiskTable.date_opened <= cutoff.isoformat(),
        )
    )
    rows = result.scalars().all()

    alerts = []
    for r in rows:
        age = (today - date.fromisoformat(str(r.date_opened))).days
        logger.warning(
            "blocker_aging",
            risk_id=r.risk_id,
            title=r.title,
            severity=r.severity,
            age_days=age,
            threshold=settings.blocker_age_alert_days,
        )
        alerts.append({
            "risk_id": r.risk_id,
            "title": r.title,
            "severity": r.severity,
            "escalation_status": r.escalation_status,
            "owner": r.owner,
            "age_days": age,
            "threshold_days": settings.blocker_age_alert_days,
        })

    return alerts


async def _check_critical_blockers(
    session: AsyncSession, today: date
) -> list[dict[str, Any]]:
    """Find critical blockers open > 3 days — escalate faster than standard threshold."""
    cutoff = today - timedelta(days=_CRITICAL_BLOCKER_AGE_DAYS)

    result = await session.execute(
        select(RiskTable).where(
            RiskTable.severity == "critical",
            RiskTable.status.in_(["open", "in_mitigation"]),
            RiskTable.escalation_status.notin_(["escalated", "resolved"]),
            RiskTable.date_opened <= cutoff.isoformat(),
        )
    )
    rows = result.scalars().all()

    alerts = []
    for r in rows:
        age = (today - date.fromisoformat(str(r.date_opened))).days
        logger.error(
            "blocker_critical_aging",
            risk_id=r.risk_id,
            title=r.title,
            age_days=age,
            escalation_status=r.escalation_status,
        )
        alerts.append({
            "risk_id": r.risk_id,
            "title": r.title,
            "severity": "critical",
            "escalation_status": r.escalation_status,
            "owner": r.owner,
            "age_days": age,
        })

    return alerts
