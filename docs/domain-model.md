# BAM Systematic Execution OS — Domain Model Reference

**Version:** 1.1
**Date:** 2026-03-01
**Status:** Final — reflects post-review corrections from `design-decisions.md`

All domain models are implemented as Pydantic v2 classes in `sidecar/models/`. This document is the authoritative schema reference. Changes to model fields must be reflected here.

---

## Table of Contents

1. [Design Conventions](#1-design-conventions)
2. [Shared Types — `common.py`](#2-shared-types--commonpy)
3. [PMCoverageRecord — `pm_coverage.py`](#3-pmcoveragerecord--pm_coveragepy)
4. [PMNeed — `pm_need.py`](#4-pmneed--pm_needpy)
5. [Project — `project.py`](#5-project--projectpy)
6. [Milestone — `milestone.py`](#6-milestone--milestonepy)
7. [Deliverable — `deliverable.py`](#7-deliverable--deliverablepy)
8. [RiskBlocker — `risk.py`](#8-riskblocker--riskpy)
9. [Decision — `decision.py`](#9-decision--decisionpy)
10. [StatusUpdate — `status_update.py`](#10-statusupdate--status_updatepy)
11. [Capability — `capability.py` (v2 stub)](#11-capability--capabilitypy-v2-stub)
12. [Entity Relationship Summary](#12-entity-relationship-summary)
13. [State Machines](#13-state-machines)

---

## 1. Design Conventions

### Model triads

Every entity has three model variants:

| Variant | Purpose | Example |
|---------|---------|---------|
| `Entity` | Full record (read/query) | `PMCoverageRecord` |
| `EntityCreate` | Creation payload | `PMCoverageCreate` |
| `EntityUpdate` | Partial update payload | `PMCoverageUpdate` |

### Source-of-truth annotation

Every model module declares its source of truth in its module docstring:

| Source | Meaning |
|--------|---------|
| **Sidecar** | Canonical in sidecar SQLite; Asana may have a summary mirror |
| **Asana** | Canonical in Asana; sidecar stores `asana_gid` reference only |
| **Hybrid** | Operational data in Asana; relational enrichment in sidecar |

### `AsanaLinkedRecord` base class

All models that mirror Asana objects inherit from `AsanaLinkedRecord` and carry:

```python
asana_gid: Optional[str]         # Set after first Asana sync; non-nullable in practice
asana_synced_at: Optional[datetime]  # Timestamp of last successful sync
created_at: Optional[datetime]
updated_at: Optional[datetime]
archived_at: Optional[datetime]
```

`SyncState` enum (pending_push/pull/conflict) is deferred to v2. V1 uses `asana_gid` + `asana_synced_at` only. See `design-decisions.md D6`.

### `extra = "forbid"`

All models use `extra="forbid"` to catch schema drift at validation time. Unrecognized fields raise a validation error immediately.

---

## 2. Shared Types — `common.py`

**File:** `sidecar/models/common.py`

### Enums

| Enum | Values |
|------|--------|
| `HealthStatus` | `green`, `yellow`, `red`, `unknown` |
| `Priority` | `critical`, `high`, `medium`, `low` |
| `Urgency` | `immediate`, `this_week`, `this_month`, `next_quarter`, `backlog` |
| `BusinessImpact` | `blocker`, `high`, `medium`, `low` |

### Base classes

| Class | Purpose |
|-------|---------|
| `SidecarBaseModel` | Root Pydantic base; extra=forbid, from_attributes=True, populate_by_name=True |
| `AsanaLinkedRecord` | Adds `asana_gid`, `asana_synced_at`, `created_at`, `updated_at`, `archived_at` |

---

## 3. PMCoverageRecord — `pm_coverage.py`

**Source of truth:** Sidecar
**Asana mirror:** Summary task in the PM Coverage tracking project (Kanban board)

A persistent record for each PM or team being supported. This is the highest-priority object in the system — all other entities link back to it.

**Write path (per `design-decisions.md D2`):**
- `onboarding_stage` and `health_status` are written by operators moving Kanban cards in Asana. Webhook syncs these fields to sidecar.
- All other fields are writable via the sidecar API (`PATCH /pm-coverage/{pm_id}`).

### `OnboardingStage` enum

```
pipeline → pre_start → requirements_discovery → onboarding_in_progress
  → uat → go_live_ready → live → stabilization → steady_state
```

Allowed backwards transitions: `uat → onboarding_in_progress`, `go_live_ready → onboarding_in_progress`.
Enforced by `validate_onboarding_transition()` in `pm_coverage_service.py`.

### Fields — `PMCoverageRecord`

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `pm_id` | str | Yes | — | Internal ID, e.g. `pm-jane-doe` |
| `pm_name` | str | Yes | — | |
| `team_or_pod` | Optional[str] | No | None | |
| `strategy_type` | Optional[str] | No | None | e.g. `US Equities Long/Short` |
| `region` | Optional[str] | No | None | |
| `coverage_owner` | Optional[str] | No | None | BAM Systematic staff responsible for this PM |
| `onboarding_stage` | OnboardingStage | Yes | `pipeline` | Write via Asana Kanban; sidecar mirrors |
| `go_live_target_date` | Optional[date] | No | None | |
| `health_status` | HealthStatus | Yes | `unknown` | Write via Asana Kanban; sidecar mirrors |
| `last_touchpoint_date` | Optional[date] | No | None | Update after every PM meeting |
| `notes` | Optional[str] | No | None | |
| `linked_project_ids` | list[str] | No | `[]` | FKs to `Project.project_id` |
| `asana_gid` | Optional[str] | No | None | Set after first Asana sync |
| `asana_synced_at` | Optional[datetime] | No | None | |

**Note:** `top_open_need_ids` and `top_blocker_ids` are NOT stored on this model. They are computed on read by querying `PMNeed` and `RiskBlocker` tables filtered by `pm_id`. See `design-decisions.md D5`.

### Fields — `PMCoverageCreate`

Requires: `pm_id`, `pm_name`. All other fields are optional at creation.

### Fields — `PMCoverageUpdate`

Writable via sidecar API: `onboarding_stage`, `health_status`, `go_live_target_date`, `coverage_owner`, `last_touchpoint_date`, `notes`.

---

## 4. PMNeed — `pm_need.py`

**Source of truth:** Hybrid
**Asana:** Intake task in PM Needs project (operational store)
**Sidecar:** Relational metadata, links to capabilities/projects, routing state

The most important routing object in the system. Every PM ask must end up mapped, prioritized, owned, and visible.

**Naming convention:** `[PM] - [Category] - [Short Need]`
Example: `Jane Doe - Execution - DMA via Goldman`

**Mandatory intake fields:** `pm_id`, `title`, `category`, `urgency`, `requested_by`, `date_raised`

**Status write path (per `design-decisions.md D1`):** `NeedStatus` on the sidecar is a read-only cache. The canonical source for status is the Asana task's section (Kanban column). The `status` field is excluded from `PMNeedUpdate`. To change a need's status, move the Asana task to the corresponding section; the webhook syncs the change to sidecar.

### `NeedCategory` enum

`market_data`, `historical_data`, `alt_data`, `execution`, `broker`, `infra`, `research`, `ops`, `other`

### `NeedStatus` enum

```
new → triaged → mapped_to_existing_capability
              → needs_new_project → in_progress → blocked → in_progress
                                               → delivered
                                               → deferred
                                               → cancelled
```

### Fields — `PMNeed`

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `pm_need_id` | str | Yes | — | Internal ID |
| `pm_id` | str | Yes | — | FK to `PMCoverageRecord.pm_id` |
| `title` | str | Yes | — | Follow naming convention |
| `problem_statement` | Optional[str] | No | None | |
| `business_rationale` | Optional[str] | No | None | Minimum one sentence |
| `requested_by` | str | Yes | — | Name of PM or leadership contact |
| `date_raised` | date | Yes | — | |
| `category` | NeedCategory | Yes | — | |
| `urgency` | Urgency | Yes | `this_month` | |
| `business_impact` | BusinessImpact | Yes | `medium` | |
| `desired_by_date` | Optional[date] | No | None | |
| `status` | NeedStatus | — | `new` | Read-only in sidecar API; Asana section is canonical |
| `mapped_capability_id` | Optional[str] | No | None | FK to Capability (v2) |
| `linked_project_ids` | list[str] | No | `[]` | |
| `resolution_path` | Optional[str] | No | None | |
| `notes` | Optional[str] | No | None | |

### Fields — `PMNeedUpdate`

Writable via sidecar API: `urgency`, `business_impact`, `mapped_capability_id`, `linked_project_ids`, `resolution_path`, `notes`.
**`status` is explicitly excluded** — change status by moving the Asana card.

---

## 5. Project — `project.py`

**Source of truth:** Asana
**Sidecar role:** Stores `asana_gid` + enrichment fields (linked PM needs, capabilities, health rollup)

Maps 1:1 to an Asana project.

**Naming convention:** `[Type] - [PM or Capability] - [Short Outcome]`
Example: `Onboarding - PM Jane Doe - US Equities Launch`

### `ProjectType` enum

`pm_onboarding`, `capability_build`, `remediation`, `expansion`, `investigation`

### `ProjectStatus` enum

`planning`, `active`, `on_hold`, `at_risk`, `complete`, `cancelled`

### Fields — `Project`

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `project_id` | str | Yes | — | Internal ID |
| `name` | str | Yes | — | Follow naming convention |
| `project_type` | ProjectType | Yes | — | |
| `business_objective` | Optional[str] | No | None | |
| `success_criteria` | Optional[str] | No | None | |
| `primary_pm_ids` | list[str] | No | `[]` | FKs to `PMCoverageRecord.pm_id` |
| `owner` | Optional[str] | No | None | Single named owner |
| `status` | ProjectStatus | Yes | `planning` | |
| `priority` | Priority | Yes | `medium` | |
| `health` | HealthStatus | Yes | `unknown` | |
| `start_date` | Optional[date] | No | None | |
| `target_date` | Optional[date] | No | None | |
| `linked_pm_need_ids` | list[str] | No | `[]` | |
| `linked_capability_ids` | list[str] | No | `[]` | v2 FK stub |
| `linked_milestone_ids` | list[str] | No | `[]` | |
| `linked_risk_ids` | list[str] | No | `[]` | |
| `linked_decision_ids` | list[str] | No | `[]` | |

### Fields — `ProjectUpdate`

Writable: `status`, `health`, `priority`, `owner`, `target_date`, `success_criteria`.

---

## 6. Milestone — `milestone.py`

**Source of truth:** Asana (milestone task)
**Sidecar role:** Stores `asana_gid` + confidence and acceptance criteria enrichment

**Naming convention:** `[PM or Project] - [Checkpoint]`
Example: `PM Jane Doe - Go Live Ready`

### Standard Onboarding Milestones

Defined in `STANDARD_ONBOARDING_MILESTONES` (used when instantiating onboarding templates):

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

### `MilestoneStatus` enum

`not_started`, `in_progress`, `at_risk`, `complete`, `missed`, `deferred`

### `MilestoneConfidence` enum

`high`, `medium`, `low`, `unknown`

### Fields — `Milestone`

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `milestone_id` | str | Yes | — | Internal ID |
| `project_id` | str | Yes | — | FK to `Project.project_id` |
| `name` | str | Yes | — | Follow naming convention |
| `target_date` | Optional[date] | No | None | |
| `owner` | Optional[str] | No | None | Single named owner |
| `status` | MilestoneStatus | Yes | `not_started` | |
| `confidence` | MilestoneConfidence | Yes | `unknown` | |
| `gating_conditions` | Optional[str] | No | None | What must be true to be reachable |
| `acceptance_criteria` | Optional[str] | No | None | What must be true to close |
| `notes` | Optional[str] | No | None | |

**Gate rule:** A milestone cannot move to `complete` without `acceptance_criteria` confirmed. Enforced in `milestone_service.py`.

### Fields — `MilestoneUpdate`

Writable: `status`, `confidence`, `target_date`, `owner`, `acceptance_criteria`, `notes`.

---

## 7. Deliverable — `deliverable.py`

**Source of truth:** Asana (standard task)
**Sidecar role:** `asana_gid` reference + key metadata for rollup queries only

The sidecar does NOT replicate task descriptions, comments, or subtask details. Only fields needed for overdue detection and weekly review prep are stored.

### `DeliverableStatus` enum

`not_started`, `in_progress`, `blocked`, `complete`, `cancelled`

### Fields — `Deliverable`

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `deliverable_id` | str | Yes | — | Internal ID |
| `project_id` | str | Yes | — | FK to `Project.project_id` |
| `title` | str | Yes | — | |
| `owner` | Optional[str] | No | None | Single named owner required in `active` state |
| `due_date` | Optional[date] | No | None | |
| `status` | DeliverableStatus | Yes | `not_started` | |
| `related_milestone_id` | Optional[str] | No | None | FK to Milestone this deliverable gates |
| `blocked_by` | list[str] | No | `[]` | List of `deliverable_id`s this is waiting on |
| `last_updated` | Optional[datetime] | No | None | |
| `notes` | Optional[str] | No | None | |

**Ownership rule:** Every deliverable must have a single named human owner in `in_progress` state. "Team" or "TBD" are not valid. Validated in `deliverable_service.py`.

**Staleness rule:** Deliverables not updated in > 7 days are flagged by the `milestone_watch.py` automation job.

---

## 8. RiskBlocker — `risk.py`

**Source of truth:** Hybrid
**Asana:** Task in the Risks & Blockers project
**Sidecar:** Severity, impact linkages, escalation state, age computation

**Naming convention:** `[Scope] - [Short Problem]`
Example: `PM Jane Doe - Historical Data Feed Delayed`

**`age_days`** is computed on read as a `@property` from `date_opened` to today. It is never stored in the sidecar or written back to Asana. See `design-decisions.md D7`.

### Alert thresholds (configurable via `.env`)

| Severity | Alert trigger |
|----------|--------------|
| `critical` | > 3 days open → immediate escalation flag |
| `high` | > 7 days open → escalation watch |
| `medium` | > 14 days open |
| `low` | > 30 days open |

### `RiskType` enum

`risk`, `blocker`, `issue`

### `RiskSeverity` enum

`critical`, `high`, `medium`, `low`

### `RiskStatus` enum

`open`, `in_mitigation`, `resolved`, `accepted`, `closed`

### `EscalationStatus` enum

`none`, `watching`, `escalated`, `resolved`

### Fields — `RiskBlocker`

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `risk_id` | str | Yes | — | Internal ID |
| `title` | str | Yes | — | Follow naming convention |
| `risk_type` | RiskType | Yes | `risk` | |
| `severity` | RiskSeverity | Yes | `medium` | |
| `status` | RiskStatus | Yes | `open` | |
| `owner` | Optional[str] | No | None | Single named owner required before closing |
| `date_opened` | date | Yes | — | |
| `resolution_date` | Optional[date] | No | None | Set when resolved |
| `impacted_pm_ids` | list[str] | No | `[]` | FKs to PMCoverageRecord |
| `impacted_project_ids` | list[str] | No | `[]` | FKs to Project |
| `impacted_milestone_ids` | list[str] | No | `[]` | FKs to Milestone |
| `escalation_status` | EscalationStatus | Yes | `none` | |
| `mitigation_plan` | Optional[str] | No | None | |
| `notes` | Optional[str] | No | None | |
| `age_days` | int (computed) | — | — | `@property`; not stored |

### Fields — `RiskUpdate`

Writable: `status`, `severity`, `escalation_status`, `owner`, `mitigation_plan`, `resolution_date`, `notes`.

---

## 9. Decision — `decision.py`

**Source of truth:** Sidecar-only
**Asana representation:** None — decisions require searchable history that Asana tasks cannot provide

**Append-only semantics (per `design-decisions.md D3`):** Decisions are immutable once `status = decided`. To revise a decided outcome, create a new `Decision` with `status = pending` and set `superseded_by_id` on the original. The `PATCH /decisions/{decision_id}` endpoint only accepts updates to `pending` decisions.

### `DecisionStatus` enum

```
pending → decided (immutable from this point)
pending → deferred
decided → superseded (via new Decision with superseded_by_id)
```

### `ArtifactType` enum

`pm`, `project`, `milestone`, `pm_need`, `capability`, `risk`

### `ImpactedArtifact` sub-schema

| Field | Type | Notes |
|-------|------|-------|
| `artifact_type` | ArtifactType | |
| `artifact_id` | str | |
| `description` | Optional[str] | Optional context |

### Fields — `Decision`

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `decision_id` | str | Yes | — | Internal ID |
| `title` | str | Yes | — | |
| `context` | Optional[str] | No | None | Background and situation |
| `options_considered` | Optional[str] | No | None | Alternatives evaluated |
| `chosen_path` | Optional[str] | No | None | Selected option |
| `rationale` | Optional[str] | No | None | Why this option was chosen |
| `approvers` | list[str] | No | `[]` | Names/IDs of approvers |
| `decision_date` | Optional[date] | No | None | Set when resolved |
| `status` | DecisionStatus | Yes | `pending` | Immutable once `decided` |
| `superseded_by_id` | Optional[str] | No | None | FK to replacement Decision |
| `impacted_artifacts` | list[ImpactedArtifact] | No | `[]` | |
| `created_at` | Optional[date] | No | None | |
| `notes` | Optional[str] | No | None | |

### `DecisionResolve` schema

Used by `POST /decisions/{decision_id}/resolve`. Requires: `decision_id`, `chosen_path`, `rationale`, `approvers`, `decision_date`. Sets `status = decided`. Enforced as the only path to close a decision — cannot be done via PATCH.

---

## 10. StatusUpdate — `status_update.py`

**Source of truth:**
- Project-level: Asana (project status updates)
- PM-level: Sidecar-only
- Initiative-level: Sidecar-only

StatusUpdates are append-only snapshots. They are never edited after publishing.

### `StatusScopeType` enum

`project`, `pm`, `initiative`

### Fields — `StatusUpdate`

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `status_update_id` | str | Yes | — | Internal ID |
| `scope_type` | StatusScopeType | Yes | — | |
| `scope_id` | str | Yes | — | ID of the PM, project, or initiative |
| `overall_status` | HealthStatus | Yes | `unknown` | |
| `what_changed_this_period` | Optional[str] | No | None | |
| `next_key_milestones` | Optional[str] | No | None | |
| `top_blockers` | Optional[str] | No | None | |
| `decisions_needed` | Optional[str] | No | None | |
| `confidence` | Optional[str] | No | None | Free text or percentage |
| `updated_by` | Optional[str] | No | None | |
| `updated_at` | Optional[datetime] | No | None | |
| `asana_gid` | Optional[str] | No | None | Set for project-level updates only |

---

## 11. Capability — `capability.py` (v2 stub)

**Source of truth:** Sidecar (v2)
**Status:** Deferred to v2. Included as a stub to prevent future breaking migrations.

The `mapped_capability_id` FK field is included as nullable in `PMNeed` and `linked_capability_ids` is included in `Project` so v2 capability work does not require schema changes to those tables.

### `CapabilityMaturity` enum

`none`, `planned`, `in_build`, `basic`, `stable`, `mature`

### `RoadmapStatus` enum

`not_started`, `planned`, `in_progress`, `stable`, `deprecated`

See `docs/future-roadmap.md` for the full v2 capability model specification.

---

## 12. Entity Relationship Summary

```
PMCoverageRecord
    ├── has many PMNeed            (pm_id FK on PMNeed)
    ├── has many Project           (primary_pm_ids FK on Project)
    └── referenced by RiskBlocker  (impacted_pm_ids FK on RiskBlocker)

Project
    ├── belongs to PMCoverageRecord (primary_pm_ids)
    ├── linked to PMNeed            (linked_pm_need_ids)
    ├── has many Milestone          (project_id FK on Milestone)
    ├── has many Deliverable        (project_id FK on Deliverable)
    ├── referenced by RiskBlocker   (impacted_project_ids FK on RiskBlocker)
    └── referenced by Decision      (impacted_artifacts on Decision)

Milestone
    ├── belongs to Project          (project_id FK)
    ├── has many Deliverable        (related_milestone_id FK on Deliverable)
    └── referenced by RiskBlocker   (impacted_milestone_ids FK)

RiskBlocker
    └── references PMCoverageRecord, Project, Milestone (impact lists)

Decision
    └── references any artifact     (impacted_artifacts — polymorphic via ArtifactType)

StatusUpdate
    └── scoped to: PM, Project, or Initiative (scope_type + scope_id)
```

---

## 13. State Machines

### PMCoverageRecord — `onboarding_stage`

```
pipeline → pre_start → requirements_discovery → onboarding_in_progress
  → uat → go_live_ready → live → stabilization → steady_state

Allowed backwards:
  uat → onboarding_in_progress         (UAT failed)
  go_live_ready → onboarding_in_progress  (gate review failed)
```

All transitions validated by `validate_onboarding_transition()` in `pm_coverage_service.py`. Backwards transitions automatically open a new `RiskBlocker` with severity `high`.

### PMNeed — `status`

Driven by Asana task section. Not writable via sidecar API.

```
new → triaged → mapped_to_existing_capability
             → needs_new_project → in_progress → blocked → in_progress
                                             → delivered
                                             → deferred
                                             → cancelled
```

### Project — `status`

```
planning → active → on_hold ↔ active
                 → at_risk → active (when blockers resolved)
                 → complete → archived (Asana)
                 → cancelled
```

### Milestone — `status`

```
not_started → in_progress → at_risk → in_progress
                         → complete (requires acceptance_criteria validation)
                         → missed
                         → deferred
```

### RiskBlocker — `status` + `escalation_status`

```
status:            open → in_mitigation → resolved | accepted | closed
escalation_status: none → watching → escalated → resolved
```

`escalation_status` escalates automatically when `age_days` exceeds severity thresholds. See Section 8.

### Decision — `status`

```
pending → decided (immutable; requires DecisionResolve)
        → deferred
decided → superseded (create new Decision with superseded_by_id)
```
