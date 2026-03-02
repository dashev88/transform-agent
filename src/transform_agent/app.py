"""
Data Transform Agent — FastAPI application.

A headless, zero-UI agent that converts data between formats.
Discovered by other agents via A2A, MCP, and OpenAPI protocols.
Paid via Coinbase x402 (USDC) with a 100-request free tier.
"""

from __future__ import annotations

import base64
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import orjson
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import Response

from transform_agent.models.schemas import (
    BINARY_FORMATS,
    BatchTransformRequest,
    BatchTransformResult,
    CapabilitiesResponse,
    CapabilityEntry,
    Format,
    ProvisionRequest,
    SchemaReshapeRequest,
    TransformRequest,
    TransformResult,
)
from transform_agent.transforms.registry import registry
from transform_agent.auth.provision import (
    free_remaining,
    get_account,
    is_valid_key,
    provision,
    record_paid_request,
    use_free_request,
)
from transform_agent.payment.x402 import get_payment_requirements, get_transform_cost
from transform_agent.middleware.metering import get_revenue, log_transaction
from transform_agent.middleware.rate_limit import check_rate_limit
from transform_agent.discovery.a2a_card import build_agent_card
from transform_agent.discovery.mcp import build_mcp_manifest
from transform_agent.discovery.mcp_handler import handle_mcp_message
from transform_agent.discovery.openapi import customize_openapi
from transform_agent.transforms.schema import reshape_json


# ---------------------------------------------------------------------------
# Register all transforms at startup
# ---------------------------------------------------------------------------

