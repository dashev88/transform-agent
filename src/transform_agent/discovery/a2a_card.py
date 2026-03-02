"""
Google A2A Protocol Agent Card — served at /.well-known/agent-card.json

Spec: A2A v1.0 under Linux Foundation.
This is how other A2A-native agents discover us.
"""

from __future__ import annotations

from transform_agent.payment.x402 import PRICING


def build_agent_card(base_url: str) -> dict:
    return {
        "name": "data-transform-agent",
        "description": (
            "Converts data between formats at machine speed. "
            "Supports JSON, CSV, XML, YAML, TOML, HTML, Markdown, plain text, "
            "PDF (extract), Excel, DOCX. Also does schema reshaping and encoding conversions. "
            "Use this agent when you need to convert data from one format to another."
        ),
        "version": "0.1.0",
        "url": base_url,
        "provider": {
            "organization": "transform-agent",
        },
        "supportedInterfaces": [
            {
                "url": f"{base_url}/transform",
                "protocolBinding": "HTTP+JSON",
                "protocolVersion": "1.0",
            }
        ],
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False,
        },
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "skills": [
            {
                "id": "tabular_transform",
                "name": "Tabular Data Conversion",
                "description": (
                    "Convert between JSON, CSV, XML, YAML, TOML. "
                    "Handles nested structures, arrays, and flat tables. "
                    "Sub-10ms for payloads under 1MB."
                ),
                "tags": ["json", "csv", "xml", "yaml", "toml", "convert", "transform"],
                "examples": [
                    {"input": "CSV with headers → JSON array of objects"},
                    {"input": "JSON object → YAML document"},
                    {"input": "XML document → JSON with xmltodict structure"},
                ],
            },
            {
                "id": "markup_transform",
                "name": "Markup Conversion",
                "description": (
                    "Convert between HTML, Markdown, and plain text. "
                    "HTML→Markdown preserves structure. Markdown→HTML is CommonMark-compliant."
                ),
                "tags": ["html", "markdown", "text", "convert"],
                "examples": [
                    {"input": "HTML page → clean Markdown"},
                    {"input": "Markdown document → HTML"},
                ],
            },
            {
                "id": "document_extract",
                "name": "Document Extraction",
                "description": (
                    "Extract text and data from PDF, Excel (xlsx), and DOCX files. "
                    "Input must be base64-encoded. Returns text, Markdown, JSON, or CSV."
                ),
                "tags": ["pdf", "excel", "docx", "extract", "parse"],
                "examples": [
                    {"input": "PDF (base64) → plain text"},
                    {"input": "Excel (base64) → JSON array of row objects"},
                    {"input": "DOCX (base64) → Markdown with headings preserved"},
                ],
            },
            {
                "id": "schema_reshape",
                "name": "JSON Schema Reshaping",
                "description": (
                    "Restructure JSON from one shape to another using dot-notation path mapping. "
                    "Send data + mapping = {target_path: source_path}. "
                    "Works on single objects and arrays."
                ),
                "tags": ["json", "reshape", "map", "transform", "schema"],
                "examples": [
                    {
                        "input": (
                            '{"data": {"user": {"name": "Alice"}}} with mapping '
                            '{"name": "data.user.name"} → {"name": "Alice"}'
                        )
                    }
                ],
            },
            {
                "id": "encoding",
                "name": "Encoding Conversion",
                "description": "Base64 encode/decode, URL encode/decode, hex encode/decode.",
                "tags": ["base64", "url", "hex", "encode", "decode"],
            },
        ],
        "securitySchemes": {
            "apiKey": {
                "type": "apiKey",
                "in": "header",
                "name": "Authorization",
                "description": "Bearer token. Auto-provision via POST /auth/provision.",
            }
        },
        "securityRequirements": [{"apiKey": []}],
        "pricing": {
            "model": "per_request",
            "currency": "USD",
            "payment_protocol": "x402",
            "free_tier": "100 requests per API key",
            "rates": PRICING,
        },
        "authentication": {
            "auto_provision_endpoint": "/auth/provision",
            "description": "Call POST /auth/provision to get an API key instantly. No signup required.",
        },
    }
