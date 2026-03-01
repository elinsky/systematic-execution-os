# BAM Systematic Execution OS — Architecture

> Document version: 1.0
> Date: 2026-03-01
> Status: Initial design — pending team review

---

## 1. System Architecture Overview

The system consists of three tiers that build on each other:

```
┌─────────────────────────────────────────────────────────────────────┐
│  TIER 3: Chat / Agent Layer (Phase 3 — deferred)                    │
│  Slack or Teams bot  →  MCP tool layer  →  Python sidecar API       │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ HTTP (REST)
┌───────────────────────────────▼─────────────────────────────────────┐
│  TIER 2: Python Sidecar Service                                      │
│                                                                      │
│  FastAPI app                                                         │
│  ├── /api          REST endpoints (query, create, update)            │
│  ├── /automation   Scheduled jobs (digests, alerts, prep)            │
│  ├── /sync         Asana webhook receiver + outbound sync            │
│  └── /services     Business logic (PM coverage, needs routing, etc.) │
│                                                                      │
│  SQLite DB (v1)     Pydantic v2 models     APScheduler jobs          │
└─────────────┬─────────────────────────────────────┬─────────────────┘
              │ Asana REST API                       │ Asana Webhooks
┌─────────────▼─────────────────────────────────────▼─────────────────┐
│  TIER 1: Asana Workspace                                             │
│                                                                      │
│  Projects / Tasks / Milestones / Custom Fields / Portfolios          │
│  Templates / Status Updates / Dependencies / Forms                   │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Summary

| Component | Role | Phase |
|---|---|---|
| Asana workspace | System of record for active project execution | Phase 1 |
| Python sidecar (FastAPI) | Cross-project intelligence, automation, query API | Phase 2 |
| SQLite database | Sidecar persistence for enriched records and derived state | Phase 2 |
| APScheduler | Background job runner for digests, alerts, review prep | Phase 2 |
| Webhook receiver | Ingests Asana change events to keep sidecar in sync | Phase 2 |
| Chat/bot adapter | Conversational create/query interface for Slack or Teams | Phase 3 |

### Rationale

Asana is an enterprise-grade work management platform with strong native task/project/milestone primitives. Building on top of it — rather than replacing it — avoids reinventing project management and keeps adoption low for non-technical users. The sidecar exists exclusively to cover Asana's weaknesses: cross-project relational modeling, enriched PM records, decision registry, rollup views, and the bot query layer.

---

## 2. Source-of-Truth Rules

These rules are unambiguous and non-negotiable. Violating them creates the dual-write ambiguity the vision explicitly warns against.

### Master Table

| Data / Artifact | Source of Truth | Direction | Notes |
|---|---|---|---|
| Projects (structure, status) | **Asana** | Asana → sidecar read | Sidecar stores `asana_gid` reference only |
| Tasks and deliverables | **Asana** | Asana → sidecar read | Sidecar does not replicate task bodies |
| Milestones | **Asana** | Asana → sidecar read | Sidecar stores GID + computed fields |
| Day-to-day ownership / due dates | **Asana** | Asana → sidecar read | |
| Project status updates | **Asana** | Asana → sidecar read | |
| Dependencies (task-level) | **Asana** | Asana → sidecar read | |
| PM Coverage Records | **Sidecar** | Sidecar → writes to Asana summary task | Richer fields than Asana can store natively |
| PM Needs | **Hybrid** | Asana task is created first; sidecar adds metadata and links | Asana is operational store; sidecar holds relational links |
| Capability records | **Sidecar** | Sidecar creates linked Asana project if needed | |
| Decision registry | **Sidecar** | Sidecar-only; no Asana representation required | Decisions need searchable history |
| Cross-project dependencies | **Sidecar** | Sidecar-only; displayed in query layer | Asana cannot cross-link cleanly |
| Risk/Blocker records | **Hybrid** | Asana task + sidecar enrichment (severity, impacted PMs) | |
| Automation state (job runs, alerts) | **Sidecar** | Sidecar-only | |
| Bot audit log | **Sidecar** | Sidecar-only | |
| Asana custom field IDs / workspace config | **Config file** | Read-only at runtime | See Section 7 |

### Sync Rules

1. **Every sidecar record that mirrors an Asana object must store `asana_gid`** as a non-nullable foreign key.
2. **Writes are idempotent** — all create/update operations check for existing records before writing. Use `asana_gid` as the idempotency key for Asana objects.
3. **Sidecar never deletes from Asana** — it may archive or soft-delete internally, but destructive Asana actions require explicit human confirmation.
4. **Conflict resolution is Asana-wins** for fields that exist in both stores. If a field is sidecar-only, sidecar-wins.
5. **Webhook-triggered syncs are preferred** over polling for real-time fidelity. Polling is the fallback.

---

## 3. Recommended Repo Structure

```
systematic-execution-os/
├── docs/
│   ├── architecture.md          ← this file
│   ├── domain-models.md         ← Pydantic schema reference
│   ├── api-spec.md              ← API endpoint catalog
│   ├── asana-mapping.md         ← Asana object / field mapping
│   └── workflow-templates.md    ← Operating cadence templates
│
├── sidecar/                     ← Python sidecar root package
│   ├── __init__.py
│   ├── main.py                  ← FastAPI app factory + startup
│   ├── config.py                ← Settings via Pydantic BaseSettings
│   ├── database.py              ← SQLite engine + session factory
│   │
│   ├── models/                  ← Pydantic v2 domain models
│   │   ├── __init__.py
│   │   ├── pm_coverage.py
│   │   ├── pm_need.py
│   │   ├── project.py
│   │   ├── milestone.py
│   │   ├── deliverable.py
│   │   ├── risk.py
│   │   ├── decision.py
│   │   ├── capability.py
│   │   ├── dependency.py
│   │   ├── status_update.py
│   │   └── common.py            ← shared enums, base classes
│   │
│   ├── db/                      ← SQLAlchemy ORM table definitions
│   │   ├── __init__.py
│   │   ├── base.py              ← DeclarativeBase + TimestampMixin
│   │   ├── pm_coverage.py
│   │   ├── pm_need.py
│   │   ├── project.py
│   │   ├── milestone.py
│   │   ├── risk.py
│   │   ├── decision.py
│   │   └── capability.py
│   │
│   ├── services/                ← Business logic layer
│   │   ├── __init__.py
│   │   ├── pm_coverage_service.py
│   │   ├── pm_need_service.py
│   │   ├── project_service.py
│   │   ├── milestone_service.py
│   │   ├── risk_service.py
│   │   ├── decision_service.py
│   │   ├── capability_service.py
│   │   └── operating_review_service.py
│   │
│   ├── integrations/            ← External system clients
│   │   ├── __init__.py
│   │   ├── asana_client.py      ← Asana REST API wrapper
│   │   ├── asana_sync.py        ← Sync logic (pull/push per entity)
│   │   └── asana_webhooks.py    ← Webhook receiver and dispatcher
│   │
│   ├── api/                     ← FastAPI routers
│   │   ├── __init__.py
│   │   ├── router.py            ← Top-level router mount
│   │   ├── pm_coverage.py
│   │   ├── pm_needs.py
│   │   ├── projects.py
│   │   ├── milestones.py
│   │   ├── risks.py
│   │   ├── decisions.py
│   │   ├── capabilities.py
│   │   └── operating_review.py
│   │
│   ├── automation/              ← Scheduled jobs
│   │   ├── __init__.py
│   │   ├── scheduler.py         ← APScheduler setup and job registry
│   │   ├── daily_digest.py
│   │   ├── weekly_review_prep.py
│   │   ├── milestone_watch.py
│   │   └── pm_health_watch.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logging.py
│       └── idempotency.py
│
├── tests/
│   ├── unit/
│   │   ├── test_services/
│   │   └── test_models/
│   └── integration/
│       ├── test_asana_client.py
│       └── test_api/
│
├── migrations/                  ← Alembic migration scripts (v2+)
│   └── versions/
│
├── scripts/
│   ├── seed_config.py           ← One-time workspace setup helper
│   └── backfill_sync.py         ← Manual full-sync from Asana
│
├── .env.example                 ← Environment variable template
├── pyproject.toml               ← Project metadata + dependencies
└── README.md
```

### Rationale

- **Flat top-level** — only `sidecar/`, `tests/`, `docs/`, `scripts/` at root; easy to navigate.
- **models/ vs db/ split** — Pydantic models (domain logic, validation, serialization) are decoupled from SQLAlchemy ORM tables (persistence). This prevents schema leakage and makes the domain model portable.
- **services/ owns business logic** — routers delegate to services, services delegate to integrations or db. Nothing in `api/` contains business logic.
- **integrations/ owns all Asana I/O** — one place to change when Asana API evolves.

---

## 4. Technology Choices

| Technology | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Strong async support, rich ecosystem, standard for API + automation work |
| Web framework | FastAPI | Automatic OpenAPI docs, native async, clean dependency injection, Pydantic integration |
| Domain models | Pydantic v2 | Fast validation, excellent IDE support, strict mode catches errors early |
| ORM | SQLAlchemy 2.0 (async) | Mature, flexible, supports SQLite and Postgres for future migration |
| Database (v1) | SQLite | Zero-ops, sufficient for the single-writer access pattern of this service |
| Migrations | Alembic | Standard SQLAlchemy companion; deferred to v2 when schema is stabilizing |
| Background jobs | APScheduler | Lightweight, in-process scheduler; no separate broker needed for v1 |
| HTTP client | httpx (async) | Modern async HTTP client; used for Asana API calls |
| Config | Pydantic BaseSettings + `.env` | Type-safe, environment-variable-driven, no custom parsing code |
| Logging | Python `structlog` | Structured JSON logs; easy to integrate with log aggregators later |
| Testing | pytest + pytest-asyncio | Standard; async test support required for FastAPI/SQLAlchemy async patterns |
| Dependency management | uv + pyproject.toml | Fast, modern, reproducible |

### Why SQLite for v1

SQLite is sufficient because:
- The sidecar is a single-writer service (no horizontal scaling in v1)
- Data volumes are small (tens of PMs, hundreds of projects)
- Zero infrastructure setup cost
- Trivial to swap for Postgres later via SQLAlchemy connection string change

SQLite limitations to be aware of:
- No concurrent writes from multiple processes — acceptable for v1
- WAL mode should be enabled for better read concurrency

---

## 5. Domain Boundaries

The codebase is organized into five logical domains. Each domain has a dedicated module in `models/`, `db/`, `services/`, and `api/`.

### Domain Map

```
┌─────────────────────────────────────────────────────────────────────┐
│  PM Domain                                                          │
│  PMCoverageRecord  ←→  PMNeed                                       │
│  (sidecar SoT)         (hybrid: Asana task + sidecar metadata)      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ linked to
┌──────────────────────────────▼──────────────────────────────────────┐
│  Execution Domain                                                   │
│  Project  →  Milestone  →  Deliverable                              │
│  (Asana SoT, sidecar reads)                                         │
└──────────────────┬────────────────────────┬─────────────────────────┘
                   │ linked to              │ linked to
