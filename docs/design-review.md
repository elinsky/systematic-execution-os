# BAM Systematic Execution OS — Design Review

> Reviewer: Devil's Advocate / Design Review Agent
> Date: 2026-03-01
> Status: Final review — for team discussion before implementation begins
> Documents reviewed: vision.md, docs/architecture.md, docs/asana-mapping.md, docs/domain-models.md, docs/workflows.md, docs/api-design.md

---

## Executive Summary

The design is coherent and well-considered. The three-tier architecture (Asana → Python sidecar → chat layer) is appropriate for this use case and the phasing is sound. However, there are several issues that could cause real operational pain if not addressed before implementation begins. The most critical are: dual-write ambiguity on the PM Need and Decision objects, the APScheduler-in-process scheduler creating silent failure modes, the sidecar writing derived fields back to Asana as a daily batch job (creating a window of stale data in the system of record), and the absence of a clear human-in-the-loop gate for any bot-initiated write action in v2.

---

## 1. Scope Assessment

### Is v1 scope appropriate?

**Verdict: Mostly yes, with two scope creep concerns.**

The architecture doc's v1 scope table includes:
- PM Coverage Records (full CRUD)
- PM Needs (hybrid: create + enrich)
- Project sync from Asana
- Milestone sync from Asana
- Risk / Blocker records (hybrid)
- Decision registry
- REST query API (5+ entity types)
- Daily digest automation
- Weekly review prep automation
- Milestone watch alerts
- Webhook receiver

This is a substantial v1. For a team starting from zero, building full CRUD for five entity types plus four automation jobs plus a webhook receiver in one phase is ambitious. The real risk is not any individual feature but the combinatorial testing and operational complexity of all of them running in the same process simultaneously.

**Scope creep flags:**

1. **Decision registry in v1** — The vision explicitly defers Decisions to v1 minimum viable schema, but the architecture includes a full decision CRUD API and registry. This is a relatively low-urgency object (nobody has died because decision rationale wasn't queryable on day 1). Recommend deferring the full decision registry to v1.5 and delivering a lightweight Asana-only Decisions view first.

2. **Webhook receiver in v1** — Webhooks are the right long-term pattern but they add significant reliability infrastructure (registration, re-registration, HMAC verification, event deduplication, replay handling). For v1, a polling-based sync fallback is already in the design. Recommend making the webhook receiver a "nice to have" in v1 and treating polling as the primary sync mechanism until the system is stable. This de-risks the initial deployment substantially.

3. **`asana_gid` external ID writeback** — The asana-mapping doc recommends using Asana's `external.id` field on tasks to store sidecar primary keys. This is a good pattern but requires write access to every task the sidecar monitors. Confirm this is permitted by the Asana service account's permissions before building around it.

---

## 2. Source-of-Truth Conflicts

### Identified conflicts and ambiguities

**[HIGH] PM Need: dual-write ambiguity on `status`**

The architecture doc says PM Needs are "hybrid: Asana task is created first; sidecar adds metadata and links." The asana-mapping doc says the PM Need `status` field is driven by Asana task section (A→S sync), but also maps to a custom field `Need Status` that mirrors the section. The domain model doc also shows a `status` field in the sidecar.

**Problem:** If the sidecar creates a PM Need (via the `POST /pm-needs` API), it must write to Asana. If a user then moves the Asana task to a different section, the webhook fires and updates the sidecar. But the sidecar also holds its own `status` field. There is no explicit rule about what happens if the sidecar's `status` and the Asana section disagree during a conflict window (e.g., sidecar writes status, Asana webhook hasn't fired yet).

**Resolution:** Document an explicit tie-breaking rule. The cleanest option: for PM Needs, the Asana section is always canonical for `status`; the sidecar's `status` field is a cached mirror, never the write target. Remove `status` from the sidecar `PMNeedUpdate` schema.

---

**[HIGH] PM Coverage: "dual-homed" without a clear write path**

The asana-mapping doc says PM Coverage is "dual-homed — Asana task provides the Kanban-style stage view and is the visual operating artifact; sidecar holds the richer relational record." The architecture doc says PM Coverage is "Sidecar SoT" with a "summary task mirrored to Asana."

**Problem:** There are two stated ownership claims. If Asana is the stage/health SoT (architecture table says A→S for onboarding stage and health), then users would update stage in Asana and the sidecar reads it. But if the sidecar is SoT (architecture master table says Sidecar), then the sidecar should be the write target. This contradiction is unresolved.

