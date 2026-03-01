# BAM Systematic Execution OS

A business-side execution platform for BAM Systematic that makes PM onboarding, platform buildout, and cross-functional delivery visible, structured, accountable, and scalable.

## What This Is

The Execution OS combines three layers:

1. **Asana** — system of record for active project execution (tasks, milestones, deliverables, project status)
2. **Python sidecar** — cross-project intelligence layer (PM coverage records, decision registry, enriched rollups, automation jobs, REST API)
3. **Chat/agent layer** (Phase 3) — Slack/Teams bot for safe conversational query and create operations

The sidecar does not replace Asana. It covers what Asana handles poorly: cross-project relational modeling, richer PM records, a searchable decision log, rollup views across all active work, and the bot query layer.

## Repository Structure

```
systematic-execution-os/
├── docs/
│   ├── architecture.md        System architecture, source-of-truth rules, tech choices
│   ├── domain-model.md        Pydantic schema reference for all domain objects
│   ├── workflows.md           Operating cadences, meeting templates, artifact lifecycles
│   ├── api-design.md          REST endpoint catalog, bot command spec
│   ├── asana-mapping.md       Asana object/field mapping and integration strategy
│   └── future-roadmap.md      v2 and beyond — what is deferred and why
│
├── sidecar/                   Python sidecar root package
│   ├── models/                Pydantic v2 domain models
│   │   ├── common.py          Shared enums and base classes
│   │   ├── pm_coverage.py     PMCoverageRecord, OnboardingStage
│   │   ├── pm_need.py         PMNeed, NeedCategory, NeedStatus
│   │   ├── project.py         Project, ProjectType, ProjectStatus
│   │   ├── milestone.py       Milestone, MilestoneStatus, STANDARD_ONBOARDING_MILESTONES
│   │   ├── deliverable.py     Deliverable, DeliverableStatus
│   │   ├── risk.py            RiskBlocker, RiskSeverity, EscalationStatus
│   │   ├── decision.py        Decision, DecisionStatus, ImpactedArtifact
│   │   ├── status_update.py   StatusUpdate, StatusScopeType
│   │   └── capability.py      Capability stub (v2)
│   ├── db/                    SQLAlchemy ORM table definitions (Phase 2)
│   ├── services/              Business logic layer (Phase 2)
│   ├── integrations/          Asana API client and sync logic (Phase 2)
│   ├── api/                   FastAPI routers (Phase 2)
│   ├── automation/            Scheduled jobs — digests, alerts, review prep (Phase 2)
│   └── utils/                 Logging, idempotency helpers
│
├── tests/
│   ├── unit/
│   └── integration/
│
├── scripts/
│   ├── seed_config.py         One-time Asana workspace setup helper
│   └── backfill_sync.py       Manual full-sync from existing Asana workspace
│
├── .env.example               Environment variable template
├── pyproject.toml             Project metadata and dependencies
└── README.md                  This file
```

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- An Asana account with a Personal Access Token
- Access to the BAM Systematic Asana workspace

## Setup

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd systematic-execution-os
uv sync
```

Or with pip:

```bash
pip install -e ".[dev]"
```

### 2. Configure environment

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Required variables:

```
ASANA_PERSONAL_ACCESS_TOKEN=<your PAT>
ASANA_WORKSPACE_GID=<workspace GID>
ASANA_PM_NEEDS_PROJECT_GID=<GID of PM Needs Asana project>
ASANA_PM_COVERAGE_PROJECT_GID=<GID of PM Coverage Asana project>
ASANA_RISKS_PROJECT_GID=<GID of Risks & Blockers Asana project>
ASANA_WEBHOOK_SECRET=<shared secret for webhook HMAC validation>
```

See `.env.example` for the full list including optional scheduler cron overrides.

### 3. Bootstrap Asana GIDs (first-time setup only)

After completing Phase 1 Asana workspace setup (projects, custom fields, templates), run:

```bash
uv run python scripts/seed_config.py
```

This queries the Asana API to discover custom field GIDs by name and prints the corresponding `.env` lines for you to paste in.

### 4. Run the sidecar

```bash
uv run uvicorn sidecar.main:app --reload
```

The API will be available at `http://localhost:8000`. Interactive API docs at `http://localhost:8000/docs`.

