"""Idempotency helpers for Asana sync and bot operations.

Rules (from architecture.md Section 6):
1. Create operations: check asana_gid — if exists, convert to update.
2. Update operations: compare field values before writing — skip no-ops.
3. Job runs: deduplicate by job name + execution date.
4. Bot actions: deduplicate by client_request_id within 24h window.
"""

# TODO (Task #13): Implement idempotency key checking and job run deduplication.
