"""Tests for AsanaClient — authenticated HTTP transport layer.

Uses httpx mock transport so no real Asana calls are made.
All tests are async (pytest-asyncio).
"""

from __future__ import annotations

import json
import pytest
import httpx

from sidecar.integrations.asana.client import (
    AsanaClient,
    AsanaAuthError,
    AsanaNotFoundError,
    AsanaRateLimitError,
    AsanaAPIError,
)


# ---------------------------------------------------------------------------
# Test fixtures and helpers
# ---------------------------------------------------------------------------

def make_response(status_code: int, body: dict) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )


def make_client(transport: httpx.MockTransport) -> AsanaClient:
    """Return an AsanaClient wired to a mock transport."""
    client = AsanaClient(
        token="test-token",
        workspace_gid="workspace-123",
        base_url="https://app.asana.com/api/1.0",
    )
    # Replace the internal httpx client with a mock-transport version
    client._http = httpx.AsyncClient(
        base_url="https://app.asana.com/api/1.0",
        headers={"Authorization": "Bearer test-token"},
        transport=transport,
    )
    return client


# ---------------------------------------------------------------------------
# GET tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_returns_data_field():
    payload = {"data": {"gid": "123", "name": "Test Project"}}
    transport = httpx.MockTransport(handler=lambda r: make_response(200, payload))
    client = make_client(transport)
    result = await client.get("projects/123")
    assert result == {"gid": "123", "name": "Test Project"}
    await client.aclose()


@pytest.mark.asyncio
async def test_get_with_params():
    received_params: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        received_params.append(str(request.url))
        return make_response(200, {"data": {"gid": "abc"}})

    transport = httpx.MockTransport(handler=handler)
    client = make_client(transport)
    await client.get("tasks/abc", params={"opt_fields": "gid,name"})
    assert "opt_fields=gid%2Cname" in received_params[0] or "opt_fields" in received_params[0]
    await client.aclose()


# ---------------------------------------------------------------------------
# POST tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_wraps_body_in_data_envelope():
    received_bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        received_bodies.append(json.loads(request.content))
        return make_response(201, {"data": {"gid": "new-task-gid"}})

    transport = httpx.MockTransport(handler=handler)
    client = make_client(transport)
    result = await client.post("tasks", {"name": "My Task"})
    assert result == {"gid": "new-task-gid"}
    assert received_bodies[0] == {"data": {"name": "My Task"}}
    await client.aclose()


# ---------------------------------------------------------------------------
# PATCH tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_sends_data_envelope():
    received: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(json.loads(request.content))
        return make_response(200, {"data": {"gid": "task-1", "completed": True}})

    transport = httpx.MockTransport(handler=handler)
    client = make_client(transport)
    result = await client.patch("tasks/task-1", {"completed": True})
    assert result["completed"] is True
    assert received[0] == {"data": {"completed": True}}
    await client.aclose()


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_401_raises_auth_error():
    payload = {"errors": [{"message": "Not Authorized"}]}
    transport = httpx.MockTransport(handler=lambda r: make_response(401, payload))
    client = make_client(transport)
    with pytest.raises(AsanaAuthError):
        await client.get("projects/123")
    await client.aclose()


@pytest.mark.asyncio
async def test_403_raises_auth_error():
    payload = {"errors": [{"message": "Forbidden"}]}
    transport = httpx.MockTransport(handler=lambda r: make_response(403, payload))
    client = make_client(transport)
    with pytest.raises(AsanaAuthError):
        await client.get("projects/123")
    await client.aclose()


@pytest.mark.asyncio
async def test_404_raises_not_found():
    payload = {"errors": [{"message": "Not found"}]}
    transport = httpx.MockTransport(handler=lambda r: make_response(404, payload))
    client = make_client(transport)
    with pytest.raises(AsanaNotFoundError):
        await client.get("tasks/missing-gid")
    await client.aclose()


@pytest.mark.asyncio
async def test_400_raises_api_error():
    payload = {"errors": [{"message": "Bad request"}]}
    transport = httpx.MockTransport(handler=lambda r: make_response(400, payload))
    client = make_client(transport)
    with pytest.raises(AsanaAPIError) as exc_info:
        await client.post("tasks", {"bad": "payload"})
    assert exc_info.value.status_code == 400
    await client.aclose()


