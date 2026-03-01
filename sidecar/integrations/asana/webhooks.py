"""Asana webhook receiver and event dispatcher.

Responsibilities:
- Validate X-Hook-Secret HMAC signature on incoming requests
- Handle the initial Asana handshake (echo the secret on first delivery)
- Dispatch events to typed handlers by resource_type + action
- Synchronous processing in v1 (per design-decision D4) — fits within 10s window
- Idempotent event processing via event_id deduplication
- Return 200 always to Asana; log errors internally

Event handler contract:
    Each handler receives the raw event dict (from the Asana payload) and
    returns a dict with ``{"processed": bool, "entity_type": str, "gid": str}``.
    Handlers must not raise — they should catch and log internally.

Reference: https://developers.asana.com/docs/webhooks
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Asana webhook header names
HEADER_HOOK_SECRET = "X-Hook-Secret"
HEADER_HOOK_SIGNATURE = "X-Hook-Signature"

# Event action constants
ACTION_ADDED = "added"
ACTION_CHANGED = "changed"
ACTION_REMOVED = "removed"
ACTION_DELETED = "deleted"

# Resource type constants
RESOURCE_TASK = "task"
RESOURCE_PROJECT = "project"
RESOURCE_SECTION = "section"
RESOURCE_STORY = "story"

# Fields we care about for task changes — ignore noise like num_likes, stories
RELEVANT_TASK_FIELDS = frozenset(
    {
        "name",
        "assignee",
        "due_on",
        "completed",
        "custom_fields",
        "memberships",  # section changes
        "dependencies",
        "notes",
    }
)

# Handler type: async callable that accepts an event dict
EventHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class AsanaWebhookHandler:
    """Validates and dispatches Asana webhook events.

    Usage::

        handler = AsanaWebhookHandler(secret="my-webhook-secret")
        handler.register("task", "changed", my_task_changed_handler)

        # In FastAPI route:
        @app.post("/sync/webhook")
        async def webhook(request: Request):
            body = await request.body()
            headers = dict(request.headers)

            # Handshake — Asana sends X-Hook-Secret on first delivery
            handshake_secret = headers.get("x-hook-secret")
            if handshake_secret:
                return Response(headers={"X-Hook-Secret": handshake_secret})

            result = await webhook_handler.handle(headers, body)
            return {"ok": True}
    """

    def __init__(self, secret: str) -> None:
        self._secret = secret.encode() if isinstance(secret, str) else secret
        self._handlers: dict[tuple[str, str], list[EventHandler]] = {}
        self._seen_event_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Handler registration
    # ------------------------------------------------------------------

    def register(
        self,
        resource_type: str,
        action: str,
        handler: EventHandler,
    ) -> None:
        """Register a handler for a specific (resource_type, action) pair.

        Multiple handlers can be registered for the same event type —
        all are called in registration order.
        """
        key = (resource_type, action)
        self._handlers.setdefault(key, []).append(handler)

    # ------------------------------------------------------------------
    # Main dispatch entrypoint
    # ------------------------------------------------------------------

    async def handle(
        self,
        headers: dict[str, str],
        raw_body: bytes,
    ) -> dict[str, Any]:
        """Validate signature and dispatch all events in the payload.

        Returns a summary dict. Always logs errors internally rather than
        raising, so the HTTP handler can safely return 200 to Asana.
        """
        # Normalize header keys to lowercase for consistent lookup
        norm_headers = {k.lower(): v for k, v in headers.items()}

        # Signature validation
        signature = norm_headers.get("x-hook-signature", "")
        if not self._verify_signature(raw_body, signature):
            logger.warning("asana_webhook_bad_signature")
            return {"ok": False, "error": "invalid_signature"}

        # Parse payload
        import json

        try:
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("asana_webhook_parse_error", error=str(exc))
            return {"ok": False, "error": "parse_error"}

        events: list[dict[str, Any]] = payload.get("events", [])
        results = []

        for event in events:
            result = await self._dispatch_event(event)
            results.append(result)

        logger.info(
            "asana_webhook_processed",
            total_events=len(events),
            processed=sum(1 for r in results if r.get("processed")),
            skipped=sum(1 for r in results if r.get("skipped")),
        )
        return {"ok": True, "results": results}

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    async def _dispatch_event(self, event: dict[str, Any]) -> dict[str, Any]:
        event_gid = event.get("gid") or ""
        resource = event.get("resource") or {}
        resource_type = resource.get("resource_type", "")
        resource_gid = resource.get("gid", "")
        action = event.get("action", "")

        log = logger.bind(
            event_gid=event_gid,
            resource_type=resource_type,
            resource_gid=resource_gid,
            action=action,
        )

        # Idempotency: skip already-seen events
        if event_gid and event_gid in self._seen_event_ids:
            log.debug("asana_webhook_duplicate_skipped")
            return {"processed": False, "skipped": True, "reason": "duplicate"}
        if event_gid:
            self._seen_event_ids.add(event_gid)
            # Bound memory: trim oldest entries if set grows large
            if len(self._seen_event_ids) > 10_000:
                # Remove ~10% by converting to list and slicing
                ids = list(self._seen_event_ids)
                self._seen_event_ids = set(ids[1000:])

        # Filter noise: for task changes, skip if only irrelevant fields changed
        if resource_type == RESOURCE_TASK and action == ACTION_CHANGED:
            changed_fields = {c.get("field", "") for c in event.get("change", [])}
            if changed_fields and not changed_fields.intersection(RELEVANT_TASK_FIELDS):
                log.debug("asana_webhook_irrelevant_fields_skipped", fields=changed_fields)
                return {"processed": False, "skipped": True, "reason": "irrelevant_fields"}

        # Skip story events (comments, likes)
        if resource_type == RESOURCE_STORY:
            return {"processed": False, "skipped": True, "reason": "story_event"}

        # Dispatch to registered handlers
        key = (resource_type, action)
        handlers = self._handlers.get(key, [])

        if not handlers:
            log.debug("asana_webhook_no_handler")
            return {
                "processed": False,
                "skipped": True,
                "reason": "no_handler",
                "resource_type": resource_type,
                "action": action,
            }

        handler_results = []
        for handler in handlers:
            try:
                result = await handler(event)
                handler_results.append(result)
            except Exception as exc:
                log.error(
                    "asana_webhook_handler_error",
                    handler=handler.__name__,
                    error=str(exc),
                    exc_info=True,
                )
                handler_results.append({"error": str(exc)})

        return {
            "processed": True,
            "resource_type": resource_type,
            "resource_gid": resource_gid,
            "action": action,
            "handler_results": handler_results,
        }

    # ------------------------------------------------------------------
    # Signature verification
    # ------------------------------------------------------------------

    def _verify_signature(self, body: bytes, signature: str) -> bool:
        """Verify Asana HMAC-SHA256 signature.

        Asana computes: HMAC-SHA256(secret, request_body)
        and sends as hex digest in X-Hook-Signature.
        """
        if not signature:
            # If Asana doesn't send a signature, reject in production.
            # Allow unsigned in tests by subclassing and overriding.
            return False
        expected = hmac.new(self._secret, body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    # ------------------------------------------------------------------
    # Handshake helper
    # ------------------------------------------------------------------

    @staticmethod
    def is_handshake(headers: dict[str, str]) -> str | None:
        """Return the handshake secret if this is an initial Asana handshake, else None.

        Asana sends X-Hook-Secret on the first delivery to verify the endpoint.
        The handler must echo it back in the response header with the same name.
        """
        norm = {k.lower(): v for k, v in headers.items()}
        return norm.get("x-hook-secret")


# ---------------------------------------------------------------------------
# Standard event handler stubs — to be implemented by the sync module
# ---------------------------------------------------------------------------


async def noop_handler(event: dict[str, Any]) -> dict[str, Any]:
    """Placeholder handler that logs and returns without processing."""
    resource = event.get("resource", {})
    logger.debug(
        "asana_webhook_noop",
        resource_type=resource.get("resource_type"),
        resource_gid=resource.get("gid"),
        action=event.get("action"),
    )
    return {"processed": False, "reason": "noop"}
