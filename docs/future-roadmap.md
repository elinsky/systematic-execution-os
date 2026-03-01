# BAM Systematic Execution OS — Future Roadmap

**Version:** 1.0
**Date:** 2026-03-01

This document records what is deferred from v1, why it was deferred, and what the intended design is when each item is built. It is the authoritative reference for "what's next" so that v2 engineering does not need to re-derive scope from first principles.

---

## Table of Contents

1. [Phased Delivery Summary](#1-phased-delivery-summary)
2. [v1.5 — Hardening and Operational Reliability](#2-v15--hardening-and-operational-reliability)
3. [v2 — Capability Model and Richer Intelligence](#3-v2--capability-model-and-richer-intelligence)
4. [Phase 3 — Chat and Agent Layer](#4-phase-3--chat-and-agent-layer)
5. [Phase 4 — Intelligence and Optimization](#5-phase-4--intelligence-and-optimization)
6. [Deferred Features Reference Table](#6-deferred-features-reference-table)
7. [Open Questions for v2 Planning](#7-open-questions-for-v2-planning)

---

## 1. Phased Delivery Summary

| Phase | Primary Outcome | Status |
|-------|----------------|--------|
| **Phase 1** | Asana workspace — project templates, custom fields, PM Needs intake, PM Coverage board, operating cadences | Design complete |
| **Phase 2 (v1)** | Python sidecar — domain models, persistence, REST API, Asana sync, scheduled automation | In progress |
| **v1.5** | Hardening — Alembic migrations, enhanced sync reliability, PM health watch automation, onboarding state guard | Planned |
| **v2** | Capability model, initiative/portfolio view, cross-project dependency graph, richer decision registry | Planned |
| **Phase 3** | Chat/agent layer — Slack or Teams bot with safe query and create commands | Planned |
| **Phase 4** | Intelligence layer — PM health scoring, launch-readiness scoring, capability gap ranking | Future |

---

## 2. v1.5 — Hardening and Operational Reliability

These items were flagged as P2 in `design-review.md`. They are not blocking v1 launch but should be delivered shortly after the system is in production use.

### 2.1 Alembic Database Migrations

**Why deferred:** The v1 schema evolves rapidly during early development. Adding Alembic overhead before the schema stabilizes creates churn.

**When to add:** Once the first PM has completed onboarding through the system end-to-end and no major schema changes are expected.

**Design:** Standard Alembic setup with `migrations/versions/`. Migration scripts should be reviewed by at least one engineer before applying to production. Add a `scripts/migrate.py` helper that validates the DB state before running migrations.

### 2.2 PM Health Watch Automation

**Why deferred:** The daily digest job covers the most critical alerts. Adding a second automation job doubles the operational surface for v1.

**Planned design:**
- New `automation/pm_health_watch.py` scheduled job (configurable cron; default: every 4 hours during business hours)
- Triggers for: PM with ≥ 3 open high/critical needs; PM with no touchpoint in > 14 days; PM health_status = red for > 3 days without an escalation
- Sends alert to coverage owner (Slack DM in Phase 3; email or log entry in v1.5)

### 2.3 Onboarding Stage Transition Guard

**Why deferred:** Requires `pm_coverage_service.py` to be implemented first.

**Planned design:** `validate_onboarding_transition(current_stage, new_stage)` in `pm_coverage_service.py`:
- Enforces the valid transition graph
- Logs all backwards transitions as `INFO` events with full context
- On backwards transition (e.g., `uat → onboarding_in_progress`): automatically opens a `RiskBlocker` with severity `high`, title `[PM Name] — Stage Regression: [stage] → [stage]`, and `impacted_pm_ids` set
- Rejects skipping multiple stages without an `override=True` flag

### 2.4 DB-Level Unique Constraint on Job Run Deduplication

**Why deferred:** Schema will be finalized before adding constraints.

**Planned design:** Add a `UNIQUE(job_name, execution_date)` constraint to the `job_run` table. This prevents duplicate job runs on multi-instance deployments atomically. Remove the application-level deduplication check once the DB constraint is in place (the DB check is authoritative).

### 2.5 PM Need Archival Policy

**Planned design:** Delivered PM Needs are archived in Asana after 90 days (`mark_as_archived` via Asana API). Retained in sidecar indefinitely with `archived_at` timestamp. Excluded from active queries by default (`WHERE archived_at IS NULL`). A new query param `include_archived=true` shows archived needs for historical analysis.

### 2.6 Webhook Secret Rotation Procedure

**Planned design:** Document and test a zero-downtime rotation:
1. Add a `ASANA_WEBHOOK_SECRET_PREVIOUS` env var that the sidecar accepts for a 5-minute overlap window
2. Register new webhook with new secret
3. Update `.env` with new secret
4. After 5 minutes, remove old secret env var

The sidecar webhook handler should check both secrets during the overlap window.

### 2.7 Separate API Keys Per Consumer

**Planned design:** Issue separate API keys for: (a) internal scheduled automation jobs, (b) any external bot/client. Each key has a `source_label` (e.g., `scheduler`, `slack-bot`, `admin`). Every write operation in the audit log includes `source_label`. Add a `GET /admin/audit-log` endpoint filtered by source.

---

## 3. v2 — Capability Model and Richer Intelligence

### 3.1 Full Capability Model

**Why deferred:** Building a meaningful capability model requires 3–6 months of PM Need data to cluster needs into genuine capability gaps. Building it before that data exists produces an empty model that nobody uses.

**Planned design:**

```python
class Capability(SidecarBaseModel):
    capability_id: str
    name: str
    domain: str           # market_data, execution, research, infra, ops
    owner_team: str
    current_maturity: CapabilityMaturity
    description: str
    known_gaps: list[str]
    dependent_pm_ids: list[str]
    linked_project_ids: list[str]
    roadmap_status: RoadmapStatus
```

The stub is already in `sidecar/models/capability.py` with nullable FK stubs in `PMNeed.mapped_capability_id` and `Project.linked_capability_ids`. No schema migration is needed to activate the capability model — only the service and API layers need to be built.

**New API endpoints:**
- `GET /capabilities` — list all capabilities with maturity and PM impact count
- `GET /capabilities/{capability_id}` — detail with linked PM needs and projects
- `GET /operating-review/capability-gaps` — cluster unmet PM needs by capability area

### 3.2 Initiative / Portfolio Model

**Why deferred:** Requires stable capability model first; Asana Portfolios can cover this manually until then.

**Planned design:** Add an `Initiative` model that groups projects under one of the three business horizons (`short_term`, `medium_term`, `long_term`). Mapped to Asana Portfolios. The sidecar adds cross-initiative health rollups that Asana Portfolios cannot produce natively.

### 3.3 Cross-Project Dependency Graph

**Why deferred:** High engineering complexity; only valuable once basic PM/project data is clean and stable.

**Planned design:** Add a `Dependency` model:

```python
class Dependency(SidecarBaseModel):
    dependency_id: str
    predecessor_type: str         # project, milestone, deliverable, capability
    predecessor_id: str
    successor_type: str
    successor_id: str
    dependency_type: str          # finish_to_start, start_to_start, etc.
    owner_of_predecessor: str
    risk_if_missed: str
    current_confidence: MilestoneConfidence
```

New endpoint: `GET /dependencies?project_id={id}` returns cross-project dependencies for a project, including predecessor status and confidence.

### 3.4 Full SyncState Machine

**Why deferred:** Adds state machine complexity not justified at v1 scale.

**Planned design:** Replace `asana_gid + asana_synced_at` with a full `SyncState` enum: `synced`, `pending_push`, `pending_pull`, `conflict`, `asana_deleted`. Add a `conflict_resolver.py` service that handles the `conflict` state using the "Asana wins" rule for shared fields. Add alerting when `asana_deleted` state is detected on critical objects.

### 3.5 PM Duplicate Detection

**Why deferred:** Requires triage tooling to be built first.

**Planned design:** Add `possible_duplicate_of: Optional[str]` (FK to another `PMNeed`) to the `PMNeed` schema. In v2, build a similarity check: on new PM Need creation, query existing needs for the same PM + same category, compute title similarity score, and flag as potential duplicate if score exceeds threshold. Present candidates to the triage operator.

### 3.6 Stakeholder Map

**Why deferred:** Low urgency in v1; a YAML config file covers the escalation notification use case.

**Planned design (v2):**

```python
class Stakeholder(SidecarBaseModel):
    stakeholder_id: str
    name: str
    team: str
    function: str                 # tech, business, ops, pm
    region: str
    relationship_owner: str       # BAM Systematic staff responsible
    role_in_delivery: str
    meeting_cadence: str
    linked_project_ids: list[str]
    slack_handle: Optional[str]
    email: Optional[str]
```

**v1 substitute:** A `config/stakeholders.yaml` file with team names and Slack handles for the escalation notification system.

### 3.7 Richer Decision Registry

**Why deferred:** Lightweight decision tracking is sufficient for v1; full structured registry adds complexity.

**v1:** Full decision model already implemented in `sidecar/models/decision.py` with `options_considered`, `rationale`, `impacted_artifacts`, and `DecisionResolve`. No additional model work needed.

**v2 additions:**
- Searchable full-text search across decision content
- Decision templates for common decision types (broker selection, capability phasing, PM scope)
- `GET /decisions/search?q={query}` endpoint
- Link decisions to Asana projects/tasks via `asana_gid`

---

## 4. Phase 3 — Chat and Agent Layer

### 4.1 Bot Architecture

The chat layer sits on top of the sidecar REST API. It does not have direct database access. All bot-initiated actions flow through the API, enforcing the same validation and audit logging as human-initiated API calls.

```
User (Slack/Teams)
  → Bot adapter (Slack API / Teams API)
  → Intent parser (natural language → structured command)
  → Sidecar REST API (authenticated with bot API key)
  → Asana + SQLite (via sidecar services)
```

**Adapter pattern:** The bot adapter is pluggable. The sidecar exposes a well-defined REST API that either a Slack bot or a Teams bot can call. The first implementation is Slack (per `design-decisions.md` open question #5). Teams support is added in a later sub-phase by implementing the same adapter interface.

### 4.2 Bot Safety Principles

All bot-initiated writes must:
1. Collect all required fields via multi-turn conversation before writing
2. Present a confirmation summary before any create or high-impact update
3. Post to the sidecar REST API (no direct DB access)
4. Log all actions with `source_label = "slack-bot"` in the audit trail
5. Return the created/updated record summary and Asana deep link after every write
6. Never create free-form unstructured objects — every write routes through a template

**Bot-allowed creates (no human escalation required):**
- `POST /pm-needs`
- `POST /risks`
- `POST /decisions`
- `PATCH /risks/{risk_id}` (status/escalation updates)
- `PATCH /pm-coverage/{pm_id}` (non-stage/health fields only)

**Human confirmation required before bot writes:**
- `POST /pm-coverage` (creates an entire PM onboarding track)
- `POST /pm-onboarding` (composite endpoint: PM Coverage + Asana project template)
- `PATCH /pm-coverage/{pm_id}` with `onboarding_stage` change
- Any delete or archive operation

### 4.3 Planned Bot Commands

**Read (Phase 3.0):**
- `/pm-status [PM name]` — PM coverage snapshot
- `/project-status [project]` — project detail with blockers and milestones
- `/at-risk` — cross-portfolio at-risk summary
- `/decisions` — pending decisions list
- `/pm-needs [PM or category]` — open PM needs
- `/weekly-review` — auto-generate operating review agenda

**Create (Phase 3.1 — guarded writes):**
- `/new-pm [PM name]` — create PM Coverage Record + onboarding project
- `/new-need [PM name]` — log a PM Need
- `/new-blocker [project]` — open a RiskBlocker
- `/new-decision [title]` — create a Decision record

**Update (Phase 3.1):**
- `/escalate-blocker [risk ID]`
- `/update-pm-stage [PM name] [stage]`
- `/update-health [project] [status]`

### 4.4 MCP Tool Layer (Phase 3+)

For integration with AI assistants (e.g., Claude Code, internal AI tools), expose the sidecar API as an MCP (Model Context Protocol) tool layer. Each REST endpoint maps to an MCP tool with structured input/output schemas. The MCP layer enforces the same safety rules as the bot layer.

---

## 5. Phase 4 — Intelligence and Optimization

These features require at least 6 months of clean data from v1/v2 before they can produce reliable signals.

### 5.1 PM Health Heuristics

**Description:** A composite score derived from: onboarding stage velocity (are they moving through stages on schedule?), open need count and age, blocker frequency and severity, touchpoint recency, and PM sentiment (manually entered, or inferred from meeting notes in a future LLM integration).

**Output:** `pm_health_score: float` (0.0–1.0) + `health_signals: list[str]` explaining the score. Surface in PM View and Executive Summary View.

### 5.2 Launch-Readiness Scoring

**Description:** For PMs approaching go-live, a readiness score based on: % of pre-go-live milestones complete, open blocker count by severity, acceptance criteria completeness, UAT status, and time remaining.

**Output:** `readiness_score: float` + `readiness_checklist: list[ReadinessItem]` with pass/fail per item. Surface in Milestone Readiness Review and Executive Summary View.

### 5.3 Capability Gap Ranking

**Description:** Automatically cluster PM Needs by category and domain, identify which capability gaps are blocking the most PMs or the highest-priority PMs, and rank capability investment opportunities by business leverage.

**Output:** `GET /capabilities/gap-ranking` returning capabilities sorted by `pm_impact_score` (function of: number of blocked PMs, their combined AUM/priority, and time the gap has been open).

### 5.4 Blocker Aging Prioritization

**Description:** A predictive model that learns from historical blocker resolution patterns to surface blockers most likely to escalate or miss milestones if not addressed this week.

**Output:** `GET /risks?predicted_risk=true` — blockers sorted by predicted escalation probability.

### 5.5 Recurring Pattern Detection

**Description:** Identify recurring PM needs (same PM keeps raising the same type of ask after each resolution), recurring blocker patterns (same team or capability area appears in blockers repeatedly), and milestone slip patterns (certain milestone types reliably slip by certain amounts).

**Output:** `GET /operating-review/patterns` returning detected patterns with evidence and suggested structural fixes.

---

## 6. Deferred Features Reference Table

| Feature | Deferred to | Reason | Pre-conditions |
|---------|------------|--------|----------------|
| Alembic migrations | v1.5 | Schema too volatile in v1 | Schema stabilizes after first PM goes live |
| PM health watch automation job | v1.5 | Doubles operational surface; daily digest covers critical alerts | Daily digest running stably |
| Onboarding stage transition guard | v1.5 | Requires pm_coverage_service.py | Service layer implemented |
| DB unique constraint on job_run | v1.5 | Schema finalization | Schema stable |
| PM Need archival policy | v1.5 | Not urgent until need volume accumulates | PM Needs in production use |
| Separate API keys per consumer | v1.5 | Single key is sufficient for internal-only v1 | Bot or external consumer added |
| Full SyncState machine | v2 | Over-engineered for v1; requires understanding real conflict patterns | 6+ months of sync operational data |
| external.id field on Asana tasks | v2 | Adds write surface; not worth complexity | Write permission confirmed for service account |
| Capability model | v2 | Requires 3–6 months PM Need data to cluster meaningfully | v1 PM Need data populated |
| Initiative / portfolio model | v2 | Requires capability model | Capability model complete |
| Cross-project dependency graph | v2 | High complexity; tackle after PM/project data stable | v1 data model stable |
| Stakeholder Map | v2 | Low urgency; YAML config covers v1 escalation use case | Stakeholder patterns understood |
| Full decision registry (search, templates) | v2 | Lightweight registry sufficient for v1 | Decision volume accumulates |
| PM duplicate detection | v2 | Requires triage tooling first | v1 triage workflow in use |
| Chat / Slack bot | Phase 3 | REST API must be stable and well-tested | Phase 2 API stable and tested |
| Teams adapter | Phase 3.1 | Second after Slack | Slack bot operational |
| MCP tool layer | Phase 3+ | Requires stable API and bot patterns | Phase 3 bot operational |
| PM happiness heuristics | Phase 4 | Requires 6+ months of clean data | v2 data model in use |
| Launch-readiness scoring | Phase 4 | Requires milestone/UAT data history | v1 onboarding data |
| Capability gap ranking | Phase 4 | Requires capability model + PM Need history | v2 capability model stable |
| Blocker aging ML | Phase 4 | Requires blocker resolution history | 12+ months of data |
| Recurring pattern detection | Phase 4 | Requires sufficient data volume | 12+ months of multi-PM data |
| Full autonomous bot actions | Out of scope | Violates bot safety principles | Never for create/delete |
| Direct trading system integration | Out of scope | Not in scope for this platform | — |

---

## 7. Open Questions for v2 Planning

These questions should be answered before v2 scoping begins:

1. **Capability ownership:** Who owns each capability record — a specific tech team, a PMO lead, or a shared ownership model? This determines the write path for capability updates.

2. **Initiative definition:** How granular should Initiative objects be? Should each of the three business horizons (current PM support, next-gen onboarding, long-term platform buildout) be one Initiative each, or should Initiatives map to specific programs within each horizon?

3. **Dependency confidence:** For cross-project dependencies, what does "current_confidence" mean operationally? Should it be set by the predecessor owner or the successor owner?

4. **Bot approval gate:** For Phase 3, who is the human approver for bot-initiated PM Coverage Record creation? Is it the coverage owner, the business lead, or any authorized user?

5. **PM sentiment signal:** For Phase 4 health heuristics, should PM sentiment be captured as a structured field (1–5 scale set during touchpoint meetings) or inferred from unstructured meeting notes via LLM? The structured field is simpler but requires discipline; the LLM approach is more passive but harder to trust.

6. **Data retention for intelligence features:** Phase 4 pattern detection and scoring require historical data. What is the retention policy for archived PM Needs, completed milestones, and resolved blockers? Permanent retention in sidecar is the simplest policy but may create compliance considerations.

7. **Postgres migration trigger:** What operational signal should trigger migration from SQLite to Postgres? Suggested thresholds: > 5 concurrent API users, > 10,000 rows in any table, or first horizontal scaling requirement (multiple sidecar instances).
