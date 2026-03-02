"""Asana webhook endpoint.

Receives webhook events from Asana, validates HMAC signatures,
and dispatches to the AsanaWebhookHandler for processing.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from sidecar.config import get_settings
from sidecar.integrations.asana.webhooks import AsanaWebhookHandler

router = APIRouter()

# Lazy-init handler — created on first request so settings are available
_handler: AsanaWebhookHandler | None = None


def _get_handler() -> AsanaWebhookHandler:
    global _handler
    if _handler is None:
        settings = get_settings()
        secret = settings.asana_webhook_secret or "no-secret-configured"
        _handler = AsanaWebhookHandler(secret=secret)
    return _handler


@router.post("/asana", response_model=None)
async def asana_webhook(request: Request):
    """Handle Asana webhook deliveries.

    Two modes:
    1. Handshake — Asana sends X-Hook-Secret, we echo it back (200 + header)
    2. Events — Asana sends signed payload, we validate and dispatch
    """
    headers = dict(request.headers)
    handler = _get_handler()

    # Handshake check
    handshake_secret = handler.is_handshake(headers)
    if handshake_secret:
        return Response(
            status_code=200,
            headers={"X-Hook-Secret": handshake_secret},
        )

    # Event processing
    body = await request.body()
    result = await handler.handle(headers, body)
    return result
