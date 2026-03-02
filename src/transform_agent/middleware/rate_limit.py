"""
In-memory sliding-window rate limiter. Per API key.
"""

from __future__ import annotations

import time
from collections import defaultdict

_windows: dict[str, list[float]] = defaultdict(list)

DEFAULT_LIMIT = 60  # requests per minute


def check_rate_limit(api_key: str, limit: int = DEFAULT_LIMIT) -> bool:
    """Returns True if request is allowed, False if rate-limited."""
    now = time.time()
    window = _windows[api_key]

    # Purge entries older than 60s
    cutoff = now - 60
    _windows[api_key] = [t for t in window if t > cutoff]

    if len(_windows[api_key]) >= limit:
        return False

    _windows[api_key].append(now)
    return True


def requests_remaining(api_key: str, limit: int = DEFAULT_LIMIT) -> int:
    now = time.time()
    cutoff = now - 60
    recent = [t for t in _windows.get(api_key, []) if t > cutoff]
    return max(0, limit - len(recent))
