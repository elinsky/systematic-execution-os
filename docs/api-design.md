# BAM Systematic Execution OS — API Design

> Document version: 1.0
> Date: 2026-03-01
> Status: Initial design

---

## Overview

The sidecar exposes a REST API built with FastAPI. This document defines:
1. REST endpoint catalog with request/response shapes
2. Query patterns the system must support
3. Bot command spec for the future chat layer (Phase 3)

All endpoints return JSON. Validation errors return HTTP 422. Auth in v1 is API key via `X-API-Key` header.

---

## Base URL

```
http://localhost:8000/api/v1
```

---

## Common Response Patterns

### Success (single object)
```json
{
  "data": { ... },
  "request_id": "req-abc-123"
}
```

### Success (list)
```json
{
  "data": [ ... ],
  "total": 42,
  "request_id": "req-abc-123"
}
```

### Error
```json
{
  "error": "not_found",
  "message": "PM Coverage record not found: pm-jane-doe",
  "request_id": "req-abc-123"
}
```

### HTTP Status Codes
| Code | Meaning |
|---|---|
| 200 | Success (GET, PATCH) |
| 201 | Created (POST) |
| 400 | Bad request (malformed payload) |
| 401 | Unauthorized (missing/invalid API key) |
| 404 | Not found |
| 409 | Conflict (idempotency duplicate) |
| 422 | Validation error (Pydantic) |
| 503 | Service unavailable (DB or Asana unreachable) |

---

## 1. PM Coverage Endpoints

### `GET /pm-coverage`

List all PM Coverage Records.

**Query params:**
| Param | Type | Description |
|---|---|---|
| `stage` | OnboardingStage | Filter by onboarding stage |
| `health` | HealthStatus | Filter by health status |
| `coverage_owner` | str | Filter by assigned coverage owner |
| `region` | str | Filter by region |

**Response:** List of `PMCoverageRecord`

---

### `GET /pm-coverage/{pm_id}`

Full PM status summary — the answer to "What's the status of PM X?"

**Response:**
```json
{
  "pm": { ...PMCoverageRecord... },
  "open_needs": [ ...PMNeed[] (top 5 by urgency)... ],
  "active_blockers": [ ...RiskBlocker[] (open, sorted by severity)... ],
  "upcoming_milestones": [ ...Milestone[] (next 3 by target_date)... ],
  "recent_status_update": { ...StatusUpdate or null... }
}
```

---

### `POST /pm-coverage`

Create a new PM Coverage Record. Creates a summary task in Asana.

**Request body:** `PMCoverageCreate`

**Response:** `PMCoverageRecord` (201)

---

### `PATCH /pm-coverage/{pm_id}`

Partial update to a PM Coverage Record.

**Request body:** `PMCoverageUpdate`

**Response:** `PMCoverageRecord` (200)

---

## 2. PM Need Endpoints

### `GET /pm-needs`

List PM Needs.

**Query params:**
| Param | Type | Description |
|---|---|---|
| `pm_id` | str | Filter by PM |
| `status` | NeedStatus | Filter by status |
| `category` | NeedCategory | Filter by category |
| `urgency` | Urgency | Filter by urgency |
| `unmet_only` | bool | If true, exclude delivered/cancelled |

**Response:** List of `PMNeed` sorted by urgency desc, date_raised asc

---

### `GET /pm-needs/{pm_need_id}`

Get a single PM Need.

**Response:** `PMNeed`

---

### `POST /pm-needs`

Create a new PM Need. Creates Asana intake task + sidecar record.

**Request body:** `PMNeedCreate`

**Response:** `PMNeed` (201)

---

### `PATCH /pm-needs/{pm_need_id}`

Update PM Need status, routing, or metadata.

**Request body:** `PMNeedUpdate`

**Response:** `PMNeed` (200)

---

## 3. Project Endpoints

### `GET /projects`

List projects.