┌──────────────────▼──────────┐  ┌──────────▼─────────────────────────┐
│  Risk Domain                │  │  Decision Domain                   │
│  Risk / Blocker / Issue      │  │  Decision  (sidecar SoT)          │
│  (hybrid: Asana + sidecar)  │  │                                    │
└─────────────────────────────┘  └────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────┐
│  Capability Domain (v2)                                             │
│  Capability  ←→  Initiative  ←→  StakeholderMap                     │
│  (sidecar SoT)                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Domain Responsibility Rules

- **PM Domain** is the highest-priority domain. All other entities can link to PM.
- **Execution Domain** follows Asana's data model most closely.
- **Risk Domain** is a cross-cutting concern — any execution entity can have associated risks.
- **Decision Domain** is append-only by design — decisions should never be deleted, only superseded.
- **Capability Domain** is deferred to v2 but the `capability_id` foreign key field should be included in v1 schemas as a nullable field to avoid a future breaking migration.

---

## 6. Sync Patterns

### Pull Sync (Asana → Sidecar)

Used during startup and as a fallback when webhooks are missed.

```
for each entity type (project, milestone, task):
    page through Asana API results
    for each result:
        upsert into SQLite using asana_gid as idempotency key
        update sidecar-specific fields only if they are not already set
```

