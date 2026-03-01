"""Unit tests for all service classes.

Uses in-memory SQLite via the shared db_session fixture.
Services are tested end-to-end through real repositories.
"""

from __future__ import annotations

import pytest
from datetime import date, timedelta

from sidecar.models.common import HealthStatus, Urgency
from sidecar.models.decision import DecisionCreate, DecisionResolve, DecisionStatus
from sidecar.models.milestone import MilestoneConfidence, MilestoneCreate, MilestoneStatus, MilestoneUpdate
from sidecar.models.pm_coverage import OnboardingStage, PMCoverageCreate, PMCoverageUpdate
from sidecar.models.pm_need import NeedCategory, NeedStatus, PMNeedCreate, PMNeedUpdate
from sidecar.models.project import ProjectCreate, ProjectStatus, ProjectType, ProjectUpdate
from sidecar.models.risk import RiskCreate, RiskSeverity, RiskStatus, RiskType, RiskUpdate
from sidecar.persistence.decision import DecisionRepository
from sidecar.persistence.milestone import MilestoneRepository
from sidecar.persistence.pm_coverage import PMCoverageRepository
from sidecar.persistence.pm_need import PMNeedRepository
from sidecar.persistence.project import ProjectRepository
from sidecar.persistence.risk import RiskRepository
from sidecar.services.decision_service import DecisionService
from sidecar.services.milestone_service import MilestoneService
from sidecar.services.operating_review_service import OperatingReviewService
from sidecar.services.pm_coverage_service import PMCoverageService
from sidecar.services.pm_need_service import PMNeedService
from sidecar.services.project_service import ProjectService
from sidecar.services.risk_service import RiskService


# ---------------------------------------------------------------------------
# PMCoverageService
# ---------------------------------------------------------------------------

class TestPMCoverageService:
    async def test_create_and_get(self, db_session):
        repo = PMCoverageRepository(db_session)
        svc = PMCoverageService(repo)
        created = await svc.create(PMCoverageCreate(pm_id="pm-jane", pm_name="Jane Doe"))
        assert created.pm_id == "pm-jane"
        fetched = await svc.get("pm-jane")
        assert fetched is not None

    async def test_create_duplicate_raises(self, db_session):
        repo = PMCoverageRepository(db_session)
        svc = PMCoverageService(repo)
        await svc.create(PMCoverageCreate(pm_id="pm-jane", pm_name="Jane"))
        with pytest.raises(ValueError, match="already exists"):
            await svc.create(PMCoverageCreate(pm_id="pm-jane", pm_name="Jane"))

    async def test_update_not_found_raises(self, db_session):
        repo = PMCoverageRepository(db_session)
        svc = PMCoverageService(repo)
        with pytest.raises(KeyError):
            await svc.update(PMCoverageUpdate(pm_id="ghost"))

    async def test_list_at_risk(self, db_session):
        repo = PMCoverageRepository(db_session)
        svc = PMCoverageService(repo)
        await svc.create(PMCoverageCreate(pm_id="pm-1", pm_name="A", health_status=HealthStatus.RED))
        await svc.create(PMCoverageCreate(pm_id="pm-2", pm_name="B", health_status=HealthStatus.GREEN))
        at_risk = await svc.list_at_risk()
        assert len(at_risk) == 1
        assert at_risk[0].pm_id == "pm-1"

    async def test_list_active_onboarding(self, db_session):
        repo = PMCoverageRepository(db_session)
        svc = PMCoverageService(repo)
        await svc.create(PMCoverageCreate(pm_id="pm-1", pm_name="A", onboarding_stage=OnboardingStage.UAT))
        await svc.create(PMCoverageCreate(pm_id="pm-2", pm_name="B", onboarding_stage=OnboardingStage.LIVE))
        await svc.create(PMCoverageCreate(pm_id="pm-3", pm_name="C", onboarding_stage=OnboardingStage.PIPELINE))
        active = await svc.list_active_onboarding()
        assert len(active) == 1
        assert active[0].pm_id == "pm-1"

    async def test_archive(self, db_session):
        repo = PMCoverageRepository(db_session)
        svc = PMCoverageService(repo)
        await svc.create(PMCoverageCreate(pm_id="pm-1", pm_name="A"))
        await svc.archive("pm-1")
        all_visible = await svc.list()
        assert len(all_visible) == 0

    async def test_archive_not_found_raises(self, db_session):
        repo = PMCoverageRepository(db_session)
        svc = PMCoverageService(repo)
        with pytest.raises(KeyError):
            await svc.archive("ghost")


# ---------------------------------------------------------------------------
# PMNeedService
# ---------------------------------------------------------------------------

