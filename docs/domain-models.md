# BAM Systematic Execution OS — Domain Models

> Document version: 1.0
> Date: 2026-03-01
> Implements: V1 minimum viable schema per vision.md

All domain models are implemented as Pydantic v2 classes in `sidecar/models/`.

---

## Design Conventions

### Model pairs

Every entity has three model variants:

| Variant | Purpose | Example |
|---|---|---|
| `Entity` | Full record (read/query) | `PMCoverageRecord` |
| `EntityCreate` | Payload for creation | `PMCoverageCreate` |
| `EntityUpdate` | Partial update payload | `PMCoverageUpdate` |

### Source-of-truth annotation

Every model's module docstring states its source of truth:
- **Sidecar** — canonical in SQLite; Asana may have a summary mirror
- **Asana** — canonical in Asana; sidecar stores `asana_gid` reference only
- **Hybrid** — operational data in Asana, relational enrichment in sidecar

### `asana_gid` field

All models that mirror Asana objects inherit from `AsanaLinkedRecord` and carry:
- `asana_gid: Optional[str]` — set to `None` before first Asana sync; non-nullable in practice once synced
- `sync_state: SyncState` — tracks sync status (SYNCED, PENDING_PUSH, PENDING_PULL, CONFLICT, ASANA_DELETED)

---

## Shared Enums (`sidecar/models/common.py`)

| Enum | Values |
|---|---|
| `HealthStatus` | green, yellow, red, unknown |
| `Priority` | critical, high, medium, low |
| `Urgency` | immediate, this_week, this_month, next_quarter, backlog |
| `BusinessImpact` | blocker, high, medium, low |
| `SyncState` | synced, pending_push, pending_pull, conflict, asana_deleted |

---

## 1. PMCoverageRecord

**File:** `sidecar/models/pm_coverage.py`
**Source of truth:** Sidecar
**Asana mirror:** Summary task in PM Coverage project

A persistent record for each PM or team being supported. This is a first-class object because much of the execution role is organized around PM-specific needs, milestones, and health signals.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `pm_id` | str | Yes | Internal ID, e.g. `pm-jane-doe` |
| `pm_name` | str | Yes | |
| `team_or_pod` | str | No | |
| `strategy_type` | str | No | e.g. `US Equities Long/Short` |
| `region` | str | No | |
| `coverage_owner` | str | No | BAM staff responsible for relationship |
| `onboarding_stage` | OnboardingStage | Yes | Default: pipeline |
| `go_live_target_date` | date | No | |
| `health_status` | HealthStatus | Yes | Default: unknown |
| `last_touchpoint_date` | date | No | |
| `linked_project_ids` | list[str] | No | FKs to Project |
| `top_open_need_ids` | list[str] | No | FKs to PMNeed |
| `top_blocker_ids` | list[str] | No | FKs to RiskBlocker |
| `asana_gid` | str | No | Set after first Asana sync |
| `notes` | str | No | |

### OnboardingStage enum

`pipeline → pre_start → requirements_discovery → onboarding_in_progress → uat → go_live_ready → live → stabilization → steady_state`

---

## 2. PMNeed

**File:** `sidecar/models/pm_need.py`
**Source of truth:** Hybrid (Asana task + sidecar metadata)
**Asana representation:** Intake task in PM Needs project

The most important routing object in the system. Every PM ask must end up mapped, prioritized, owned, and visible.

**Naming convention:** `[PM] - [Category] - [Short Need]`
Example: `Jane Doe - Execution - DMA via Goldman`

**Mandatory intake fields:** `pm_id`, `title`, `category`, `urgency`, `requested_by`, `date_raised`

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `pm_need_id` | str | Yes | Internal ID |
| `pm_id` | str | Yes | FK to PMCoverageRecord |
| `title` | str | Yes | Short clear statement |
| `category` | NeedCategory | Yes | See enum below |
| `urgency` | Urgency | Yes | Default: this_month |
| `business_impact` | BusinessImpact | Yes | Default: medium |
| `requested_by` | str | Yes | PM or leadership contact |
| `date_raised` | date | Yes | |
| `status` | NeedStatus | Yes | Default: new |
| `problem_statement` | str | No | |
| `business_rationale` | str | No | |
| `desired_by_date` | date | No | |
| `mapped_capability_id` | str | No | FK to Capability (v2) |
| `linked_project_ids` | list[str] | No | FKs to Project |
| `resolution_path` | str | No | |
| `asana_gid` | str | No | Set after Asana task creation |