Pull sync is rate-limited by Asana's API. Use cursor-based pagination and back off exponentially on 429s.

### Push Sync (Sidecar → Asana)

Used when sidecar creates or enriches an Asana object.

```
1. Validate object locally (Pydantic, business rules)
2. Check idempotency: does asana_gid already exist in sidecar DB?
3. If yes: update Asana task/project fields via PATCH
4. If no: create in Asana via POST, store returned GID in sidecar DB
5. Log action to audit table
```

### Webhook-Driven Sync (Asana → Sidecar)

Preferred for real-time fidelity.

```
Asana sends POST to /sync/webhook/{event_type}
→ Validate HMAC signature
→ Enqueue event to in-memory queue (or lightweight job table)
→ Worker processes event: fetch full object from Asana API
→ Upsert into sidecar DB
```

Webhook registration is managed at startup via `asana_webhooks.py`. Webhooks should be re-registered if the sidecar restarts and detects stale/missing registrations.

### Idempotency Rules

1. **Create operations**: check `asana_gid` column — if exists, convert to update.
2. **Update operations**: compare field values before writing — skip no-op updates.
3. **Job runs**: each scheduled job writes a `job_run` record with a deduplication key (job name + execution date). Skip if already run for that window.
4. **Bot actions**: require a `client_request_id` header; sidecar rejects duplicates within a 24-hour window.

