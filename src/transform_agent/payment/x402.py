"""
x402 payment integration — Coinbase stablecoin payments over HTTP.

When an agent exhausts its free tier, requests return HTTP 402 with
payment requirements. The agent signs a USDC payment and retries.
"""

from __future__ import annotations

import os

# Pricing per transform category (USD)
PRICING = {
    "text": 0.001,       # JSON/CSV/XML/YAML/TOML/HTML/MD/text
    "document": 0.005,   # PDF/Excel/DOCX
    "schema": 0.002,     # JSON reshaping
    "encoding": 0.0005,  # Base64/hex/URL
}

# x402 configuration
WALLET_ADDRESS = os.environ.get("WALLET_ADDRESS", "0x0000000000000000000000000000000000000000")
X402_FACILITATOR_URL = os.environ.get("X402_FACILITATOR_URL", "https://www.x402.org/facilitator")
X402_NETWORK = os.environ.get("X402_NETWORK", "eip155:84532")  # Base Sepolia testnet
USDC_ADDRESS = os.environ.get("USDC_ADDRESS", "0x036CbD53842c5426634e7929541eC2318f3dCF7e")  # USDC on Base Sepolia


def get_payment_requirements(cost_usd: float) -> dict:
    """Build x402 PaymentRequirements for a given cost."""
    return {
        "scheme": "exact",
        "network": X402_NETWORK,
        "maxAmountRequired": str(int(cost_usd * 1_000_000)),  # USDC has 6 decimals
        "resource": "transform",
        "description": f"Data transformation — ${cost_usd}",
        "payTo": WALLET_ADDRESS,
        "asset": USDC_ADDRESS,
        "extra": {},
    }


def get_transform_cost(source_format: str, target_format: str) -> float:
    """Determine cost based on the format pair."""
    document_formats = {"pdf", "excel", "docx"}
    encoding_formats = {"base64", "url_encoded", "hex"}

    src = source_format.lower()
    tgt = target_format.lower()

    if src in document_formats or tgt in document_formats:
        return PRICING["document"]
    if src in encoding_formats or tgt in encoding_formats:
        return PRICING["encoding"]
    if src == tgt == "json":
        return PRICING["schema"]
    return PRICING["text"]