### NeedCategory enum

`market_data, historical_data, alt_data, execution, broker, infra, research, ops, other`

### NeedStatus enum

`new → triaged → mapped_to_existing_capability | needs_new_project → in_progress → blocked | delivered | deferred | cancelled`

---

## 3. Project

**File:** `sidecar/models/project.py`
**Source of truth:** Asana
**Sidecar role:** Stores `asana_gid` + enrichment fields

Maps 1:1 to an Asana project.

**Naming convention:** `[Type] - [PM or Capability] - [Short Outcome]`
Example: `Onboarding - PM Jane Doe - US Equities Launch`

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `project_id` | str | Yes | Internal ID |
| `name` | str | Yes | |
| `project_type` | ProjectType | Yes | See enum below |
| `business_objective` | str | No | |
| `success_criteria` | str | No | |
| `primary_pm_ids` | list[str] | No | FKs to PMCoverageRecord |
| `owner` | str | No | |
| `status` | ProjectStatus | Yes | Default: planning |
| `priority` | Priority | Yes | Default: medium |
| `health` | HealthStatus | Yes | Default: unknown |
| `start_date` | date | No | |
| `target_date` | date | No | |
| `linked_pm_need_ids` | list[str] | No | |
| `linked_capability_ids` | list[str] | No | v2 FK stub |
| `linked_milestone_ids` | list[str] | No | |
| `linked_risk_ids` | list[str] | No | |
| `linked_decision_ids` | list[str] | No | |
| `asana_gid` | str | No | |

### ProjectType enum

`pm_onboarding, capability_build, remediation, expansion, investigation`

### ProjectStatus enum

`planning, active, on_hold, at_risk, complete, cancelled`

---

## 4. Milestone

**File:** `sidecar/models/milestone.py`
**Source of truth:** Asana (milestone task)
**Sidecar role:** Stores `asana_gid` + confidence/acceptance criteria enrichment

**Naming convention:** `[Project/PM] - [Checkpoint]`
Example: `PM Jane Doe - Go Live Ready`

### Standard Onboarding Milestones (template)

1. Kickoff
2. Requirements Confirmed
3. Market Data Ready
4. Historical Data Ready
5. Alt Data Ready
6. Execution Ready
7. UAT Complete
8. Go-Live Ready
9. PM Live
10. Stabilization Complete

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `milestone_id` | str | Yes | Internal ID |
| `project_id` | str | Yes | FK to Project |
| `name` | str | Yes | |
| `target_date` | date | No | |
| `owner` | str | No | |
| `status` | MilestoneStatus | Yes | Default: not_started |
| `confidence` | MilestoneConfidence | Yes | Default: unknown |
| `gating_conditions` | str | No | What must be true to be reachable |
| `acceptance_criteria` | str | No | What must be true to mark complete |
| `asana_gid` | str | No | |

### MilestoneStatus enum

`not_started, in_progress, at_risk, complete, missed, deferred`

### MilestoneConfidence enum

`high, medium, low, unknown`

---

## 5. Deliverable

**File:** `sidecar/models/deliverable.py`
**Source of truth:** Asana (standard task)
**Sidecar role:** `asana_gid` reference + key metadata for rollup queries

The lowest-level tracked unit. Sidecar does not replicate task descriptions or comments — only metadata needed for overdue detection and weekly review prep.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `deliverable_id` | str | Yes | Internal ID |
| `project_id` | str | Yes | FK to Project |
| `title` | str | Yes | |
| `owner` | str | No | |
| `due_date` | date | No | |
| `status` | DeliverableStatus | Yes | Default: not_started |
| `related_milestone_id` | str | No | FK to Milestone |
| `blocked_by` | list[str] | No | Other deliverable IDs this waits on |
| `last_updated` | datetime | No | |
| `asana_gid` | str | No | |

### DeliverableStatus enum

`not_started, in_progress, blocked, complete, cancelled`

---

## 6. RiskBlocker

**File:** `sidecar/models/risk.py`
**Source of truth:** Hybrid (Asana task + sidecar severity/impact metadata)
**Asana representation:** Task in Risks & Blockers project

**Naming convention:** `[Scope] - [Short Problem]`
Example: `PM Jane Doe - Historical Data Feed Delayed`