**Concretely:** When an operator runs `PATCH /pm-coverage/{pm_id}` with a new `onboarding_stage`, what happens? Does the sidecar update its record and push to Asana, or does it refuse the update and tell the user to move the Asana Kanban card?

**Resolution:** Decide once: Asana Kanban section is the write surface for onboarding stage and health (operators drag cards); sidecar reads via webhook and mirrors. All other PMCoverageRecord fields (notes, linked projects, strategy type) are writable via sidecar API. This is the sensible split; just document it explicitly and enforce it in the API validation layer.

---

**[MEDIUM] Decision: status lives in both Asana and sidecar**

The asana-mapping doc says `decision_status` is "A→S: Set in Asana custom field." The architecture master table says Decisions are "Sidecar-only." The Asana mapping section for Decisions shows `status` mirrored in both Asana and sidecar.

**Problem:** If a user marks a decision as "Decided" in Asana (via custom field), the webhook syncs to the sidecar. If they also use the API to update decision status, there's a dual-write path. More practically: the decision registry is described as "append-only" in architecture.md but the API includes `PATCH /decisions/{decision_id}`. Append-only and PATCH-able are contradictions.

**Resolution:** Clarify "append-only" semantics. Decisions should be immutable once `status = decided`; only `pending` decisions should be patchable. Add validation enforcement. For status sync, make Asana the write surface for Decision status only; sidecar reads via webhook.

---

**[MEDIUM] Risks & Blockers: `age_days` writeback creates stale data window**

The asana-mapping doc says `age_days` is computed by the sidecar and written back to Asana as a daily batch job (S→A). This means the `Age (Days)` field in Asana will be up to 24 hours stale.

**Problem:** If a business user reads the Asana task and sees `Age (Days) = 5`, it might actually be 6. This is minor for most cases but problematic if escalation thresholds (e.g., "escalate blockers > 7 days") are being evaluated by humans reading Asana. Users will see age=6, not escalate, and the sidecar triggers the alert overnight.

**Resolution:** Either compute `age_days` on-read (sidecar returns it dynamically, never stores in Asana), or change the writeback to near-real-time (triggered by webhook, not daily batch). The on-read computation is simpler and avoids the writeback entirely — recommend this approach.

---

**[LOW] Status Update: project-level in Asana, PM-level and initiative-level in sidecar**

This is a reasonable split but the asana-mapping doc doesn't clearly state what happens when the sidecar generates a PM-level status update. Does it write to Asana? Where? The architecture doc says "sidecar-only" for PM-level and initiative-level status. This should be called out more explicitly: PM and initiative status summaries do not appear anywhere in Asana; they are sidecar-only and query-only.

---

## 3. Abstraction Quality

### Domain boundaries

**[POSITIVE] The domain map (architecture.md Section 5) is clean.** Five domains (PM, Execution, Risk, Decision, Capability), each with clear ownership. Capability deferred to v2. The `capability_id` placeholder in v1 schemas is the right approach to avoid a breaking migration later.

**[POSITIVE] The services layer / router layer split is correct.** No business logic in routers. Services own all domain rules. Integrations own all Asana I/O.

**[CONCERN] `top_open_need_ids` and `top_blocker_ids` on PMCoverageRecord are pre-materialized lists.**

The domain model has `top_open_need_ids: list[str]` and `top_blocker_ids: list[str]` on PMCoverageRecord. These are derived data — they should be computed from the PM Needs and Risks tables filtered by `pm_id`, not stored as fields on the PM Coverage record.

Storing them as fields creates a sync problem: every time a new PM Need is created or resolved, the sidecar must also update the PM Coverage record's `top_open_need_ids`. This is unnecessary fan-out. The `/pm-coverage/{pm_id}` query endpoint should assemble this list at query time from the relational tables.

**Recommendation:** Remove `top_open_need_ids` and `top_blocker_ids` from the PMCoverageRecord schema. Compute them on read in `pm_coverage_service.py`. Only store the canonical foreign keys in the PMNeed and RiskBlocker tables (`pm_id` fields).

---

**[CONCERN] `SyncState` enum adds significant state machine complexity**

The domain model introduces a `SyncState` enum: `synced, pending_push, pending_pull, conflict, asana_deleted`. This is a correct and mature data model pattern, but it means every entity now needs a state machine to manage transitions between sync states. Who transitions a record from `pending_push` to `synced`? What happens on `conflict`? Is there a retry queue?

