"""Unit tests for all repository classes (persistence layer).

Uses an in-memory SQLite database via the shared db_session fixture.
"""

import pytest
from datetime import date

from sidecar.models.common import HealthStatus, Priority, Urgency, BusinessImpact
from sidecar.models.pm_coverage import OnboardingStage, PMCoverageCreate, PMCoverageUpdate
from sidecar.models.pm_need import NeedCategory, NeedStatus, PMNeedCreate, PMNeedUpdate
from sidecar.models.project import Project, ProjectCreate, ProjectStatus, ProjectType, ProjectUpdate
from sidecar.models.milestone import (
    Milestone, MilestoneConfidence, MilestoneCreate, MilestoneStatus, MilestoneUpdate
)
from sidecar.models.risk import (
    EscalationStatus, RiskBlocker, RiskCreate, RiskSeverity, RiskStatus, RiskType, RiskUpdate
)
from sidecar.models.decision import (
    ArtifactType, DecisionCreate, DecisionResolve, DecisionStatus, ImpactedArtifact
)
from sidecar.persistence.pm_coverage import PMCoverageRepository
from sidecar.persistence.pm_need import PMNeedRepository
from sidecar.persistence.project import ProjectRepository
from sidecar.persistence.milestone import MilestoneRepository
from sidecar.persistence.risk import RiskRepository
from sidecar.persistence.decision import DecisionRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pm_create(pm_id: str = "pm-jane", pm_name: str = "Jane Doe") -> PMCoverageCreate:
    return PMCoverageCreate(pm_id=pm_id, pm_name=pm_name)


def _need_create(need_id: str = "n-1", pm_id: str = "pm-jane") -> PMNeedCreate:
    return PMNeedCreate(
        pm_need_id=need_id,
        pm_id=pm_id,
        title=f"{pm_id} - Execution - DMA",
        requested_by="Jane Doe",
        date_raised=date(2026, 1, 15),
        category=NeedCategory.EXECUTION,
    )


def _project_create(project_id: str = "proj-1") -> ProjectCreate:
    return ProjectCreate(
        project_id=project_id,
        name=f"Onboarding - PM Jane - Launch",
        project_type=ProjectType.PM_ONBOARDING,
        primary_pm_ids=["pm-jane"],
    )


def _milestone_create(milestone_id: str = "m-1", project_id: str = "proj-1") -> MilestoneCreate:
    return MilestoneCreate(
        milestone_id=milestone_id,
        project_id=project_id,
        name="PM Jane - Go Live Ready",
        target_date=date(2026, 6, 30),
    )


def _risk_create(risk_id: str = "r-1") -> RiskCreate:
    return RiskCreate(
        risk_id=risk_id,
        title="PM Jane - Historical Data Delayed",
        date_opened=date(2026, 2, 1),
        risk_type=RiskType.BLOCKER,
        severity=RiskSeverity.HIGH,
        impacted_pm_ids=["pm-jane"],
        impacted_project_ids=["proj-1"],
    )


def _decision_create(decision_id: str = "d-1") -> DecisionCreate:
    return DecisionCreate(
        decision_id=decision_id,
        title="Choose broker A over B",
        status=DecisionStatus.PENDING,
    )


# ---------------------------------------------------------------------------
# PMCoverageRepository
# ---------------------------------------------------------------------------