---

## 7. Config Management

All configuration flows through `sidecar/config.py`, which uses Pydantic `BaseSettings`.

### Settings Schema

```python
class Settings(BaseSettings):
    # Asana credentials
    asana_personal_access_token: str
    asana_workspace_gid: str

    # Asana project GIDs (set after Phase 1 Asana setup)
    asana_pm_needs_project_gid: str
    asana_pm_coverage_project_gid: str
    asana_risks_project_gid: str

    # Asana custom field GIDs (populated by seed_config.py)
    asana_custom_field_pm_id: str
    asana_custom_field_urgency: str
    asana_custom_field_health: str
    # ... etc.

    # Database
    database_url: str = "sqlite+aiosqlite:///./bam_execution.db"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Scheduler
    daily_digest_cron: str = "0 7 * * *"      # 7am daily
    weekly_review_cron: str = "0 8 * * MON"   # Monday 8am

    # Webhook
    asana_webhook_secret: str

    class Config:
        env_file = ".env"
```

### Environment File

`.env.example` is committed to the repo as a template. The actual `.env` is gitignored.

### Asana GID Bootstrap

After the Phase 1 Asana workspace is set up, run `scripts/seed_config.py` to:
1. Query the Asana API for custom field GIDs by name
2. Print `.env` export lines to be pasted into `.env`

This avoids hardcoding GIDs in source code and makes the config self-documenting.

---

## 8. Logging and Error Handling

### Logging

Use `structlog` throughout. Every log line is structured JSON at runtime, human-readable in development.

```python
import structlog
logger = structlog.get_logger(__name__)

# Usage
logger.info("asana_sync_complete", entity="project", count=42, duration_ms=310)
logger.warning("milestone_missing_criteria", milestone_id="M123", project="P456")
logger.error("asana_api_error", status=429, retry_in=60)
```

Log levels:
- `DEBUG`: detailed per-record sync steps (disabled in production)
- `INFO`: job completions, sync summaries, API request/response counts
- `WARNING`: data quality issues, missing fields, skipped records
- `ERROR`: API failures, DB write failures, unexpected exceptions

### Error Handling Strategy

**Asana API errors:**
- 401/403 → raise `AsanaAuthError`, halt job, alert on startup
- 404 → log warning, mark sidecar record as `asana_deleted`, continue
- 429 → exponential backoff with jitter (max 3 retries, then log and skip)
- 5xx → retry once after 30s, then log error and continue

**Database errors:**
- Constraint violations → log warning, return conflict response (409 from API)
- Connection errors → raise, FastAPI returns 503

**Webhook failures:**
- Invalid signature → 400, log warning (possible misconfiguration or replay attack)
- Processing error → 200 response to Asana (avoid retry flood), log error internally

**Background job failures:**
- Catch all exceptions per-job, log with full context
- Jobs should never crash the scheduler process
- Write `job_run` record with `status=failed` and `error_message` for observability

### API Error Responses

Standard error envelope:

```json
{
  "error": "not_found",
  "message": "PM Coverage record not found: pm-123",
  "request_id": "req-abc-456"
}
```

Use HTTP status codes correctly: 404 for not found, 409 for conflicts, 422 for validation, 500 for unexpected errors.

---

## 9. V1 Scope Boundary

### In V1 (Phase 2 sidecar build)

