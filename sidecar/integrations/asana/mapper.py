"""Asana API payload ↔ domain model translation layer.

Each ``from_asana_*`` method accepts a raw Asana API dict (already unwrapped
from the ``data`` envelope) and returns the corresponding domain model.

Each ``to_asana_*`` method accepts a domain model or create/update schema and
returns the dict to send as the Asana request body.

Custom field values are resolved by GID using the ``AsanaFieldConfig`` passed
at construction time. This keeps the mapper free of environment-specific magic
strings and testable with any config fixture.

Source-of-truth rules enforced here:
- PM Need ``status`` is read-only in the sidecar (driven by Asana section).
  The mapper sets it from the task's section name; callers must not override it.
- PM Coverage ``onboarding_stage`` and ``health_status`` are written by Asana
  (Kanban drag); the mapper reads them from custom fields.
- Risk ``age_days`` is computed on read, not stored in Asana.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sidecar.models import (
    HealthStatus,
    MilestoneConfidence,
    MilestoneStatus,
    NeedCategory,
    NeedStatus,
    OnboardingStage,
    PMCoverageRecord,
    PMNeed,
    Priority,
    Project,
    ProjectStatus,
    ProjectType,
    Milestone,
    RiskBlocker,
    RiskSeverity,
    RiskStatus,
    RiskType,
    EscalationStatus,
    Urgency,
    BusinessImpact,
)


# ---------------------------------------------------------------------------
# Config dataclass — maps field names to Asana custom field GIDs
# ---------------------------------------------------------------------------

class AsanaFieldConfig:
    """Holds Asana custom field GIDs loaded from settings.

    GIDs are strings like "1234567890123456". All fields are optional (None)
    so the mapper degrades gracefully if a field hasn't been configured yet.
    """

    def __init__(
        self,
        # PM Coverage Board custom fields
        onboarding_stage_gid: str | None = None,
        health_gid: str | None = None,
        region_gid: str | None = None,
        last_touchpoint_gid: str | None = None,
        # PM Needs custom fields
        need_category_gid: str | None = None,
        urgency_gid: str | None = None,
        business_impact_gid: str | None = None,
        need_status_gid: str | None = None,
        resolution_path_gid: str | None = None,
        # Project custom fields
        project_type_gid: str | None = None,
        priority_gid: str | None = None,
        project_health_gid: str | None = None,
        # Milestone custom fields
        milestone_status_gid: str | None = None,
        milestone_confidence_gid: str | None = None,
        # Risk custom fields
        risk_type_gid: str | None = None,
        severity_gid: str | None = None,
        escalation_status_gid: str | None = None,
        risk_status_gid: str | None = None,
        # Singleton project GIDs
        pm_coverage_project_gid: str | None = None,
        pm_needs_project_gid: str | None = None,
        risks_project_gid: str | None = None,
    ) -> None:
        self.onboarding_stage_gid = onboarding_stage_gid
        self.health_gid = health_gid
        self.region_gid = region_gid
        self.last_touchpoint_gid = last_touchpoint_gid
        self.need_category_gid = need_category_gid
        self.urgency_gid = urgency_gid
        self.business_impact_gid = business_impact_gid
        self.need_status_gid = need_status_gid
        self.resolution_path_gid = resolution_path_gid
        self.project_type_gid = project_type_gid
        self.priority_gid = priority_gid
        self.project_health_gid = project_health_gid
        self.milestone_status_gid = milestone_status_gid
        self.milestone_confidence_gid = milestone_confidence_gid
        self.risk_type_gid = risk_type_gid
        self.severity_gid = severity_gid
        self.escalation_status_gid = escalation_status_gid
        self.risk_status_gid = risk_status_gid
        self.pm_coverage_project_gid = pm_coverage_project_gid
        self.pm_needs_project_gid = pm_needs_project_gid
        self.risks_project_gid = risks_project_gid


# ---------------------------------------------------------------------------
# Mapper
# ---------------------------------------------------------------------------

class AsanaMapper:
    """Translates between raw Asana API dicts and sidecar domain models.

    All ``from_asana_*`` methods are pure functions of the input dict and the
    field config. They never call the Asana API.
    """

    def __init__(self, field_config: AsanaFieldConfig) -> None:
        self._cfg = field_config

    # ------------------------------------------------------------------
    # PM Coverage Record
    # ------------------------------------------------------------------

    def from_asana_pm_coverage(
        self,
        task: dict[str, Any],
        pm_id: str,
    ) -> PMCoverageRecord:
        """Build a PMCoverageRecord from an Asana task in the PM Coverage Board."""
        fields = self._index_custom_fields(task)
        section_name = self._task_section_name(task)

        return PMCoverageRecord(
            pm_id=pm_id,
            pm_name=task.get("name", ""),
            onboarding_stage=self._stage_from_section(section_name),
            health_status=self._enum_from_field(
                fields, self._cfg.health_gid, HealthStatus, HealthStatus.UNKNOWN
            ),
            region=self._text_from_field(fields, self._cfg.region_gid),
            last_touchpoint_date=self._date_from_field(fields, self._cfg.last_touchpoint_gid),
            coverage_owner=self._assignee_name(task),
            asana_gid=task.get("gid"),
            asana_synced_at=datetime.utcnow(),
        )

    def to_asana_pm_coverage(
        self,
        pm_name: str,
        coverage_owner_gid: str | None,
        go_live_target_date: date | None,
        project_gid: str,
    ) -> dict[str, Any]:
        """Build the Asana task body for a new PM Coverage task."""
        body: dict[str, Any] = {
            "name": pm_name,
            "projects": [project_gid],
        }
        if coverage_owner_gid:
            body["assignee"] = coverage_owner_gid
        if go_live_target_date:
            body["due_on"] = go_live_target_date.isoformat()
        return body

    # ------------------------------------------------------------------
    # PM Need
    # ------------------------------------------------------------------

    def from_asana_pm_need(
        self,
        task: dict[str, Any],
        pm_need_id: str,
        pm_id: str,
    ) -> PMNeed:
        """Build a PMNeed from an Asana task in the PM Needs project."""
        fields = self._index_custom_fields(task)
        section_name = self._task_section_name(task)

        return PMNeed(
            pm_need_id=pm_need_id,
            pm_id=pm_id,
            title=task.get("name", ""),
            requested_by=self._assignee_name(task) or "",
            date_raised=self._parse_date(task.get("created_at", "")) or date.today(),
            category=self._enum_from_field(
                fields, self._cfg.need_category_gid, NeedCategory, NeedCategory.OTHER
            ),
            urgency=self._enum_from_field(
                fields, self._cfg.urgency_gid, Urgency, Urgency.THIS_MONTH
            ),
            business_impact=self._enum_from_field(
                fields, self._cfg.business_impact_gid, BusinessImpact, BusinessImpact.MEDIUM
            ),
            status=self._need_status_from_section(section_name),
            desired_by_date=self._parse_date(task.get("due_on")),
            notes=task.get("notes") or None,
            asana_gid=task.get("gid"),
            asana_synced_at=datetime.utcnow(),
        )

    def to_asana_pm_need(
        self,
        title: str,
        category: NeedCategory,
        urgency: Urgency,
        business_impact: BusinessImpact,
        desired_by_date: date | None,
        project_gid: str,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Build the Asana task body for a new PM Need."""
        body: dict[str, Any] = {
            "name": title,
            "projects": [project_gid],
        }
        if desired_by_date:
            body["due_on"] = desired_by_date.isoformat()
        if notes:
            body["notes"] = notes

        custom_fields: dict[str, str] = {}
        if self._cfg.need_category_gid:
            custom_fields[self._cfg.need_category_gid] = category.value
        if self._cfg.urgency_gid:
            custom_fields[self._cfg.urgency_gid] = urgency.value
        if self._cfg.business_impact_gid:
            custom_fields[self._cfg.business_impact_gid] = business_impact.value
        if custom_fields:
            body["custom_fields"] = custom_fields

        return body

    # ------------------------------------------------------------------
    # Project
    # ------------------------------------------------------------------

    def from_asana_project(
        self,
        project: dict[str, Any],
        project_id: str,
    ) -> Project:
        """Build a Project from an Asana project dict."""
        fields = self._index_custom_fields(project)
        current_status = project.get("current_status") or {}

        return Project(
            project_id=project_id,
            name=project.get("name", ""),
            project_type=self._enum_from_field(
                fields, self._cfg.project_type_gid, ProjectType, ProjectType.INVESTIGATION
            ),
            owner=self._owner_name(project),
            status=self._project_status_from_asana(current_status),
            priority=self._enum_from_field(
                fields, self._cfg.priority_gid, Priority, Priority.MEDIUM
            ),
            health=self._health_from_status(current_status),
            start_date=self._parse_date(project.get("start_on")),
            target_date=self._parse_date(project.get("due_on")),
            asana_gid=project.get("gid"),
            asana_synced_at=datetime.utcnow(),
        )

    def to_asana_project(
        self,
        name: str,
        project_type: ProjectType,
        workspace_gid: str,
        team_gid: str | None = None,
        owner_gid: str | None = None,
        start_date: date | None = None,
        target_date: date | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Build the Asana project body for project creation."""
        body: dict[str, Any] = {
            "name": name,
            "workspace": workspace_gid,
        }
        if team_gid:
            body["team"] = team_gid
        if owner_gid:
            body["owner"] = owner_gid
        if start_date:
            body["start_on"] = start_date.isoformat()
        if target_date:
            body["due_on"] = target_date.isoformat()
        if notes:
            body["notes"] = notes

        custom_fields: dict[str, str] = {}
        if self._cfg.project_type_gid:
            custom_fields[self._cfg.project_type_gid] = project_type.value
        if custom_fields:
            body["custom_fields"] = custom_fields

        return body

    # ------------------------------------------------------------------
    # Milestone
    # ------------------------------------------------------------------

    def from_asana_milestone(
        self,
        task: dict[str, Any],
        milestone_id: str,
        project_id: str,
    ) -> Milestone:
        """Build a Milestone from an Asana milestone task dict."""
        fields = self._index_custom_fields(task)
        completed = task.get("completed", False)

        return Milestone(
            milestone_id=milestone_id,
            project_id=project_id,
            name=task.get("name", ""),
            target_date=self._parse_date(task.get("due_on")),
            owner=self._assignee_name(task),
            status=self._milestone_status(fields, completed),
            confidence=self._enum_from_field(
                fields,
                self._cfg.milestone_confidence_gid,
                MilestoneConfidence,
                MilestoneConfidence.UNKNOWN,
            ),
            acceptance_criteria=task.get("notes") or None,
            asana_gid=task.get("gid"),
            asana_synced_at=datetime.utcnow(),
        )

    def to_asana_milestone(
        self,
        name: str,
        project_gid: str,
        target_date: date | None,
        owner_gid: str | None = None,
        acceptance_criteria: str | None = None,
    ) -> dict[str, Any]:
        """Build the Asana task body for a milestone task."""
        body: dict[str, Any] = {
            "name": name,
            "resource_subtype": "milestone",
            "projects": [project_gid],
        }
        if target_date:
            body["due_on"] = target_date.isoformat()
        if owner_gid:
            body["assignee"] = owner_gid
        if acceptance_criteria:
            body["notes"] = acceptance_criteria
        return body

    # ------------------------------------------------------------------
    # Risk / Blocker
    # ------------------------------------------------------------------

    def from_asana_risk(
        self,
        task: dict[str, Any],
        risk_id: str,
    ) -> RiskBlocker:
        """Build a RiskBlocker from an Asana task in the Risks & Blockers project."""
        fields = self._index_custom_fields(task)
        completed = task.get("completed", False)

        return RiskBlocker(
            risk_id=risk_id,
            title=task.get("name", ""),
            risk_type=self._enum_from_field(
                fields, self._cfg.risk_type_gid, RiskType, RiskType.RISK
            ),
            severity=self._enum_from_field(
                fields, self._cfg.severity_gid, RiskSeverity, RiskSeverity.MEDIUM
            ),
            status=RiskStatus.RESOLVED if completed else self._enum_from_field(
                fields, self._cfg.risk_status_gid, RiskStatus, RiskStatus.OPEN
            ),
            escalation_status=self._enum_from_field(
                fields, self._cfg.escalation_status_gid, EscalationStatus, EscalationStatus.NONE
            ),
            mitigation_plan=task.get("notes") or None,
            date_opened=self._parse_date(task.get("created_at", "")) or date.today(),
            resolution_date=self._parse_date(task.get("completed_at")) if completed else None,
            asana_gid=task.get("gid"),
            asana_synced_at=datetime.utcnow(),
        )

    def to_asana_risk(
        self,
        title: str,
        risk_type: RiskType,
        severity: RiskSeverity,
        project_gid: str,
        mitigation_plan: str | None = None,
        owner_gid: str | None = None,
    ) -> dict[str, Any]:
        """Build the Asana task body for a new Risk/Blocker."""
        body: dict[str, Any] = {
            "name": title,
            "projects": [project_gid],
        }
        if owner_gid:
            body["assignee"] = owner_gid
        if mitigation_plan:
            body["notes"] = mitigation_plan

        custom_fields: dict[str, str] = {}
        if self._cfg.risk_type_gid:
            custom_fields[self._cfg.risk_type_gid] = risk_type.value
        if self._cfg.severity_gid:
            custom_fields[self._cfg.severity_gid] = severity.value
        if custom_fields:
            body["custom_fields"] = custom_fields

        return body

    # ------------------------------------------------------------------
    # Custom field helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _index_custom_fields(obj: dict[str, Any]) -> dict[str, Any]:
        """Return {gid: custom_field_dict} index for quick lookup."""
        result: dict[str, Any] = {}
        for cf in obj.get("custom_fields") or []:
            gid = cf.get("gid")
            if gid:
                result[gid] = cf
        return result

    @staticmethod
    def _enum_from_field(
        fields: dict[str, Any],
        gid: str | None,
        enum_cls: type,
        default: Any,
    ) -> Any:
        """Extract an enum value from an Asana custom field dict."""
        if not gid or gid not in fields:
            return default
        cf = fields[gid]
        # Enum fields: value is under enum_value.name (display) — we use name as value
        enum_val = cf.get("enum_value")
        if enum_val:
            raw = enum_val.get("name", "").lower().replace(" ", "_")
            try:
                return enum_cls(raw)
            except ValueError:
                pass
        # Text fields used as enum (fallback)
        raw = cf.get("text_value", "")
        if raw:
            try:
                return enum_cls(raw.lower().replace(" ", "_"))
            except ValueError:
                pass
        return default

    @staticmethod
    def _text_from_field(fields: dict[str, Any], gid: str | None) -> str | None:
        if not gid or gid not in fields:
            return None
        return fields[gid].get("text_value") or None

    @staticmethod
    def _date_from_field(fields: dict[str, Any], gid: str | None) -> date | None:
        if not gid or gid not in fields:
            return None
        raw = fields[gid].get("date_value", {}) or {}
        date_str = raw.get("date") or fields[gid].get("text_value") or ""
        return AsanaMapper._parse_date(date_str)

    @staticmethod
    def _parse_date(raw: str | None) -> date | None:
        if not raw:
            return None
        try:
            # ISO 8601 date "YYYY-MM-DD"
            if len(raw) == 10:
                return date.fromisoformat(raw)
            # ISO 8601 datetime "YYYY-MM-DDTHH:MM:SS.000Z"
            return datetime.fromisoformat(raw.rstrip("Z")).date()
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _assignee_name(task: dict[str, Any]) -> str | None:
        assignee = task.get("assignee") or {}
        return assignee.get("name") or None

    @staticmethod
    def _owner_name(project: dict[str, Any]) -> str | None:
        owner = project.get("owner") or {}
        return owner.get("name") or None

    @staticmethod
    def _task_section_name(task: dict[str, Any]) -> str:
        """Return the section name from the task's memberships."""
        for membership in task.get("memberships") or []:
            section = membership.get("section") or {}
            name = section.get("name", "")
            if name:
                return name
        return ""

    # ------------------------------------------------------------------
    # Domain-specific status derivations
    # ------------------------------------------------------------------

    _SECTION_TO_STAGE: dict[str, OnboardingStage] = {
        "pipeline": OnboardingStage.PIPELINE,
        "pre-start": OnboardingStage.PRE_START,
        "pre_start": OnboardingStage.PRE_START,
        "requirements discovery": OnboardingStage.REQUIREMENTS_DISCOVERY,
        "requirements_discovery": OnboardingStage.REQUIREMENTS_DISCOVERY,
        "onboarding in progress": OnboardingStage.ONBOARDING_IN_PROGRESS,
        "onboarding_in_progress": OnboardingStage.ONBOARDING_IN_PROGRESS,
        "uat": OnboardingStage.UAT,
        "go live ready": OnboardingStage.GO_LIVE_READY,
        "go_live_ready": OnboardingStage.GO_LIVE_READY,
        "live": OnboardingStage.LIVE,
        "stabilization": OnboardingStage.STABILIZATION,
        "steady state": OnboardingStage.STEADY_STATE,
        "steady_state": OnboardingStage.STEADY_STATE,
    }

    def _stage_from_section(self, section_name: str) -> OnboardingStage:
        return self._SECTION_TO_STAGE.get(
            section_name.lower().strip(), OnboardingStage.PIPELINE
        )

    _SECTION_TO_NEED_STATUS: dict[str, NeedStatus] = {
        "new": NeedStatus.NEW,
        "triaged": NeedStatus.TRIAGED,
        "mapped to existing capability": NeedStatus.MAPPED_TO_EXISTING_CAPABILITY,
        "mapped to existing": NeedStatus.MAPPED_TO_EXISTING_CAPABILITY,
        "needs new project": NeedStatus.NEEDS_NEW_PROJECT,
        "in progress": NeedStatus.IN_PROGRESS,
        "blocked": NeedStatus.BLOCKED,
        "delivered": NeedStatus.DELIVERED,
        "deferred": NeedStatus.DEFERRED,
        "cancelled": NeedStatus.CANCELLED,
    }

    def _need_status_from_section(self, section_name: str) -> NeedStatus:
        return self._SECTION_TO_NEED_STATUS.get(
            section_name.lower().strip(), NeedStatus.NEW
        )

    @staticmethod
    def _project_status_from_asana(current_status: dict[str, Any]) -> ProjectStatus:
        color = current_status.get("color", "")
        text = (current_status.get("title") or "").lower()
        if "complete" in text or "done" in text:
            return ProjectStatus.COMPLETE
        if "cancelled" in text or "canceled" in text:
            return ProjectStatus.CANCELLED
        if color == "red":
            return ProjectStatus.AT_RISK
        if color in ("yellow", "green"):
            return ProjectStatus.ACTIVE
        return ProjectStatus.PLANNING

    @staticmethod
    def _health_from_status(current_status: dict[str, Any]) -> HealthStatus:
        color = current_status.get("color", "")
        return {
            "green": HealthStatus.GREEN,
            "yellow": HealthStatus.YELLOW,
            "red": HealthStatus.RED,
        }.get(color, HealthStatus.UNKNOWN)

    def _milestone_status(
        self,
        fields: dict[str, Any],
        completed: bool,
    ) -> MilestoneStatus:
        if completed:
            return MilestoneStatus.COMPLETE
        return self._enum_from_field(
            fields,
            self._cfg.milestone_status_gid,
            MilestoneStatus,
            MilestoneStatus.NOT_STARTED,
        )