### 5. First-time sync from existing Asana workspace

If you are connecting to an Asana workspace that already contains projects and tasks:

```bash
uv run python scripts/backfill_sync.py
```

This performs a full pull sync in dependency order (projects → milestones → tasks → risks) and upserts all objects into the sidecar database. Safe to re-run — all writes are idempotent.

## Development

### Running tests

```bash
uv run pytest
```

Integration tests require a valid `.env` with Asana credentials. Unit tests run without Asana access.

### Code style

The project uses `ruff` for linting and formatting:

```bash
uv run ruff check .
uv run ruff format .
```

### Database

The sidecar uses SQLite in v1. The database file (`bam_execution.db`) is created automatically on first startup. WAL mode is enabled at startup for better read concurrency.

There are no Alembic migrations in v1 — schema changes require dropping and recreating the database during the early development phase. Alembic is introduced in v2 once the schema stabilizes.

### Environment variables

All configuration flows through `sidecar/config.py` using Pydantic `BaseSettings`. Settings are loaded from the `.env` file. No secrets should be hardcoded in source.

## System Phases

| Phase | What it delivers | Status |
|-------|-----------------|--------|
| Phase 1 | Asana workspace setup — project templates, custom fields, PM Needs intake project, PM Coverage board, operating cadences | Design complete |
| Phase 2 | Python sidecar — domain models, persistence layer, REST API, Asana sync, scheduled automation jobs | In progress |
| Phase 3 | Chat/agent layer — Slack or Teams bot with safe query and create commands | Planned |
| Phase 4 | Intelligence layer — PM health heuristics, capability gap ranking, launch-readiness scoring | Future |

## Key Design Decisions

**Source of truth:**
- Asana owns: tasks, milestones, projects, day-to-day ownership, project status updates
- Sidecar owns: PM Coverage Records, Decision registry, cross-project relational links, automation state
- Hybrid (both): PM Needs (Asana task + sidecar metadata), Risks & Blockers (Asana task + sidecar severity/impact)

**PM Need status:** Asana task section (Kanban column) is the canonical source for PM Need status. The sidecar's `status` field is a read-only cache — it is not writable via the API. See `docs/design-decisions.md D1`.

**Decision immutability:** Decisions are immutable once `status = decided`. To revise a decided outcome, create a new decision and set `superseded_by_id` on the original. See `docs/design-decisions.md D3`.

**Sidecar degraded mode:** If Asana is unreachable at startup, the sidecar starts in read-only mode — it serves cached SQLite data but refuses writes that require Asana. See `GET /health` for connectivity status.

For the full list of architectural decisions, see `docs/architecture.md` and `docs/design-decisions.md`.

## Documentation

| Document | Contents |
|----------|----------|
| `docs/architecture.md` | System architecture, source-of-truth rules, sync patterns, technology choices |
| `docs/domain-model.md` | All domain objects with field schemas, state machines, and entity relationships |
| `docs/workflows.md` | Workflow lifecycle specs, meeting templates, artifact lifecycle rules, bot use cases |
| `docs/api-design.md` | REST endpoint catalog, request/response shapes, bot command spec |
| `docs/asana-mapping.md` | Asana object/field mapping, custom fields schema, webhook strategy |
| `docs/design-decisions.md` | Resolved P0 design decisions from review |
| `docs/design-review.md` | Design review findings and recommendations |
| `docs/future-roadmap.md` | Deferred features and v2/v3 roadmap |

## Getting Help

For questions about operating the Execution OS as a business user, see `docs/workflows.md`.

For questions about the Asana workspace setup, see `docs/asana-mapping.md`.

For API usage, see `http://localhost:8000/docs` (when the sidecar is running) or `docs/api-design.md`.