This adds hidden complexity to v1. A simpler v1 approach: remove `SyncState` from models and just track `asana_gid` (set or null) and `asana_synced_at` (last sync timestamp). Let the daily consistency job identify divergence by comparing Asana data to sidecar data. Add the full SyncState machine in v2 when the operational patterns are better understood.

---

**[CONCERN] `AsanaLinkedRecord` as mixin vs base class**

The domain-models doc shows `asana_gid` coming from `AsanaLinkedRecord` inheritance. If this is a Pydantic mixin (via inheritance), then all Pydantic validators for `asana_gid` need to be consistent across all subclasses. If any subclass overrides `asana_gid` validation, it creates subtle bugs. Enforce that `AsanaLinkedRecord` is never subclassed with conflicting field definitions — add a test for this.

---

## 4. Sync Risk

### Patterns that could lead to data inconsistency

**[CRITICAL] Webhook-driven sync as "preferred" without a recovery guarantee**

The architecture doc says "Webhook-triggered syncs are preferred over polling for real-time fidelity. Polling is the fallback." The asana-mapping doc says the daily consistency check polls modified tasks to compare sidecar state. This is the right safety net, but the design doesn't specify:

1. What is the maximum acceptable data lag? (If a webhook is missed, data can be 24 hours stale until the nightly consistency check.)
2. What does the consistency check do when it finds a divergence? Does it always take Asana as the winner? Does it alert a human?
3. The architecture doc says "Asana-wins for fields that exist in both stores" — but this is only documented in the architecture doc, not in the code design. This rule needs to be encoded as a concrete function in `asana_sync.py`, not just stated in documentation.

**Resolution:** Add an hourly incremental poll as the safety net (not just daily), checking tasks modified in the last 2 hours. This closes the webhook miss window to ~1 hour instead of 24 hours. Document the divergence handling rule in code comments, not just in docs.

---

**[HIGH] APScheduler in-process: no alerting when jobs fail silently**

The architecture specifies APScheduler running inside the FastAPI process. The error handling section says jobs should "never crash the scheduler process" and should write `job_run` records with `status=failed`. This is correct.

**Problem:** Who reads the `job_run` table to detect failures? There is no monitoring or alerting layer specified. If the daily digest job has been failing for 3 days, nobody knows until a user notices they haven't received digests. In a financial services PMO context, a silent digest failure for 3 days could mean missed escalations.

**Resolution:** Add a watchdog job that runs hourly, queries the `job_run` table for any job that has `status=failed` in the last 24 hours or has not run in more than its expected interval, and sends an alert (Slack message or email). This can be a simple APScheduler job itself. This should be in v1, not deferred.

---

**[HIGH] Webhook handler returns 200 immediately but processing could be incomplete**

The asana-mapping doc says "Webhook handler must return 200 within 10 seconds; enqueue heavy processing to a job queue (Celery, RQ, or similar)." However, the architecture doc recommends APScheduler (an in-process scheduler) and does not mention Celery or RQ anywhere. There is a conflict between the two documents.

In-process APScheduler cannot serve as a reliable job queue for webhook event processing. If the FastAPI process restarts after returning 200 but before processing an enqueued webhook event, that event is lost.

**Resolution:** For v1, accept the risk and process webhook events synchronously (the 10-second window is usually sufficient for simple DB upserts). For v2, introduce a proper job queue. Do not claim webhook processing is "reliable" if it's happening in-memory.

---

**[MEDIUM] Template instantiation: batched Asana API calls with no rollback**

The asana-mapping doc describes a 15–25 API call sequence to create a PM onboarding project from template. If calls 12–15 fail (e.g., due to rate limiting), the partially-created project will be in Asana with missing milestones or sections.

**Problem:** There is no compensation / rollback logic described. A human user will find a broken project in Asana and may not know the sidecar failed to complete it.

**Resolution:** Add idempotent re-try logic to the template instantiation flow. On each step, check if the object already exists before creating. Store the instantiation progress in the sidecar so a retry can resume from the last successful step. This is essentially a saga pattern, which is standard for multi-step Asana API sequences.

---

**[MEDIUM] `asana_deleted` state with no human notification**

