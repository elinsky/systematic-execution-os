"""Webhook integration test — sends simulated Asana webhook payloads to the sidecar.

Validates that the sidecar's webhook endpoint correctly handles:
  1. Handshake: X-Hook-Secret header exchange (Asana initial verification)
  2. Task created events (action: "added")
  3. Task updated events (action: "changed" with relevant field changes)
  4. Task completed events (action: "changed" with completed field)
  5. HMAC-SHA256 signature validation (valid and invalid signatures)
  6. Irrelevant field filtering (events with only noise fields are skipped)
  7. Duplicate event deduplication (same event_gid sent twice)

Prerequisites:
  - The sidecar server is running on localhost:8000 (or SIDECAR_BASE_URL)
  - ASANA_WEBHOOK_SECRET is set (or defaults to "test-webhook-secret")

Usage:
    python3 scripts/test_webhooks.py

Exit codes:
    0  — all checks passed
    1  — one or more checks failed (see FAIL lines in output)
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import sys
import uuid

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SIDECAR_BASE_URL = os.environ.get("SIDECAR_BASE_URL", "http://localhost:8000")
WEBHOOK_PATH = "/api/v1/webhooks/asana"
WEBHOOK_URL = f"{SIDECAR_BASE_URL}{WEBHOOK_PATH}"
WEBHOOK_SECRET = os.environ.get("ASANA_WEBHOOK_SECRET", "test-webhook-secret")


# ---------------------------------------------------------------------------
# Result tracking (mirrors smoke_test.py pattern)
# ---------------------------------------------------------------------------


class WebhookTestRunner:
    def __init__(self) -> None:
        self._pass = 0
        self._fail = 0

    def check(self, label: str, condition: bool, detail: str = "") -> None:
        if condition:
            self._pass += 1
            print(f"  PASS  {label}")
        else:
            self._fail += 1
            msg = f"  FAIL  {label}"
            if detail:
                msg += f"\n        {detail}"
            print(msg)

    def summary(self) -> int:
        total = self._pass + self._fail
        print(f"\n{'=' * 50}")
        print(f"Results: {self._pass}/{total} passed, {self._fail} failed")
        print("=" * 50)
        return 0 if self._fail == 0 else 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_signature(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    """Compute Asana-style HMAC-SHA256 hex digest for a request body."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _make_task_event(
    *,
    action: str,
    task_gid: str | None = None,
    event_gid: str | None = None,
    change_fields: list[str] | None = None,
) -> dict:
    """Build a realistic Asana webhook event dict for a task."""
    task_gid = task_gid or str(uuid.uuid4().int)[:16]
    event_gid = event_gid or str(uuid.uuid4().int)[:16]

    event: dict = {
        "gid": event_gid,
        "action": action,
        "resource": {
            "gid": task_gid,
            "resource_type": "task",
        },
        "user": {
            "gid": "1200000000000001",
            "resource_type": "user",
        },
        "created_at": "2026-03-01T12:00:00.000Z",
        "parent": {
            "gid": "1200000000000099",
            "resource_type": "project",
        },
    }

    if change_fields is not None:
        event["change"] = [{"field": f, "action": "changed"} for f in change_fields]

    return event


def _make_payload(events: list[dict]) -> bytes:
    """Wrap events in the Asana webhook payload envelope and serialize to bytes."""
    return json.dumps({"events": events}).encode()


# ---------------------------------------------------------------------------
# Test functions
# ---------------------------------------------------------------------------


async def test_handshake(runner: WebhookTestRunner, client: httpx.AsyncClient) -> None:
    """Test Asana webhook handshake (X-Hook-Secret header exchange)."""
    print("\n[1] Webhook handshake (X-Hook-Secret)")

    hook_secret = f"handshake-secret-{uuid.uuid4().hex[:8]}"

    resp = await client.post(
        WEBHOOK_URL,
        content=b"",
        headers={"X-Hook-Secret": hook_secret},
    )

    runner.check("Handshake returns 200", resp.status_code == 200, f"got {resp.status_code}")
    returned_secret = resp.headers.get("X-Hook-Secret", "")
    runner.check(
        "Handshake echoes X-Hook-Secret",
        returned_secret == hook_secret,
        f"got {returned_secret!r}, want {hook_secret!r}",
    )


async def test_task_created(runner: WebhookTestRunner, client: httpx.AsyncClient) -> None:
    """Test handling of a task-added event with valid HMAC signature."""
    print("\n[2] Task created event (action: added)")

    event = _make_task_event(action="added")
    body = _make_payload([event])
    signature = _compute_signature(body)

    resp = await client.post(
        WEBHOOK_URL,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hook-Signature": signature,
        },
    )

    runner.check("Task created returns 200", resp.status_code == 200, f"got {resp.status_code}")

    data = resp.json()
    runner.check("Response has ok=True", data.get("ok") is True, f"got {data}")


