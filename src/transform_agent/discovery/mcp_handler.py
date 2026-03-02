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
    "prompts": {"listChanged": False},
    "resources": {"subscribe": False, "listChanged": False},
}

PROTOCOL_VERSION = "2025-03-26"
SUPPORTED_VERSIONS = {"2024-11-05", "2025-03-26"}


# ---------------------------------------------------------------------------
# Tool definitions with full annotations & parameter descriptions
# ---------------------------------------------------------------------------

def _get_tools() -> list[dict]:
    return [
        {
            "name": "transform",
            "description": (
                "Convert data from one format to another. "
                "Supports 43+ conversion pairs across JSON, CSV, XML, YAML, TOML, HTML, "
                "Markdown, plain text, PDF, Excel, and DOCX. "
                "For binary input formats (pdf, excel, docx), send data as a base64-encoded string. "
                "Returns the transformed data as a string (or base64 for binary output formats like excel)."
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
                        "description": "The format of the input data. Use the exact enum value, e.g. 'json', 'csv', 'xml'.",
                    },
                    "target_format": {
                        "type": "string",
                        "enum": [
                            "json", "csv", "xml", "yaml", "toml",
                            "html", "markdown", "plain_text",
                            "excel",
                        ],
                        "description": "The desired output format to convert to. Use the exact enum value, e.g. 'csv', 'yaml'.",
                    },
                    "data": {
                        "type": "string",
                        "description": (
                            "The input data as a text string. For binary formats (pdf, excel, docx), "
                            "provide the file content as a base64-encoded string."
                        ),
                    },
                    "options": {
                        "type": "object",
                        "description": (
                            "Optional configuration for the conversion. Supported keys: "
                            "'delimiter' (CSV separator, default ','), "
                            "'sheet_name' (Excel sheet, default 'Sheet1'), "
                            "'root_tag' (XML root element, default 'root'), "
                            "'item_tag' (XML item element, default 'item')."
                        ),
                        "properties": {
                            "delimiter": {
                                "type": "string",
                                "description": "CSV column delimiter character. Default: ','",
                            },
                            "sheet_name": {
                                "type": "string",
                                "description": "Excel worksheet name to read from or write to. Default: 'Sheet1'",
                            },
                            "root_tag": {
                                "type": "string",
                                "description": "Root XML element name when generating XML. Default: 'root'",
                            },
                            "item_tag": {
                                "type": "string",
                                "description": "XML element name for each record. Default: 'item'",
                            },
                        },
                    },
                },
                "required": ["source_format", "target_format", "data"],
            },
            "annotations": {
                "title": "Data Format Converter",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        },
        {
            "name": "reshape_json",
            "description": (
                "Restructure JSON data from one schema to another using dot-notation path mapping. "
                "Maps fields from the source to new positions in the target. "
                "Handles both single objects and arrays of objects. "
                "Example: mapping={'full_name': 'user.profile.name', 'email': 'user.contact.email'} "
                "extracts nested values into a flat structure."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "object",
                        "description": (
                            "The input JSON data to reshape. Can be a single object or an array of objects. "
                            "Example: {'user': {'profile': {'name': 'Alice'}}}"
                        ),
                    },
                    "mapping": {
                        "type": "object",
                        "description": (
                            "A dictionary mapping target field paths to source field paths using dot-notation. "
                            "Example: {'name': 'user.profile.name', 'city': 'user.address.city'} "
                            "Target paths can also be nested: {'output.name': 'input.user.name'}."
                        ),
                    },
                },
                "required": ["data", "mapping"],
            },
            "annotations": {
                "title": "JSON Schema Reshaper",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        },
        {
            "name": "list_capabilities",
            "description": (
                "List all supported format conversion pairs with pricing and average response times. "
                "Call this first to discover which source→target format combinations are available "
                "before attempting a transform."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
            "annotations": {
                "title": "List Supported Conversions",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        },
    ]


# ---------------------------------------------------------------------------
# Prompts — pre-built interaction templates
# ---------------------------------------------------------------------------

def _get_prompts() -> list[dict]:
    return [
        {
            "name": "convert-data",
            "description": "Convert data from one format to another. Provide the source format, target format, and data.",
            "arguments": [
                {
                    "name": "source_format",
                    "description": "Source format (json, csv, xml, yaml, toml, html, markdown, plain_text, pdf, excel, docx)",
                    "required": True,
                },
                {
                    "name": "target_format",
                    "description": "Target format (json, csv, xml, yaml, toml, html, markdown, plain_text, excel)",
                    "required": True,
                },
                {
                    "name": "data",
                    "description": "The data to convert",
                    "required": True,
                },
            ],
        },
        {
            "name": "reshape-json",
            "description": "Restructure JSON by mapping fields from one schema to another using dot-notation paths.",
            "arguments": [
                {
                    "name": "data",
                    "description": "The JSON data to reshape (as a JSON string)",
                    "required": True,
                },
                {
                    "name": "mapping",
                    "description": "Field mapping as JSON: {\"target_path\": \"source_path\", ...}",
                    "required": True,
                },
            ],
        },
    ]


def _get_prompt(name: str, arguments: dict) -> dict:
    if name == "convert-data":
        return {
            "description": f"Convert {arguments.get('source_format', '?')} to {arguments.get('target_format', '?')}",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Please convert this {arguments.get('source_format', 'data')} "
                            f"to {arguments.get('target_format', 'the target format')}:\n\n"
                            f"{arguments.get('data', '')}"
                        ),
                    },
                },
            ],
        }
    elif name == "reshape-json":
        return {
            "description": "Reshape JSON data with field mapping",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Reshape this JSON using the field mapping.\n\n"
                            f"Data: {arguments.get('data', '{}')}\n\n"
                            f"Mapping: {arguments.get('mapping', '{}')}"
                        ),
                    },
                },
            ],
        }
    raise ValueError(f"Unknown prompt: {name}")