class TestPMNeedService:
    async def _setup(self, db_session):
        pm_repo = PMCoverageRepository(db_session)
        await pm_repo.create(PMCoverageCreate(pm_id="pm-jane", pm_name="Jane"))
        return PMNeedService(PMNeedRepository(db_session))

    async def test_create_and_get(self, db_session):
        svc = await self._setup(db_session)
        need = await svc.create(PMNeedCreate(
            pm_need_id="n-1",
            pm_id="pm-jane",
            title="DMA need",
            requested_by="Jane",
            date_raised=date(2026, 1, 1),
            category=NeedCategory.EXECUTION,
        ))
        assert need.pm_need_id == "n-1"
        assert need.status == NeedStatus.NEW

    async def test_update_does_not_change_status(self, db_session):
        svc = await self._setup(db_session)
        await svc.create(PMNeedCreate(
            pm_need_id="n-1",
            pm_id="pm-jane",
            title="T",
            requested_by="Jane",
            date_raised=date(2026, 1, 1),
            category=NeedCategory.EXECUTION,
        ))
        updated = await svc.update(PMNeedUpdate(pm_need_id="n-1", urgency=Urgency.IMMEDIATE))
        assert updated.status == NeedStatus.NEW  # D1: status unchanged
        assert updated.urgency == Urgency.IMMEDIATE

    async def test_sync_status(self, db_session):
        svc = await self._setup(db_session)
        await svc.create(PMNeedCreate(
            pm_need_id="n-1",
            pm_id="pm-jane",
            title="T",
            requested_by="Jane",
            date_raised=date(2026, 1, 1),
            category=NeedCategory.EXECUTION,
        ))
        synced = await svc.sync_status("n-1", NeedStatus.IN_PROGRESS)
        assert synced.status == NeedStatus.IN_PROGRESS

    async def test_update_not_found_raises(self, db_session):
        svc = await self._setup(db_session)
        with pytest.raises(KeyError):
            await svc.update(PMNeedUpdate(pm_need_id="ghost"))

    async def test_list_unresolved_for_pm(self, db_session):
        svc = await self._setup(db_session)
        await svc.create(PMNeedCreate(
            pm_need_id="n-1",
            pm_id="pm-jane",
            title="Active",
            requested_by="Jane",
            date_raised=date(2026, 1, 1),
            category=NeedCategory.EXECUTION,
        ))
        await svc.create(PMNeedCreate(
            pm_need_id="n-2",
            pm_id="pm-jane",
            title="Done",
            requested_by="Jane",
            date_raised=date(2026, 1, 2),
            category=NeedCategory.OTHER,
        ))
        await svc.sync_status("n-2", NeedStatus.DELIVERED)
        unresolved = await svc.list_unresolved_for_pm("pm-jane")
        assert len(unresolved) == 1
        assert unresolved[0].pm_need_id == "n-1"


# ---------------------------------------------------------------------------
# RiskService
# ---------------------------------------------------------------------------

class TestRiskService:
    async def test_create_and_escalate(self, db_session):
        repo = RiskRepository(db_session)
        svc = RiskService(repo)
        await svc.create(RiskCreate(
            risk_id="r-1",
            title="Blocker",
            date_opened=date(2026, 2, 1),
            risk_type=RiskType.BLOCKER,
            severity=RiskSeverity.HIGH,
        ))
        escalated = await svc.escalate("r-1")
        from sidecar.models.risk import EscalationStatus
        assert escalated.escalation_status == EscalationStatus.ESCALATED

    async def test_resolve(self, db_session):
        repo = RiskRepository(db_session)
        svc = RiskService(repo)
        await svc.create(RiskCreate(
            risk_id="r-1",
            title="T",
            date_opened=date(2026, 1, 1),
            risk_type=RiskType.RISK,
            severity=RiskSeverity.LOW,
        ))
        resolved = await svc.resolve("r-1")
        assert resolved.status == RiskStatus.RESOLVED

    async def test_list_aging(self, db_session):
        repo = RiskRepository(db_session)
        svc = RiskService(repo)
        old_date = date.today() - timedelta(days=20)
        new_date = date.today() - timedelta(days=2)
        await svc.create(RiskCreate(
            risk_id="r-old",
            title="Old blocker",
            date_opened=old_date,
            risk_type=RiskType.BLOCKER,
            severity=RiskSeverity.HIGH,
        ))
        await svc.create(RiskCreate(
            risk_id="r-new",
            title="New blocker",
            date_opened=new_date,
            risk_type=RiskType.BLOCKER,
            severity=RiskSeverity.MEDIUM,
        ))
        aging = await svc.list_aging(threshold_days=7)
        assert len(aging) == 1
        assert aging[0].risk_id == "r-old"


# ---------------------------------------------------------------------------
# DecisionService
# ---------------------------------------------------------------------------