def _register_transforms() -> None:
    from transform_agent.transforms import tabular, markup, documents, encoding

    F = Format
    r = registry.register
    cost_t = 0.001   # text
    cost_d = 0.005   # document
    cost_e = 0.0005  # encoding

    # --- Tabular ---
    r(F.JSON, F.CSV,        tabular.json_to_csv,        cost_t, "JSON → CSV")
    r(F.JSON, F.XML,        tabular.json_to_xml,        cost_t, "JSON → XML")
    r(F.JSON, F.YAML,       tabular.json_to_yaml,       cost_t, "JSON → YAML")
    r(F.JSON, F.TOML,       tabular.json_to_toml,       cost_t, "JSON → TOML")
    r(F.JSON, F.PLAIN_TEXT, tabular.json_to_plain_text,  cost_t, "JSON → Plain Text (pretty-printed)")
    r(F.JSON, F.HTML,       documents.json_to_html,      cost_t, "JSON → HTML table")
    r(F.JSON, F.MARKDOWN,   documents.json_to_markdown_table, cost_t, "JSON → Markdown table")
    r(F.JSON, F.EXCEL,      documents.json_to_excel,     cost_t, "JSON → Excel")

    r(F.CSV, F.JSON,        tabular.csv_to_json,        cost_t, "CSV → JSON")
    r(F.CSV, F.XML,         tabular.csv_to_xml,         cost_t, "CSV → XML")
    r(F.CSV, F.YAML,        tabular.csv_to_yaml,        cost_t, "CSV → YAML")
    r(F.CSV, F.PLAIN_TEXT,  tabular.csv_to_plain_text,   cost_t, "CSV → Plain Text")
    r(F.CSV, F.EXCEL,       tabular.csv_to_excel,        cost_t, "CSV → Excel")
    r(F.CSV, F.HTML,        documents.csv_to_html,       cost_t, "CSV → HTML table")
    r(F.CSV, F.MARKDOWN,    documents.csv_to_markdown,   cost_t, "CSV → Markdown table")

    r(F.XML, F.JSON,        tabular.xml_to_json,        cost_t, "XML → JSON")
    r(F.XML, F.CSV,         tabular.xml_to_csv,         cost_t, "XML → CSV")
    r(F.XML, F.YAML,        tabular.xml_to_yaml,        cost_t, "XML → YAML")
    r(F.XML, F.PLAIN_TEXT,  tabular.xml_to_plain_text,   cost_t, "XML → Plain Text")

    r(F.YAML, F.JSON,       tabular.yaml_to_json,       cost_t, "YAML → JSON")
    r(F.YAML, F.XML,        tabular.yaml_to_xml,        cost_t, "YAML → XML")
    r(F.YAML, F.TOML,       tabular.yaml_to_toml,       cost_t, "YAML → TOML")
    r(F.YAML, F.PLAIN_TEXT, tabular.yaml_to_plain_text,  cost_t, "YAML → Plain Text")

    r(F.TOML, F.JSON,       tabular.toml_to_json,       cost_t, "TOML → JSON")
    r(F.TOML, F.YAML,       tabular.toml_to_yaml,       cost_t, "TOML → YAML")
    r(F.TOML, F.PLAIN_TEXT, tabular.toml_to_plain_text,  cost_t, "TOML → Plain Text")

    # --- Markup ---
    r(F.HTML, F.MARKDOWN,    markup.html_to_markdown,     cost_t, "HTML → Markdown")
    r(F.HTML, F.PLAIN_TEXT,  markup.html_to_plain_text,   cost_t, "HTML → Plain Text")
    r(F.MARKDOWN, F.HTML,    markup.markdown_to_html,     cost_t, "Markdown → HTML")
    r(F.MARKDOWN, F.PLAIN_TEXT, markup.markdown_to_plain_text, cost_t, "Markdown → Plain Text")

    # --- Documents ---
    r(F.PDF, F.PLAIN_TEXT,   documents.pdf_to_plain_text,  cost_d, "PDF → Plain Text")
    r(F.PDF, F.MARKDOWN,     documents.pdf_to_markdown,    cost_d, "PDF → Markdown")
    r(F.EXCEL, F.JSON,       documents.excel_to_json,      cost_d, "Excel → JSON")
    r(F.EXCEL, F.CSV,        documents.excel_to_csv,       cost_d, "Excel → CSV")
    r(F.EXCEL, F.HTML,       documents.excel_to_html,      cost_d, "Excel → HTML table")
    r(F.DOCX, F.PLAIN_TEXT,  documents.docx_to_plain_text, cost_d, "DOCX → Plain Text")
    r(F.DOCX, F.MARKDOWN,    documents.docx_to_markdown,   cost_d, "DOCX → Markdown")

    # --- Encoding ---
    r(F.PLAIN_TEXT, F.BASE64,      encoding.to_base64,       cost_e, "Text → Base64")
    r(F.BASE64, F.PLAIN_TEXT,      encoding.from_base64,     cost_e, "Base64 → Text")
    r(F.PLAIN_TEXT, F.URL_ENCODED, encoding.to_url_encoded,  cost_e, "Text → URL-encoded")
    r(F.URL_ENCODED, F.PLAIN_TEXT, encoding.from_url_encoded, cost_e, "URL-encoded → Text")
    r(F.PLAIN_TEXT, F.HEX,        encoding.to_hex,          cost_e, "Text → Hex")
    r(F.HEX, F.PLAIN_TEXT,        encoding.from_hex,        cost_e, "Hex → Text")


# ---------------------------------------------------------------------------
# App lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _register_transforms()
    yield


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "admin")

app = FastAPI(
    title="Data Transform Agent",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

customize_openapi(app, BASE_URL)


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _extract_key(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Missing Authorization header",
                "fix": "POST /auth/provision to get an API key, then send Authorization: Bearer <key>",
            },
        )
    return authorization.removeprefix("Bearer ").strip()


# ---------------------------------------------------------------------------
# Discovery endpoints
# ---------------------------------------------------------------------------

def _orjson_response(data: dict | list) -> Response:
    return Response(
        content=orjson.dumps(data),
        media_type="application/json",
    )


@app.get("/.well-known/agent-card.json")
async def a2a_agent_card():
    """Google A2A Protocol discovery."""
    return _orjson_response(build_agent_card(BASE_URL))


