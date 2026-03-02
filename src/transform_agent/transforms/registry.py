"""
Transform registry — maps (source_format, target_format) → handler function.

Every handler has the signature:
    async def handler(data: bytes, options: dict | None) -> bytes

The registry enables O(1) routing and dynamic capability listing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Awaitable

from transform_agent.models.schemas import Format


@dataclass(frozen=True)
class TransformKey:
    source: Format
    target: Format


@dataclass
class TransformEntry:
    handler: Callable[[bytes, dict | None], Awaitable[bytes]]
    cost_usd: float
    avg_time_ms: float = 0.0
    description: str = ""
    call_count: int = field(default=0, repr=False)
    total_time_ms: float = field(default=0.0, repr=False)


class TransformRegistry:
    """Central registry for all transformations."""

    def __init__(self) -> None:
        self._registry: dict[TransformKey, TransformEntry] = {}

    def register(
        self,
        source: Format,
        target: Format,
        handler: Callable[[bytes, dict | None], Awaitable[bytes]],
        cost_usd: float,
        description: str = "",
    ) -> None:
        key = TransformKey(source, target)
        self._registry[key] = TransformEntry(
            handler=handler,
            cost_usd=cost_usd,
            description=description,
        )

    def get(self, source: Format, target: Format) -> TransformEntry | None:
        return self._registry.get(TransformKey(source, target))

    async def execute(
        self, source: Format, target: Format, data: bytes, options: dict | None = None
    ) -> tuple[bytes, float, float]:
        """Execute a transform. Returns (result_bytes, cost_usd, time_ms)."""
        entry = self.get(source, target)
        if entry is None:
            raise ValueError(f"No transform registered for {source.value} → {target.value}")

        start = time.perf_counter()
        result = await entry.handler(data, options)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Update running stats
        entry.call_count += 1
        entry.total_time_ms += elapsed_ms
        entry.avg_time_ms = entry.total_time_ms / entry.call_count

        return result, entry.cost_usd, elapsed_ms

    def list_capabilities(self) -> list[dict]:
        """Return the full capability matrix."""
        return [
            {
                "source": key.source,
                "target": key.target,
                "cost_usd": entry.cost_usd,
                "avg_time_ms": round(entry.avg_time_ms, 2),
                "description": entry.description,
            }
            for key, entry in self._registry.items()
        ]

    def supports(self, source: Format, target: Format) -> bool:
        return TransformKey(source, target) in self._registry

    def __len__(self) -> int:
        return len(self._registry)


# Global singleton
registry = TransformRegistry()