| Feature | Notes |
|---|---|
| PM Coverage Records (sidecar SoT) | Full CRUD + link to Asana summary task |
| PM Needs (hybrid) | Create in Asana, enrich in sidecar |
| Project sync from Asana | Read-only pull sync |
| Milestone sync from Asana | Read-only pull sync |
| Risk / Blocker records (hybrid) | Asana task + sidecar severity/impact metadata |
| Decision registry (sidecar SoT) | Full CRUD, append-only semantics |
| REST query API | PM status, blockers, open needs, at-risk projects, pending decisions |
| Daily digest automation | Overdue tasks, near-milestone alerts, PMs at risk |
| Weekly review prep automation | Agenda generation from live data |
| Milestone watch alerts | Alert when milestone near but tasks incomplete |
| Webhook receiver | Asana event ingestion |
| Structured logging | structlog JSON |
| Config via BaseSettings | `.env` driven |
| SQLite persistence | Single-file, WAL mode |

### Deferred to V2+

| Feature | Reason |
|---|---|
| Capability records and rollups | Need stable v1 data first to cluster needs meaningfully |
| Initiative / portfolio model | Requires validated capability model first |
| Stakeholder map | Low urgency in v1 |
| Cross-project dependency graph | Complex; tackle once basic PM/project data is clean |
| Alembic migrations | v1 schema evolves quickly; lock down in v2 |
| Postgres migration | Only needed when concurrent writes or scale become issues |
| Chat / Slack bot | Phase 3 |
| LLM tool layer | Phase 3-4 |
| PM happiness heuristics | Phase 4 |
| Launch-readiness scoring | Phase 4 |
| Full autonomous bot actions | Out of scope |

### V1 API Endpoints (Minimum Set)

```
GET  /pm-coverage                    List all PM records
GET  /pm-coverage/{pm_id}           PM status summary (stage, blockers, needs, health)
POST /pm-coverage                    Create PM coverage record

GET  /pm-needs                       List PM needs (filterable by PM, status, category)
POST /pm-needs                       Create PM need (creates Asana task + sidecar record)
PATCH /pm-needs/{need_id}            Update need status / metadata

GET  /projects                       List projects (filterable by health, PM)
GET  /projects/{project_id}          Project detail (milestones, blockers, decisions)

GET  /risks                          List open risks/blockers (filterable by severity, PM)
POST /risks                          Create risk/blocker
PATCH /risks/{risk_id}               Update risk status

GET  /decisions                      List decisions (filterable by status, project)
POST /decisions                      Create decision record

GET  /operating-review/agenda        Auto-generate weekly review agenda
GET  /operating-review/at-risk-pms   PMs with active blockers or slipping milestones
```

---

## 10. Open Decisions Resolved by This Architecture

The vision document listed ten open questions. This architecture resolves them as follows:

| Question | Decision | Rationale |
|---|---|---|
| PM Coverage in Asana or sidecar? | **Sidecar SoT**, summary task mirrored to Asana | Asana cannot hold relational fields; sidecar is richer |
| Cross-project dependencies? | **Sidecar-only** cross-project dep table in v1 | Asana native deps are task-level only |
| Decisions: Asana, sidecar, or hybrid? | **Sidecar-only** | Decisions need searchable history; Asana tasks are not well-suited |
| Auth model for bot actions? | **API key (v1)**, OAuth 2.0 with scopes for v3 | Simple for v1; scoped access needed when multiple users can write via bot |
| Chat platform first? | **Slack (v3)** | Deferred; architecture supports either via adapter pattern |
| Approval required for project vs task creation? | **Project creation requires human confirmation**; task creation via bot is allowed with required metadata | Aligns with vision's "safe create" principles |
| Mandatory fields for PM Need intake? | `pm_id`, `title`, `category`, `urgency`, `requested_by`, `date_raised` | Minimum to route and prioritize; all others optional at intake |
| Thresholds for risk/escalation alerts? | Blocker age > 7 days; milestone due in ≤ 7 days with incomplete tasks; PM with ≥ 3 open needs | Configurable via `.env`; these are defaults |
| Archival model for completed PM onboarding? | Archive in Asana (mark complete), soft-delete in sidecar (set `archived_at`) | Preserve history; remove from active views |
| Naming conventions enforced how? | Validated at sidecar create time via Pydantic regex validator | Not enforced retroactively on Asana-native objects in v1 |