**Query params:**
| Param | Type | Description |
|---|---|---|
| `pm_id` | str | Filter by PM |
| `status` | ProjectStatus | Filter by status |
| `health` | HealthStatus | Filter by health |
| `project_type` | ProjectType | Filter by type |
| `at_risk_only` | bool | If true, return only at_risk or red health |

**Response:** List of `Project`

---

### `GET /projects/{project_id}`

Project detail including milestones, blockers, decisions.

**Response:**
```json
{
  "project": { ...Project... },
  "milestones": [ ...Milestone[]... ],
  "open_risks": [ ...RiskBlocker[] (open only)... ],
  "pending_decisions": [ ...Decision[] (pending only)... ],
  "overdue_deliverables": [ ...Deliverable[] (past due_date, not complete)... ]
}
```

---

### `GET /projects/{project_id}/milestones`

List milestones for a project.

**Response:** List of `Milestone` sorted by target_date

---

## 4. Milestone Endpoints

### `GET /milestones`

List milestones.

**Query params:**
| Param | Type | Description |
|---|---|---|
| `project_id` | str | Filter by project |
| `status` | MilestoneStatus | Filter by status |
| `at_risk_only` | bool | at_risk or low confidence |
| `due_within_days` | int | Milestones due within N days |

**Response:** List of `Milestone`

---

### `PATCH /milestones/{milestone_id}`

Update milestone status, confidence, or acceptance criteria.

**Request body:** `MilestoneUpdate`

**Response:** `Milestone` (200)

---

## 5. Risk / Blocker Endpoints

### `GET /risks`

List risks, blockers, and issues.

**Query params:**
| Param | Type | Description |
|---|---|---|
| `risk_type` | RiskType | Filter by type |
| `severity` | RiskSeverity | Filter by severity |
| `status` | RiskStatus | Filter to open/in_mitigation/etc. |
| `pm_id` | str | Filter by impacted PM |
| `project_id` | str | Filter by impacted project |
| `open_only` | bool | Default true; exclude resolved/closed |
| `escalated_only` | bool | Filter to escalated |
| `older_than_days` | int | Blockers open longer than N days |

**Response:** List of `RiskBlocker` sorted by severity desc, age desc

---

### `POST /risks`

Create a new risk/blocker. Creates Asana task + sidecar record.

**Request body:** `RiskCreate`

**Response:** `RiskBlocker` (201)

---

### `PATCH /risks/{risk_id}`

Update risk status, severity, escalation state.

**Request body:** `RiskUpdate`

**Response:** `RiskBlocker` (200)

---

## 6. Decision Endpoints

### `GET /decisions`

List decisions.

**Query params:**
| Param | Type | Description |
|---|---|---|
| `status` | DecisionStatus | Filter by status |
| `pm_id` | str | Decisions impacting a PM |
| `project_id` | str | Decisions impacting a project |
| `pending_only` | bool | Default false |
| `older_than_days` | int | Pending decisions older than N days |

**Response:** List of `Decision` sorted by decision_date desc (or created_at for pending)

---

### `POST /decisions`

Create a new decision record (initially in PENDING status).

**Request body:** `DecisionCreate`

**Response:** `Decision` (201)

---

### `POST /decisions/{decision_id}/resolve`

Record the outcome of a pending decision.

**Request body:** `DecisionResolve`

**Response:** `Decision` (200)

---

## 7. Operating Review Endpoints

These are the high-value aggregation endpoints that power the weekly operating cadence.

### `GET /operating-review/agenda`

Auto-generate the weekly operating review agenda.

**Response:**
```json
{
  "generated_at": "2026-03-01T08:00:00Z",
  "overdue_deliverables": [
    { "project": "Onboarding - PM Jane Doe - US Equities", "title": "...", "owner": "...", "days_overdue": 3 }
  ],
  "milestone_slips": [
    { "project": "...", "milestone": "Go-Live Ready", "original_date": "2026-02-28", "days_slipped": 1, "confidence": "low" }
  ],
  "pms_at_risk": [
    { "pm_name": "Jane Doe", "stage": "uat", "health": "red", "top_blockers": [...] }
  ],
  "open_blockers": [
    { "title": "...", "severity": "critical", "age_days": 8, "owner": "..." }
  ],
  "pending_decisions": [
    { "title": "...", "age_days": 5, "approvers": [...] }
  ]
}
```

