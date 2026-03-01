# Asana Object Mapping and Integration Strategy

## BAM Systematic Execution OS — Asana Integration Design

**Version:** 1.0
**Last Updated:** 2026-03-01
**Status:** Approved Design

---

## Table of Contents

1. [Asana Object Mapping](#1-asana-object-mapping)
2. [Custom Fields Schema](#2-custom-fields-schema)
3. [Project Templates](#3-project-templates)
4. [Webhook Strategy](#4-webhook-strategy)
5. [Sync Direction Rules](#5-sync-direction-rules)
6. [Asana API Patterns](#6-asana-api-patterns)
7. [What Stays in Asana vs Sidecar](#7-what-stays-in-asana-vs-sidecar)
8. [GID Cross-Reference Strategy](#8-gid-cross-reference-strategy)
9. [Naming Conventions](#9-naming-conventions)
10. [Open Decisions](#10-open-decisions)

---

## 1. Asana Object Mapping

This section defines exactly how each domain object from the vision maps to Asana primitives, which fields are Asana-native vs sidecar-enriched, and the GID cross-reference approach.

### 1.1 Initiative

**Vision object:** Top-level strategic grouping across business horizons (current PM support, next-gen onboarding, long-term platform buildout).

**Asana mapping:** Asana **Portfolio**

| Field | Asana Native | Sidecar-Enriched | Notes |
|---|---|---|---|
| `name` | Portfolio name | — | Enforce naming convention |
| `horizon` | Portfolio custom field: `Horizon` | Mirror | Enum: short_term / medium_term / long_term |
| `business_objective` | Portfolio description | Full record | Asana description is plain text; sidecar stores structured |
| `executive_sponsor` | Portfolio member (Owner role) | `executive_sponsor` field | Asana has limited sponsor metadata |
| `priority` | Portfolio custom field: `Priority` | Mirror | Enum: critical / high / medium / low |
| `status` | Portfolio status (RAG) | Mirror | Asana portfolio status = overall health |
| `target_outcome` | Portfolio description | `target_outcome` field | |
| `linked_projects[]` | Portfolio project members | `linked_project_gids[]` | Asana portfolios natively contain projects |
| `initiative_id` | — | Primary key | Sidecar assigns and manages |

**GID cross-reference:** Sidecar stores `asana_portfolio_gid` on the Initiative record.

**Decision:** Initiatives are v2 scope. In v1, portfolios can be created manually and linked by the sidecar. Do not block v1 on portfolio automation.

---

### 1.2 PM Coverage Record

**Vision object:** A persistent record for each PM / team being supported, tracking onboarding stage, health, open needs, and linked projects.

**Asana mapping:** Dedicated Asana **Project** named `PM Coverage Board` using Board layout. One **task** per PM.

| Field | Asana Native | Sidecar-Enriched | Notes |
|---|---|---|---|
| `pm_name` | Task name | Mirror | Task name = PM display name |
| `team_or_pod` | Custom field: `Team / Pod` | Mirror | Text field |
| `strategy_type` | Custom field: `Strategy Type` | Mirror | Text: equity / futures / options / multi-strat / etc. |
| `region` | Custom field: `Region` | Mirror | Enum: AMER / EMEA / APAC / Global |
| `coverage_owner` | Task assignee | Mirror | Asana assignee = coverage lead |
| `onboarding_stage` | Custom field: `Onboarding Stage` | Mirror | Enum (9 values, see below) |
| `go_live_target_date` | Task due date | Mirror | Due date on the PM task = go-live target |
| `health_status` | Custom field: `Health` | Mirror | Enum: green / yellow / red |
| `top_open_needs[]` | — | Full list | Sidecar queries linked PM Needs |
| `top_blockers[]` | — | Full list | Sidecar queries linked Risk/Blockers |
| `linked_projects[]` | — | `linked_project_gids[]` | Multi-project link; Asana task can't natively do this |
| `last_touchpoint_date` | Custom field: `Last Touchpoint` | Mirror | Date field |
| `pm_id` | — | Primary key | Sidecar-assigned |

**Board sections (columns):**

```
Pipeline | Pre-Start | Requirements Discovery | Onboarding In Progress | UAT | Go Live Ready | Live | Stabilization | Steady State
```

**GID cross-reference:** Sidecar stores `asana_task_gid` and `asana_project_gid` (for the PM Coverage Board project) on the PMCoverageRecord.

**Design decision:** PM Coverage Record lives **dual-homed** — Asana task provides the Kanban-style stage view and is the visual operating artifact; sidecar holds the richer relational record (linked needs, linked blockers, full history). Asana is the stage/health source of truth; sidecar is the relational source of truth.

---

### 1.3 PM Need

**Vision object:** A normalized business request from a PM or leadership that must be triaged, mapped, and owned.

**Asana mapping:** Asana **Task** inside a dedicated **PM Needs** project, organized by sections.

| Field | Asana Native | Sidecar-Enriched | Notes |
|---|---|---|---|
| `title` | Task name | Mirror | Use naming convention: `[PM] - [Category] - [Short Need]` |
| `problem_statement` | Task description | `problem_statement` field | Asana description plain text; sidecar structured |
| `business_rationale` | Task description (appended) | `business_rationale` field | |
| `requested_by` | Task follower / custom field: `Requested By` | Mirror | |
| `date_raised` | Task created_at | Mirror | Asana creation timestamp |
| `category` | Custom field: `Need Category` | Mirror | Enum: market_data / historical_data / alt_data / execution / broker / infra / research / ops / other |
| `urgency` | Custom field: `Urgency` | Mirror | Enum: critical / high / medium / low |
| `business_impact` | Custom field: `Business Impact` | Mirror | Enum: high / medium / low |
| `desired_by_date` | Task due date | Mirror | |
| `status` | Task section (Kanban column) | Custom field: `Need Status` | Section drives workflow; custom field provides machine-readable status |
| `mapped_capability_id` | Custom field: `Linked Capability` | `mapped_capability_gid` | Text reference; sidecar resolves |
| `linked_project_ids[]` | Task dependency / project member | `linked_project_gids[]` | Sidecar tracks multi-project links |
| `resolution_path` | Custom field: `Resolution Path` | Mirror | Enum: existing_capability / new_project / deferred / cancelled |
| `pm_id` | Custom field: `PM` | `pm_gid` | References PM Coverage Record |
| `notes` | Task comments | — | Native Asana comments are sufficient |
| `pm_need_id` | — | Primary key | |

**PM Needs project sections:**

```
New | Triaged | Mapped to Existing | Needs New Project | In Progress | Blocked | Delivered | Deferred | Cancelled
```

**Asana Form integration:** Enable an Asana Form on the PM Needs project to capture new needs from PMs directly. Required form fields: PM name, need title, category, urgency, business rationale, desired by date. Form submission creates a task in the `New` section.

**GID cross-reference:** Sidecar stores `asana_task_gid` on each PMNeed record.

---

### 1.4 Capability

**Vision object:** A reusable platform capability shared across multiple PMs (e.g., security master, DMA connectivity, research platform).

**Asana mapping:** Dedicated Asana **Project** named `Capability Registry` with one **task** per capability, plus separate execution projects for active build work.

| Field | Asana Native | Sidecar-Enriched | Notes |
|---|---|---|---|
| `name` | Task name | Mirror | |
| `domain` | Custom field: `Capability Domain` | Mirror | Enum: market_data / execution / research / infra / ops / broker / data |
| `owner_team` | Task assignee | Mirror | Team lead as assignee |
| `current_maturity` | Custom field: `Maturity` | Mirror | Enum: planned / in_build / available / stable / deprecated |
| `description` | Task description | `description` field | |
| `known_gaps[]` | Task subtasks (Gap items) | `known_gaps[]` | Subtasks for each gap |
| `dependent_pms[]` | — | `dependent_pm_ids[]` | Sidecar tracks; too complex for Asana native |
| `linked_projects[]` | — | `linked_project_gids[]` | Sidecar tracks |
| `roadmap_status` | Custom field: `Roadmap Status` | Mirror | Enum: backlog / planned / active / complete |
| `capability_id` | — | Primary key | |

**Note:** Capability is v2 scope. In v1, the Capability Registry project can be created manually and populated without sidecar automation.

**GID cross-reference:** Sidecar stores `asana_task_gid` on each Capability record.

---

### 1.5 Project

**Vision object:** A bounded execution effort (PM onboarding, capability build, remediation, investigation) that delivers a business outcome.

**Asana mapping:** Direct 1:1 with an Asana **Project**. This is the most natural mapping.

| Field | Asana Native | Sidecar-Enriched | Notes |
|---|---|---|---|
| `name` | Project name | Mirror | Enforce naming convention |
| `project_type` | Custom field: `Project Type` | Mirror | Enum: pm_onboarding / capability_build / remediation / expansion / investigation |
| `business_objective` | Project description | `business_objective` field | Asana description plain text; sidecar structured |
| `primary_pm_ids[]` | Custom field: `Primary PMs` | `primary_pm_gids[]` | Text or multi-select; sidecar resolves to PM records |
| `owner` | Project owner | Mirror | Asana project owner = delivery lead |
| `status` | Project status (RAG) | Mirror | Asana built-in project status update |
| `priority` | Custom field: `Priority` | Mirror | Enum: critical / high / medium / low |
| `start_date` | Project start date | Mirror | |
| `target_date` | Project due date | Mirror | |
| `success_criteria` | Project description (section) | `success_criteria` field | Template should include structured success criteria section |
| `linked_pm_needs[]` | — | `linked_pm_need_gids[]` | Sidecar tracks cross-project links |
| `linked_capabilities[]` | — | `linked_capability_ids[]` | Sidecar tracks |
| `linked_milestones[]` | Tasks (milestone type) in project | Mirror | Asana tasks with milestone flag |
| `linked_risks[]` | — | `linked_risk_gids[]` | Risks in dedicated project; sidecar links |
| `linked_decisions[]` | — | `linked_decision_ids[]` | Sidecar tracks decision registry |
| `project_id` | — | Primary key | |

**GID cross-reference:** Sidecar stores `asana_project_gid` on each Project record.

---

### 1.6 Milestone

**Vision object:** A named checkpoint with explicit gating criteria (e.g., Data Ready, Go Live Ready, Stabilization Complete).

**Asana mapping:** Asana **Task with milestone flag** inside the parent project. Use Asana's native milestone task type.

| Field | Asana Native | Sidecar-Enriched | Notes |
|---|---|---|---|
| `name` | Task name | Mirror | Use naming convention: `[PM/Project] - [Checkpoint]` |
| `target_date` | Task due date | Mirror | |
| `owner` | Task assignee | Mirror | |
| `status` | Task completion + Custom field: `Milestone Status` | Mirror | Enum: not_started / in_progress / at_risk / complete / missed |
| `gating_conditions` | Task description | `gating_conditions` field | Template section in task description |
| `acceptance_criteria` | Task description | `acceptance_criteria` field | Required field; alert if missing |
| `confidence` | Custom field: `Confidence` | Mirror | Enum: high / medium / low / blocked |
| `project_id` | Parent project GID | Mirror | |
| `milestone_id` | — | Primary key | |

**Design decision:** `acceptance_criteria` is mandatory. The sidecar will alert when a milestone due within 14 days lacks acceptance criteria.

**GID cross-reference:** Sidecar stores `asana_task_gid` on each Milestone record.

---

### 1.7 Deliverable / Action Item

**Vision object:** A concrete owned work item — the lowest-level tracked unit supporting the "who will do what by when" cadence.

**Asana mapping:** Standard Asana **Task** (non-milestone) inside the parent project. Subtasks for sub-items.

| Field | Asana Native | Sidecar-Enriched | Notes |
|---|---|---|---|
| `title` | Task name | Mirror | |
| `owner` | Task assignee | Mirror | |
| `due_date` | Task due date | Mirror | |
| `status` | Task completion | Custom field: `Delivery Status` | Enum: not_started / in_progress / blocked / complete |
| `related_milestone_id` | Task dependency (milestone task) | `related_milestone_gid` | Asana dependency links deliverable to milestone |
| `blocked_by[]` | Task dependencies | `blocked_by_gids[]` | Asana native task dependencies |
| `last_updated` | Task modified_at | Mirror | Asana provides this natively |
| `notes` | Task comments | — | |
| `project_id` | Parent project GID | Mirror | |
| `deliverable_id` | — | Primary key | Assigned by sidecar if created via API |

**GID cross-reference:** Sidecar stores `asana_task_gid` on Deliverables created via automation. Manually created tasks are linked lazily (on first webhook event).

---

### 1.8 Risk / Blocker / Issue

**Vision object:** A trackable object for things threatening outcomes, dates, or PM confidence.

**Asana mapping:** Asana **Task** inside a dedicated **Risks & Blockers** project. All risks across all projects live here for unified visibility.

| Field | Asana Native | Sidecar-Enriched | Notes |
|---|---|---|---|
| `title` | Task name | Mirror | Convention: `[Scope] - [Short Problem]` |
| `type` | Custom field: `Item Type` | Mirror | Enum: risk / blocker / issue |
| `severity` | Custom field: `Severity` | Mirror | Enum: critical / high / medium / low |
| `impacted_pm_ids[]` | Custom field: `Impacted PMs` (multi-select) | `impacted_pm_gids[]` | Text tags in Asana; sidecar resolves |
| `impacted_project_ids[]` | Custom field: `Impacted Projects` | `impacted_project_gids[]` | Text tags; sidecar resolves |
| `impacted_milestone_ids[]` | — | `impacted_milestone_gids[]` | Sidecar-tracked |
| `owner` | Task assignee | Mirror | |
| `date_opened` | Task created_at | Mirror | |
| `age_days` | — | Computed field | Sidecar computes on read |
| `mitigation_plan` | Task description | `mitigation_plan` field | |
| `escalation_status` | Custom field: `Escalation Status` | Mirror | Enum: none / monitoring / escalated / resolved |
| `resolution_date` | Task completion date | Mirror | |
| `risk_id` | — | Primary key | |

**Risks & Blockers project sections:**

```
Open - Critical | Open - High | Open - Medium | Monitoring | Resolved
```

**GID cross-reference:** Sidecar stores `asana_task_gid` on each RiskBlocker record.

---

### 1.9 Decision

**Vision object:** A durable record of meaningful business/technology tradeoffs with full context and rationale.

> **Architecture reconciliation:** `architecture.md` (Section 2) resolves Decisions as **sidecar-only** — no Asana representation required. The hybrid approach below is preserved as an optional enhancement but the Decision Log Asana project is not required for v1. The sidecar decision registry is the canonical store.

**Asana mapping (hybrid — optional in v1):** Light Asana presence via a **Decision Log** project with one task per decision for visibility and assignment. Full structured record in sidecar decision registry.

| Field | Asana Native (task) | Sidecar-Enriched | Notes |
|---|---|---|---|
| `title` | Task name | Mirror | |
| `approver(s)` | Task assignee | Mirror | Primary approver as assignee |
| `decision_date` | Task due date (or completed_at) | Mirror | |
| `status` | Custom field: `Decision Status` | Mirror | Enum: pending / decided / deferred / cancelled |
| `context` | Task description (brief) | Full `context` field | Asana has abbreviated; sidecar has full |
| `options_considered` | — | `options_considered[]` | Too structured for Asana native |
| `chosen_path` | Task description (headline) | `chosen_path` field | |
| `rationale` | — | `rationale` field | Sidecar-only |
| `impacted_artifacts[]` | — | `impacted_artifact_gids[]` | Sidecar tracks |
| `decision_id` | — | Primary key | |

**Design decision:** Decisions are sidecar-primary. The Asana task exists for visibility and to surface pending decisions in operating reviews. The canonical decision record (with full options, rationale, and impacted artifacts) lives in the sidecar decision registry.

**GID cross-reference:** Sidecar stores `asana_task_gid` on each Decision record.

---

### 1.10 Status Update

**Vision object:** A structured snapshot for stakeholders at project, PM, or initiative level.

**Asana mapping:** Asana **Project Status Update** (native feature) for project-level. PM-level and initiative-level status updates live in sidecar.

| Field | Asana Native | Sidecar-Enriched | Notes |
|---|---|---|---|
| `overall_status` | Status update color (green/yellow/red) | Mirror | |
| `what_changed_this_period` | Status update body | `what_changed` field | |
| `next_key_milestones` | Status update body | `next_milestones[]` | |
| `top_blockers` | Status update body | `top_blockers[]` | |
| `decisions_needed` | Status update body | `decisions_needed[]` | |
| `confidence` | Custom field on project: `Confidence` | Mirror | |
| `updated_by` | Status update author | Mirror | |
| `updated_at` | Status update created_at | Mirror | |
| `scope_type` | — | `scope_type` field | project / pm / initiative |
| `scope_id` | — | `scope_gid` | |
| `status_update_id` | — | Primary key | |

**Design decision:** Asana project status updates are the primary medium for project-level status. The sidecar ingests these via webhook and stores them for cross-project rollup and bot query access.

---

## 2. Custom Fields Schema

All custom fields should be created in the **organization-level custom field library** in Asana, then applied to relevant projects. This ensures consistency and avoids field proliferation.

### 2.1 Global Custom Fields (Applied to All Projects)

| Field Name | Type | Values / Format | Applied To |
|---|---|---|---|
| `Project Type` | Enum | pm_onboarding / capability_build / remediation / expansion / investigation | All projects |
| `Priority` | Enum | critical / high / medium / low | All projects |
| `Health` | Enum | green / yellow / red | All projects |
| `Confidence` | Enum | high / medium / low / blocked | All projects |
| `Owner Group` | Text | Free text (team name) | All projects |
| `Region` | Enum | AMER / EMEA / APAC / Global | All projects |

### 2.2 PM Coverage Board Custom Fields

| Field Name | Type | Values / Format | Notes |
|---|---|---|---|
| `Onboarding Stage` | Enum | pipeline / pre_start / requirements_discovery / onboarding_in_progress / uat / go_live_ready / live / stabilization / steady_state | Drives Kanban column |
| `Strategy Type` | Text | equity / futures / options / multi-strat / macro / quant / etc. | Free text; will standardize in v2 |
| `Team / Pod` | Text | Free text | |
| `Last Touchpoint` | Date | YYYY-MM-DD | |
| `Go Live Target` | Date | YYYY-MM-DD | Mirrors task due date |

### 2.3 PM Needs Project Custom Fields

| Field Name | Type | Values / Format | Notes |
|---|---|---|---|
| `Need Category` | Enum | market_data / historical_data / alt_data / execution / broker / infra / research / ops / other | |
| `Urgency` | Enum | critical / high / medium / low | |
| `Business Impact` | Enum | high / medium / low | |
| `Need Status` | Enum | new / triaged / mapped_to_existing / needs_new_project / in_progress / blocked / delivered / deferred / cancelled | Machine-readable; mirrors section |
| `Resolution Path` | Enum | existing_capability / new_project / deferred / cancelled | Set during triage |
| `PM` | Text | PM name or ID | References PM Coverage Record |
| `Requested By` | Text | Name of requestor | Could differ from PM |
| `Linked Capability` | Text | Capability name | Resolved by sidecar |
| `Desired By Date` | Date | YYYY-MM-DD | Mirrors task due date |

### 2.4 Milestone Custom Fields (On All Projects with Milestones)

| Field Name | Type | Values / Format | Notes |
|---|---|---|---|
| `Milestone Status` | Enum | not_started / in_progress / at_risk / complete / missed | Supplements Asana completion flag |
| `Confidence` | Enum | high / medium / low / blocked | Required on all milestones |
| `Acceptance Criteria Confirmed` | Checkbox | true / false | Sidecar alerts when false and due < 14 days |
| `Gate Type` | Enum | data_ready / execution_ready / uat_complete / go_live_ready / stabilization_complete / custom | |

### 2.5 Risks & Blockers Project Custom Fields

| Field Name | Type | Values / Format | Notes |
|---|---|---|---|
| `Item Type` | Enum | risk / blocker / issue | |
| `Severity` | Enum | critical / high / medium / low | |
| `Escalation Status` | Enum | none / monitoring / escalated / resolved | |
| `Impacted PMs` | Text | Comma-separated PM names | Sidecar resolves to GIDs |
| `Impacted Projects` | Text | Comma-separated project names | Sidecar resolves |
| `Age (Days)` | Number | Auto-computed by sidecar, written back | Read-only in practice |
| `Resolution Date` | Date | YYYY-MM-DD | Set when resolved |

### 2.6 Decision Log Project Custom Fields

| Field Name | Type | Values / Format | Notes |
|---|---|---|---|
| `Decision Status` | Enum | pending / decided / deferred / cancelled | |
| `Decision Date` | Date | YYYY-MM-DD | When decision was made |
| `Approver` | Text | Name(s) | Mirrors assignee for primary approver |
| `Impacted Scope` | Text | Project / PM names affected | Sidecar resolves |

### 2.7 Capability Registry Custom Fields

| Field Name | Type | Values / Format | Notes |
|---|---|---|---|
| `Capability Domain` | Enum | market_data / execution / research / infra / ops / broker / data | |
| `Maturity` | Enum | planned / in_build / available / stable / deprecated | |
| `Roadmap Status` | Enum | backlog / planned / active / complete | |
| `Dependent PM Count` | Number | Integer | Written by sidecar |

---

## 3. Project Templates

Templates define the standard structure for each recurring project type. Every template should include: required sections, seed milestone tasks, required custom fields, and a template description.

### 3.1 PM Onboarding Project Template

**Naming convention:** `Onboarding - [PM Name] - [Strategy/Region Short Label]`

**Description:** Standard onboarding and go-live track for an incoming PM. Covers requirements through stabilization.

**Required custom fields:** Project Type (pm_onboarding), Primary PMs, Priority, Health, Confidence, Region

**Sections:**

```
Kickoff & Discovery
Requirements & Scoping
Market Data & Infrastructure
Execution & Connectivity
UAT & Validation
Go Live Readiness
Post Go Live Stabilization
Admin & Wrap-Up
```

**Seed milestones (milestone tasks):**

| Milestone Name | Section | Required Acceptance Criteria? |
|---|---|---|
| Onboarding Kickoff | Kickoff & Discovery | Yes |
| Requirements Confirmed | Requirements & Scoping | Yes |
| Market Data Ready | Market Data & Infrastructure | Yes |
| Historical Data Ready | Market Data & Infrastructure | Yes |
| Alt Data Ready (if applicable) | Market Data & Infrastructure | Conditional |
| Execution Ready | Execution & Connectivity | Yes |
| UAT Complete | UAT & Validation | Yes |
| Go Live Ready | Go Live Readiness | Yes |
| PM Live | Go Live Readiness | Yes — critical gate |
| Stabilization Complete | Post Go Live Stabilization | Yes |

**Seed tasks (non-milestone):**

```
Kickoff & Discovery:
  - Schedule kickoff meeting with PM
  - Capture PM background and strategy overview
  - Document initial PM needs list
  - Identify key contacts (PM team, tech, ops, broker)

Requirements & Scoping:
  - Conduct requirements discovery sessions
  - Document full PM needs in PM Needs project
  - Map needs to existing capabilities or new projects
  - Define success criteria for go-live
  - Get PM sign-off on requirements scope

Market Data & Infrastructure:
  - Confirm market data coverage requirements
  - Confirm historical data requirements
  - Submit data feed requests to tech
  - Validate data feed delivery
  - Confirm infrastructure provisioned

Execution & Connectivity:
  - Confirm broker connectivity requirements
  - Submit DMA / broker integration requests
  - Validate execution infrastructure
  - End-to-end execution test

UAT & Validation:
  - Define UAT plan and criteria
  - Run UAT sessions with PM
  - Document and resolve UAT issues
  - Get PM sign-off on UAT completion

Go Live Readiness:
  - Final readiness checklist
  - Confirm support coverage on go-live day
  - Go/no-go decision meeting
  - Execute go-live

Post Go Live Stabilization:
  - Day 1 check-in with PM
  - Week 1 stabilization review
  - Capture early issues and follow-up needs
  - Week 2-4 stabilization reviews
  - Stabilization closure decision

Admin & Wrap-Up:
  - Update PM Coverage Record to Steady State
  - Archive onboarding project
  - Document lessons learned
```

---

### 3.2 Capability Build Project Template

**Naming convention:** `Capability - [Capability Name] - [Phase or Scope]`

**Description:** Structured build or expansion of a shared platform capability that serves multiple PMs.

**Required custom fields:** Project Type (capability_build), Priority, Health, Confidence, Owner Group

**Sections:**

```
Definition & Scoping
Design & Architecture
Build
Testing & Validation
Launch & Documentation
Monitoring & Optimization
```

**Seed milestones:**

| Milestone Name | Section |
|---|---|
| Capability Definition Confirmed | Definition & Scoping |
| Architecture Approved | Design & Architecture |
| Build Complete | Build |
| Testing Complete | Testing & Validation |
| Capability Available | Launch & Documentation |
| Stable & Monitored | Monitoring & Optimization |

**Seed tasks:**

```
Definition & Scoping:
  - Aggregate PM needs that this capability addresses
  - Define capability scope and non-scope
  - Identify dependent PMs and onboarding timeline
  - Document success criteria
  - Get business sign-off on scope

Design & Architecture:
  - Tech design review
  - Identify dependencies on other capabilities
  - Risk review
  - Architecture approval

Build:
  - Sprint planning with tech team
  - Weekly build check-ins
  - Track blockers in Risks & Blockers project

Testing & Validation:
  - Define test plan
  - Conduct testing with PM(s)
  - Resolve issues
  - Sign-off on testing

Launch & Documentation:
  - Update Capability Registry maturity to Available
  - Publish runbook / documentation
  - Notify dependent PMs
  - Link capability to PM Needs (mark as resolved)

Monitoring & Optimization:
  - 30-day post-launch review
  - Capture issues and gaps
  - Update Capability Registry
```

---

### 3.3 Stabilization Project Template

**Naming convention:** `Stabilization - [PM Name or Capability] - [Scope]`

**Description:** Post-go-live support track to ensure PMs or capabilities are fully functional and issues are addressed.

**Required custom fields:** Project Type (remediation), Primary PMs, Priority, Health

**Sections:**

```
Active Issues
Monitoring & Watch
Follow-On Needs
Closure Criteria
```

**Seed tasks:**

```
Active Issues:
  - Day 1 issues log
  - Week 1 issues review

Monitoring & Watch:
  - Daily PM check-in (first week)
  - Weekly health review
  - Escalation log

Follow-On Needs:
  - Capture follow-on PM needs
  - Prioritize follow-on work
  - Create new PM Needs entries

Closure Criteria:
  - Verify all critical issues resolved
  - PM confirms readiness for steady state
  - Update PM Coverage Record to Steady State
  - Close stabilization project
```

---

### 3.4 PM Needs Intake Project Template

**Naming convention:** `PM Needs - BAM Systematic` (singleton; one project for all PM needs)

**Description:** Centralized intake and routing for all PM needs and business requests.

**Required custom fields:** Need Category, Urgency, Business Impact, Need Status, Resolution Path, PM, Requested By, Desired By Date, Linked Capability

**Sections (Kanban):**

```
New | Triaged | Mapped to Existing Capability | Needs New Project | In Progress | Blocked | Delivered | Deferred | Cancelled
```

**Setup notes:**
- Enable Asana Form for PM need intake
- Form required fields: PM Name, Need Title, Category, Urgency, Business Rationale, Desired By Date
- Auto-assign new form submissions to PMO lead
- New submissions land in `New` section

---

### 3.5 Risks & Blockers Tracking Project Template

**Naming convention:** `Risks & Blockers - BAM Systematic` (singleton; one project for all risks)

**Description:** Centralized log for all open risks, blockers, and issues across projects and PMs.

**Required custom fields:** Item Type, Severity, Escalation Status, Impacted PMs, Impacted Projects, Age (Days), Resolution Date

**Sections:**

```
Open - Critical | Open - High | Open - Medium | Monitoring | Resolved
```

**Setup notes:**
- Configure Asana Rule: when Item Type = blocker AND Severity = critical → assign to PMO lead, add to `Open - Critical`
- Configure Asana Rule: when task completed → move to `Resolved`, set Resolution Date to today
- Weekly review: triage all items in `Open - Critical` and `Open - High`

---

### 3.6 Decision Log Project Template

**Naming convention:** `Decision Log - BAM Systematic` (singleton)

**Description:** Lightweight Asana surface for pending and made decisions. Full record in sidecar.

**Required custom fields:** Decision Status, Decision Date, Approver, Impacted Scope

**Sections:**

```
Pending Decisions | Decisions Made | Deferred | Cancelled
```

---

## 4. Webhook Strategy

### 4.1 Which Events to Subscribe To

Subscribe at the **workspace level** where possible, or at the **project level** for critical projects. Use Asana's Events API with webhook subscriptions.

**Primary webhook subscriptions:**

| Resource Type | Events | Why |
|---|---|---|
| All tasks in PM Needs project | `task.created`, `task.changed`, `task.completed`, `task.moved_to_section` | Track need lifecycle |
| All tasks in PM Coverage Board | `task.changed`, `task.moved_to_section` | Track onboarding stage transitions |
| All tasks in Risks & Blockers | `task.created`, `task.changed`, `task.completed` | Alert on new critical blockers |
| All tasks in Decision Log | `task.created`, `task.changed` | Track pending decisions |
| All onboarding/capability projects | `task.changed`, `task.completed`, `milestone.completed` | Track milestone progress |
| Any project | `project.status_update.created` | Ingest project status updates into sidecar |
| Any task (filtered) | `task.dependency_removed`, `task.dependency_added` | Track dependency changes |

**Events to ignore:** comments, attachments, likes, story events (unless auditing is required).

### 4.2 Webhook Handler Design

```
Webhook receiver (FastAPI endpoint: /webhooks/asana)
  ↓
Validate X-Hook-Secret header
  ↓
Parse event batch (Asana sends batches)
  ↓
Route by resource_type + event_type
  ↓
Handlers:
  - handle_task_changed(event)    → update sidecar record, compute derived fields
  - handle_task_created(event)    → create sidecar shadow record, backfill GID
  - handle_task_completed(event)  → mark sidecar record resolved, trigger alerts
  - handle_section_moved(event)   → update status/stage field in sidecar
  - handle_status_update(event)   → store status snapshot, roll up to PM/initiative
  ↓
Idempotency check (event_id deduplication)
  ↓
Enqueue job if async processing needed
  ↓
Return 200 OK immediately (Asana expects fast response)
```

### 4.3 Webhook Registration

- Register webhooks on workspace creation or template deployment
- Store webhook GID and secret in sidecar config
- Implement `/webhooks/asana/handshake` for initial Asana verification (X-Hook-Secret echo)
- Re-register webhooks on sidecar restart if needed (check existing registrations first)

### 4.4 Event Filtering

Asana sends all events for subscribed resources. Apply server-side filters:

```python
IGNORED_CHANGE_FIELDS = {"modified_at", "liked", "num_likes", "stories"}
CRITICAL_CHANGE_FIELDS = {"custom_fields", "assignee", "due_on", "completed", "memberships"}
```

Only process events where changed fields intersect with `CRITICAL_CHANGE_FIELDS`.

---

## 5. Sync Direction Rules

These rules define the authoritative source and sync direction for each data element.

### 5.1 Sync Direction Legend

- **A→S:** Asana is source of truth; sidecar reads from Asana (webhook or poll)
- **S→A:** Sidecar is source of truth; sidecar writes to Asana
- **Both (A primary):** Asana is primary; sidecar mirrors and may write derived fields back
- **S only:** Sidecar-only; not represented meaningfully in Asana

### 5.2 Per-Element Sync Rules

| Data Element | Sync Direction | Notes |
|---|---|---|
| Task name / title | A→S | Users edit in Asana; sidecar mirrors |
| Task assignee / owner | A→S | Users edit in Asana |
| Task due date | A→S | Users edit in Asana |
| Task completion | A→S | Users complete in Asana; sidecar reacts |
| Task section (Kanban position) | A→S | Users move in Asana; sidecar updates status field |
| Custom field values | Both (A primary) | Users edit in Asana; sidecar can write derived fields (e.g., Age Days) back |
| Project status update | A→S | PMO writes in Asana; sidecar ingests for rollup |
| PM Coverage onboarding stage | A→S | Stage driven by Kanban section in Asana |
| PM Coverage health | A→S | Set in Asana; sidecar mirrors |
| PM Coverage linked needs | S only | Sidecar queries PM Needs project; Asana has no native cross-project list |
| PM Coverage linked blockers | S only | Sidecar queries Risks & Blockers project |
| PM Need status (section-based) | A→S | Section drives canonical status |
| PM Need resolution path | A→S | Set in Asana custom field |
| PM Need → Project link | Both (S primary) | Sidecar tracks relational link; may write Linked Capability field to Asana |
| Milestone confidence | A→S | Set in Asana custom field |
| Milestone acceptance criteria | A→S | Set in Asana task description |
| Risk/Blocker severity | A→S | Set in Asana custom field |
| Risk/Blocker escalation status | A→S | Set in Asana custom field |
| Risk age (days) | S→A | Sidecar computes and writes back to Age (Days) field daily |
| Decision full record | S only | Sidecar is decision registry |
| Decision status | A→S | Set in Asana custom field on Decision Log task |
| Decision → impacted artifacts | S only | Sidecar tracks relational links |
| Project status snapshots (history) | S only | Sidecar stores historical project status; Asana only shows current |
| Cross-project rollups | S only | Sidecar computes; Asana cannot do cross-project aggregation natively |
| PM initiative-level status | S only | Synthesized by sidecar from project status |
| Capability dependent PM list | S only | Sidecar tracks |
| Webhook event log | S only | Sidecar audit log |
| Bot query cache | S only | Sidecar query layer |

### 5.3 Sync Frequency

| Sync Type | Frequency | Method |
|---|---|---|
| Asana task events → sidecar | Real-time | Webhook |
| Sidecar derived fields → Asana | Hourly (batch) | Scheduled job |
| Full re-sync / consistency check | Daily (off-hours) | Scheduled job |
| Status snapshot archive | On webhook event | Webhook handler |
| PM health / risk digest | Daily 8am | Scheduled job |

---

## 6. Asana API Patterns

### 6.1 Rate Limiting

Asana rate limit: **1,500 requests per minute** per OAuth app (varies by plan).

**Handling strategy:**

```python
class AsanaRateLimiter:
    max_requests_per_minute = 1400  # conservative buffer
    retry_on_429 = True
    max_retries = 3
    base_backoff_seconds = 60  # Asana 429 includes Retry-After header; use it

    # Implementation: token bucket or leaky bucket
    # On 429: read Retry-After header, sleep, retry with exponential backoff
```

**Batching:** Use Asana's batch API (`POST /batch`) for operations that create/update multiple objects in one HTTP call. Max 10 operations per batch request.

### 6.2 Pagination

All Asana list endpoints paginate with `offset` tokens.

```python
def get_all_pages(client, endpoint, params):
    results = []
    params["limit"] = 100  # max page size
    while True:
        response = client.get(endpoint, params=params)
        results.extend(response["data"])
        next_page = response.get("next_page")
        if not next_page:
            break
        params["offset"] = next_page["offset"]
    return results
```

Always paginate. Never assume a single response contains all results.

### 6.3 Field Selection (opt_fields)

Always specify `opt_fields` to limit response payload. Asana default responses omit most fields.

**Standard opt_fields by object type:**

```python
TASK_FIELDS = "gid,name,assignee.gid,assignee.name,due_on,completed,completed_at,custom_fields,memberships.section.gid,memberships.section.name,memberships.project.gid,modified_at,notes,dependencies,dependents"

MILESTONE_FIELDS = "gid,name,assignee.gid,due_on,completed,custom_fields,memberships.project.gid"

PROJECT_FIELDS = "gid,name,owner.gid,due_on,start_on,custom_fields,current_status,members"
```

### 6.4 Error Handling

```python
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 422}

def call_asana(method, endpoint, **kwargs):
    for attempt in range(MAX_RETRIES):
        try:
            response = asana_client.request(method, endpoint, **kwargs)
            return response
        except AsanaError as e:
            if e.status in NON_RETRYABLE_STATUS_CODES:
                log_error(e)
                raise
            if e.status == 429:
                wait = int(e.headers.get("Retry-After", 60))
                sleep(wait)
            else:
                sleep(2 ** attempt)  # exponential backoff
    raise MaxRetriesExceeded()
```

### 6.5 Idempotency

All create operations must be idempotent:

- Before creating an Asana object, check if a sidecar record with that `external_id` or name already has an `asana_gid`
- If `asana_gid` exists, verify the object still exists in Asana (GET by GID)
- If it exists, skip creation and return existing GID
- If it doesn't exist (deleted externally), re-create and update sidecar record

Use Asana's `external.id` field (available on tasks) to store the sidecar's primary key. This enables lookup by external ID without a database query first.

```python
# Set external ID on task creation
task_body = {
    "name": title,
    "external": {"id": f"sidecar:{domain_object_type}:{internal_id}"}
}
```

### 6.6 Batch Operations for Template Instantiation

When creating a project from template (e.g., new PM onboarding):

1. Create project (single API call)
2. Collect all section/task/milestone definitions from template config
3. Batch API: create all sections (up to 10 per batch request)
4. Batch API: create all milestone tasks (up to 10 per batch)
5. Batch API: create all seed tasks (up to 10 per batch)
6. Batch API: set custom field values
7. Return project GID + task GID map to caller

Estimated API calls for full onboarding template: ~15–25 calls (versus 50–80 unbatched).

### 6.7 Webhook Reliability

- Asana webhooks can miss events during outages. Run a **daily consistency check** that polls modified tasks and compares to sidecar state.
- Log all incoming webhook events with `event_id` for deduplication.
- Webhook handler must return 200 within 10 seconds; enqueue heavy processing to a job queue (Celery, RQ, or similar).

---

## 7. What Stays in Asana vs Sidecar

### 7.1 Decision Table

| Capability | Stays In | Rationale |
|---|---|---|
| Task creation, assignment, due dates | Asana | Core project management; Asana UX is best-in-class for this |
| Milestone tracking within a project | Asana | Native milestone tasks; visible in timeline view |
| Project status updates (RAG) | Asana | Native feature; good for team visibility |
| Day-to-day task comments and collaboration | Asana | Native; no reason to duplicate |
| Kanban-style stage tracking (PM stage, need status) | Asana | Sections + custom fields provide good visual workflow |
| Task dependencies (within a project) | Asana | Native; clean UX |
| Cross-project task dependencies | Sidecar | Asana cross-project dependencies are limited; sidecar tracks via GID pairs |
| PM Coverage relational record | Sidecar (primary) + Asana (visual) | Asana task provides visual stage; sidecar holds linked needs, blockers, projects |
| Full PM Need history and cross-PM analysis | Sidecar | Cross-project rollup not possible natively in Asana |
| Capability registry and PM dependency mapping | Sidecar | Many-to-many PM→Capability links exceed Asana's native modeling |
| Decision registry with full rationale | Sidecar | Searchable history, options, rationale need structured store |
| Historical project status snapshots | Sidecar | Asana only shows current status; history requires sidecar |
| Cross-project risk heatmap | Sidecar | Cannot aggregate custom fields across projects in Asana |
| Bot/agent query layer | Sidecar | Asana API too slow and limited for real-time conversational queries |
| Derived metrics (age, health score, velocity) | Sidecar | Asana has no computation layer |
| Weekly review agenda generation | Sidecar | Requires cross-project data aggregation |
| PM health signals and alerts | Sidecar | Requires derived logic across multiple objects |
| Initiative/horizon rollups | Sidecar + Asana Portfolios | Portfolio for visual rollup; sidecar for structured data |
| Automation audit log | Sidecar | Not appropriate for Asana |
| Naming convention enforcement | Sidecar | Webhook-triggered validation |

### 7.2 Guiding Principles for Boundary Decisions

1. **If a user interacts with it daily via Asana UI → keep it in Asana.** Don't force users into a sidecar UI for routine PM work.

2. **If it requires joining data across 3+ Asana projects → put it in the sidecar.** Asana has no native cross-project join.

3. **If it needs to be queried by a bot → put it (or a mirror) in the sidecar.** Bot latency and cost of Asana API calls makes it unsuitable as a real-time query layer.

4. **If it's a first-class relational link (e.g., PM → multiple needs → multiple projects → multiple capabilities) → sidecar-primary.** Asana custom fields can hold text references but cannot enforce referential integrity.

5. **If it's a structured historical record (decisions, status snapshots, audit log) → sidecar-only.** Asana is not an append-only record store.

6. **When in doubt, start with Asana and migrate to sidecar when pain is felt.** Avoid over-engineering the sidecar for data that's perfectly fine in Asana.

---

## 8. GID Cross-Reference Strategy

### 8.1 Core Principle

Every sidecar record that mirrors an Asana object must store the Asana GID. Every Asana task created via the sidecar should store the sidecar's internal ID in `external.id`.

### 8.2 GID Storage Schema

Each sidecar domain model should include:

```python
class AsanaMixin:
    asana_gid: str | None          # Asana GID of primary mapped object
    asana_project_gid: str | None  # Asana GID of containing project (if task)
    asana_external_id: str | None  # Value stored in Asana task external.id
    asana_synced_at: datetime | None  # Last successful sync timestamp
```

### 8.3 GID Lookup Pattern

```python
def resolve_asana_gid(domain_type: str, internal_id: str) -> str | None:
    """
    Look up the Asana GID for a given domain object.
    Returns None if not yet synced to Asana.
    """
    record = db.query(domain_type).filter_by(id=internal_id).first()
    return record.asana_gid if record else None
```

### 8.4 Orphan Detection

Daily consistency job:
1. Query all sidecar records with `asana_gid` set
2. Batch GET from Asana to verify objects still exist
3. Mark missing objects as `asana_orphaned=True`
4. Alert PMO if critical objects (milestones, PM Coverage tasks) are orphaned

### 8.5 GID Map for Key Singleton Projects

The following Asana project GIDs are fixed constants once workspace is set up. Store in sidecar config:

```python
ASANA_PROJECT_GIDS = {
    "pm_coverage_board": "<GID after creation>",
    "pm_needs": "<GID after creation>",
    "risks_and_blockers": "<GID after creation>",
    "decision_log": "<GID after creation>",
    "capability_registry": "<GID after creation>",
}
```

---

## 9. Naming Conventions

All object names should follow these conventions. The sidecar should validate and warn on violations.

| Object Type | Convention | Example |
|---|---|---|
| PM Onboarding project | `Onboarding - [PM Name] - [Strategy/Region]` | `Onboarding - Jane Doe - US Equities` |
| Capability Build project | `Capability - [Capability Name] - [Phase]` | `Capability - Security Master - Phase 1` |
| Remediation project | `Remediation - [Subject] - [Scope]` | `Remediation - Historical Data - Coverage Gaps` |
| Stabilization project | `Stabilization - [PM or Capability] - [Scope]` | `Stabilization - Jane Doe - Post Live` |
| PM Coverage task | `[PM Full Name]` | `Jane Doe` |
| PM Need task | `[PM] - [Category] - [Short Need]` | `Jane Doe - Execution - DMA via Goldman` |
| Milestone task | `[PM/Project Short Name] - [Checkpoint]` | `Jane Doe - Go Live Ready` |
| Risk/Blocker task | `[Scope] - [Short Problem]` | `Jane Doe - Historical Data Feed Delayed` |
| Decision task | `[Date YYYY-MM] - [Short Decision Title]` | `2026-03 - Broker Selection for APAC` |

---

## 10. Open Decisions

The following questions from the vision remain open and should be resolved before Phase 1 deployment.

| # | Question | Recommended Default | Impact |
|---|---|---|---|
| 1 | Will PM Coverage live primarily in Asana or sidecar? | Dual-homed (Asana visual, sidecar relational) | Determines sync complexity |
| 2 | How should cross-project dependencies be represented? | Sidecar tracks GID pairs; no Asana native cross-project deps in v1 | Scope of sidecar v1 |
| 3 | Will Decisions be first-class in Asana, sidecar-only, or hybrid? | Hybrid (Asana task for visibility, sidecar for full record) | Schema design |
| 4 | What auth model for bot actions? | Service account with scoped Asana PAT; human-in-the-loop for creates | Security |
| 5 | Slack or Teams first? | TBD by team — recommend Slack for faster iteration | Phase 3 scope |
| 6 | Approval required for project creation vs task creation? | Project creation = PMO lead approval; task creation = automated OK | Bot safety |
| 7 | Mandatory fields for PM Need intake? | PM, Title, Category, Urgency, Business Rationale, Desired By Date | Form design |
| 8 | Thresholds for risk/escalation alerts? | Blocker age > 7 days → alert; Critical severity → immediate alert | Alert tuning |
| 9 | Archival model for completed onboarding projects? | Archive in Asana after stabilization closure; sidecar retains full record | Workspace hygiene |
| 10 | Naming convention enforcement? | Soft enforcement via sidecar validation; Asana Rules for section routing | User experience |

---

## Appendix A: Asana Workspace Structure Summary

```
BAM Systematic Workspace
├── Portfolios
│   ├── Horizon: Current PM Support
│   ├── Horizon: Next-Gen PM Onboarding
│   └── Horizon: Long-Term Platform Buildout
│
├── Singleton Projects (always exist)
│   ├── PM Coverage Board         [Board layout, one task per PM]
│   ├── PM Needs                  [Kanban, intake form enabled]
│   ├── Risks & Blockers          [Kanban, severity sections]
│   ├── Decision Log              [List, pending/decided sections]
│   └── Capability Registry       [List, one task per capability]
│
├── Active Execution Projects (created from templates)
│   ├── Onboarding - [PM Name] - [Strategy]   [Timeline layout]
│   ├── Onboarding - [PM Name] - [Strategy]
│   ├── Capability - [Name] - [Phase]          [List layout]
│   ├── Stabilization - [Subject]              [List layout]
│   └── ...
│
└── Templates
    ├── PM Onboarding Template
    ├── Capability Build Template
    ├── Stabilization Template
    └── (PM Needs and Risks use singleton projects, not templates)
```

---

## Appendix B: Asana Custom Field Library — Full List

Complete list of all custom fields to create at organization level:

| Field Name | Type | Used In |
|---|---|---|
| Project Type | Enum | All projects |
| Priority | Enum | All projects, PM Needs |
| Health | Enum | All projects, PM Coverage |
| Confidence | Enum | All projects, Milestones |
| Owner Group | Text | All projects |
| Region | Enum | PM Coverage, All projects |
| Onboarding Stage | Enum | PM Coverage Board |
| Strategy Type | Text | PM Coverage Board |
| Team / Pod | Text | PM Coverage Board |
| Last Touchpoint | Date | PM Coverage Board |
| Need Category | Enum | PM Needs |
| Urgency | Enum | PM Needs, Risks & Blockers |
| Business Impact | Enum | PM Needs |
| Need Status | Enum | PM Needs |
| Resolution Path | Enum | PM Needs |
| PM | Text | PM Needs, Milestones |
| Requested By | Text | PM Needs |
| Linked Capability | Text | PM Needs |
| Desired By Date | Date | PM Needs |
| Milestone Status | Enum | Onboarding, Capability Build projects |
| Acceptance Criteria Confirmed | Checkbox | Milestone tasks |
| Gate Type | Enum | Milestone tasks |
| Item Type | Enum | Risks & Blockers |
| Severity | Enum | Risks & Blockers |
| Escalation Status | Enum | Risks & Blockers |
| Impacted PMs | Text | Risks & Blockers |
| Impacted Projects | Text | Risks & Blockers |
| Age (Days) | Number | Risks & Blockers |
| Resolution Date | Date | Risks & Blockers |
| Decision Status | Enum | Decision Log |
| Decision Date | Date | Decision Log |
| Approver | Text | Decision Log |
| Impacted Scope | Text | Decision Log |
| Capability Domain | Enum | Capability Registry |
| Maturity | Enum | Capability Registry |
| Roadmap Status | Enum | Capability Registry |
| Dependent PM Count | Number | Capability Registry |