class TestPMCoverageRepository:
    async def test_create_and_get(self, db_session):
        repo = PMCoverageRepository(db_session)
        created = await repo.create(_pm_create())
        assert created.pm_id == "pm-jane"
        assert created.pm_name == "Jane Doe"
        assert created.onboarding_stage == OnboardingStage.PIPELINE

        fetched = await repo.get("pm-jane")
        assert fetched is not None
        assert fetched.pm_id == "pm-jane"

    async def test_get_not_found(self, db_session):
        repo = PMCoverageRepository(db_session)
        assert await repo.get("no-such-pm") is None

    async def test_list_all(self, db_session):
        repo = PMCoverageRepository(db_session)
        await repo.create(_pm_create("pm-1", "Alice"))
        await repo.create(_pm_create("pm-2", "Bob"))
        records = await repo.list()
        assert len(records) == 2

    async def test_list_filter_by_stage(self, db_session):
        repo = PMCoverageRepository(db_session)
        await repo.create(_pm_create("pm-1"))
        await repo.create(PMCoverageCreate(
            pm_id="pm-2", pm_name="Bob",
            onboarding_stage=OnboardingStage.LIVE,
        ))
        live = await repo.list(stage=OnboardingStage.LIVE)
        assert len(live) == 1
        assert live[0].pm_id == "pm-2"

    async def test_list_filter_by_health(self, db_session):
        repo = PMCoverageRepository(db_session)
        await repo.create(PMCoverageCreate(pm_id="pm-1", pm_name="A", health_status=HealthStatus.RED))
        await repo.create(PMCoverageCreate(pm_id="pm-2", pm_name="B", health_status=HealthStatus.GREEN))
        red = await repo.list(health=HealthStatus.RED)
        assert len(red) == 1
        assert red[0].pm_id == "pm-1"

    async def test_update_stage(self, db_session):
        repo = PMCoverageRepository(db_session)
        await repo.create(_pm_create())
        updated = await repo.update(PMCoverageUpdate(
            pm_id="pm-jane",
            onboarding_stage=OnboardingStage.GO_LIVE_READY,
        ))
        assert updated is not None
        assert updated.onboarding_stage == OnboardingStage.GO_LIVE_READY

    async def test_update_not_found(self, db_session):
        repo = PMCoverageRepository(db_session)
        result = await repo.update(PMCoverageUpdate(pm_id="ghost"))
        assert result is None

    async def test_archive(self, db_session):
        repo = PMCoverageRepository(db_session)
        await repo.create(_pm_create())
        archived = await repo.archive("pm-jane")
        assert archived is True
        # Should not appear in default list
        records = await repo.list()
        assert len(records) == 0
        # Should appear with include_archived=True
        all_records = await repo.list(include_archived=True)
        assert len(all_records) == 1

    async def test_upsert_by_asana_gid_creates_new(self, db_session):
        repo = PMCoverageRepository(db_session)
        data = PMCoverageCreate(pm_id="pm-new", pm_name="New PM", asana_gid="gid-123")
        result = await repo.upsert_by_asana_gid(data)
        assert result.pm_id == "pm-new"
        assert result.asana_gid == "gid-123"

    async def test_upsert_by_asana_gid_updates_existing(self, db_session):
        repo = PMCoverageRepository(db_session)
        await repo.create(PMCoverageCreate(pm_id="pm-jane", pm_name="Jane", asana_gid="gid-abc"))
        data = PMCoverageCreate(
            pm_id="pm-jane",
            pm_name="Jane",
            asana_gid="gid-abc",
            onboarding_stage=OnboardingStage.LIVE,
        )
        result = await repo.upsert_by_asana_gid(data)
        assert result.onboarding_stage == OnboardingStage.LIVE


# ---------------------------------------------------------------------------
# PMNeedRepository
# ---------------------------------------------------------------------------

class TestPMNeedRepository:
    async def test_create_and_get(self, db_session):
        # Need a PM coverage record for FK
        pm_repo = PMCoverageRepository(db_session)
        await pm_repo.create(_pm_create())

        repo = PMNeedRepository(db_session)
        created = await repo.create(_need_create())
        assert created.pm_need_id == "n-1"
        assert created.status == NeedStatus.NEW

        fetched = await repo.get("n-1")
        assert fetched is not None
        assert fetched.category == NeedCategory.EXECUTION

    async def test_list_by_pm_id(self, db_session):
        pm_repo = PMCoverageRepository(db_session)
        await pm_repo.create(_pm_create("pm-jane"))
        await pm_repo.create(_pm_create("pm-bob", "Bob"))

        repo = PMNeedRepository(db_session)
        await repo.create(_need_create("n-1", "pm-jane"))
        await repo.create(_need_create("n-2", "pm-bob"))
        await repo.create(_need_create("n-3", "pm-jane"))

        jane_needs = await repo.list(pm_id="pm-jane")
        assert len(jane_needs) == 2

    async def test_status_not_updated_by_update(self, db_session):
        pm_repo = PMCoverageRepository(db_session)
        await pm_repo.create(_pm_create())

        repo = PMNeedRepository(db_session)
        await repo.create(_need_create())

        # Attempt update — status should NOT change
        update = PMNeedUpdate(pm_need_id="n-1", urgency=Urgency.IMMEDIATE)
        updated = await repo.update(update)
        assert updated is not None
        assert updated.status == NeedStatus.NEW  # unchanged
        assert updated.urgency == Urgency.IMMEDIATE

    async def test_sync_status_from_asana(self, db_session):
        pm_repo = PMCoverageRepository(db_session)
        await pm_repo.create(_pm_create())

        repo = PMNeedRepository(db_session)
        await repo.create(_need_create())

        success = await repo.sync_status_from_asana("n-1", NeedStatus.IN_PROGRESS)
        assert success is True
        updated = await repo.get("n-1")
        assert updated is not None
        assert updated.status == NeedStatus.IN_PROGRESS