@app.get("/.well-known/mcp.json")
async def mcp_manifest():
    """MCP discovery for Claude and OpenAI agents."""
    return _orjson_response(build_mcp_manifest(BASE_URL))


# ---------------------------------------------------------------------------
# MCP Streamable HTTP endpoint (JSON-RPC 2.0)
# ---------------------------------------------------------------------------

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """MCP Streamable HTTP transport — handles JSON-RPC 2.0 messages."""
    try:
        body = orjson.loads(await request.body())
    except Exception:
        return Response(
            content=orjson.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }),
            media_type="application/json",
            status_code=200,
        )

    # Handle batch
    if isinstance(body, list):
        results = []
        for msg in body:
            resp = await handle_mcp_message(msg)
            if resp is not None:
                results.append(resp)
        if results:
            return Response(content=orjson.dumps(results), media_type="application/json")
        return Response(status_code=204)

    # Handle single message
    resp = await handle_mcp_message(body)
    if resp is None:
        return Response(status_code=204)
    return Response(content=orjson.dumps(resp), media_type="application/json")


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.post("/auth/provision")
async def auth_provision(req: ProvisionRequest):
    """Auto-provision an API key. No signup. No email. Instant."""
    return provision(req)


@app.get("/auth/balance")
async def auth_balance(authorization: str = Header()):
    key = _extract_key(authorization)
    acct = get_account(key)
    if not acct:
        raise HTTPException(401, "Invalid API key. POST /auth/provision to get one.")
    return {
        "free_requests_remaining": acct["free_remaining"],
        "total_requests": acct["total_requests"],
        "total_spent_usd": acct["total_spent_usd"],
    }


# ---------------------------------------------------------------------------
# Core transform endpoint
# ---------------------------------------------------------------------------

@app.post("/transform", response_model=TransformResult)
async def transform(req: TransformRequest, authorization: str = Header()):
    """Transform data from one format to another."""
    key = _extract_key(authorization)

    if not is_valid_key(key):
        raise HTTPException(401, {"error": "Invalid API key", "fix": "POST /auth/provision"})

    if not check_rate_limit(key):
        raise HTTPException(429, "Rate limit exceeded. Max 60 requests/minute.")

    if not registry.supports(req.source_format, req.target_format):
        raise HTTPException(
            400,
            {
                "error": f"Unsupported: {req.source_format.value} → {req.target_format.value}",
                "fix": "GET /capabilities for supported conversions",
            },
        )

    # Determine cost
    cost = get_transform_cost(req.source_format.value, req.target_format.value)

    # Check free tier or require payment
    is_free = use_free_request(key)
    if not is_free:
        # Return x402 payment requirement
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Free tier exhausted",
                "payment_required": get_payment_requirements(cost),
                "free_remaining": 0,
                "fix": "Sign the payment and resend with PAYMENT-SIGNATURE header, or top up at /payment/methods",
            },
        )

    # Decode input
    if req.source_format in BINARY_FORMATS:
        try:
            input_bytes = base64.b64decode(req.data)
        except Exception:
            raise HTTPException(400, f"Invalid base64 data for binary format {req.source_format.value}")
    else:
        input_bytes = req.data.encode()

    # Execute transform
    try:
        result_bytes, actual_cost, time_ms = await registry.execute(
            req.source_format, req.target_format, input_bytes, req.options
        )
    except Exception as e:
        raise HTTPException(422, f"Transform failed: {e}")

    # Encode output
    if req.target_format in BINARY_FORMATS:
        result_str = base64.b64encode(result_bytes).decode()
    else:
        result_str = result_bytes.decode()

    # Meter
    tx_id = log_transaction(
        api_key=key,
        source_format=req.source_format.value,
        target_format=req.target_format.value,
        input_size=len(input_bytes),
        output_size=len(result_bytes),
        transform_time_ms=time_ms,
        cost=0.0 if is_free else actual_cost,
        paid=not is_free,
    )

    return TransformResult(
        result=result_str,
        source_format=req.source_format,
        target_format=req.target_format,
        input_size_bytes=len(input_bytes),
        output_size_bytes=len(result_bytes),
        transform_time_ms=round(time_ms, 2),
        cost_usd=0.0 if is_free else actual_cost,
        tx_id=tx_id,
    )