async def test_task_updated(runner: WebhookTestRunner, client: httpx.AsyncClient) -> None:
    """Test handling of a task-changed event with relevant field changes."""
    print("\n[3] Task updated event (action: changed, relevant fields)")

    event = _make_task_event(
        action="changed",
        change_fields=["name", "assignee", "due_on"],
    )
    body = _make_payload([event])
    signature = _compute_signature(body)

    resp = await client.post(
        WEBHOOK_URL,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hook-Signature": signature,
        },
    )

    runner.check("Task updated returns 200", resp.status_code == 200, f"got {resp.status_code}")

    data = resp.json()
    runner.check("Response has ok=True", data.get("ok") is True, f"got {data}")

    # Verify the event was processed (not skipped as irrelevant)
    results = data.get("results", [])
    if results:
        first = results[0]
        runner.check(
            "Event was not skipped as irrelevant",
            first.get("skipped") is not True or first.get("reason") != "irrelevant_fields",
            f"got {first}",
        )
    else:
        runner.check("Response contains results", False, "empty results list")


async def test_task_completed(runner: WebhookTestRunner, client: httpx.AsyncClient) -> None:
    """Test handling of a task completion event (completed field change)."""
    print("\n[4] Task completed event (action: changed, completed field)")

    event = _make_task_event(
        action="changed",
        change_fields=["completed"],
    )
    body = _make_payload([event])
    signature = _compute_signature(body)

    resp = await client.post(
        WEBHOOK_URL,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hook-Signature": signature,
        },
    )

    runner.check(
        "Task completed returns 200", resp.status_code == 200, f"got {resp.status_code}"
    )

    data = resp.json()
    runner.check("Response has ok=True", data.get("ok") is True, f"got {data}")


async def test_valid_signature(runner: WebhookTestRunner, client: httpx.AsyncClient) -> None:
    """Test that a correctly signed request is accepted."""
    print("\n[5] HMAC-SHA256 signature validation (valid signature)")

    event = _make_task_event(action="added")
    body = _make_payload([event])
    signature = _compute_signature(body, WEBHOOK_SECRET)

    resp = await client.post(
        WEBHOOK_URL,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hook-Signature": signature,
        },
    )

    runner.check(
        "Valid signature accepted (200)",
        resp.status_code == 200,
        f"got {resp.status_code}",
    )

    data = resp.json()
    runner.check(
        "Valid signature: ok=True",
        data.get("ok") is True,
        f"got {data}",
    )


async def test_invalid_signature(runner: WebhookTestRunner, client: httpx.AsyncClient) -> None:
    """Test that a request with an invalid HMAC signature is rejected."""
    print("\n[6] HMAC-SHA256 signature validation (invalid signature)")

    event = _make_task_event(action="added")
    body = _make_payload([event])

    # Compute signature with the wrong secret
    bad_signature = _compute_signature(body, "wrong-secret-value")

    resp = await client.post(
        WEBHOOK_URL,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hook-Signature": bad_signature,
        },
    )

    # The endpoint should still return 200 (Asana best practice: always return 200)
    # but the internal result should indicate an invalid signature
    runner.check(
        "Invalid signature returns 200",
        resp.status_code == 200,
        f"got {resp.status_code}",
    )

    data = resp.json()
    runner.check(
        "Invalid signature: ok=False",
        data.get("ok") is False,
        f"got {data}",
    )
    runner.check(
        "Invalid signature: error=invalid_signature",
        data.get("error") == "invalid_signature",
        f"got error={data.get('error')!r}",
    )


async def test_missing_signature(runner: WebhookTestRunner, client: httpx.AsyncClient) -> None:
    """Test that a request with no signature header is rejected."""
    print("\n[7] Missing signature header")

    event = _make_task_event(action="added")
    body = _make_payload([event])

    resp = await client.post(
        WEBHOOK_URL,
        content=body,
        headers={"Content-Type": "application/json"},
        # No X-Hook-Signature header
    )

    runner.check(
        "Missing signature returns 200",
        resp.status_code == 200,
        f"got {resp.status_code}",
    )

    data = resp.json()
    runner.check(
        "Missing signature: ok=False",
        data.get("ok") is False,
        f"got {data}",
    )