The architecture describes marking sidecar records as `asana_deleted=True` when an Asana object is no longer found via the daily consistency check. But there's no notification to operators when a critical object (e.g., a PM Coverage task or a go-live milestone) is deleted from Asana.

In a trading PMO context, a PM Coverage task or a go-live milestone being accidentally deleted from Asana could have serious operational consequences. The daily orphan detection job should immediately alert (not just log) when milestone, PM Coverage, or Risk/Blocker tasks are found to be orphaned.

---

## 5. Over-Engineering

### What can be simplified or deferred?

**[DEFER] Full SyncState machine**
As noted above, the `SyncState` enum (pending_push, pending_pull, conflict) is premature for v1. Start with `asana_gid` + `asana_synced_at`. Add SyncState in v2 when conflict patterns are understood.

**[DEFER] `external.id` field on Asana tasks**
Using Asana's `external.id` field to store sidecar PKs is a good pattern but requires write access on every monitored task. This is complexity that can be deferred. In v1, just use the sidecar DB as the lookup authority. The performance hit of an extra DB query on webhook events is negligible at this scale.

**[DEFER] Alembic migrations**
The architecture correctly defers Alembic to v2. Reinforce this: do not add Alembic in v1. The schema will change too fast and the overhead of migration management outweighs the benefit when you have zero production users.

**[DEFER] `daily_digest.py` and `pm_health_watch.py` in the same v1 scope**
Both the daily digest and the PM health watch automation are scheduled jobs. Starting with both in v1 doubles the operational surface. Recommend starting with one (the daily digest overdue/at-risk alert) and deferring PM health watch to v1.5.

**[SIMPLIFY] Decisions in v1**
The full decision registry (full CRUD + Asana hybrid + sidecar registry + options_considered array) is over-specified for v1. A simpler v1 design: a single Asana project (`Decision Log`) with structured custom fields is sufficient to track pending decisions. The sidecar can add a lightweight decision endpoint to query pending decisions by project/PM. Save the full rationale/options/impacted_artifacts model for v2.

**[SIMPLIFY] `PM` custom field on PM Needs tasks**
The asana-mapping doc uses a `PM` text field (free text) on PM Needs tasks to reference the PM Coverage Record. This is a reliability problem: if someone types "Jane Doe" slightly differently ("Jane A. Doe", "JD"), the link breaks silently. In v1, use a strict `pm_id` format (e.g., `pm-jane-doe`) and validate on intake. In the Asana Form, make it a dropdown or restricted field.

---

## 6. Operational Failure Modes

### What happens when Asana API is down?

The architecture doc specifies behavior for 401/403, 404, 429, and 5xx errors. What it does **not** specify:

**[CRITICAL] Asana API unavailable: sidecar starts up in degraded mode**

If Asana returns 5xx consistently on startup, should the sidecar:
a) Fail to start entirely (circuit breaker)?
b) Start in read-only mode (serve cached data, refuse writes)?
c) Start normally and queue writes for retry?

Currently, the design says nothing about this. In a financial PMO, operators may need to read status dashboards even when Asana is degraded. The sidecar should be able to serve cached data from SQLite even when Asana is unreachable. This means the sidecar must never be in a state where it cannot serve reads due to Asana unavailability.

**Recommendation:** Add an explicit startup health check: if Asana is unreachable, log a warning and start in read-only mode. Surface a `GET /health` endpoint that returns Asana connectivity status. This enables operators to know immediately if sync is degraded.

---

**[HIGH] Rate limiting: 1,500 req/min is shared across all Asana apps on the account**

The asana-mapping doc sets `max_requests_per_minute = 1400` as a conservative buffer below Asana's 1,500 limit. **However, this 1,500 limit is per OAuth application, not per user.** If there are other Asana integrations on the BAM Systematic account (e.g., existing project management tools, data connectors), those will compete for the same rate limit budget.

**Recommendation:** Validate whether BAM Systematic already has other Asana integrations consuming rate limit budget before committing to the 1,400 req/min assumption. Size the full-sync batch job (which does the most API calls) conservatively.

---

**[HIGH] Webhook secret rotation**

The architecture stores `asana_webhook_secret` in `.env`. There is no documented process for rotating this secret if it is compromised, or if the webhook registration needs to be re-done. In a security-conscious financial services environment, secrets must be rotatable without downtime.

**Recommendation:** Document the webhook secret rotation procedure before v1 goes live. The sidecar should support loading a new webhook secret without restart (e.g., via a config reload endpoint or by reading from a secrets manager rather than the `.env` file at startup).

