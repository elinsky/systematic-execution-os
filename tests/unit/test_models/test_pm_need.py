"""Unit tests for sidecar/models/pm_need.py."""

import pytest
from datetime import date
from pydantic import ValidationError

from sidecar.models.pm_need import (
    NeedCategory,
    NeedStatus,
    PMNeed,
    PMNeedCreate,
    PMNeedUpdate,
)
from sidecar.models.common import Urgency, BusinessImpact


class TestNeedCategory:
    def test_all_categories_present(self):
        cats = set(NeedCategory)
        assert "market_data" in cats
        assert "execution" in cats
        assert "other" in cats
        assert len(cats) == 9


class TestNeedStatus:
    def test_new_is_default(self):
        need = PMNeed(
            pm_need_id="n-1",
            pm_id="pm-x",
            title="Need X",
            requested_by="PM X",
            date_raised=date(2026, 1, 15),
            category=NeedCategory.EXECUTION,
        )
        assert need.status == NeedStatus.NEW


class TestPMNeed:
    def test_minimal_valid_need(self):
        need = PMNeed(
            pm_need_id="n-1",
            pm_id="pm-jane",
            title="Jane Doe - Execution - DMA via Goldman",
            requested_by="Jane Doe",
            date_raised=date(2026, 1, 15),
            category=NeedCategory.EXECUTION,
        )
        assert need.urgency == Urgency.THIS_MONTH
        assert need.business_impact == BusinessImpact.MEDIUM
        assert need.linked_project_ids == []

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            PMNeed(pm_need_id="n-1", pm_id="pm-x")  # missing required fields

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            PMNeed(
                pm_need_id="n-1",
                pm_id="pm-x",
                title="T",
                requested_by="X",
                date_raised=date(2026, 1, 1),
                category=NeedCategory.OTHER,
                unexpected="bad",
            )

    def test_has_asana_gid_not_sync_state(self):
        need = PMNeed(
            pm_need_id="n-1",
            pm_id="pm-x",
            title="T",
            requested_by="X",
            date_raised=date(2026, 1, 1),
            category=NeedCategory.OTHER,
        )
        assert hasattr(need, "asana_gid")
        assert not hasattr(need, "sync_state")


class TestPMNeedUpdate:
    def test_status_not_writable(self):
        # D1: status is NOT in PMNeedUpdate — Asana section is canonical
        update = PMNeedUpdate(pm_need_id="n-1", urgency=Urgency.IMMEDIATE)
        assert not hasattr(update, "status")

    def test_partial_update_urgency(self):
        update = PMNeedUpdate(pm_need_id="n-1", urgency=Urgency.THIS_WEEK)
        assert update.urgency == Urgency.THIS_WEEK
        assert update.business_impact is None

    def test_partial_update_links(self):
        update = PMNeedUpdate(
            pm_need_id="n-1",
            linked_project_ids=["proj-1"],
            mapped_capability_id="cap-1",
        )
        assert update.linked_project_ids == ["proj-1"]
        assert update.mapped_capability_id == "cap-1"
