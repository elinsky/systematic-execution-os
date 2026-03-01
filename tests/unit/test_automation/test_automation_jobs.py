"""Unit tests for automation jobs.

Tests daily_digest, weekly_review_prep, milestone_watch, and pm_health_watch
using an in-memory SQLite database seeded with controlled fixtures.

The session_factory fixture wraps the shared db_session so jobs run against
the same populated database without opening a second connection.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from sidecar.config import Settings
from sidecar.db.milestone import MilestoneTable
from sidecar.db.pm_coverage import PMCoverageTable
from sidecar.db.pm_need import PMNeedTable
from sidecar.db.risk import RiskTable
from sidecar.db.decision import DecisionTable

from sidecar.automation.daily_digest import run_daily_digest
from sidecar.automation.milestone_watch import run_milestone_watch
from sidecar.automation.pm_health_watch import run_pm_health_watch
from sidecar.automation.weekly_review_prep import run_weekly_review_prep


# ---------------------------------------------------------------------------
# Helpers to make session_factory from an existing db_session
# ---------------------------------------------------------------------------

def make_session_factory(session: AsyncSession):
    """Wrap a single AsyncSession in a factory compatible with the automation jobs."""
    @asynccontextmanager
    async def factory() -> AsyncIterator[AsyncSession]:
        yield session

    return factory


def _settings(**overrides) -> Settings:
    defaults = {
        "asana_personal_access_token": "test-token",
        "asana_workspace_gid": "ws-1",
        "milestone_due_alert_days": overrides.pop("MILESTONE_DUE_ALERT_DAYS", 7),
        "blocker_age_alert_days": overrides.pop("BLOCKER_AGE_ALERT_DAYS", 7),
        "pm_open_needs_alert_count": overrides.pop("PM_OPEN_NEEDS_ALERT_COUNT", 3),
    }
    defaults.update(overrides)
    return Settings(**defaults)


# ---------------------------------------------------------------------------
# DB seed helpers
# ---------------------------------------------------------------------------

def _today() -> date:
    return date.today()


def _days(n: int) -> date:
    """Return date object n days from today (negative = past)."""
    return date.today() + timedelta(days=n)


def _today_str() -> str:
    return date.today().isoformat()


async def _add_milestone(
    session: AsyncSession,
    *,
    milestone_id: str,
    project_id: str = "proj-1",
    name: str = "Test Milestone",
    target_date: date | None = None,
    status: str = "not_started",
    confidence: str = "high",
    acceptance_criteria: str | None = "AC defined",
    owner: str | None = "Alice",
) -> MilestoneTable:
    row = MilestoneTable(
        milestone_id=milestone_id,
        project_id=project_id,
        name=name,
        target_date=target_date,
        status=status,
        confidence=confidence,
        acceptance_criteria=acceptance_criteria,
        owner=owner,
    )
    session.add(row)
    await session.flush()
    return row


async def _add_pm(
    session: AsyncSession,
    *,
    pm_id: str,
    pm_name: str = "Jane Doe",
    health_status: str = "green",
    onboarding_stage: str = "onboarding_in_progress",
) -> PMCoverageTable:
    row = PMCoverageTable(
        pm_id=pm_id,
        pm_name=pm_name,
        health_status=health_status,
        onboarding_stage=onboarding_stage,
        linked_project_ids="[]",
    )
    session.add(row)
    await session.flush()
    return row


async def _add_need(
    session: AsyncSession,
    *,
    need_id: str,
    pm_id: str,
    title: str = "A PM Need",
    status: str = "new",
    urgency: str = "this_month",
) -> PMNeedTable:
    row = PMNeedTable(
        need_id=need_id,
        pm_id=pm_id,
        title=title,
        requested_by="PM",
        date_raised=_today(),
        category="execution",
        urgency=urgency,
        status=status,
        linked_project_ids="[]",
    )
    session.add(row)
    await session.flush()
    return row


async def _add_risk(
    session: AsyncSession,
    *,
    risk_id: str,
    title: str = "Blocker",
    risk_type: str = "blocker",
    severity: str = "medium",
    status: str = "open",
    date_opened: date | None = None,
    escalation_status: str = "none",
) -> RiskTable:
    row = RiskTable(
        risk_id=risk_id,
        title=title,
        risk_type=risk_type,
        severity=severity,
        status=status,
        date_opened=date_opened or _today(),
        escalation_status=escalation_status,
        impacted_pm_ids="[]",
        impacted_project_ids="[]",
        impacted_milestone_ids="[]",
    )
    session.add(row)
    await session.flush()
    return row


async def _add_decision(
    session: AsyncSession,
    *,
    decision_id: str,
    title: str = "Pending Decision",
    status: str = "pending",
) -> DecisionTable:
    row = DecisionTable(
        decision_id=decision_id,
        title=title,
        status=status,
        impacted_artifact_ids="[]",
    )
    session.add(row)
    await session.flush()
    return row


# ---------------------------------------------------------------------------
# daily_digest tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daily_digest_empty_db(db_session):
    """Digest with no data returns empty lists."""
    settings = _settings()
    factory = make_session_factory(db_session)

    digest = await run_daily_digest(settings, factory)

    assert digest["overdue_milestones"] == []
    assert digest["near_milestones"] == []
    assert digest["pms_at_risk"] == []
    assert digest["aging_blockers"] == []
    assert "generated_at" in digest


@pytest.mark.asyncio
async def test_daily_digest_overdue_milestone(db_session):
    """Overdue milestones appear in digest."""
    await _add_milestone(
        db_session,
        milestone_id="ms-overdue",
        target_date=_days(-5),
        status="not_started",
    )
    await db_session.commit()

    digest = await run_daily_digest(_settings(), make_session_factory(db_session))

    overdue = digest["overdue_milestones"]
    assert len(overdue) == 1
    assert overdue[0]["milestone_id"] == "ms-overdue"
    assert overdue[0]["days_overdue"] == 5


@pytest.mark.asyncio
async def test_daily_digest_complete_milestone_excluded(db_session):
    """Complete milestones do NOT appear in overdue list."""
    await _add_milestone(
        db_session,
        milestone_id="ms-done",
        target_date=_days(-3),
        status="complete",
    )
    await db_session.commit()

    digest = await run_daily_digest(_settings(), make_session_factory(db_session))
    assert digest["overdue_milestones"] == []


@pytest.mark.asyncio
async def test_daily_digest_near_milestone(db_session):
    """Milestones within the alert window appear in near_milestones."""
    await _add_milestone(
        db_session,
        milestone_id="ms-near",
        target_date=_days(3),
        status="in_progress",
    )
    await db_session.commit()

    digest = await run_daily_digest(_settings(MILESTONE_DUE_ALERT_DAYS=7), make_session_factory(db_session))

    near = digest["near_milestones"]
    assert len(near) == 1
    assert near[0]["milestone_id"] == "ms-near"
    assert near[0]["days_until_due"] == 3


@pytest.mark.asyncio
async def test_daily_digest_pms_at_risk(db_session):
    """PMs with red/yellow health appear in pms_at_risk."""
    await _add_pm(db_session, pm_id="pm-red", health_status="red")
    await _add_pm(db_session, pm_id="pm-yellow", health_status="yellow")
    await _add_pm(db_session, pm_id="pm-green", health_status="green")
    await db_session.commit()

    digest = await run_daily_digest(_settings(), make_session_factory(db_session))

    risk_ids = {r["pm_id"] for r in digest["pms_at_risk"]}
    assert risk_ids == {"pm-red", "pm-yellow"}


@pytest.mark.asyncio
async def test_daily_digest_aging_blockers(db_session):
    """Risks opened before threshold appear in aging_blockers."""
    old_date = _days(-10)
    recent_date = _days(-1)

    await _add_risk(db_session, risk_id="risk-old", date_opened=old_date)
    await _add_risk(db_session, risk_id="risk-recent", date_opened=recent_date)
    await db_session.commit()

    digest = await run_daily_digest(_settings(BLOCKER_AGE_ALERT_DAYS=7), make_session_factory(db_session))

    ids = [r["risk_id"] for r in digest["aging_blockers"]]
    assert "risk-old" in ids
    assert "risk-recent" not in ids


# ---------------------------------------------------------------------------
# milestone_watch tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_milestone_watch_overdue(db_session):
    await _add_milestone(
        db_session,
        milestone_id="ms-ow",
        target_date=_days(-2),
        status="not_started",
    )
    await db_session.commit()

    result = await run_milestone_watch(_settings(), make_session_factory(db_session))

    assert len(result["overdue"]) == 1
    assert result["overdue"][0]["days_overdue"] == 2


@pytest.mark.asyncio
async def test_milestone_watch_missing_criteria(db_session):
    """Near milestones with no acceptance_criteria appear in missing_criteria."""
    await _add_milestone(
        db_session,
        milestone_id="ms-no-ac",
        target_date=_days(3),
        status="in_progress",
        acceptance_criteria=None,
    )
    await db_session.commit()

    result = await run_milestone_watch(
        _settings(MILESTONE_DUE_ALERT_DAYS=7), make_session_factory(db_session)
    )

    assert any(r["milestone_id"] == "ms-no-ac" for r in result["missing_criteria"])


@pytest.mark.asyncio
async def test_milestone_watch_low_confidence(db_session):
    """Near milestones with low/blocked confidence appear in low_confidence."""
    await _add_milestone(
        db_session,
        milestone_id="ms-low-conf",
        target_date=_days(4),
        status="in_progress",
        confidence="low",
        acceptance_criteria="AC here",
    )
    await db_session.commit()

    result = await run_milestone_watch(
        _settings(MILESTONE_DUE_ALERT_DAYS=7), make_session_factory(db_session)
    )

    assert any(r["milestone_id"] == "ms-low-conf" for r in result["low_confidence"])


@pytest.mark.asyncio
async def test_milestone_watch_high_confidence_with_ac_excluded(db_session):
    """Near milestone with high confidence and AC set should not trigger any alert."""
    await _add_milestone(
        db_session,
        milestone_id="ms-ok",
        target_date=_days(3),
        status="in_progress",
        confidence="high",
        acceptance_criteria="Done when all tests pass.",
    )
    await db_session.commit()

    result = await run_milestone_watch(
        _settings(MILESTONE_DUE_ALERT_DAYS=7), make_session_factory(db_session)
    )

    assert not any(r["milestone_id"] == "ms-ok" for r in result["missing_criteria"])
    assert not any(r["milestone_id"] == "ms-ok" for r in result["low_confidence"])


@pytest.mark.asyncio
async def test_milestone_watch_complete_excluded(db_session):
    """Complete milestones must not appear in any alert category."""
    await _add_milestone(
        db_session,
        milestone_id="ms-complete",
        target_date=_days(-5),
        status="complete",
    )
    await db_session.commit()

    result = await run_milestone_watch(_settings(), make_session_factory(db_session))

    for category in ("missing_criteria", "low_confidence", "overdue"):
        assert not any(r["milestone_id"] == "ms-complete" for r in result[category])


# ---------------------------------------------------------------------------
# pm_health_watch tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pm_health_watch_too_many_needs(db_session):
    """PM with >= threshold unresolved needs is flagged."""
    pm = await _add_pm(db_session, pm_id="pm-needs", health_status="green")

    for i in range(4):
        await _add_need(db_session, need_id=f"n-needs-{i}", pm_id="pm-needs", status="new")
    await db_session.commit()

    result = await run_pm_health_watch(
        _settings(PM_OPEN_NEEDS_ALERT_COUNT=3), make_session_factory(db_session)
    )

    flagged = result["pms_with_too_many_needs"]
    assert len(flagged) == 1
    assert flagged[0]["pm_id"] == "pm-needs"
    assert flagged[0]["open_needs_count"] == 4


@pytest.mark.asyncio
async def test_pm_health_watch_delivered_needs_excluded(db_session):
    """Delivered/cancelled/deferred needs do not count toward open needs."""
    await _add_pm(db_session, pm_id="pm-ok", health_status="green")

    for i in range(3):
        await _add_need(
            db_session, need_id=f"n-del-{i}", pm_id="pm-ok", status="delivered"
        )
    await _add_need(db_session, need_id="n-new-1", pm_id="pm-ok", status="new")
    await db_session.commit()

    result = await run_pm_health_watch(
        _settings(PM_OPEN_NEEDS_ALERT_COUNT=3), make_session_factory(db_session)
    )

    assert result["pms_with_too_many_needs"] == []


@pytest.mark.asyncio
async def test_pm_health_watch_aging_blockers(db_session):
    """Aging blockers (open > threshold days) are reported."""
    old = _days(-10)
    await _add_risk(db_session, risk_id="rb-old", severity="high", date_opened=old)
    await _add_risk(db_session, risk_id="rb-new", severity="low", date_opened=_days(-1))
    await db_session.commit()

    result = await run_pm_health_watch(
        _settings(BLOCKER_AGE_ALERT_DAYS=7), make_session_factory(db_session)
    )

    aging_ids = [r["risk_id"] for r in result["aging_blockers"]]
    assert "rb-old" in aging_ids
    assert "rb-new" not in aging_ids


@pytest.mark.asyncio
async def test_pm_health_watch_critical_blocker_escalation(db_session):
    """Critical blockers open > 3 days trigger critical_aging_blockers regardless of general threshold."""
    old_critical = _days(-4)
    await _add_risk(
        db_session,
        risk_id="crit-old",
        severity="critical",
        date_opened=old_critical,
        escalation_status="none",
    )
    await db_session.commit()

    # General threshold is 14 days (would NOT catch this normally)
    result = await run_pm_health_watch(
        _settings(BLOCKER_AGE_ALERT_DAYS=14), make_session_factory(db_session)
    )

    critical_ids = [r["risk_id"] for r in result["critical_aging_blockers"]]
    assert "crit-old" in critical_ids


@pytest.mark.asyncio
async def test_pm_health_watch_already_escalated_excluded_from_critical(db_session):
    """Critical blockers already escalated are excluded from critical_aging_blockers."""
    old_critical = _days(-10)
    await _add_risk(
        db_session,
        risk_id="crit-esc",
        severity="critical",
        date_opened=old_critical,
        escalation_status="escalated",
    )
    await db_session.commit()

    result = await run_pm_health_watch(_settings(), make_session_factory(db_session))

    critical_ids = [r["risk_id"] for r in result["critical_aging_blockers"]]
    assert "crit-esc" not in critical_ids


# ---------------------------------------------------------------------------
# weekly_review_prep tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_weekly_review_prep_empty(db_session):
    """Weekly review with no data returns empty sections."""
    agenda = await run_weekly_review_prep(_settings(), make_session_factory(db_session))

    assert agenda["overdue_milestones"] == []
    assert agenda["milestone_slips"] == []
    assert agenda["pms_at_risk"] == []
    assert agenda["open_blockers"] == []
    assert agenda["pending_decisions"] == []
    assert "generated_at" in agenda


@pytest.mark.asyncio
async def test_weekly_review_prep_milestone_slips(db_session):
    """Milestones within 30-day window that are at_risk appear in milestone_slips."""
    await _add_milestone(
        db_session,
        milestone_id="ms-slip",
        target_date=_days(15),
        status="at_risk",
        confidence="high",
    )
    await _add_milestone(
        db_session,
        milestone_id="ms-ok",
        target_date=_days(5),
        status="in_progress",
        confidence="high",
    )
    await db_session.commit()

    agenda = await run_weekly_review_prep(_settings(), make_session_factory(db_session))

    slip_ids = [r["milestone_id"] for r in agenda["milestone_slips"]]
    assert "ms-slip" in slip_ids
    assert "ms-ok" not in slip_ids


@pytest.mark.asyncio
async def test_weekly_review_prep_pms_at_risk_with_needs(db_session):
    """PMs at risk include open need counts."""
    await _add_pm(db_session, pm_id="pm-w1", health_status="red")
    await _add_need(db_session, need_id="n-w1", pm_id="pm-w1", status="new")
    await _add_need(db_session, need_id="n-w2", pm_id="pm-w1", status="triaged")
    await db_session.commit()

    agenda = await run_weekly_review_prep(_settings(), make_session_factory(db_session))

    at_risk = agenda["pms_at_risk"]
    assert len(at_risk) == 1
    assert at_risk[0]["pm_id"] == "pm-w1"
    assert at_risk[0]["open_needs_count"] == 2


@pytest.mark.asyncio
async def test_weekly_review_prep_blockers_sorted_by_severity(db_session):
    """Open blockers are returned critical-first."""
    await _add_risk(db_session, risk_id="r-crit", severity="critical", date_opened=_days(-1))
    await _add_risk(db_session, risk_id="r-low", severity="low", date_opened=_days(-20))
    await _add_risk(db_session, risk_id="r-high", severity="high", date_opened=_days(-5))
    await db_session.commit()

    agenda = await run_weekly_review_prep(_settings(), make_session_factory(db_session))

    ids = [r["risk_id"] for r in agenda["open_blockers"]]
    assert ids[0] == "r-crit"
    assert ids[-1] == "r-low"


@pytest.mark.asyncio
async def test_weekly_review_prep_pending_decisions(db_session):
    """Pending decisions appear in agenda; resolved decisions do not."""
    await _add_decision(db_session, decision_id="dec-1", title="Pending Choice", status="pending")
    await _add_decision(db_session, decision_id="dec-2", title="Resolved Choice", status="resolved")
    await db_session.commit()

    agenda = await run_weekly_review_prep(_settings(), make_session_factory(db_session))

    decision_ids = [d["decision_id"] for d in agenda["pending_decisions"]]
    assert "dec-1" in decision_ids
    assert "dec-2" not in decision_ids