# ---------------------------------------------------------------------------
# ProjectRepository
# ---------------------------------------------------------------------------

class TestProjectRepository:
    async def test_create_and_get(self, db_session):
        repo = ProjectRepository(db_session)
        created = await repo.create(_project_create())
        assert created.project_id == "proj-1"
        assert created.status == ProjectStatus.PLANNING
        assert "pm-jane" in created.primary_pm_ids

        fetched = await repo.get("proj-1")
        assert fetched is not None
        assert fetched.name == created.name

    async def test_list_filter_by_pm(self, db_session):
        repo = ProjectRepository(db_session)
        await repo.create(_project_create("proj-1"))
        await repo.create(ProjectCreate(
            project_id="proj-2",
            name="Other Project",
            project_type=ProjectType.CAPABILITY_BUILD,
            primary_pm_ids=["pm-bob"],
        ))
        jane_projects = await repo.list(pm_id="pm-jane")
        assert len(jane_projects) == 1
        assert jane_projects[0].project_id == "proj-1"

    async def test_update_health_and_status(self, db_session):
        repo = ProjectRepository(db_session)
        await repo.create(_project_create())
        updated = await repo.update(ProjectUpdate(
            project_id="proj-1",
            status=ProjectStatus.AT_RISK,
            health=HealthStatus.RED,
        ))
        assert updated is not None
        assert updated.status == ProjectStatus.AT_RISK
        assert updated.health == HealthStatus.RED


# ---------------------------------------------------------------------------
# MilestoneRepository
# ---------------------------------------------------------------------------

class TestMilestoneRepository:
    async def test_create_and_get(self, db_session):
        proj_repo = ProjectRepository(db_session)
        await proj_repo.create(_project_create())

        repo = MilestoneRepository(db_session)
        created = await repo.create(_milestone_create())
        assert created.milestone_id == "m-1"
        assert created.status == MilestoneStatus.NOT_STARTED
        assert created.confidence == MilestoneConfidence.UNKNOWN

    async def test_list_for_project(self, db_session):
        proj_repo = ProjectRepository(db_session)
        await proj_repo.create(_project_create())

        repo = MilestoneRepository(db_session)
        await repo.create(_milestone_create("m-1"))
        await repo.create(_milestone_create("m-2"))

        milestones = await repo.list_for_project("proj-1")
        assert len(milestones) == 2

    async def test_list_at_risk(self, db_session):
        proj_repo = ProjectRepository(db_session)
        await proj_repo.create(_project_create())

        repo = MilestoneRepository(db_session)
        await repo.create(_milestone_create("m-1"))
        await repo.create(MilestoneCreate(
            milestone_id="m-2",
            project_id="proj-1",
            name="At Risk",
            status=MilestoneStatus.AT_RISK,
        ))
        at_risk = await repo.list_at_risk()
        assert len(at_risk) == 1
        assert at_risk[0].milestone_id == "m-2"

    async def test_update_confidence(self, db_session):
        proj_repo = ProjectRepository(db_session)
        await proj_repo.create(_project_create())

        repo = MilestoneRepository(db_session)
        await repo.create(_milestone_create())
        updated = await repo.update(MilestoneUpdate(
            milestone_id="m-1",
            confidence=MilestoneConfidence.LOW,
            status=MilestoneStatus.AT_RISK,
        ))
        assert updated is not None
        assert updated.confidence == MilestoneConfidence.LOW


# ---------------------------------------------------------------------------
# RiskRepository
# ---------------------------------------------------------------------------