---

**[MEDIUM] SQLite WAL mode not enforced in code**

The architecture recommends enabling WAL mode for better read concurrency. The `database.py` configuration should explicitly set `PRAGMA journal_mode=WAL` on connection startup. This is not mentioned in the architecture doc as a required implementation step — it is mentioned as advice but could be missed during implementation.

**Recommendation:** Add `PRAGMA journal_mode=WAL` as a required step in `database.py` setup, documented explicitly in the implementation checklist.

---

**[MEDIUM] APScheduler job: what if two sidecar instances run simultaneously?**

If the sidecar is ever deployed in more than one process (e.g., for a blue-green deployment or restart), two instances of APScheduler could fire the same jobs simultaneously. This would create duplicate digests, double-write to Asana, and corrupt the `job_run` deduplication table.

**Recommendation:** The job run deduplication check (`job_name + execution_date`) must use a database-level unique constraint, not application-level logic, to prevent duplicate job runs. A DB-level unique constraint fails fast and atomically; application-level checks have a TOCTOU race condition.

---

## 7. Security / Safety Concerns

**[HIGH] Bot `POST /pm-coverage` and `POST /pm-needs` have no approval gate**

The architecture doc says "Project creation requires human confirmation; task creation via bot is allowed with required metadata." But the API spec includes `POST /pm-coverage` (creates a PM Coverage record) without explicitly flagging this as project-creation vs task-creation.

Creating a PM Coverage record is functionally equivalent to starting a new PM onboarding track. This should require human confirmation, not be allowed as an unrestricted bot-initiated action. The "task creation via bot is allowed" rule was probably intended for creating deliverables and PM Needs, not for standing up entire PM Coverage records.

**Recommendation:** Add an explicit list of "bot-allowed creates" vs "human-confirmation required creates":
- Bot-allowed: `POST /pm-needs`, `POST /risks`, `POST /decisions`
- Human confirmation required: `POST /pm-coverage`, template instantiation (which creates an Asana project)

---

**[HIGH] API key authentication in v1 is single-key-for-all-clients**

The architecture resolves the auth question as "API key (v1)." If there is only one API key and it is shared between the scheduled automation jobs, a future Slack bot, and any human-operated API calls, then a compromise of that key gives full write access to everything. In a financial services context, this is a material risk.

**Recommendation:** Issue separate API keys for: (a) internal scheduled jobs, (b) any external bot/client. Log the source key with every write operation in the audit log. This enables forensic analysis if something goes wrong.

---

**[MEDIUM] Sidecar can write derived fields back to Asana custom fields**

The sync direction table includes S→A writes for `Age (Days)`, risk age computed by the sidecar written back to Asana. If the sidecar's computation has a bug (e.g., off-by-one on date math), it will silently overwrite correct data in Asana with incorrect data. Users who trust the Asana `Age (Days)` field will see incorrect escalation triggers.

**Recommendation:** Any sidecar S→A writeback should include a sanity check: refuse to write a value that would change an existing Asana value by more than a configurable threshold (e.g., refuse to write `Age (Days) = 500` when the previous value was 5). Log these skipped writes as warnings.

---

**[LOW] No input sanitization noted for PM names used in naming conventions**

The asana-mapping doc enforces naming conventions like `Onboarding - [PM Name] - [Strategy/Region]`. If a PM name contains special characters (slashes, colons, pipes), Asana project names could become malformed or cause issues in later string matching. Add a sanitization step in the naming convention validator.

---

## 8. Missing Elements

**[MEDIUM] workflows.md: backward state transitions for onboarding stage have no enforcement mechanism**

The workflows doc specifies backward transitions: `uat → onboarding_in_progress` (failed UAT), `go_live_ready → onboarding_in_progress` (gate failure). This is the right design, but neither the architecture doc nor the domain model doc specifies where these transition rules are enforced. The PMCoverageRecord domain model just has an `OnboardingStage` enum — there is no state machine guard.

**Problem:** A bot or API call could move a PM from `live` back to `pipeline` without triggering any side effects. Backward transitions should be: (1) logged as significant events in the audit trail, (2) subject to validation (you cannot skip multiple stages backward without explicit override), and (3) trigger a new RiskBlocker automatically (e.g., "UAT Failed — PM moved back to onboarding_in_progress").

