"""REST API connector for interacting with AI agents exposed via HTTP."""

from __future__ import annotations

import time
from typing import Any

import httpx

from agentprobe.connectors.base import BaseConnector
from agentprobe.probe.models import (
    ConnectorType,
    TargetProfile,
    ToolSchema,
)


class APIConnector(BaseConnector):
    """Connects to a target AI agent via REST API.

    Supports agents exposed via FastAPI, Flask, or any HTTP endpoint
    that accepts a prompt and returns a response.
    """

    def __init__(
        self,
        url: str,
        name: str = "",
        auth_token: str = "",
        chat_endpoint: str = "/chat",
        tools_endpoint: str | None = "/tools",
        health_endpoint: str = "/health",
        prompt_field: str = "message",
        response_field: str = "response",
        **kwargs: Any,
    ):
        super().__init__(url, name, **kwargs)
        self.auth_token = auth_token
        self.chat_endpoint = chat_endpoint
        self.tools_endpoint = tools_endpoint
        self.health_endpoint = health_endpoint
        self.prompt_field = prompt_field
        self.response_field = response_field
        self._client: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        """Establish connection and verify the agent is reachable."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        self._client = httpx.AsyncClient(
            base_url=self.url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(60.0),
        )

        # Health check
        try:
            resp = await self._client.get(self.health_endpoint)
            if resp.status_code >= 500:
                raise ConnectionError(
                    f"Target agent at {self.url} returned {resp.status_code}"
                )
        except httpx.ConnectError as e:
            raise ConnectionError(
                f"Cannot reach target agent at {self.url}: {e}"
            ) from e

    async def discover(self) -> TargetProfile:
        """Discover the agent's capabilities via its tools/schema endpoint."""
        if not self._client:
            raise RuntimeError("Not connected. Call connect() first.")

        tools: list[ToolSchema] = []

        if self.tools_endpoint:
            try:
                resp = await self._client.get(self.tools_endpoint)
                if resp.status_code == 200:
                    data = resp.json()
                    tool_list = (
                        data if isinstance(data, list) else data.get("tools", [])
                    )
                    for t in tool_list:
                        tools.append(
                            ToolSchema(
                                name=t.get("name", "unknown"),
                                description=t.get("description", ""),
                                parameters=t.get("parameters", {}),
                                required_params=t.get("required", []),
                            )
                        )
            except (httpx.HTTPError, ValueError):
                pass

        # Try OpenAPI spec discovery as fallback
        if not tools:
            tools = await self._discover_from_openapi()

        return TargetProfile(
            name=self.name,
            url=self.url,
            connector_type=ConnectorType.REST_API,
            description=f"REST API agent at {self.url}",
            tools=tools,
            metadata={
                "chat_endpoint": self.chat_endpoint,
                "tools_endpoint": self.tools_endpoint,
            },
        )

    async def _discover_from_openapi(self) -> list[ToolSchema]:
        """Try to discover tools from an OpenAPI spec."""
        tools: list[ToolSchema] = []

        for path in ["/openapi.json", "/docs/openapi.json", "/api/openapi.json"]:
            try:
                resp = await self._client.get(path)  # type: ignore[union-attr]
                if resp.status_code == 200:
                    spec = resp.json()
                    paths = spec.get("paths", {})
                    for endpoint, methods in paths.items():
                        for method, details in methods.items():
                            if method.lower() in ("get", "post", "put", "patch"):
                                params = {}
                                required = []
                                request_body = details.get("requestBody", {})
                                if request_body:
                                    content = request_body.get("content", {})
                                    json_schema = content.get(
                                        "application/json", {}
                                    ).get("schema", {})
                                    params = json_schema.get("properties", {})
                                    required = json_schema.get("required", [])

                                tools.append(
                                    ToolSchema(
                                        name=f"{method.upper()} {endpoint}",
                                        description=details.get("summary", ""),
                                        parameters=params,
                                        required_params=required,
                                    )
                                )
                    break
            except (httpx.HTTPError, ValueError):
                continue

        return tools

    async def invoke(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """Send a prompt to the target agent and capture the response."""
        if not self._client:
            raise RuntimeError("Not connected. Call connect() first.")

        start_time = time.monotonic()
        error: str | None = None
        response_text = ""
        tool_calls: list[dict[str, Any]] = []

        payload = {self.prompt_field: prompt}
        payload.update(kwargs.get("extra_fields", {}))

        try:
            resp = await self._client.post(self.chat_endpoint, json=payload)
            resp.raise_for_status()
            data = resp.json()

            # Extract response text
            if isinstance(data, str):
                response_text = data
            elif isinstance(data, dict):
                response_text = (
                    data.get(self.response_field, "")
                    or data.get("text", "")
                    or data.get("content", "")
                    or data.get("output", "")
                    or str(data)
                )
                # Extract tool calls if present
                for tc in data.get("tool_calls", []):
                    tname = tc.get("name", tc.get("tool", ""))
                    tool_calls.append(
                        {
                            "name": tname,
                            "tool_name": tname,
                            "arguments": tc.get("arguments", tc.get("args", {})),
                            "result": tc.get("result", tc.get("output", "")),
                        }
                    )

        except httpx.HTTPError as e:
            error = f"HTTP error: {e}"
        except ValueError as e:
            error = f"Response parse error: {e}"

        elapsed_ms = (time.monotonic() - start_time) * 1000

        # Extract token usage if available
        input_tokens = 0
        output_tokens = 0
        if isinstance(data, dict):
            usage = data.get("usage", {})
            input_tokens = usage.get("input_tokens", usage.get("prompt_tokens", 0))
            output_tokens = usage.get(
                "output_tokens", usage.get("completion_tokens", 0)
            )

        return {
            "response_text": response_text,
            "tool_calls": tool_calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": round(elapsed_ms, 2),
            "error": error,
        }

    async def disconnect(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