---

### `GET /operating-review/at-risk-pms`

PMs with active blockers, slipping milestones, or red/yellow health.

**Response:** List of PM summary objects with risk signals

---

### `GET /operating-review/pm-needs-summary`

Cross-PM view of PM needs — the answer to "What are the top PM needs across the business?"

**Response:**
```json
{
  "by_category": { "market_data": 5, "execution": 3, ... },
  "unmet_by_pm": [
    { "pm_name": "...", "open_count": 3, "oldest_days": 45 }
  ],
  "oldest_unresolved": [ ...top 5 PMNeed by date_raised... ]
}
```

---

### `GET /operating-review/milestone-calendar`

Upcoming milestones across all active projects.

**Query params:** `days_ahead` (default 30)

**Response:** List of `Milestone` with project context, sorted by target_date

---

## 8. Sync / Webhook Endpoints

### `POST /sync/webhook`

Receives Asana webhook events.

**Headers:**
- `X-Hook-Secret`: Asana HMAC signature

**Request body:** Asana webhook event payload

**Response:** `200 OK` always (to prevent Asana retry storms). Errors are logged internally.

---

### `POST /sync/pull`

Manually trigger a full pull sync from Asana (admin use).

**Query params:** `entity_type` (optional — sync specific type only)

**Response:**
```json
{ "synced": 42, "skipped": 3, "errors": 0, "duration_ms": 1240 }
```

---

## 9. Health Endpoint

### `GET /health`

Liveness and readiness check.

**Response:**
```json
{
  "status": "ok",
  "db": "connected",
  "asana": "reachable",
  "scheduler": "running"
}
```

---

## Query Patterns (Non-Meeting Use Cases)

The following maps the vision.md query use cases to the API endpoints that fulfill them.

| Vision query | Endpoints |
|---|---|
| "What's the status of PM X?" | `GET /pm-coverage/{pm_id}` |
| "What is delaying go-live for PM Y?" | `GET /pm-coverage/{pm_id}` → filter active_blockers + upcoming milestones |
| "What are the top PM needs across the business?" | `GET /operating-review/pm-needs-summary` |
| "Which projects are at risk this month?" | `GET /projects?at_risk_only=true` + `GET /milestones?due_within_days=30&at_risk_only=true` |
| "Create a new PM onboarding project for [PM]" | `POST /pm-coverage` + `POST /projects` (with template) |
| "Prepare tomorrow's weekly operating review" | `GET /operating-review/agenda` |
| "What decisions are pending right now?" | `GET /decisions?pending_only=true` |
| "Which capabilities are creating the most drag?" | `GET /operating-review/pm-needs-summary` grouped by category (v2 with Capability model) |

---

## Bot Command Spec (Phase 3 — Slack/Teams)

These commands will be implemented when the chat layer is built. The spec is defined here so the REST API can be validated against it.

### Read Commands

#### `/pm-status [PM name]`
**Intent:** What's the status of PM X?
**Maps to:** `GET /pm-coverage/{pm_id}`
**Output:** Formatted summary card with stage, health, top needs, top blockers, next milestone

---

#### `/project-status [project name or ID]`
**Intent:** What's blocking project Y?
**Maps to:** `GET /projects/{project_id}`
**Output:** Project card with next milestones, overdue items, open blockers, pending decisions

---

#### `/at-risk`
**Intent:** What's at risk this week?
**Maps to:** `GET /operating-review/at-risk-pms` + `GET /projects?at_risk_only=true`
**Output:** Bulleted list of at-risk PMs and projects with brief context

---

#### `/decisions`
**Intent:** What decisions are pending?
**Maps to:** `GET /decisions?pending_only=true`
**Output:** List of pending decisions with age, approvers, impacted artifacts

---