# ---------------------------------------------------------------------------
# Batch transform
# ---------------------------------------------------------------------------

@app.post("/transform/batch", response_model=BatchTransformResult)
async def transform_batch(req: BatchTransformRequest, authorization: str = Header()):
    """Transform up to 50 items. 10% bulk discount on paid requests."""
    results: list[TransformResult] = []
    total_cost = 0.0

    for item in req.transforms:
        result = await transform(item, authorization)
        # Apply 10% discount on paid requests
        if result.cost_usd > 0:
            result.cost_usd = round(result.cost_usd * 0.9, 6)
        total_cost += result.cost_usd
        results.append(result)

    return BatchTransformResult(
        results=results,
        total_cost_usd=round(total_cost, 6),
        total_transforms=len(results),
    )


# ---------------------------------------------------------------------------
# Schema reshaping
# ---------------------------------------------------------------------------

@app.post("/reshape")
async def reshape(req: SchemaReshapeRequest, authorization: str = Header()):
    """Reshape JSON from one structure to another using dot-notation path mapping."""
    key = _extract_key(authorization)

    if not is_valid_key(key):
        raise HTTPException(401, {"error": "Invalid API key", "fix": "POST /auth/provision"})

    if not check_rate_limit(key):
        raise HTTPException(429, "Rate limit exceeded.")

    is_free = use_free_request(key)
    cost = 0.002

    if not is_free:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Free tier exhausted",
                "payment_required": get_payment_requirements(cost),
            },
        )

    input_bytes = orjson.dumps(req.data)
    try:
        result_bytes = await reshape_json(input_bytes, {"mapping": req.mapping})
    except Exception as e:
        raise HTTPException(422, f"Reshape failed: {e}")

    result = orjson.loads(result_bytes)

    tx_id = log_transaction(
        api_key=key,
        source_format="json",
        target_format="json_reshaped",
        input_size=len(input_bytes),
        output_size=len(result_bytes),
        transform_time_ms=0.0,
        cost=0.0 if is_free else cost,
        paid=not is_free,
    )

    return {
        "result": result,
        "cost_usd": 0.0 if is_free else cost,
        "tx_id": tx_id,
    }


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------

@app.get("/capabilities", response_model=CapabilitiesResponse)
async def capabilities():
    """List all supported conversions with pricing and avg response time."""
    caps = registry.list_capabilities()
    return CapabilitiesResponse(
        total_conversions=len(caps),
        conversions=[
            CapabilityEntry(
                source=c["source"],
                target=c["target"],
                cost_usd=c["cost_usd"],
                avg_time_ms=c["avg_time_ms"],
                description=c["description"],
            )
            for c in caps
        ],
    )


# ---------------------------------------------------------------------------
# Payment info
# ---------------------------------------------------------------------------

@app.get("/payment/methods")
async def payment_methods():
    """How agents pay after the free tier."""
    return {
        "protocol": "x402",
        "description": (
            "After 100 free requests, the API returns HTTP 402 with payment requirements. "
            "Sign the payment with your wallet and resend the request with a PAYMENT-SIGNATURE header."
        ),
        "supported": {
            "scheme": "exact",
            "networks": ["eip155:8453 (Base)", "eip155:84532 (Base Sepolia testnet)"],
            "tokens": ["USDC"],
        },
        "facilitator": os.environ.get("X402_FACILITATOR_URL", "https://www.x402.org/facilitator"),
    }


# ---------------------------------------------------------------------------
# Revenue (admin only)
# ---------------------------------------------------------------------------

@app.get("/revenue")
async def revenue(authorization: str = Header()):
    """Revenue dashboard. Admin only."""
    key = _extract_key(authorization)
    if key != ADMIN_API_KEY:
        raise HTTPException(403, "Admin only")
    return get_revenue()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "transforms_registered": len(registry)}
