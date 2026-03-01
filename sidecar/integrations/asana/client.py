"""Asana REST API HTTP client.

Responsibilities:
- Authenticated requests using Personal Access Token
- Rate-limit handling (429 with Retry-After respect)
- Exponential backoff for transient 5xx errors
- Cursor-based pagination helper (async generator)
- Batch request support (up to 10 ops per call)
- opt_fields constants for lean payloads
- Structured logging on every request and error

This is a thin transport layer. It knows nothing about domain models.
All callers receive plain dicts from the Asana `data` envelope.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator

import httpx
import structlog

logger = structlog.get_logger(__name__)

_BASE_URL = "https://app.asana.com/api/1.0"

# Standard opt_fields per resource — keeps payloads lean and predictable
TASK_OPT_FIELDS = (
    "gid,name,assignee.gid,assignee.name,due_on,completed,completed_at,"
    "custom_fields,memberships.section.gid,memberships.section.name,"
    "memberships.project.gid,memberships.project.name,"
    "modified_at,notes,dependencies,dependents,resource_subtype,external"
)

PROJECT_OPT_FIELDS = (
    "gid,name,owner.gid,owner.name,due_on,start_on,custom_fields,"
    "current_status,members.gid,notes,archived,public"
)

MILESTONE_OPT_FIELDS = (
    "gid,name,assignee.gid,assignee.name,due_on,completed,completed_at,"
    "custom_fields,memberships.project.gid,resource_subtype,notes"
)

SECTION_OPT_FIELDS = "gid,name,project.gid"

WEBHOOK_OPT_FIELDS = "gid,resource.gid,resource.resource_type,target,active"

# Retry behaviour
_MAX_RETRIES = 3
_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
_BASE_BACKOFF_SECONDS = 1.0


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AsanaAuthError(Exception):
    """401/403 — misconfigured PAT or missing Asana permissions."""


class AsanaNotFoundError(Exception):
    """404 — object does not exist or was deleted in Asana."""


class AsanaRateLimitError(Exception):
    """429 retries exhausted."""


class AsanaAPIError(Exception):
    """Non-retryable Asana error (400, 422, etc.)."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class AsanaClient:
    """Async HTTP client for the Asana REST API.

    Designed for dependency injection — create once at startup, inject into
    services, close at shutdown.

    Usage (async context manager)::

        async with AsanaClient(token="...", workspace_gid="...") as client:
            project = await client.get("projects/1234567890")

    Usage (manual lifecycle)::

        client = AsanaClient(token=settings.asana_personal_access_token,
                             workspace_gid=settings.asana_workspace_gid)
        # ... use client ...
        await client.aclose()
    """

    def __init__(
        self,
        token: str,
        workspace_gid: str,
        base_url: str = _BASE_URL,
    ) -> None:
        self.workspace_gid = workspace_gid
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "AsanaClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()

    # ------------------------------------------------------------------
    # Public request methods — return the `data` payload from Asana
    # ------------------------------------------------------------------

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """GET a single resource. Returns the unwrapped `data` dict."""
        result = await self._request("GET", path, params=params)
        return result.get("data", result)

    async def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """POST to create a resource. Returns the unwrapped `data` dict."""
        result = await self._request("POST", path, json={"data": body})
        return result.get("data", result)

    async def patch(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """PATCH to partially update a resource. Returns the unwrapped `data` dict."""
        result = await self._request("PATCH", path, json={"data": body})
        return result.get("data", result)

    async def delete(self, path: str) -> None:
        """DELETE a resource."""
        await self._request("DELETE", path)

    async def paginate(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        page_size: int = 100,
    ) -> AsyncIterator[dict[str, Any]]:
        """Async generator that yields every item across all pages.

        Usage::

            async for task in client.paginate("projects/123/tasks", params={"opt_fields": "..."}):
                process(task)
        """
        params = dict(params or {})
        params["limit"] = page_size

        while True:
            result = await self._request("GET", path, params=params)
            for item in result.get("data", []):
                yield item

            next_page = result.get("next_page")
            if not next_page:
                break
            params["offset"] = next_page["offset"]
            # Remove limit from subsequent requests (offset carries pagination)
            params.pop("limit", None)

    async def batch(
        self,
        operations: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Execute up to 10 operations in a single Asana batch request.

        Each operation dict must have:
            - ``method``: HTTP method string (e.g. "POST")
            - ``relative_url``: path relative to /api/1.0 (e.g. "/tasks")
            - ``data``: optional request body dict

        Returns list of per-operation response dicts with keys
        ``status_code`` and ``body``.

        Reference: https://developers.asana.com/docs/submit-parallel-requests
        """
        if not operations:
            return []
        if len(operations) > 10:
            raise ValueError(
                f"Asana batch API supports at most 10 operations; got {len(operations)}"
            )
        result = await self._request(
            "POST", "batch", json={"data": {"actions": operations}}
        )
        return result.get("data", [])

    # ------------------------------------------------------------------
    # Internal retry-aware request engine
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = path.lstrip("/")

        for attempt in range(_MAX_RETRIES + 1):
            t0 = time.monotonic()
            try:
                response = await self._http.request(
                    method, url, params=params, json=json
                )
            except httpx.TimeoutException:
                elapsed = int((time.monotonic() - t0) * 1000)
                logger.warning(
                    "asana_timeout",
                    method=method,
                    path=path,
                    attempt=attempt,
                    elapsed_ms=elapsed,
                )
                if attempt == _MAX_RETRIES:
                    raise
                await self._sleep_backoff(attempt)
                continue

            elapsed_ms = int((time.monotonic() - t0) * 1000)
            status = response.status_code

            # Success
            if status in (200, 201):
                logger.debug(
                    "asana_ok",
                    method=method,
                    path=path,
                    status=status,
                    elapsed_ms=elapsed_ms,
                )
                return response.json()

            if status == 204:
                return {}

            # Error handling
            body = self._safe_json(response)
            error_msg = self._extract_error(body)

            if status in (401, 403):
                logger.error(
                    "asana_auth_error",
                    status=status,
                    path=path,
                    message=error_msg,
                )
                raise AsanaAuthError(
                    f"Asana auth error {status} on {method} {path}: {error_msg}"
                )

            if status == 404:
                logger.warning("asana_not_found", path=path, message=error_msg)
                raise AsanaNotFoundError(
                    f"Asana 404 on {method} {path}: {error_msg}"
                )

            if status in _RETRYABLE_STATUSES:
                retry_after = self._parse_retry_after(response, attempt)
                logger.warning(
                    "asana_retryable_error",
                    status=status,
                    method=method,
                    path=path,
                    attempt=attempt,
                    retry_after_s=retry_after,
                )
                if attempt == _MAX_RETRIES:
                    if status == 429:
                        raise AsanaRateLimitError(
                            f"Rate limit retries exhausted on {method} {path}"
                        )
                    raise AsanaAPIError(
                        status,
                        f"Asana {status} on {method} {path} after {_MAX_RETRIES} retries: {error_msg}",
                    )
                await asyncio.sleep(retry_after)
                continue

            # Non-retryable client error (400, 409, 422, etc.)
            logger.error(
                "asana_client_error",
                status=status,
                method=method,
                path=path,
                message=error_msg,
            )
            raise AsanaAPIError(
                status,
                f"Asana {status} on {method} {path}: {error_msg}",
            )

        # Should never reach here — loop always raises or continues
        raise AsanaAPIError(0, f"Unexpected exit from retry loop for {method} {path}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_json(response: httpx.Response) -> dict[str, Any]:
        try:
            return response.json()
        except Exception:
            return {}

    @staticmethod
    def _extract_error(body: dict[str, Any]) -> str:
        errors = body.get("errors")
        if errors and isinstance(errors, list):
            return "; ".join(e.get("message", str(e)) for e in errors)
        return body.get("message", "unknown error")

    @staticmethod
    def _parse_retry_after(response: httpx.Response, attempt: int) -> float:
        """Return seconds to wait. Uses Retry-After header if present, else exponential backoff."""
        header = response.headers.get("Retry-After")
        if header:
            try:
                return float(header)
            except ValueError:
                pass
        return _BASE_BACKOFF_SECONDS * (2 ** attempt)

    @staticmethod
    async def _sleep_backoff(attempt: int) -> None:
        wait = _BASE_BACKOFF_SECONDS * (2 ** attempt)
        logger.debug("asana_backoff", wait_s=wait, attempt=attempt)
        await asyncio.sleep(wait)