class TestRiskRepository:
    async def test_create_and_get(self, db_session):
        repo = RiskRepository(db_session)
        created = await repo.create(_risk_create())
        assert created.risk_id == "r-1"
        assert created.risk_type == RiskType.BLOCKER
        assert created.severity == RiskSeverity.HIGH
        assert "pm-jane" in created.impacted_pm_ids

    async def test_list_open_only(self, db_session):
        repo = RiskRepository(db_session)
        await repo.create(_risk_create("r-1"))
        await repo.create(RiskCreate(
            risk_id="r-2",
            title="Resolved",
            date_opened=date(2026, 1, 1),
            risk_type=RiskType.RISK,
            severity=RiskSeverity.LOW,
            status=RiskStatus.RESOLVED,
        ))
        open_risks = await repo.list(open_only=True)
        assert len(open_risks) == 1
        assert open_risks[0].risk_id == "r-1"

    async def test_filter_by_pm(self, db_session):
        repo = RiskRepository(db_session)
        await repo.create(_risk_create("r-1"))  # impacted_pm_ids=["pm-jane"]
        await repo.create(RiskCreate(
            risk_id="r-2",
            title="Other PM risk",
            date_opened=date(2026, 1, 1),
            risk_type=RiskType.RISK,
            severity=RiskSeverity.MEDIUM,
            impacted_pm_ids=["pm-bob"],
        ))
        jane_risks = await repo.list(pm_id="pm-jane")
        assert len(jane_risks) == 1
        assert jane_risks[0].risk_id == "r-1"

    async def test_update_escalation(self, db_session):
        repo = RiskRepository(db_session)
        await repo.create(_risk_create())
        updated = await repo.update(RiskUpdate(
            risk_id="r-1",
            escalation_status=EscalationStatus.ESCALATED,
            mitigation_plan="Escalated to tech lead",
        ))
        assert updated is not None
        assert updated.escalation_status == EscalationStatus.ESCALATED

    async def test_age_days_computed(self, db_session):
        repo = RiskRepository(db_session)
        await repo.create(_risk_create())
        risk = await repo.get("r-1")
        assert risk is not None
        assert isinstance(risk.age_days, int)
        assert risk.age_days >= 0


# ---------------------------------------------------------------------------
# DecisionRepository
# ---------------------------------------------------------------------------

class TestDecisionRepository:
    async def test_create_and_get(self, db_session):
        repo = DecisionRepository(db_session)
        created = await repo.create(_decision_create())
        assert created.decision_id == "d-1"
        assert created.status == DecisionStatus.PENDING

        fetched = await repo.get("d-1")
        assert fetched is not None
        assert fetched.title == "Choose broker A over B"

    async def test_list_pending(self, db_session):
        repo = DecisionRepository(db_session)
        await repo.create(_decision_create("d-1"))
        await repo.create(DecisionCreate(
            decision_id="d-2",
            title="Another decision",
            status=DecisionStatus.DECIDED,
        ))
        pending = await repo.list_pending()
        assert len(pending) == 1
        assert pending[0].decision_id == "d-1"

    async def test_resolve(self, db_session):
        repo = DecisionRepository(db_session)
        await repo.create(_decision_create())
        resolved = await repo.resolve(DecisionResolve(
            decision_id="d-1",
            chosen_path="Broker A",
            rationale="Best latency",
            approvers=["Alice"],
            decision_date=date(2026, 3, 1),
        ))
        assert resolved is not None
        assert resolved.status == DecisionStatus.DECIDED
        assert resolved.chosen_path == "Broker A"

    async def test_resolve_decided_decision_returns_none(self, db_session):
        """D3: decided decisions are immutable — resolve returns None."""
        repo = DecisionRepository(db_session)
        await repo.create(_decision_create())
        await repo.resolve(DecisionResolve(
            decision_id="d-1",
            chosen_path="Broker A",
            rationale="Best latency",
            approvers=["Alice"],
            decision_date=date(2026, 3, 1),
        ))
        # Attempt to resolve again
        result = await repo.resolve(DecisionResolve(
            decision_id="d-1",
            chosen_path="Broker B",
            rationale="Changed mind",
            approvers=["Bob"],
            decision_date=date(2026, 3, 2),
        ))
        assert result is None  # immutable once decided

    async def test_supersede(self, db_session):
        repo = DecisionRepository(db_session)
        await repo.create(_decision_create("d-1"))
        await repo.create(_decision_create("d-2"))
        superseded = await repo.supersede("d-1", superseded_by_id="d-2")
        assert superseded is not None
        assert superseded.status == DecisionStatus.SUPERSEDED

    async def test_no_delete(self, db_session):
        """Decisions have no delete method — append-only by design."""
        repo = DecisionRepository(db_session)
        assert not hasattr(repo, "delete")

    async def test_with_impacted_artifacts(self, db_session):
        repo = DecisionRepository(db_session)
        decision = DecisionCreate(
            decision_id="d-1",
            title="Choose broker",
            status=DecisionStatus.PENDING,
            impacted_artifacts=[
                ImpactedArtifact(
                    artifact_type=ArtifactType.PROJECT,
                    artifact_id="proj-1",
                    description="Execution project",
                )
            ],
        )
        created = await repo.create(decision)
        assert len(created.impacted_artifacts) == 1
        assert created.impacted_artifacts[0].artifact_type == ArtifactType.PROJECT