async def test_irrelevant_fields_skipped(
    runner: WebhookTestRunner, client: httpx.AsyncClient
) -> None:
    """Test that task changes with only irrelevant fields are skipped."""
    print("\n[8] Irrelevant field changes skipped")

    event = _make_task_event(
        action="changed",
        change_fields=["num_likes", "stories"],
    )
    body = _make_payload([event])
    signature = _compute_signature(body)

    resp = await client.post(
        WEBHOOK_URL,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hook-Signature": signature,
        },
    )

    runner.check(
        "Irrelevant fields returns 200",
        resp.status_code == 200,
        f"got {resp.status_code}",
    )

    data = resp.json()
    results = data.get("results", [])
    if results:
        first = results[0]
        runner.check(
            "Irrelevant fields event was skipped",
            first.get("skipped") is True,
            f"got {first}",
        )
        runner.check(
            "Skip reason is irrelevant_fields",
            first.get("reason") == "irrelevant_fields",
            f"got reason={first.get('reason')!r}",
        )
    else:
        runner.check("Response contains results", False, "empty results list")


async def test_duplicate_event_skipped(
    runner: WebhookTestRunner, client: httpx.AsyncClient
) -> None:
    """Test that duplicate events (same event GID) are deduplicated."""
    print("\n[9] Duplicate event deduplication")

    fixed_event_gid = f"dedup-{uuid.uuid4().hex[:8]}"
    event = _make_task_event(action="added", event_gid=fixed_event_gid)

    # Send the event the first time
    body1 = _make_payload([event])
    sig1 = _compute_signature(body1)

    resp1 = await client.post(
        WEBHOOK_URL,
        content=body1,
        headers={
            "Content-Type": "application/json",
            "X-Hook-Signature": sig1,
        },
    )
    runner.check(
        "First send returns 200",
        resp1.status_code == 200,
        f"got {resp1.status_code}",
    )

    # Send the same event a second time
    body2 = _make_payload([event])
    sig2 = _compute_signature(body2)

    resp2 = await client.post(
        WEBHOOK_URL,
        content=body2,
        headers={
            "Content-Type": "application/json",
            "X-Hook-Signature": sig2,
        },
    )

    runner.check(
        "Duplicate send returns 200",
        resp2.status_code == 200,
        f"got {resp2.status_code}",
    )

    data2 = resp2.json()
    results2 = data2.get("results", [])
    if results2:
        first = results2[0]
        runner.check(
            "Duplicate event was skipped",
            first.get("skipped") is True,
            f"got {first}",
        )
        runner.check(
            "Skip reason is duplicate",
            first.get("reason") == "duplicate",
            f"got reason={first.get('reason')!r}",
        )
    else:
        runner.check("Duplicate response contains results", False, "empty results list")


async def test_multiple_events_in_payload(
    runner: WebhookTestRunner, client: httpx.AsyncClient
) -> None:
    """Test that multiple events in a single payload are all processed."""
    print("\n[10] Multiple events in single payload")

    events = [
        _make_task_event(action="added"),
        _make_task_event(action="changed", change_fields=["name"]),
        _make_task_event(action="changed", change_fields=["completed"]),
    ]
    body = _make_payload(events)
    signature = _compute_signature(body)

    resp = await client.post(
        WEBHOOK_URL,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hook-Signature": signature,
        },
    )

    runner.check(
        "Multiple events returns 200",
        resp.status_code == 200,
        f"got {resp.status_code}",
    )

    data = resp.json()
    results = data.get("results", [])
    runner.check(
        "All 3 events have results",
        len(results) == 3,
        f"got {len(results)} results",
    )


# ---------------------------------------------------------------------------
# Connectivity check
# ---------------------------------------------------------------------------


async def check_sidecar_running() -> bool:
    """Return True if the sidecar is reachable at SIDECAR_BASE_URL."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{SIDECAR_BASE_URL}/health")
            return resp.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> int:
    print(f"Webhook test target: {WEBHOOK_URL}")
    print(f"Webhook secret:      {WEBHOOK_SECRET}")

    # Pre-flight: check sidecar is running
    if not await check_sidecar_running():
        print(f"\nERROR: Sidecar is not running at {SIDECAR_BASE_URL}")
        print("Start the sidecar first:  uv run uvicorn sidecar.main:app --reload")
        return 1

    print("Sidecar is running.\n")

    runner = WebhookTestRunner()

    async with httpx.AsyncClient(timeout=10.0) as client:
        await test_handshake(runner, client)
        await test_task_created(runner, client)
        await test_task_updated(runner, client)
        await test_task_completed(runner, client)
        await test_valid_signature(runner, client)
        await test_invalid_signature(runner, client)
        await test_missing_signature(runner, client)
        await test_irrelevant_fields_skipped(runner, client)
        await test_duplicate_event_skipped(runner, client)
        await test_multiple_events_in_payload(runner, client)

    return runner.summary()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
