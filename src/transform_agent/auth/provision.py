"""
Zero-friction auth for agent-to-agent. No signup, no email, no OAuth.
Agents call POST /auth/provision and get an API key instantly.
"""

from __future__ import annotations

import secrets
import time

from transform_agent.models.schemas import ProvisionRequest, ProvisionResponse

FREE_TIER_REQUESTS = 100
DEFAULT_RATE_LIMIT = 60  # per minute

# In-memory store (swap for Redis/SQLite in production)
_accounts: dict[str, dict] = {}


def provision(req: ProvisionRequest) -> ProvisionResponse:
    api_key = f"ta_{secrets.token_urlsafe(32)}"
    _accounts[api_key] = {
        "created_at": time.time(),
        "agent_name": req.agent_name,
        "agent_url": req.agent_url,
        "free_remaining": FREE_TIER_REQUESTS,
        "total_requests": 0,
        "total_spent_usd": 0.0,
        "rate_limit": DEFAULT_RATE_LIMIT,
    }
    return ProvisionResponse(
        api_key=api_key,
        free_requests_remaining=FREE_TIER_REQUESTS,
        rate_limit_per_minute=DEFAULT_RATE_LIMIT,
        message="Ready. Include header: Authorization: Bearer <api_key>",
    )


def get_account(api_key: str) -> dict | None:
    return _accounts.get(api_key)


def use_free_request(api_key: str) -> bool:
    """Decrement free tier. Returns True if free request was used, False if exhausted."""
    acct = _accounts.get(api_key)
    if acct is None:
        return False
    if acct["free_remaining"] > 0:
        acct["free_remaining"] -= 1
        acct["total_requests"] += 1
        return True
    return False


def record_paid_request(api_key: str, cost: float) -> None:
    acct = _accounts.get(api_key)
    if acct:
        acct["total_requests"] += 1
        acct["total_spent_usd"] += cost


def is_valid_key(api_key: str) -> bool:
    return api_key in _accounts


def free_remaining(api_key: str) -> int:
    acct = _accounts.get(api_key)
    return acct["free_remaining"] if acct else 0
