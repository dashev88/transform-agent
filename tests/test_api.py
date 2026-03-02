"""Tests for the HTTP API endpoints — discovery, auth, transform."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from transform_agent.app import app, _register_transforms

# Register transforms once (lifespan doesn't run with ASGITransport)
_register_transforms()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestDiscovery:
    @pytest.mark.asyncio
    async def test_agent_card(self, client: AsyncClient):
        resp = await client.get("/.well-known/agent-card.json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "data-transform-agent"
        assert "skills" in data
        assert len(data["skills"]) >= 4

    @pytest.mark.asyncio
    async def test_mcp_manifest(self, client: AsyncClient):
        resp = await client.get("/.well-known/mcp.json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "data-transform"
        assert len(data["tools"]) >= 3

    @pytest.mark.asyncio
    async def test_openapi(self, client: AsyncClient):
        resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert "paths" in data
        assert "/transform" in data["paths"]

    @pytest.mark.asyncio
    async def test_capabilities(self, client: AsyncClient):
        resp = await client.get("/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_conversions"] > 30

    @pytest.mark.asyncio
    async def test_health(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestAuth:
    @pytest.mark.asyncio
    async def test_provision(self, client: AsyncClient):
        resp = await client.post("/auth/provision", json={"agent_name": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["api_key"].startswith("ta_")
        assert data["free_requests_remaining"] == 100

    @pytest.mark.asyncio
    async def test_balance(self, client: AsyncClient):
        # Provision first
        prov = await client.post("/auth/provision", json={})
        key = prov.json()["api_key"]

        resp = await client.get(
            "/auth/balance",
            headers={"Authorization": f"Bearer {key}"},
        )
        assert resp.status_code == 200
        assert resp.json()["free_requests_remaining"] == 100

    @pytest.mark.asyncio
    async def test_no_auth_rejected(self, client: AsyncClient):
        resp = await client.post(
            "/transform",
            json={"source_format": "json", "target_format": "csv", "data": "[]"},
        )
        # FastAPI will return 422 (missing header) or 401
        assert resp.status_code in (401, 422)


class TestTransform:
    @pytest.mark.asyncio
    async def test_json_to_csv(self, client: AsyncClient):
        prov = await client.post("/auth/provision", json={})
        key = prov.json()["api_key"]

        resp = await client.post(
            "/transform",
            json={
                "source_format": "json",
                "target_format": "csv",
                "data": '[{"name":"Alice","age":30},{"name":"Bob","age":25}]',
            },
            headers={"Authorization": f"Bearer {key}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "Alice" in data["result"]
        assert data["transform_time_ms"] >= 0
        assert data["cost_usd"] == 0.0  # free tier

    @pytest.mark.asyncio
    async def test_csv_to_json(self, client: AsyncClient):
        prov = await client.post("/auth/provision", json={})
        key = prov.json()["api_key"]

        resp = await client.post(
            "/transform",
            json={
                "source_format": "csv",
                "target_format": "json",
                "data": "name,age\nAlice,30\nBob,25",
            },
            headers={"Authorization": f"Bearer {key}"},
        )
        assert resp.status_code == 200
        result = resp.json()["result"]
        import json
        obj = json.loads(result)
        assert len(obj) == 2

    @pytest.mark.asyncio
    async def test_unsupported_pair(self, client: AsyncClient):
        prov = await client.post("/auth/provision", json={})
        key = prov.json()["api_key"]

        resp = await client.post(
            "/transform",
            json={
                "source_format": "pdf",
                "target_format": "excel",
                "data": "irrelevant",
            },
            headers={"Authorization": f"Bearer {key}"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_reshape(self, client: AsyncClient):
        prov = await client.post("/auth/provision", json={})
        key = prov.json()["api_key"]

        resp = await client.post(
            "/reshape",
            json={
                "data": {"response": {"user": {"name": "Alice"}}},
                "mapping": {"name": "response.user.name"},
            },
            headers={"Authorization": f"Bearer {key}"},
        )
        assert resp.status_code == 200
        assert resp.json()["result"]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_payment_methods(self, client: AsyncClient):
        resp = await client.get("/payment/methods")
        assert resp.status_code == 200
        assert resp.json()["protocol"] == "x402"
