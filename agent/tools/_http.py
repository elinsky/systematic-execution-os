"""Shared async HTTP helpers for sidecar API calls."""

from __future__ import annotations

import json
from typing import Any

import httpx

from agent.config import get_config


def _client() -> httpx.AsyncClient:
    cfg = get_config()
    return httpx.AsyncClient(base_url=cfg.api_base, timeout=cfg.api_timeout)


def _health_client() -> httpx.AsyncClient:
    cfg = get_config()
    return httpx.AsyncClient(base_url=cfg.sidecar_url, timeout=cfg.api_timeout)


async def get(path: str, params: dict[str, Any] | None = None) -> Any:
    """GET request, returns parsed JSON."""
    async with _client() as client:
        resp = await client.get(path, params=params)
    resp.raise_for_status()
    return resp.json()


async def post(path: str, payload: dict[str, Any]) -> Any:
    """POST request with JSON body, returns parsed JSON."""
    async with _client() as client:
        resp = await client.post(path, json=payload)
    resp.raise_for_status()
    return resp.json()


async def patch(path: str, payload: dict[str, Any]) -> Any:
    """PATCH request with JSON body, returns parsed JSON."""
    async with _client() as client:
        resp = await client.patch(path, json=payload)
    resp.raise_for_status()
    return resp.json()


async def health_get(path: str) -> Any:
    """GET request against the sidecar root (not /api/v1)."""
    async with _health_client() as client:
        resp = await client.get(path)
    resp.raise_for_status()
    return resp.json()


def ok(data: Any) -> dict:
    """Format a successful tool response."""
    text = json.dumps(data, indent=2, default=str)
    return {"content": [{"type": "text", "text": text}]}


def err(message: str) -> dict:
    """Format an error tool response."""
    return {"content": [{"type": "text", "text": f"Error: {message}"}], "isError": True}