**Recommendation:** Add a `validate_onboarding_transition(current_stage, new_stage)` function to `pm_coverage_service.py` that enforces allowed transitions and fires side effects on backwards moves.

---

**[MEDIUM] workflows.md: duplicate PM Need detection has no system mechanism**

The PM Need intake workflow (step error handling) says "Duplicate need detected (same PM, similar category) — Flag for deduplication; link to existing need or close as duplicate." However, there is no system mechanism described to detect or flag duplicates. The asana-mapping doc does not include a deduplication field on PMNeed.

In practice, duplicate PM Needs will accumulate silently. Over 6 months, a PM could have 3 nearly-identical "historical data feed for region X" needs, none linked, all sitting in different statuses.

**Recommendation:** Add a `possible_duplicate_of: Optional[str]` field (FK to another PMNeed) to the PMNeed schema. In v1, flag duplicates manually during triage. In v2, build a similarity check based on PM + category + title text.

---

**[LOW] Weekly operating review agenda generation: no idempotency specification**

The workflows doc says "The system generates the agenda automatically" and the architecture mentions `weekly_review_prep.py` as a scheduled job. But there is no idempotency spec: if the weekly review prep job runs twice (e.g., due to a scheduler retry), does it create two status update drafts? Two Slack messages? Two Asana tasks?

