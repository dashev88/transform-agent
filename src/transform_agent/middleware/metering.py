"""
Metering middleware — logs every request for revenue tracking.
"""

from __future__ import annotations

import hashlib
import time


_ledger: list[dict] = []


def log_transaction(
    api_key: str,
    source_format: str,
    target_format: str,
    input_size: int,
    output_size: int,
    transform_time_ms: float,
    cost: float,
    paid: bool,
) -> str:
    """Log a transaction and return the tx_id."""
    tx_id = hashlib.sha256(f"{time.time()}{api_key}{source_format}{target_format}".encode()).hexdigest()[:16]
    _ledger.append({
        "tx_id": tx_id,
        "api_key": api_key[:8] + "...",  # truncated for privacy
        "source": source_format,
        "target": target_format,
        "input_size": input_size,
        "output_size": output_size,
        "time_ms": round(transform_time_ms, 2),
        "cost": cost,
        "paid": paid,
        "ts": time.time(),
    })
    return tx_id


def get_revenue() -> dict:
    """Aggregate revenue stats."""
    total = sum(tx["cost"] for tx in _ledger)
    today_cutoff = time.time() - 86400
    today = sum(tx["cost"] for tx in _ledger if tx["ts"] > today_cutoff)

    by_transform: dict[str, float] = {}
    by_hour: dict[str, float] = {}
    for tx in _ledger:
        key = f"{tx['source']}→{tx['target']}"
        by_transform[key] = by_transform.get(key, 0) + tx["cost"]
        hour = time.strftime("%Y-%m-%d %H:00", time.gmtime(tx["ts"]))
        by_hour[hour] = by_hour.get(hour, 0) + tx["cost"]

    return {
        "total_revenue_usd": round(total, 6),
        "today_revenue_usd": round(today, 6),
        "total_transactions": len(_ledger),
        "revenue_by_transform": {k: round(v, 6) for k, v in by_transform.items()},
        "revenue_by_hour": {k: round(v, 6) for k, v in by_hour.items()},
    }
