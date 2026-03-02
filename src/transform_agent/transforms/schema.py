"""
Schema reshaping — transform JSON structure from one shape to another.

Agents constantly need to reshape API responses. This uses dot-notation
path mapping to restructure JSON without any external dependencies.
"""

from __future__ import annotations

from typing import Any

import orjson


def _get_by_path(obj: Any, path: str) -> Any:
    """Get a nested value using dot-notation path: 'a.b.c' → obj['a']['b']['c']."""
    parts = path.split(".")
    current = obj
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, (list, tuple)):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def _set_by_path(obj: dict, path: str, value: Any) -> None:
    """Set a nested value using dot-notation: 'a.b.c' = value."""
    parts = path.split(".")
    current = obj
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def reshape(data: Any, mapping: dict[str, str]) -> Any:
    """
    Reshape data using a mapping of {target_path: source_path}.

    If data is a list, apply the mapping to each element.
    If data is a dict, apply once.

    Example mapping:
        {"user.name": "response.data.full_name", "user.id": "response.data.uid"}
    """
    if isinstance(data, list):
        return [_reshape_single(item, mapping) for item in data]
    return _reshape_single(data, mapping)


def _reshape_single(item: Any, mapping: dict[str, str]) -> dict:
    result: dict = {}
    for target_path, source_path in mapping.items():
        value = _get_by_path(item, source_path)
        _set_by_path(result, target_path, value)
    return result


async def reshape_json(data: bytes, options: dict | None = None) -> bytes:
    """
    Transform handler for the registry.

    Expects options = {"mapping": {"target.path": "source.path", ...}}
    """
    if not options or "mapping" not in options:
        raise ValueError("Schema reshape requires options.mapping: {target_path: source_path, ...}")
    obj = orjson.loads(data)
    result = reshape(obj, options["mapping"])
    return orjson.dumps(result, option=orjson.OPT_NON_STR_KEYS)
