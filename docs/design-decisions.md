# Design Decisions — P0 Resolutions

Resolved by team lead on 2026-03-01 in response to design-review.md findings.

---

## D1: PM Need `status` write ownership

**Decision:** Asana section (Kanban column) is the canonical source for PM Need `status`. The sidecar's `status` field is a read-only cache synced from Asana via webhook/poll. `status` has been removed from `PMNeedUpdate` schema.

**Rationale:** Eliminates dual-write ambiguity. Operators manage PM Need status by dragging cards in Asana; the sidecar mirrors this.

---

## D2: PM Coverage write path

**Decision:** PM Coverage Record is split-ownership:
- **Asana** is the write surface for `onboarding_stage` and `health_status` (operators drag Kanban cards in the PM Coverage Board)
- **Sidecar API** is the write surface for all other fields (notes, linked_project_ids, strategy_type, coverage_owner, etc.)
- Webhook syncs stage/health changes from Asana to sidecar

**Rationale:** Operators already use Asana daily for status tracking. Forcing them through an API for stage changes adds friction. Rich relational fields don't exist in Asana, so those stay sidecar-writable.

---

## D3: Decision immutability

**Decision:** Decisions are immutable once `status = decided`. Only `pending` decisions can be updated via `PATCH`. To change a decided outcome, create a new Decision with `status = pending` and set `superseded_by_id` on the original.

**Rationale:** Preserves decision history and rationale. Prevents silent re-litigation.

---

## D4: Webhook processing in v1

**Decision:** Process webhook events synchronously in v1 (within the 10-second Asana window). No async job queue. Accept that if the process restarts during processing, that event may be lost. The hourly incremental poll (see D6) closes the reliability gap.

**Rationale:** Adding Celery/RQ is over-engineered for v1 scale. Simple DB upserts easily fit within 10 seconds. The polling fallback catches any missed events.

---

## D5: Remove derived fields from PMCoverageRecord

**Decision:** `top_open_need_ids` and `top_blocker_ids` removed from the PMCoverageRecord schema. These are computed on read by querying PMNeed and RiskBlocker tables filtered by `pm_id`.

**Rationale:** Eliminates fan-out update complexity. Avoids stale denormalized data.

---

## D6: Simplify sync tracking for v1

**Decision:** Full `SyncState` enum (pending_push/pull/conflict) removed. V1 uses `asana_gid` (set or null) + `asana_synced_at` (last sync timestamp). Add hourly incremental poll checking tasks modified in the last 2 hours as a safety net for missed webhooks.

**Rationale:** SyncState machine adds complexity without clear operational benefit at v1 scale. Simpler tracking is easier to debug and maintain.

---

## D7: Age (Days) computation

**Decision:** `age_days` on Risk/Blocker is computed on read (dynamically in the query layer), not written back to Asana.

**Rationale:** Eliminates stale data window and removes an S→A writeback path.

---

## D8: Health endpoint and degraded mode

**Decision:** Add `GET /health` endpoint that returns Asana connectivity status. If Asana is unreachable at startup, sidecar starts in read-only mode (serves cached SQLite data, refuses writes that require Asana).

**Rationale:** Operators need status dashboards even when Asana is degraded. Financial PMO context requires high availability for reads.
