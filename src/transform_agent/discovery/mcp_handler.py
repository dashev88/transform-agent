"""
MCP Streamable HTTP transport handler.

Implements the MCP protocol (JSON-RPC 2.0 over HTTP) so that MCP clients
like Claude Desktop, Cursor, Smithery, etc. can call our tools natively.

Endpoint: POST /mcp
"""

from __future__ import annotations

import base64
import uuid
from typing import Any

import orjson

from transform_agent.transforms.registry import registry
from transform_agent.transforms.schema import reshape_json
from transform_agent.models.schemas import BINARY_FORMATS, Format


# ---------------------------------------------------------------------------
# Protocol constants
# ---------------------------------------------------------------------------

SERVER_INFO = {
    "name": "data-transform",
    "version": "0.1.0",
}

SERVER_CAPABILITIES = {
    "tools": {"listChanged": False},
}

PROTOCOL_VERSION = "2025-03-26"
SUPPORTED_VERSIONS = {"2024-11-05", "2025-03-26"}


# ---------------------------------------------------------------------------
# Tool definitions (same as manifest, but in MCP list format)
# ---------------------------------------------------------------------------

def _get_tools() -> list[dict]:
    return [
        {
            "name": "transform",
            "description": (
                "Convert data from one format to another. "
                "Supports: json, csv, xml, yaml, toml, html, markdown, plain_text, pdf, excel, docx. "
                "For binary formats (pdf, excel, docx), send data as base64-encoded string. "
                "Returns the transformed data as a string (or base64 for binary output)."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "source_format": {
                        "type": "string",
                        "enum": [
                            "json", "csv", "xml", "yaml", "toml",
                            "html", "markdown", "plain_text",
                            "pdf", "excel", "docx",
                        ],
                        "description": "The format of the input data",
                    },
                    "target_format": {
                        "type": "string",
                        "enum": [
                            "json", "csv", "xml", "yaml", "toml",
                            "html", "markdown", "plain_text",
                            "excel",
                        ],
                        "description": "The desired output format",
                    },
                    "data": {
                        "type": "string",
                        "description": "The input data as text (or base64 for binary formats)",
                    },
                    "options": {
                        "type": "object",
                        "description": "Optional: {delimiter, sheet_name, root_tag, ...}",
                    },
                },
                "required": ["source_format", "target_format", "data"],
            },
        },
        {
            "name": "reshape_json",
            "description": (
                "Restructure JSON from one shape to another using dot-notation path mapping. "
                "Example: mapping={'name': 'user.profile.full_name'} extracts nested values."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "object",
                        "description": "The input JSON data (object or array)",
                    },
                    "mapping": {
                        "type": "object",
                        "description": "Mapping: {target_path: source_path, ...}",
                    },
                },
                "required": ["data", "mapping"],
            },
        },
        {
            "name": "list_capabilities",
            "description": "List all supported format conversions with pricing and average response times.",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
    ]


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

async def _call_tool(name: str, arguments: dict[str, Any]) -> list[dict]:
    """Execute a tool and return MCP content blocks."""
    if name == "transform":
        return await _tool_transform(arguments)
    elif name == "reshape_json":
        return await _tool_reshape(arguments)
    elif name == "list_capabilities":
        return _tool_list_capabilities()
    else:
        raise ValueError(f"Unknown tool: {name}")


async def _tool_transform(args: dict) -> list[dict]:
    src = Format(args["source_format"])
    tgt = Format(args["target_format"])
    data_str = args["data"]
    options = args.get("options", {})

    if not registry.supports(src, tgt):
        return [{"type": "text", "text": f"Error: Unsupported conversion {src.value} → {tgt.value}. Call list_capabilities to see what's supported."}]

    # Decode binary input
    if src in BINARY_FORMATS:
        try:
            input_bytes = base64.b64decode(data_str)
        except Exception:
            return [{"type": "text", "text": "Error: Invalid base64 data for binary format."}]
    else:
        input_bytes = data_str.encode()

    try:
        result_bytes, cost, time_ms = await registry.execute(src, tgt, input_bytes, options)
    except Exception as e:
        return [{"type": "text", "text": f"Error: Transform failed — {e}"}]

    # Encode binary output
    if tgt in BINARY_FORMATS:
        result_str = base64.b64encode(result_bytes).decode()
    else:
        result_str = result_bytes.decode()

    return [{"type": "text", "text": result_str}]


async def _tool_reshape(args: dict) -> list[dict]:
    data = args["data"]
    mapping = args["mapping"]
    input_bytes = orjson.dumps(data)
    try:
        result_bytes = await reshape_json(input_bytes, {"mapping": mapping})
    except Exception as e:
        return [{"type": "text", "text": f"Error: Reshape failed — {e}"}]
    result = orjson.loads(result_bytes)
    return [{"type": "text", "text": orjson.dumps(result, option=orjson.OPT_INDENT_2).decode()}]


def _tool_list_capabilities() -> list[dict]:
    caps = registry.list_capabilities()
    lines = [f"Total conversions: {len(caps)}", ""]
    for c in caps:
        lines.append(f"• {c['source']} → {c['target']}  (${c['cost_usd']}, avg {c['avg_time_ms']}ms)")
    return [{"type": "text", "text": "\n".join(lines)}]


# ---------------------------------------------------------------------------
# JSON-RPC handler
# ---------------------------------------------------------------------------

def _jsonrpc_error(req_id: str | int | None, code: int, message: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }


def _jsonrpc_result(req_id: str | int | None, result: Any) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result,
    }


async def handle_mcp_message(body: dict) -> dict | None:
    """
    Process a single JSON-RPC 2.0 message.
    Returns a response dict, or None for notifications.
    """
    method = body.get("method", "")
    req_id = body.get("id")
    params = body.get("params", {})

    # Notifications (no id) — just acknowledge
    if req_id is None:
        return None

    if method == "initialize":
        client_version = params.get("protocolVersion", "")
        negotiated = client_version if client_version in SUPPORTED_VERSIONS else PROTOCOL_VERSION
        return _jsonrpc_result(req_id, {
            "protocolVersion": negotiated,
            "capabilities": SERVER_CAPABILITIES,
            "serverInfo": SERVER_INFO,
        })

    elif method == "ping":
        return _jsonrpc_result(req_id, {})

    elif method == "tools/list":
        return _jsonrpc_result(req_id, {
            "tools": _get_tools(),
        })

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        try:
            content = await _call_tool(tool_name, arguments)
            return _jsonrpc_result(req_id, {
                "content": content,
                "isError": False,
            })
        except Exception as e:
            return _jsonrpc_result(req_id, {
                "content": [{"type": "text", "text": f"Error: {e}"}],
                "isError": True,
            })

    else:
        return _jsonrpc_error(req_id, -32601, f"Method not found: {method}")