#### `/pm-needs [optional: PM name or category]`
**Intent:** Show open PM needs
**Maps to:** `GET /pm-needs?unmet_only=true` (filtered)
**Output:** Table of open needs sorted by urgency

---

#### `/weekly-review`
**Intent:** Prepare this week's operating review
**Maps to:** `GET /operating-review/agenda`
**Output:** Structured agenda card with sections for overdue items, slips, at-risk PMs, blockers, decisions

---

### Create Commands

#### `/new-pm [PM name]`
**Intent:** Create a new PM onboarding project
**Bot flow:**
1. Bot prompts for: PM name, strategy type, region, coverage owner, go-live target
2. Bot confirms: "Create PM Coverage Record for [name] + onboarding project?"
3. On confirm: `POST /pm-coverage` → `POST /projects` (onboarding template)
4. Bot returns: PM record link + Asana project link
**Required inputs:** pm_name, coverage_owner, go_live_target_date

---

#### `/new-need [PM name]`
**Intent:** Log a new PM need
**Bot flow:**
1. Bot prompts for: PM, title, category, urgency, requested_by
2. Bot confirms: "Log PM Need: [title] for [PM]?"
3. On confirm: `POST /pm-needs`
4. Bot returns: Need ID + Asana task link
**Required inputs:** pm_id, title, category, urgency, requested_by

---

#### `/new-blocker [project or PM]`
**Intent:** Open a blocker
**Bot flow:**
1. Bot prompts for: title, severity, impacted PM/project, owner
2. Bot confirms: "Open blocker: [title]?"
3. On confirm: `POST /risks` with risk_type=blocker
4. Bot returns: Risk ID + Asana task link

---

#### `/new-decision [title]`
**Intent:** Create a decision record
**Bot flow:**
1. Bot prompts for: title, context, options considered, approvers
2. Creates with status=PENDING
3. On confirm: `POST /decisions`
4. Bot returns: Decision ID

---

### Update Commands

#### `/escalate-blocker [risk ID]`
**Intent:** Mark a blocker as escalated
**Maps to:** `PATCH /risks/{risk_id}` with `escalation_status=escalated`
**Bot flow:** Confirm then patch; no additional inputs required

---

#### `/update-pm-stage [PM name] [stage]`
**Intent:** Move PM to a new onboarding stage
**Maps to:** `PATCH /pm-coverage/{pm_id}` with new `onboarding_stage`
**Bot flow:** Bot validates stage transition, confirms, patches

---

#### `/update-health [project] [green|yellow|red]`
**Intent:** Update project health
**Maps to:** `PATCH /projects/{project_id}` with new `health`
**Bot flow:** Confirm then patch

---

## Safe Create Flow (All Bot Write Commands)

Per the vision's bot principles, all write operations follow this flow:

```
1. Bot collects required inputs (multi-turn prompt)
2. Bot validates against schema (Pydantic, required fields)
3. Bot presents confirmation summary:
   "About to create: [type] - [title]. Confirm? [Yes/No]"
4. On Yes: POST/PATCH to sidecar API
5. Sidecar creates/updates in Asana (+ sidecar DB)
6. Bot returns: created record summary + Asana deep link
7. Sidecar logs action to audit table with user ID, timestamp, payload hash
```

High-impact actions (project creation, milestone update) require explicit confirm.
Low-impact actions (status update on a single field) may auto-confirm if inputs are unambiguous.

---

## API Authentication (V1)

**Method:** API key via `X-API-Key` header.

V1 uses a single shared API key stored in `.env`. All callers (internal services, future bot) use the same key.

V2+ will introduce OAuth 2.0 with per-user scopes:
- `read:all` — read-only access to all endpoints
- `write:needs` — create/update PM needs
- `write:projects` — create/update projects
- `write:risks` — create/update risks/blockers
- `admin` — full access including sync triggers

---

## Rate Limiting (V1)

No rate limiting in v1 (internal service, low traffic). V2 should add per-key rate limits before exposing to bot users.
