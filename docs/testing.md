# Testing Guide

## BAM Systematic Execution OS — Testing Reference

**Version:** 1.0
**Last Updated:** 2026-03-01

---

## Table of Contents

1. [Unit Tests](#1-unit-tests)
2. [Asana Sandbox Setup](#2-asana-sandbox-setup)
3. [Integration Smoke Test](#3-integration-smoke-test)
4. [Backfill Sync](#4-backfill-sync)
5. [Manual Verification Checklist](#5-manual-verification-checklist)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Unit Tests

Unit tests run entirely in-memory — no Asana account or running sidecar required.

### Running all tests

```bash
uv run pytest
```

### Running a specific module

```bash
uv run pytest tests/unit/test_integrations/test_asana_sync.py -v
uv run pytest tests/unit/test_automation/ -v
```

### Test coverage

```bash
uv run pytest --cov=sidecar --cov-report=term-missing
```

### Test structure

```
tests/
  unit/
    test_integrations/
      test_asana_client.py     — HTTP client: retry, pagination, batch
      test_asana_mapper.py     — Mapper: from_asana_* / to_asana_* round-trips
      test_asana_webhooks.py   — Webhook: HMAC validation, dispatch, idempotency
      test_asana_sync.py       — Pull sync: upsert, conflict, source-of-truth rules
    test_automation/
      test_automation_jobs.py  — daily_digest, milestone_watch, pm_health_watch, weekly_review_prep
      test_templates.py        — create_pm_onboarding_project, capability, stabilization
    test_models/               — Domain model validation and enum checks
    test_services/             — Repository layer with in-memory SQLite
  integration/
    test_api/                  — FastAPI endpoint tests with TestClient
```

### Key design decision tested

- **D1 (PM Need status):** `test_pm_need_status_driven_by_section` — status is always derived from the Asana section name, never from a writable API field.
- **D6 (Simplified sync):** All sync tests verify that `asana_gid` + `asana_synced_at` are the only sync fields; no `SyncState` enum.
- **D7 (Age on read):** No `age_days` column in any DB table; age is computed in application layer.

---

## 2. Asana Sandbox Setup

This section walks through creating a test Asana workspace that mirrors production.

### Prerequisites

1. Create a free [Asana](https://asana.com) account (or use an existing sandbox workspace).
2. Generate a **Personal Access Token (PAT)** at: `https://app.asana.com/0/my-apps`
3. Note the **Workspace GID** from `https://app.asana.com/api/1.0/workspaces` (with your PAT).
4. Optionally note a **Team GID** if you want projects created inside a specific team.

### Step 1: Configure environment

```bash
cp .env.example .env
# Edit .env and set at minimum:
#   ASANA_PERSONAL_ACCESS_TOKEN=your_pat_here
#   ASANA_WORKSPACE_GID=your_workspace_gid_here
#   ASANA_TEAM_GID=your_team_gid_here   # optional
```

### Step 2: Run seed_config.py

This script creates all custom fields and singleton projects, then prints the GID values to paste into `.env`.

```bash
uv run python scripts/seed_config.py
```

Expected output:

```
=== Custom Fields ===

-- Global --
  [create] custom field 'Project Type' → 1234567890123456
  [create] custom field 'Priority' → 1234567890123457
  ...

-- PM Coverage --
  [create] custom field 'Onboarding Stage' → 1234567890123470
  ...

=== Singleton Projects ===

-- PM Coverage Board --
  [create] project 'PM Coverage Board' → 9876543210987654
    [create] section 'Pipeline' → 9876543210987655
    ...

============================================================
Paste the following into your .env file:
============================================================
ASANA_CUSTOM_FIELD_PROJECT_TYPE=1234567890123456
ASANA_CUSTOM_FIELD_PRIORITY=1234567890123457
...
ASANA_PM_COVERAGE_PROJECT_GID=9876543210987654
ASANA_PM_NEEDS_PROJECT_GID=9876543210987700
ASANA_RISKS_PROJECT_GID=9876543210987750
ASANA_DECISION_LOG_PROJECT_GID=9876543210987800
============================================================
```

**The script is idempotent.** Re-running it finds existing objects by name and prints their GIDs without creating duplicates.

### Step 3: Update .env and restart sidecar

```bash
# Paste the printed lines into .env, then restart:
uv run uvicorn sidecar.main:create_app --factory --reload
```

### What gets created

| Object | Name | Purpose |
|---|---|---|
| Custom fields (global) | Project Type, Priority, Health, Confidence, Owner Group, Region | Applied to all projects |
| Custom fields (PM Coverage) | Onboarding Stage, Strategy Type, Team / Pod, Last Touchpoint | PM tracking fields |
| Custom fields (PM Needs) | Need Category, Urgency, Business Impact, Need Status, Resolution Path, PM, Requested By, Linked Capability | Need triage fields |
| Custom fields (Milestones) | Milestone Status, Gate Type | Milestone tracking |
| Custom fields (Risks) | Item Type, Severity, Escalation Status, Impacted PMs, Impacted Projects, Resolution Date | Risk management |
| Custom fields (Decisions) | Decision Status, Decision Date, Approver, Impacted Scope | Decision log |
| Project | PM Coverage Board (Board layout) | One task per PM |
| Project | PM Needs - BAM Systematic | All PM needs |
| Project | Risks & Blockers - BAM Systematic | All risks/blockers |
| Project | Decision Log - BAM Systematic | Pending/made decisions |

### Asana sections created per project

**PM Coverage Board:**
Pipeline → Pre-Start → Requirements Discovery → Onboarding In Progress → UAT → Go Live Ready → Live → Stabilization → Steady State

**PM Needs:**
New → Triaged → Mapped to Existing Capability → Needs New Project → In Progress → Blocked → Delivered → Deferred → Cancelled

**Risks & Blockers:**
Open - Critical → Open - High → Open - Medium → Monitoring → Resolved

**Decision Log:**
Pending Decisions → Decisions Made → Deferred → Cancelled

---

## 3. Integration Smoke Test

The smoke test exercises the full round-trip against a live Asana sandbox and optionally a running sidecar instance.

### Prerequisites

- `seed_config.py` has been run and `.env` is populated with GIDs.
- (Optional) Sidecar is running at `http://localhost:8000`.

### Running the smoke test

```bash
# With sidecar running locally:
uv run python scripts/smoke_test.py

# Without sidecar (Asana round-trips only):
uv run python scripts/smoke_test.py

# Keep Asana objects for manual inspection:
uv run python scripts/smoke_test.py --no-cleanup

# Against a remote sidecar:
SIDECAR_BASE_URL=http://my-server:8000 uv run python scripts/smoke_test.py
```

### What is tested

| Step | Test | Validation |
|---|---|---|
| 1 | PM Coverage record | Create task in Asana → fetch back → verify name, GID |
| 2 | PM Need | Create task in Asana → verify in PM Needs project → verify section membership |
| 3 | PM Onboarding project | Create from template → verify all 8 sections exist in Asana → verify 10 milestones created → verify Go-Live Ready milestone has correct due date and is milestone subtype |
| 4 | Risk / Blocker | Create task in Asana → fetch back → verify title, severity, status = open |
| 5 | Sidecar API | GET /health, /pm-coverage, /pm-needs, /milestones, /risks, /decisions, /operating-review/agenda → verify 200 or 404 |

### Expected output (clean run)

```
Smoke test run: a3b4c5d6
Workspace GID: 1234567890
Sidecar URL:   http://localhost:8000

[1] PM Coverage round-trip
  PASS  PM coverage task created in Asana
  PASS  PM coverage task name matches
  PASS  PM coverage fetched by GID
  PASS  PM coverage name consistent

[2] PM Need round-trip
  PASS  PM need task created in Asana
  PASS  PM need title matches
  PASS  PM need category is execution
  PASS  PM need in correct project

[3] PM Onboarding project template
  PASS  Onboarding project created
  PASS  All 8 sections created
  PASS  All 10 milestones created
  PASS  Go-Live Ready milestone has correct due date
  PASS  Go-Live Ready milestone is milestone subtype
  PASS  Section 'Kickoff & Discovery' in Asana
  ... (8 section checks) ...

[4] Risk / Blocker round-trip
  PASS  Risk task created in Asana
  PASS  Risk title matches
  PASS  Risk status is open
  PASS  Risk fetched by GID
  PASS  Risk severity is high

[5] Sidecar API health
  PASS  Health endpoint → HTTP 200
  PASS  PM Coverage list → HTTP 200
  ...

Cleaning up 3 tasks, 1 projects...
Cleanup done.

==================================================
Results: 28/28 passed, 0 failed
==================================================
```

### Cleanup

By default the smoke test **deletes all Asana objects it created** (tasks and projects tagged with `[SMOKE]`). Pass `--no-cleanup` to leave them for manual inspection in the Asana UI.

Sidecar DB records created during sync are **not deleted** — they represent a valid state. Use `DELETE FROM pm_need WHERE need_id LIKE 'smoke-%'` etc. to clean up if needed.

---

## 4. Backfill Sync

Use the backfill script to pull all Asana objects into the sidecar DB. This is for initial setup or after a gap in webhook delivery.

```bash
uv run python scripts/backfill_sync.py
```

What it syncs:
- All tasks in PM Coverage Board → `pm_coverage` table
- All tasks in PM Needs project → `pm_need` table
- All tasks in Risks & Blockers project → `risk` table

Sidecar IDs for backfilled records are set to `asana-{gid}` and can be updated later via the sidecar API.

---

## 5. Manual Verification Checklist

After running `seed_config.py` and the smoke test, verify the following in the Asana UI:

### PM Coverage Board
- [ ] Board layout is active (columns visible)
- [ ] All 9 sections/columns visible: Pipeline through Steady State
- [ ] Smoke test PM task visible in Pipeline column
- [ ] Custom field "Health" is visible on the task

### PM Needs Project
- [ ] List layout with 9 sections visible
- [ ] Smoke test need task visible in "New" section
- [ ] Custom fields "Need Category", "Urgency", "Business Impact" visible

### Risks & Blockers Project
- [ ] Smoke test risk task visible in "Open - High" section (or wherever severity places it)
- [ ] Custom fields "Item Type", "Severity", "Escalation Status" visible

### PM Onboarding Template Project (if --no-cleanup used)
- [ ] Project visible with name `Onboarding - Smoke PM {run_id} - Test Strategy`
- [ ] 8 sections visible (Kickoff & Discovery through Admin & Wrap-Up)
- [ ] Milestone tasks visible (confirmed as milestone type, not standard task)
- [ ] "Go-Live Ready" milestone has due date set correctly
- [ ] Seed tasks visible in each section

### Sidecar API (if running)
- [ ] `GET /pm-coverage` returns list
- [ ] `GET /operating-review/agenda` returns structured agenda JSON
- [ ] `GET /milestones?project_id=...` returns milestones for the test project

---

## 6. Troubleshooting

### `ASANA_PERSONAL_ACCESS_TOKEN` not recognized

Verify the PAT is valid:
```bash
curl -H "Authorization: Bearer $ASANA_PERSONAL_ACCESS_TOKEN" \
     https://app.asana.com/api/1.0/users/me
```
Should return your user info. If 401, regenerate the PAT.

### `seed_config.py` fails on custom field creation

Asana free plans have a limit of 15 custom fields. If you hit this limit, use an Asana Premium or Business workspace, or reduce the number of custom fields by commenting out less-critical entries in `seed_config.py`.

### `smoke_test.py` — FAIL on "PM need in correct project"

The `ASANA_PM_NEEDS_PROJECT_GID` in `.env` may be stale. Re-run `seed_config.py` and update `.env`.

### `smoke_test.py` — Sidecar API checks skipped

The sidecar must be running before smoke test step 5 executes API checks. Start it with:
```bash
uv run uvicorn sidecar.main:create_app --factory --reload
```

### Webhook handshake not completing

When registering a webhook, Asana sends a `X-Hook-Secret` header to the webhook URL for handshake. The sidecar must be publicly reachable. For local testing, use [ngrok](https://ngrok.com):
```bash
ngrok http 8000
# Then set webhook URL to https://<ngrok-id>.ngrok.io/webhooks/asana
```

### Duplicate objects after re-running seed_config.py

`seed_config.py` checks by **name** before creating. If you renamed a field or project in Asana, the script will create a new one. To fix: rename it back to the expected name in Asana, then re-run the script.

### DB migration needed after schema changes

If you change ORM table definitions, recreate the database:
```bash
rm bam_execution.db
uv run uvicorn sidecar.main:create_app --factory  # creates fresh DB on startup
```
Then re-run `scripts/backfill_sync.py` to repopulate from Asana.
