"""
transform-agent SDK — lightweight client for calling the Data Transform Agent.

Usage:
    from transform_agent_sdk import TransformAgent

    agent = TransformAgent()  # auto-provisions API key
    result = agent.transform("csv", "json", csv_data)
    print(result["result"])
"""

from __future__ import annotations

import httpx


DEFAULT_ENDPOINT = "https://transform-agent.fly.dev"


class TransformAgent:
    """
    Client for the Data Transform Agent.

    Auto-provisions an API key on first use. No signup, no config.
    First 100 requests are free.
    """

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = 30.0,
    ):
        self.endpoint = endpoint.rstrip("/")
        self._client = httpx.Client(timeout=timeout)
        self._api_key = api_key or self._auto_provision()

    def _auto_provision(self) -> str:
        resp = self._client.post(
            f"{self.endpoint}/auth/provision",
            json={"agent_name": "sdk-client"},
        )
        resp.raise_for_status()
        return resp.json()["api_key"]

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    def transform(
        self,
        source_format: str,
        target_format: str,
        data: str,
        options: dict | None = None,
    ) -> dict:
        """Transform data from one format to another.

        Args:
            source_format: e.g. "csv", "json", "xml", "yaml", "pdf"
            target_format: e.g. "json", "csv", "markdown", "html"
            data: Input data as string (or base64 for binary formats)
            options: Optional dict of format-specific options

        Returns:
            Dict with keys: result, source_format, target_format,
            input_size_bytes, output_size_bytes, transform_time_ms, cost_usd, tx_id
        """
        payload: dict = {
            "source_format": source_format,
            "target_format": target_format,
            "data": data,
        }
        if options:
            payload["options"] = options

        resp = self._client.post(
            f"{self.endpoint}/transform",
            json=payload,
            headers=self._headers,
        )
        resp.raise_for_status()
        return resp.json()

    def reshape(self, data: dict | list, mapping: dict[str, str]) -> dict:
        """Reshape JSON from one structure to another.

        Args:
            data: Input JSON (dict or list)
            mapping: {target_path: source_path} using dot-notation

        Returns:
            Dict with keys: result, cost_usd, tx_id
        """
        resp = self._client.post(
            f"{self.endpoint}/reshape",
            json={"data": data, "mapping": mapping},
            headers=self._headers,
        )
        resp.raise_for_status()
        return resp.json()

    def capabilities(self) -> dict:
        """List all supported format conversions."""
        resp = self._client.get(f"{self.endpoint}/capabilities")
        resp.raise_for_status()
        return resp.json()

    def balance(self) -> dict:
        """Check free requests remaining and total spent."""
        resp = self._client.get(
            f"{self.endpoint}/auth/balance",
            headers=self._headers,
        )
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "TransformAgent":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class AsyncTransformAgent:
    """Async variant of TransformAgent using httpx.AsyncClient."""

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = 30.0,
    ):
        self.endpoint = endpoint.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)
        self._api_key = api_key

    async def _ensure_key(self) -> None:
        if self._api_key is None:
            resp = await self._client.post(
                f"{self.endpoint}/auth/provision",
                json={"agent_name": "sdk-async-client"},
            )
            resp.raise_for_status()
            self._api_key = resp.json()["api_key"]

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    async def transform(
        self,
        source_format: str,
        target_format: str,
        data: str,
        options: dict | None = None,
    ) -> dict:
        await self._ensure_key()
        payload: dict = {
            "source_format": source_format,
            "target_format": target_format,
            "data": data,
        }
        if options:
            payload["options"] = options

        resp = await self._client.post(
            f"{self.endpoint}/transform",
            json=payload,
            headers=self._headers,
        )
        resp.raise_for_status()
        return resp.json()

    async def reshape(self, data: dict | list, mapping: dict[str, str]) -> dict:
        await self._ensure_key()
        resp = await self._client.post(
            f"{self.endpoint}/reshape",
            json={"data": data, "mapping": mapping},
            headers=self._headers,
        )
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncTransformAgent":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
