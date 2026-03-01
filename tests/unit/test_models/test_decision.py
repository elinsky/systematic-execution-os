"""Unit tests for sidecar/models/decision.py."""

import pytest
from datetime import date
from pydantic import ValidationError

from sidecar.models.decision import (
    ArtifactType,
    Decision,
    DecisionCreate,
    DecisionResolve,
    DecisionStatus,
    ImpactedArtifact,
)


class TestDecision:
    def test_minimal_valid_decision(self):
        d = Decision(decision_id="d-1", title="Choose broker A over B")
        assert d.status == DecisionStatus.PENDING
        assert d.approvers == []
        assert d.impacted_artifacts == []
        assert d.superseded_by_id is None

    def test_full_decision(self):
        d = Decision(
            decision_id="d-1",
            title="Choose broker A over B",
            context="Need DMA for PM Jane",
            options_considered="Broker A, Broker B, Broker C",
            chosen_path="Broker A",
            rationale="Better latency, existing relationship",
            approvers=["Alice", "Bob"],
            decision_date=date(2026, 2, 15),
            status=DecisionStatus.DECIDED,
            impacted_artifacts=[
                ImpactedArtifact(
                    artifact_type=ArtifactType.PM,
                    artifact_id="pm-jane",
                    description="Needed for execution",
                )
            ],
        )
        assert d.status == DecisionStatus.DECIDED
        assert len(d.impacted_artifacts) == 1
        assert d.impacted_artifacts[0].artifact_type == ArtifactType.PM

    def test_superseded_by_id(self):
        # D3: to revise a decided decision, create new and set superseded_by_id on old
        d = Decision(
            decision_id="d-1",
            title="Old decision",
            status=DecisionStatus.SUPERSEDED,
            superseded_by_id="d-2",
        )
        assert d.superseded_by_id == "d-2"

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            Decision(decision_id="d-1", title="T", bad_field="x")

    def test_is_sidecar_only_no_asana_gid(self):
        # Decisions are sidecar-only — no asana_gid field
        d = Decision(decision_id="d-1", title="T")
        assert not hasattr(d, "asana_gid")


class TestDecisionResolve:
    def test_resolve_requires_all_fields(self):
        resolve = DecisionResolve(
            decision_id="d-1",
            chosen_path="Broker A",
            rationale="Best fit",
            approvers=["Alice"],
            decision_date=date(2026, 3, 1),
        )
        assert resolve.chosen_path == "Broker A"
        assert resolve.decision_date == date(2026, 3, 1)

    def test_resolve_missing_required_fields(self):
        with pytest.raises(ValidationError):
            DecisionResolve(
                decision_id="d-1",
                chosen_path="Broker A",
                # missing rationale, approvers, decision_date
            )


class TestImpactedArtifact:
    def test_all_artifact_types(self):
        types = set(ArtifactType)
        assert "pm" in types
        assert "project" in types
        assert "milestone" in types
        assert "pm_need" in types
        assert "capability" in types
        assert "risk" in types

    def test_optional_description(self):
        artifact = ImpactedArtifact(artifact_type=ArtifactType.PROJECT, artifact_id="proj-1")
        assert artifact.description is None