**Recommendation:** The weekly review prep job should be idempotent: check if an agenda already exists for this week before creating one. Store the agenda as a `StatusUpdate` with a unique `scope_type=operating_review` + `week_of` date key. If it already exists, overwrite (don't create a second). Add this rule to the `weekly_review_prep.py` design.

---

**[MEDIUM] No specification for how the sidecar handles the first-ever startup (cold start)**

When the sidecar runs for the first time against an existing Asana workspace that already has projects, tasks, and milestones, what happens? The architecture mentions a `scripts/backfill_sync.py` script, but there is no specification for:
- What the backfill script does (does it upsert or insert-only?)
- What order objects should be synced (projects before tasks before milestones, to avoid FK constraint violations)
- What happens if the backfill is interrupted partway through

**Recommendation:** Document the cold-start / backfill procedure explicitly before v1 implementation. This is a critical operational moment that is underspecified.

---

**[MEDIUM] No archival model for PM Needs after delivery**

The vision and asana-mapping doc describe PM Need statuses through `delivered` and `deferred`. But there is no archival spec: do delivered PM Needs stay in the `PM Needs` Asana project forever? After 100 PMs, this project could have thousands of tasks. The Asana performance degradation threshold for large projects is real.

**Recommendation:** Define an archival policy for delivered/cancelled PM Needs (e.g., archive in Asana after 90 days, retain in sidecar indefinitely). Add this to the asana-mapping doc.

---

**[LOW] No specification for what happens when a PM's go-live date slips**

The PM Coverage Record has a `go_live_target_date`. The vision describes milestone slips and escalations. But the data model and workflow docs do not specify what system actions should happen when a go-live date is updated. Should the sidecar re-evaluate all dependent milestone dates? Should a risk be auto-created? Or is this purely a human judgment call?

---

**[LOW] Stakeholder / Team Map deferred without a lightweight substitute**

The vision includes a Stakeholder Map as a v2 artifact, but notes it is "Optional in v1." In practice, the role described in the vision (sitting between PMs, business, and tech, holding cross-functional partners accountable) requires knowing who to escalate to on the tech side. Without even a lightweight stakeholder reference, the escalation workflow has no automated "who to notify" component.

**Recommendation:** Add a minimal stakeholder reference as a config file (YAML or JSON with team names, Slack handles, email aliases) in v1. This is not a database table — just a config file that the sidecar reads to know who to notify for escalations. Promotes the Stakeholder Map to a first-class data object in v2.

---

## 9. API Design Issues

### Findings from docs/api-design.md

**[POSITIVE] `POST /decisions/{decision_id}/resolve` as a separate endpoint**

The API design uses a dedicated `POST /decisions/{decision_id}/resolve` endpoint rather than a generic `PATCH /decisions/{decision_id}` for recording decision outcomes. This is the right pattern: it enforces intent (resolving is a state transition, not a field patch), makes the audit trail cleaner, and naturally prevents resolving a decision twice via idempotency checks. This aligns with the "append-only" architecture intent and should be extended as a model for other high-consequence state transitions (e.g., consider `POST /risks/{risk_id}/escalate` rather than `PATCH /risks/{risk_id}` for escalation).

---

**[HIGH] `PATCH /projects/{project_id}` is missing from the API spec**

The bot command spec includes `/update-health [project] [green|yellow|red]` which maps to `PATCH /projects/{project_id}`. However, the Projects section of the API spec (Section 3) defines only `GET /projects`, `GET /projects/{project_id}`, and `GET /projects/{project_id}/milestones` — no PATCH endpoint. This is an incomplete API spec.

**Recommendation:** Add `PATCH /projects/{project_id}` with a `ProjectUpdate` request body (health, status, owner) to the API spec before implementation begins. This is a required endpoint for the bot to function.

---

**[HIGH] `GET /operating-review/agenda` has no caching or idempotency spec**

The agenda endpoint auto-generates the weekly operating review. If two users call `/weekly-review` simultaneously (or if the endpoint is called twice by the scheduler), two separate agenda generations execute in parallel. Each reads the same DB state and may each write a `StatusUpdate` record — resulting in duplicates. The existing idempotency recommendation (Section 8, weekly review prep) applies here but specifically at the HTTP layer too.

**Recommendation:** The `GET /operating-review/agenda` endpoint should be read-only and stateless — it should not write anything (no `StatusUpdate` record created). If the agenda needs to be persisted for the Slack post, that persistence should be done by the `weekly_review_prep.py` job, not by the HTTP endpoint. The endpoint should always return the current live state, making it naturally idempotent.

---

**[MEDIUM] Concurrent scheduled jobs can collectively exhaust the Asana API rate budget**

The API spec and architecture both note that there is no inbound rate limiting on the sidecar's REST API in v1 ("low traffic, internal service"). However, the scheduled automation jobs — daily digest, weekly review prep, milestone watch, and orphan detection — all call the Asana API. If multiple jobs fire in close succession (e.g., all scheduled at 08:00), the collective outbound Asana API call volume could spike. The asana-mapping doc sets `max_requests_per_minute = 1400`, but there is no coordination between APScheduler jobs to share that budget.

**Recommendation:** Add a shared `AsanaRateLimiter` singleton that all jobs and API handlers share when calling the Asana client. Jobs should acquire rate limit tokens from this shared pool rather than each managing their own throttle. This prevents the daily digest job from starving the webhook handler of its API budget during a sync spike.

---

**[MEDIUM] Bot command `/new-pm` maps to `POST /pm-coverage` + `POST /projects` but the API spec shows no atomicity guarantee**

The bot `/new-pm` flow (Section: Bot Command Spec) calls `POST /pm-coverage` then `POST /projects` (template instantiation). These are two separate API calls with no transaction boundary. If `POST /pm-coverage` succeeds but `POST /projects` fails (Asana timeout, rate limit), the system is left with a PM Coverage record that has no associated onboarding project.

**Recommendation:** Introduce a `POST /pm-onboarding` composite endpoint that wraps both operations in a single service call with compensating rollback logic (the saga pattern recommended in Section 4 for template instantiation). The bot should call the composite endpoint, not two separate endpoints.

---

**[LOW] `GET /health` response does not include last successful sync time**

The health endpoint returns `{"status": "ok", "db": "connected", "asana": "reachable", "scheduler": "running"}`. This tells operators the service is alive but not whether it is current. A sidecar that is running but hasn't synced from Asana in 18 hours looks identical to one that synced 5 minutes ago.

**Recommendation:** Add `"last_sync_at": "2026-03-01T07:42:00Z"` and `"last_job_run_at": "2026-03-01T08:00:00Z"` to the `GET /health` response. This makes data freshness visible at a glance and enables automated staleness monitoring.

---

## 10. Recommendations (Prioritized)

### Must fix before implementation begins

| Priority | Issue | Action |
|---|---|---|
| P0 | PM Need `status` dual-write ambiguity | Clarify write ownership; sidecar's `status` on PMNeed is read-only cache; Asana section is canonical |
| P0 | PM Coverage SoT contradiction | Document explicit write path: Asana section for stage/health, sidecar API for all other fields |
| P0 | Decision "append-only" vs PATCH contradiction | Immutable once decided; only pending decisions are patchable; enforce in validation layer |
| P0 | Webhook handler in-process reliability vs APScheduler gap | Explicitly choose: sync processing in v1 (accept 10-second latency), async queue in v2 |
| P0 | `PATCH /projects/{project_id}` missing from API spec | Add ProjectUpdate endpoint; bot `/update-health` command requires it |
| P1 | Remove `top_open_need_ids` / `top_blocker_ids` from PMCoverageRecord schema | Compute on read; avoid fan-out update complexity |
| P1 | Add job failure alerting watchdog | Hourly check of job_run table; alert on failures or missed job windows |
| P1 | Escalation on orphaned critical Asana objects | Alert (not just log) when PM Coverage tasks or go-live milestones are orphaned |
| P1 | Sidecar startup degraded mode for Asana unavailability | Read-only mode when Asana unreachable; `GET /health` endpoint |
| P1 | `Age (Days)` writeback: compute on read instead | Remove S→A daily batch writeback; compute dynamically in sidecar query layer |
| P1 | `/new-pm` bot flow: composite endpoint with rollback | `POST /pm-onboarding` wrapping PM Coverage + template instantiation in one saga |

### Should fix before v1 release

| Priority | Issue | Action |
|---|---|---|
| P2 | DB-level unique constraint on job_run deduplication | Prevent duplicate job runs on multi-instance deployments |
| P2 | Template instantiation saga pattern | Idempotent retry with progress tracking; prevent broken partial projects |
| P2 | `PM` field: text to structured ID | Validate `pm_id` format on PM Need intake; no free text |
| P2 | Webhook secret rotation procedure | Document and test before v1 goes live |
| P2 | SQLite WAL mode in code | Enforce `PRAGMA journal_mode=WAL` in `database.py` startup |
| P2 | PM Need archival policy | Define Asana archival for delivered/cancelled needs at 90 days |
| P2 | Onboarding state transition guard | `validate_onboarding_transition()` with side effects (auto-open RiskBlocker on backwards moves) |
| P2 | Weekly review prep idempotency | `GET /operating-review/agenda` must be read-only; persistence done by scheduled job only |
| P2 | Shared Asana rate limiter across jobs and handlers | Single `AsanaRateLimiter` singleton prevents job vs. webhook handler budget starvation |
| P2 | `GET /health` data freshness fields | Add `last_sync_at` and `last_job_run_at` to health response |
| P2 | Cold-start / backfill procedure doc | Explicit order-of-operations for first sync from existing Asana workspace |
| P2 | Separate API keys per consumer | Scheduled jobs key, bot key; source logged in audit trail |
| P3 | `possible_duplicate_of` on PMNeed | Manual triage field; auto-detection in v2 |
| P3 | SyncState enum: defer to v2 | Replace with `asana_gid` + `asana_synced_at` only in v1 |
| P3 | Decisions registry: simplify in v1 | Asana Decision Log only; minimal sidecar endpoint for query; full registry in v2 |
| P3 | Lightweight stakeholder config file | YAML config for escalation contacts; not a DB object in v1 |
| P3 | Use `POST /risks/{risk_id}/escalate` pattern | Model specific state transitions as dedicated endpoints rather than generic PATCH (follow `resolve` pattern) |

### Can defer to v2

| Item | Rationale |
|---|---|
| Full SyncState machine (pending_push/pull/conflict) | Over-engineered for v1 scale and cadence |
| Alembic migrations | Schema is too volatile in v1; introduce in v2 |
| `external.id` field usage on Asana tasks | Adds write surface; not worth complexity in v1 |
| PM health watch automation job | Start with daily digest only; add PM health watch in v1.5 |
| Full decision registry (options_considered, rationale, impacted_artifacts) | Deliver lightweight in v1; enrich in v2 |
| Cross-project dependency graph | Complex; start after PM/Project data is stable |
| Webhook receiver full reliability (vs polling) | Polish for v2; polling fallback is sufficient for v1 |

---

## Closing Assessment

The overall design direction is correct. The architecture team has avoided the most common failure modes in this kind of system (building a custom task tracker, ignoring Asana-native capabilities, designing for a user base that doesn't exist yet). The three-tier Asana + sidecar + chat approach is appropriate.

The issues flagged above are not fundamental architectural problems — they are specification gaps and implementation risks that should be resolved before the first line of production code is written. The highest-risk items are the PM Need and PM Coverage source-of-truth contradictions, which if left unresolved will cause confusing bugs in the sync layer that are hard to debug after the fact.

Recommend the team spend one focused session (2 hours) resolving the P0 items above as explicit decision records before the backend engineering phase begins.
