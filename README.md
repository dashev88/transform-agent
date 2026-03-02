# Data Transform Agent

A headless, zero-UI data transformation service that converts between **43+ format pairs** and reshapes JSON structures. Discovered by AI agents via [MCP](https://modelcontextprotocol.io), [Google A2A](https://github.com/google/A2A), and OpenAPI. Paid via [x402](https://www.x402.org) (USDC stablecoin) — first 100 requests free.

**Live endpoint:** `https://transform-agent.fly.dev`

---

## Supported Formats

| Category | Formats |
|---|---|
| **Structured** | JSON, CSV, XML, YAML, TOML |
| **Markup** | HTML, Markdown, Plain Text |
| **Documents** | PDF, Excel (.xlsx), DOCX |
| **Encoding** | Base64, URL-encoded, Hex |

Any-to-any conversion where a logical path exists (e.g. JSON → CSV, XML → YAML, PDF → JSON, Excel → CSV).

## Quick Start

### Use via MCP (Claude, Cursor, Windsurf, etc.)

Add to your MCP client config:

```json
{
  "mcpServers": {
    "data-transform-agent": {
      "url": "https://transform-agent.fly.dev/mcp"
    }
  }
}
```

No installation needed — connects directly to the remote server.

### Use via REST API

```bash
# 1. Get a free API key (instant, no signup)
curl -X POST https://transform-agent.fly.dev/auth/provision \
  -H "Content-Type: application/json" \
  -d '{}'

# 2. Convert JSON to CSV
curl -X POST https://transform-agent.fly.dev/transform \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: ta_YOUR_KEY" \
  -d '{
    "source_format": "json",
    "target_format": "csv",
    "data": "[{\"name\":\"Alice\",\"age\":30},{\"name\":\"Bob\",\"age\":25}]"
  }'
```

### Use via Python SDK

```python
from transform_agent_sdk import TransformAgent

agent = TransformAgent()  # auto-provisions API key
result = agent.transform("csv", "json", csv_data)
print(result["result"])
```

## Tools (MCP)

| Tool | Description |
|---|---|
| `transform` | Convert data between any two supported formats |
| `reshape_json` | Restructure nested JSON using dot-notation path mapping |
| `list_capabilities` | List all supported conversions with pricing and response times |

### Reshape Example

Flatten a deeply nested API response:

```json
{
  "data": {"user": {"profile": {"name": "Alice"}, "address": {"city": "Paris"}}},
  "mapping": {"name": "user.profile.name", "city": "user.address.city"}
}
```
→ `{"name": "Alice", "city": "Paris"}`

## Discovery Protocols

| Protocol | Endpoint |
|---|---|
| **MCP** (Streamable HTTP) | `https://transform-agent.fly.dev/mcp` |
| **Google A2A** (Agent Card) | `https://transform-agent.fly.dev/.well-known/agent-card.json` |
| **OpenAPI** | `https://transform-agent.fly.dev/openapi.json` |
| **MCP Manifest** | `https://transform-agent.fly.dev/.well-known/mcp.json` |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/provision` | Get an API key instantly (no signup) |
| `GET` | `/auth/balance?api_key=...` | Check remaining free requests |
| `POST` | `/transform` | Convert data between formats |
| `POST` | `/transform/batch` | Batch convert multiple items |
| `POST` | `/reshape` | Reshape JSON with dot-notation mapping |
| `GET` | `/capabilities` | List all supported conversions |
| `GET` | `/payment/methods` | Payment info (x402 / USDC) |
| `GET` | `/health` | Health check |

## Pricing

| Transform Type | Cost |
|---|---|
| Text formats (JSON, CSV, XML, YAML, etc.) | $0.001 |
| Documents (PDF, Excel, DOCX) | $0.005 |
| Schema reshape | $0.002 |
| Encoding (Base64, hex, URL) | $0.0005 |

First **100 requests are free** per API key. After that, pay-per-request via [x402](https://www.x402.org) (USDC on Base).

## Self-Hosting

### Docker

```bash
docker build -t transform-agent .
docker run -p 8000:8000 \
  -e WALLET_ADDRESS=0xYourAddress \
  -e ADMIN_API_KEY=your-secret \
  transform-agent
```

### Fly.io

```bash
fly launch --copy-config
fly secrets set WALLET_ADDRESS=0xYourAddress ADMIN_API_KEY=your-secret
fly deploy
```

### Local Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # edit with your values
uvicorn transform_agent.app:app --reload
```

Run tests:

```bash
pytest
```

## Architecture

```
src/transform_agent/
├── app.py                 # FastAPI application & routes
├── models/schemas.py      # Pydantic models & Format enum
├── transforms/
│   ├── registry.py        # Central registry with O(1) routing
│   ├── tabular.py         # JSON ↔ CSV ↔ XML ↔ YAML ↔ TOML
│   ├── markup.py          # HTML ↔ Markdown ↔ Plain Text
│   ├── documents.py       # PDF / Excel / DOCX extraction
│   ├── encoding.py        # Base64, URL-encode, Hex
│   └── schema.py          # JSON reshape with dot-notation
├── auth/provision.py      # Zero-friction API key provisioning
├── payment/x402.py        # x402 / USDC payment config
├── middleware/
│   ├── metering.py        # Transaction logging & revenue
│   └── rate_limit.py      # Sliding-window rate limiter
└── discovery/
    ├── a2a_card.py        # Google A2A agent card
    ├── mcp.py             # MCP manifest
    ├── mcp_handler.py     # MCP Streamable HTTP (JSON-RPC 2.0)
    └── openapi.py         # OpenAPI customization
```

**Key dependencies:** FastAPI, orjson, polars, lxml, ruamel.yaml, pymupdf, openpyxl, python-docx, markdown-it-py, beautifulsoup4.

## License

MIT
