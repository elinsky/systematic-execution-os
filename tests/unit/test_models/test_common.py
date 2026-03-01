"""Unit tests for sidecar/models/common.py."""

import pytest
from pydantic import ValidationError

from sidecar.models.common import (
    AsanaLinkedRecord,
    BusinessImpact,
    HealthStatus,
    Priority,
    SidecarBaseModel,
    Urgency,
)


class TestSidecarBaseModel:
    def test_extra_fields_forbidden(self):
        class Strict(SidecarBaseModel):
            name: str

        with pytest.raises(ValidationError):
            Strict(name="ok", unexpected_field="bad")

    def test_from_attributes_enabled(self):
        class SimpleModel(SidecarBaseModel):
            name: str

        class FakeOrm:
            name = "test"

        obj = SimpleModel.model_validate(FakeOrm(), from_attributes=True)
        assert obj.name == "test"

    def test_populate_by_name(self):
        class M(SidecarBaseModel):
            my_field: str

        obj = M(my_field="hello")
        assert obj.my_field == "hello"


class TestEnums:
    def test_health_status_values(self):
        assert set(HealthStatus) == {"green", "yellow", "red", "unknown"}

    def test_priority_values(self):
        assert set(Priority) == {"critical", "high", "medium", "low"}

    def test_urgency_values(self):
        assert set(Urgency) == {
            "immediate", "this_week", "this_month", "next_quarter", "backlog"
        }

    def test_business_impact_values(self):
        assert set(BusinessImpact) == {"blocker", "high", "medium", "low"}

    def test_enum_is_str(self):
        # StrEnum values should be plain strings
        assert HealthStatus.GREEN == "green"
        assert isinstance(HealthStatus.RED, str)


class TestAsanaLinkedRecord:
    def test_defaults_to_none(self):
        class Linked(AsanaLinkedRecord):
            item_id: str

        obj = Linked(item_id="x")
        assert obj.asana_gid is None
        assert obj.asana_synced_at is None
        assert obj.created_at is None
        assert obj.updated_at is None
        assert obj.archived_at is None

    def test_accepts_asana_gid(self):
        class Linked(AsanaLinkedRecord):
            item_id: str

        obj = Linked(item_id="x", asana_gid="1234567890")
        assert obj.asana_gid == "1234567890"