**Alert thresholds (defaults, configurable):**
- Blocker open > 7 days → escalation watch
- CRITICAL severity open > 3 days → immediate escalation flag

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `risk_id` | str | Yes | Internal ID |
| `title` | str | Yes | |
| `risk_type` | RiskType | Yes | Default: risk |
| `severity` | RiskSeverity | Yes | Default: medium |
| `status` | RiskStatus | Yes | Default: open |
| `owner` | str | No | |
| `date_opened` | date | Yes | |
| `resolution_date` | date | No | |
| `impacted_pm_ids` | list[str] | No | |
| `impacted_project_ids` | list[str] | No | |
| `impacted_milestone_ids` | list[str] | No | |
| `escalation_status` | EscalationStatus | Yes | Default: none |
| `mitigation_plan` | str | No | |
| `asana_gid` | str | No | |

### RiskType enum

`risk, blocker, issue`

### RiskSeverity enum

`critical, high, medium, low`

### EscalationStatus enum

`none, watching, escalated, resolved`

---

## 7. Decision

**File:** `sidecar/models/decision.py`
**Source of truth:** Sidecar-only
**Asana representation:** None (decisions need searchable history)

**Design rule:** Append-only. Decisions are never deleted — only superseded. Set `status=superseded` and `superseded_by_id` to link to the replacement decision.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `decision_id` | str | Yes | Internal ID |
| `title` | str | Yes | |
| `status` | DecisionStatus | Yes | Default: pending |
| `context` | str | No | Background and situation |
| `options_considered` | str | No | Alternatives evaluated |
| `chosen_path` | str | No | Selected option |
| `rationale` | str | No | Why this option was chosen |
| `approvers` | list[str] | No | Names/IDs of approvers |
| `decision_date` | date | No | |
| `superseded_by_id` | str | No | FK to replacement Decision |
| `impacted_artifacts` | list[ImpactedArtifact] | No | See sub-schema below |
| `created_at` | date | No | |

### ImpactedArtifact sub-schema

| Field | Type | Notes |
|---|---|---|
| `artifact_type` | ArtifactType | pm, project, milestone, pm_need, capability, risk |
| `artifact_id` | str | |
| `description` | str | Optional context |

### DecisionStatus enum

`pending, decided, superseded, deferred`

---

## 8. StatusUpdate

**File:** `sidecar/models/status_update.py`
**Source of truth:** Asana (project-level); Sidecar (PM-level and initiative-level rollups)

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `status_update_id` | str | Yes | Internal ID |
| `scope_type` | StatusScopeType | Yes | project, pm, or initiative |
| `scope_id` | str | Yes | ID of the PM, project, or initiative |
| `overall_status` | HealthStatus | Yes | Default: unknown |
| `what_changed_this_period` | str | No | |
| `next_key_milestones` | str | No | |
| `top_blockers` | str | No | |
| `decisions_needed` | str | No | |
| `confidence` | str | No | Free text or percentage |
| `updated_by` | str | No | |
| `updated_at` | datetime | No | |
| `asana_gid` | str | No | Set for project-level updates |

---

## 9. Capability (V2 Stub)

**File:** `sidecar/models/capability.py`
**Source of truth:** Sidecar
**Status:** Deferred to V2. Included as a stub to prevent breaking migrations.

The `capability_id` FK field is included as nullable in `PMNeed` and `Project` models so that v2 capability work does not require schema changes to those tables.

---

## Entity Relationship Summary

```
PMCoverageRecord
    ├── has many PMNeed            (pm_id FK)
    ├── has many Project           (primary_pm_ids FK)
    └── has many RiskBlocker       (impacted_pm_ids FK)

Project
    ├── belongs to PMCoverageRecord (primary_pm_ids)
    ├── linked to PMNeed            (linked_pm_need_ids)
    ├── has many Milestone          (project_id FK)
    ├── has many Deliverable        (project_id FK)
    ├── has many RiskBlocker        (impacted_project_ids FK)
    └── has many Decision           (impacted_artifacts FK)

Milestone
    ├── belongs to Project          (project_id FK)
    ├── has many Deliverable        (related_milestone_id FK)
    └── referenced by RiskBlocker   (impacted_milestone_ids FK)

Decision
    └── references any artifact     (impacted_artifacts polymorphic)
```