# ---------------------------------------------------------------------------
# Resources — expose capabilities as a readable resource
# ---------------------------------------------------------------------------

def _get_resources() -> list[dict]:
    return [
        {
            "uri": "transform://capabilities",
            "name": "Supported Conversions",
            "description": "Complete list of all supported format conversion pairs with pricing and performance data.",
            "mimeType": "application/json",
        },
        {
            "uri": "transform://formats",
            "name": "Supported Formats",
            "description": "List of all input and output formats supported by the transform agent.",
            "mimeType": "application/json",
        },
    ]


def _read_resource(uri: str) -> list[dict]:
    if uri == "transform://capabilities":
        caps = registry.list_capabilities()
        return [{"uri": uri, "mimeType": "application/json", "text": orjson.dumps(caps, option=orjson.OPT_INDENT_2).decode()}]
    elif uri == "transform://formats":
        formats = {
            "input_formats": ["json", "csv", "xml", "yaml", "toml", "html", "markdown", "plain_text", "pdf", "excel", "docx"],
            "output_formats": ["json", "csv", "xml", "yaml", "toml", "html", "markdown", "plain_text", "excel"],
            "binary_formats": ["pdf", "excel", "docx"],
        }
        return [{"uri": uri, "mimeType": "application/json", "text": orjson.dumps(formats, option=orjson.OPT_INDENT_2).decode()}]
    raise ValueError(f"Unknown resource: {uri}")


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

    elif method == "prompts/list":
        return _jsonrpc_result(req_id, {
            "prompts": _get_prompts(),
        })

    elif method == "prompts/get":
        prompt_name = params.get("name", "")
        arguments = params.get("arguments", {})
        try:
            result = _get_prompt(prompt_name, arguments)
            return _jsonrpc_result(req_id, result)
        except Exception as e:
            return _jsonrpc_error(req_id, -32602, str(e))

    elif method == "resources/list":
        return _jsonrpc_result(req_id, {
            "resources": _get_resources(),
        })

    elif method == "resources/read":
        uri = params.get("uri", "")
        try:
            contents = _read_resource(uri)
            return _jsonrpc_result(req_id, {
                "contents": contents,
            })
        except Exception as e:
            return _jsonrpc_error(req_id, -32602, str(e))

    else:
        return _jsonrpc_error(req_id, -32601, f"Method not found: {method}")
