"""Tests for AsanaWebhookHandler — signature validation and event dispatch."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from sidecar.integrations.asana.webhooks import (
    AsanaWebhookHandler,
    HEADER_HOOK_SECRET,
    noop_handler,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SECRET = "test-webhook-secret"


def sign_body(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def make_payload(events: list[dict]) -> bytes:
    return json.dumps({"events": events}).encode()


def make_task_changed_event(
    resource_gid: str = "task-1",
    changed_fields: list[str] | None = None,
) -> dict[str, Any]:
    change = [{"field": f} for f in (changed_fields or ["custom_fields"])]
    return {
        "gid": f"event-{resource_gid}",
        "action": "changed",
        "resource": {"gid": resource_gid, "resource_type": "task"},
        "change": change,
    }


def make_task_added_event(resource_gid: str = "task-2") -> dict[str, Any]:
    return {
        "gid": f"event-add-{resource_gid}",
        "action": "added",
        "resource": {"gid": resource_gid, "resource_type": "task"},
    }


# ---------------------------------------------------------------------------
# Signature validation
# ---------------------------------------------------------------------------

class TestSignatureValidation:
    @pytest.mark.asyncio
    async def test_valid_signature_accepted(self):
        handler = AsanaWebhookHandler(SECRET)
        body = make_payload([make_task_added_event()])
        sig = sign_body(body)
        result = await handler.handle({"x-hook-signature": sig}, body)
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_invalid_signature_rejected(self):
        handler = AsanaWebhookHandler(SECRET)
        body = make_payload([make_task_added_event()])
        result = await handler.handle({"x-hook-signature": "bad-sig"}, body)
        assert result["ok"] is False
        assert result["error"] == "invalid_signature"

    @pytest.mark.asyncio
    async def test_missing_signature_rejected(self):
        handler = AsanaWebhookHandler(SECRET)
        body = make_payload([make_task_added_event()])
        result = await handler.handle({}, body)
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_tampered_body_rejected(self):
        handler = AsanaWebhookHandler(SECRET)
        original_body = make_payload([make_task_added_event()])
        sig = sign_body(original_body)
        tampered_body = original_body + b"tampered"
        result = await handler.handle({"x-hook-signature": sig}, tampered_body)
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# Handshake detection
# ---------------------------------------------------------------------------

class TestHandshake:
    def test_detects_handshake_header(self):
        secret_val = AsanaWebhookHandler.is_handshake({"X-Hook-Secret": "abc123"})
        assert secret_val == "abc123"

    def test_no_handshake_returns_none(self):
        assert AsanaWebhookHandler.is_handshake({"Content-Type": "application/json"}) is None

    def test_case_insensitive_header(self):
        secret_val = AsanaWebhookHandler.is_handshake({"x-hook-secret": "mySecret"})
        assert secret_val == "mySecret"


# ---------------------------------------------------------------------------
# Event dispatch
# ---------------------------------------------------------------------------

class TestEventDispatch:
    @pytest.mark.asyncio
    async def test_registered_handler_called(self):
        handler = AsanaWebhookHandler(SECRET)
        mock_h = AsyncMock(return_value={"processed": True})
        handler.register("task", "added", mock_h)

        body = make_payload([make_task_added_event("t-abc")])
        sig = sign_body(body)
        await handler.handle({"x-hook-signature": sig}, body)
        mock_h.assert_called_once()

    @pytest.mark.asyncio
    async def test_unregistered_event_skipped(self):
        handler = AsanaWebhookHandler(SECRET)
        mock_h = AsyncMock(return_value={"processed": True})
        handler.register("task", "changed", mock_h)

        body = make_payload([make_task_added_event("t-1")])  # "added", not "changed"
        sig = sign_body(body)
        result = await handler.handle({"x-hook-signature": sig}, body)
        mock_h.assert_not_called()
        assert result["results"][0]["skipped"] is True

    @pytest.mark.asyncio
    async def test_multiple_handlers_all_called(self):
        handler = AsanaWebhookHandler(SECRET)
        mock_a = AsyncMock(return_value={"processed": True, "handler": "a"})
        mock_b = AsyncMock(return_value={"processed": True, "handler": "b"})
        handler.register("task", "changed", mock_a)
        handler.register("task", "changed", mock_b)

        body = make_payload([make_task_changed_event()])
        sig = sign_body(body)
        await handler.handle({"x-hook-signature": sig}, body)
        mock_a.assert_called_once()
        mock_b.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_events_all_dispatched(self):
        handler = AsanaWebhookHandler(SECRET)
        calls: list[dict] = []

        async def capture(event: dict) -> dict:
            calls.append(event)
            return {"processed": True}

        handler.register("task", "added", capture)
        handler.register("task", "changed", capture)

        events = [
            make_task_added_event("t-1"),
            make_task_changed_event("t-2"),
        ]
        body = make_payload(events)
        sig = sign_body(body)
        result = await handler.handle({"x-hook-signature": sig}, body)
        assert len(calls) == 2
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_handler_exception_does_not_propagate(self):
        handler = AsanaWebhookHandler(SECRET)

        async def failing_handler(event: dict) -> dict:
            raise RuntimeError("handler blew up")

        handler.register("task", "added", failing_handler)
        body = make_payload([make_task_added_event()])
        sig = sign_body(body)
        # Should not raise — errors are caught and logged
        result = await handler.handle({"x-hook-signature": sig}, body)
        assert result["ok"] is True
        event_result = result["results"][0]
        assert "error" in event_result["handler_results"][0]


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    @pytest.mark.asyncio
    async def test_duplicate_event_skipped(self):
        handler = AsanaWebhookHandler(SECRET)
        mock_h = AsyncMock(return_value={"processed": True})
        handler.register("task", "added", mock_h)

        event = make_task_added_event("t-dup")
        body = make_payload([event])
        sig = sign_body(body)

        # First delivery
        await handler.handle({"x-hook-signature": sig}, body)
        # Second delivery (same event_gid)
        await handler.handle({"x-hook-signature": sig}, body)

        # Handler should only be called once
        mock_h.assert_called_once()

    @pytest.mark.asyncio
    async def test_different_events_not_deduplicated(self):
        handler = AsanaWebhookHandler(SECRET)
        mock_h = AsyncMock(return_value={"processed": True})
        handler.register("task", "added", mock_h)

        body1 = make_payload([make_task_added_event("t-1")])
        body2 = make_payload([make_task_added_event("t-2")])
        sig1 = sign_body(body1)
        sig2 = sign_body(body2)

        await handler.handle({"x-hook-signature": sig1}, body1)
        await handler.handle({"x-hook-signature": sig2}, body2)

        assert mock_h.call_count == 2


# ---------------------------------------------------------------------------
# Noise filtering
# ---------------------------------------------------------------------------

class TestNoiseFiltering:
    @pytest.mark.asyncio
    async def test_irrelevant_field_changes_skipped(self):
        handler = AsanaWebhookHandler(SECRET)
        mock_h = AsyncMock(return_value={"processed": True})
        handler.register("task", "changed", mock_h)

        # num_likes is not in RELEVANT_TASK_FIELDS
        event = make_task_changed_event("t-likes", changed_fields=["num_likes"])
        body = make_payload([event])
        sig = sign_body(body)
        result = await handler.handle({"x-hook-signature": sig}, body)
        mock_h.assert_not_called()
        assert result["results"][0]["skipped"] is True

    @pytest.mark.asyncio
    async def test_relevant_field_change_dispatched(self):
        handler = AsanaWebhookHandler(SECRET)
        mock_h = AsyncMock(return_value={"processed": True})
        handler.register("task", "changed", mock_h)

        event = make_task_changed_event("t-cf", changed_fields=["custom_fields"])
        body = make_payload([event])
        sig = sign_body(body)
        await handler.handle({"x-hook-signature": sig}, body)
        mock_h.assert_called_once()

    @pytest.mark.asyncio
    async def test_story_events_skipped(self):
        handler = AsanaWebhookHandler(SECRET)
        mock_h = AsyncMock(return_value={"processed": True})
        handler.register("story", "added", mock_h)

        story_event = {
            "gid": "event-story-1",
            "action": "added",
            "resource": {"gid": "story-abc", "resource_type": "story"},
        }
        body = make_payload([story_event])
        sig = sign_body(body)
        result = await handler.handle({"x-hook-signature": sig}, body)
        mock_h.assert_not_called()
        assert result["results"][0]["reason"] == "story_event"


# ---------------------------------------------------------------------------
# Noop handler
# ---------------------------------------------------------------------------

class TestNoopHandler:
    @pytest.mark.asyncio
    async def test_noop_returns_not_processed(self):
        event = make_task_added_event()
        result = await noop_handler(event)
        assert result["processed"] is False
        assert result["reason"] == "noop"