class TestDecisionService:
    async def test_create_and_resolve(self, db_session):
        repo = DecisionRepository(db_session)
        svc = DecisionService(repo)
        await svc.create(DecisionCreate(decision_id="d-1", title="Choose broker"))
        resolved = await svc.resolve(DecisionResolve(
            decision_id="d-1",
            chosen_path="Broker A",
            rationale="Best latency",
            approvers=["Alice"],
            decision_date=date(2026, 3, 1),
        ))
        assert resolved.status == DecisionStatus.DECIDED

    async def test_resolve_already_decided_raises(self, db_session):
        repo = DecisionRepository(db_session)
        svc = DecisionService(repo)
        await svc.create(DecisionCreate(decision_id="d-1", title="Choose broker"))
        await svc.resolve(DecisionResolve(
            decision_id="d-1",
            chosen_path="Broker A",
            rationale="Best latency",
            approvers=["Alice"],
            decision_date=date(2026, 3, 1),
        ))
        with pytest.raises(ValueError, match="already"):
            await svc.resolve(DecisionResolve(
                decision_id="d-1",
                chosen_path="Broker B",
                rationale="Changed mind",
                approvers=["Bob"],
                decision_date=date(2026, 3, 2),
            ))

    async def test_resolve_not_found_raises(self, db_session):
        repo = DecisionRepository(db_session)
        svc = DecisionService(repo)
        with pytest.raises(KeyError):
            await svc.resolve(DecisionResolve(
                decision_id="ghost",
                chosen_path="X",
                rationale="Y",
                approvers=[],
                decision_date=date(2026, 1, 1),
            ))

    async def test_supersede(self, db_session):
        repo = DecisionRepository(db_session)
        svc = DecisionService(repo)
        await svc.create(DecisionCreate(decision_id="d-1", title="Old decision"))
        new, superseded = await svc.supersede(
            "d-1",
            DecisionCreate(decision_id="d-2", title="Revised decision"),
        )
        assert new.decision_id == "d-2"
        assert superseded.status == DecisionStatus.SUPERSEDED


# ---------------------------------------------------------------------------
# OperatingReviewService
# ---------------------------------------------------------------------------

class TestOperatingReviewService:
    def _make_service(self, db_session) -> OperatingReviewService:
        return OperatingReviewService(
            pm_repo=PMCoverageRepository(db_session),
            need_repo=PMNeedRepository(db_session),
            project_repo=ProjectRepository(db_session),
            milestone_repo=MilestoneRepository(db_session),
            risk_repo=RiskRepository(db_session),
            decision_repo=DecisionRepository(db_session),
            blocker_age_threshold_days=7,
            milestone_due_threshold_days=7,
            pm_open_needs_threshold=3,
        )

    async def test_empty_agenda(self, db_session):
        svc = self._make_service(db_session)
        agenda = await svc.get_agenda()
        assert agenda.pms_at_risk == []
        assert agenda.aging_blockers == []
        assert agenda.pending_decisions == []

    async def test_agenda_includes_red_pm(self, db_session):
        pm_repo = PMCoverageRepository(db_session)
        await pm_repo.create(PMCoverageCreate(
            pm_id="pm-1", pm_name="At Risk PM", health_status=HealthStatus.RED
        ))
        svc = self._make_service(db_session)
        agenda = await svc.get_agenda()
        assert len(agenda.pms_at_risk) == 1
        assert agenda.pms_at_risk[0].pm.pm_id == "pm-1"
        assert "health=red" in agenda.pms_at_risk[0].reasons

    async def test_agenda_includes_aging_blockers(self, db_session):
        risk_repo = RiskRepository(db_session)
        old_date = date.today() - timedelta(days=10)
        await risk_repo.create(RiskCreate(
            risk_id="r-1",
            title="Aging blocker",
            date_opened=old_date,
            risk_type=RiskType.BLOCKER,
            severity=RiskSeverity.HIGH,
        ))
        svc = self._make_service(db_session)
        agenda = await svc.get_agenda()
        assert len(agenda.aging_blockers) == 1

    async def test_agenda_includes_pending_decisions(self, db_session):
        decision_repo = DecisionRepository(db_session)
        await decision_repo.create(DecisionCreate(
            decision_id="d-1",
            title="Pending choice",
            status=DecisionStatus.PENDING,
        ))
        svc = self._make_service(db_session)
        agenda = await svc.get_agenda()
        assert len(agenda.pending_decisions) == 1

    async def test_pm_flagged_for_too_many_needs(self, db_session):
        pm_repo = PMCoverageRepository(db_session)
        await pm_repo.create(PMCoverageCreate(pm_id="pm-1", pm_name="Busy PM"))
        need_repo = PMNeedRepository(db_session)
        for i in range(3):
            await need_repo.create(PMNeedCreate(
                pm_need_id=f"n-{i}",
                pm_id="pm-1",
                title=f"Need {i}",
                requested_by="PM 1",
                date_raised=date(2026, 1, i + 1),
                category=NeedCategory.OTHER,
            ))
        svc = self._make_service(db_session)
        pms_at_risk = await svc.get_pms_at_risk()
        assert len(pms_at_risk) == 1
        assert any("open_needs" in r for r in pms_at_risk[0].reasons)