@pytest.mark.asyncio
async def test_429_retries_and_raises_rate_limit_error():
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            status_code=429,
            content=json.dumps({"errors": [{"message": "Rate limited"}]}).encode(),
            headers={"Content-Type": "application/json", "Retry-After": "0"},
        )

    transport = httpx.MockTransport(handler=handler)
    client = make_client(transport)
    with pytest.raises(AsanaRateLimitError):
        await client.get("projects/123")
    # Should have attempted 1 + MAX_RETRIES times (4 total)
    assert call_count == 4
    await client.aclose()


@pytest.mark.asyncio
async def test_500_retries_and_eventually_raises():
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return make_response(500, {"errors": [{"message": "Internal server error"}]})

    transport = httpx.MockTransport(handler=handler)
    client = make_client(transport)
    with pytest.raises(AsanaAPIError) as exc_info:
        await client.get("projects/123")
    assert exc_info.value.status_code == 500
    assert call_count == 4  # 1 initial + 3 retries
    await client.aclose()


@pytest.mark.asyncio
async def test_500_succeeds_on_retry():
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return make_response(500, {"errors": [{"message": "Transient error"}]})
        return make_response(200, {"data": {"gid": "recovered"}})

    transport = httpx.MockTransport(handler=handler)
    client = make_client(transport)
    result = await client.get("projects/123")
    assert result["gid"] == "recovered"
    assert call_count == 3
    await client.aclose()


# ---------------------------------------------------------------------------
# Pagination tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_paginate_yields_all_pages():
    page1 = {
        "data": [{"gid": "1"}, {"gid": "2"}],
        "next_page": {"offset": "abc123", "path": "/tasks?offset=abc123"},
    }
    page2 = {
        "data": [{"gid": "3"}],
        "next_page": None,
    }
    pages = [page1, page2]
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        response = pages[call_count]
        call_count += 1
        return make_response(200, response)

    transport = httpx.MockTransport(handler=handler)
    client = make_client(transport)
    items = []
    async for item in client.paginate("tasks"):
        items.append(item)
    assert items == [{"gid": "1"}, {"gid": "2"}, {"gid": "3"}]
    assert call_count == 2
    await client.aclose()


@pytest.mark.asyncio
async def test_paginate_single_page():
    payload = {"data": [{"gid": "x"}, {"gid": "y"}], "next_page": None}
    transport = httpx.MockTransport(handler=lambda r: make_response(200, payload))
    client = make_client(transport)
    items = []
    async for item in client.paginate("projects"):
        items.append(item)
    assert len(items) == 2
    await client.aclose()


# ---------------------------------------------------------------------------
# Batch tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_sends_actions():
    received: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(json.loads(request.content))
        return make_response(200, {
            "data": [
                {"status_code": 201, "body": {"data": {"gid": "new-1"}}},
                {"status_code": 201, "body": {"data": {"gid": "new-2"}}},
            ]
        })

    transport = httpx.MockTransport(handler=handler)
    client = make_client(transport)
    results = await client.batch([
        {"method": "POST", "relative_url": "/tasks", "data": {"name": "Task A"}},
        {"method": "POST", "relative_url": "/tasks", "data": {"name": "Task B"}},
    ])
    assert len(results) == 2
    actions = received[0]["data"]["actions"]
    assert len(actions) == 2
    assert actions[0]["data"]["name"] == "Task A"
    await client.aclose()


@pytest.mark.asyncio
async def test_batch_rejects_more_than_10():
    transport = httpx.MockTransport(handler=lambda r: make_response(200, {"data": []}))
    client = make_client(transport)
    with pytest.raises(ValueError, match="10"):
        await client.batch([{"method": "GET", "relative_url": "/x"}] * 11)
    await client.aclose()


# ---------------------------------------------------------------------------
# Context manager tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_context_manager():
    payload = {"data": {"gid": "proj-1"}}
    transport = httpx.MockTransport(handler=lambda r: make_response(200, payload))
    async with AsanaClient(
        token="tok", workspace_gid="ws", base_url="https://app.asana.com/api/1.0"
    ) as client:
        client._http = httpx.AsyncClient(
            base_url="https://app.asana.com/api/1.0",
            transport=transport,
        )
        result = await client.get("projects/proj-1")
        assert result["gid"] == "proj-1"
    # After __aexit__, client._http is closed — no assertion needed; no error is the test
