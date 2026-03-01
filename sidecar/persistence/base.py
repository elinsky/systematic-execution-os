"""Base repository with shared utilities.

Provides JSON list serialization helpers since SQLite stores list[str]
fields as JSON-encoded TEXT columns.
"""

import json
from typing import Any


def encode_list(values: list[str]) -> str:
    """Serialize a list of strings to a JSON string for DB storage."""
    return json.dumps(values)


def decode_list(value: str | None) -> list[str]:
    """Deserialize a JSON string from DB storage to a list of strings."""
    if value is None:
        return []
    return json.loads(value)


def encode_json(value: Any) -> str:
    """Serialize an arbitrary JSON-serializable value to a string."""
    return json.dumps(value)


def decode_json(value: str | None) -> Any:
    """Deserialize a JSON string from DB to a Python object."""
    if value is None:
        return None
    return json.loads(value)
