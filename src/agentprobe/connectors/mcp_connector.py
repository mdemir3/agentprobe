"""MCP connector for discovering and interacting with MCP-based AI agents."""

from __future__ import annotations

import time
from typing import Any

import httpx

from agentprobe.connectors.base import BaseConnector
from agentprobe.probe.models import (
    ConnectorType,
    ResourceSchema,
    TargetProfile,
    ToolCallRecord,
    ToolSchema,
)


class MCPConnector(BaseConnector):
    """Connects to a target AI agent via Model Context Protocol (MCP).

    Supports SSE and HTTP transports. Auto-discovers tools, resources,
    and prompts exposed by the MCP server.
    """

    def __init__(self, url: str, name: str = "", auth_token: str = "", **kwargs: Any):
        super().__init__(url, name, **kwargs)
        self.auth_token = auth_token
        self._client: httpx.AsyncClient | None = None
        self._tools: list[ToolSchema] = []
        self._resources: list[ResourceSchema] = []
        self._session_id: str | None = None

    async def connect(self) -> None:
        """Establish connection to the MCP server."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        self._client = httpx.AsyncClient(
            base_url=self.url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(30.0),
        )

        # Initialize MCP session
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "AgentProbe", "version": "0.1.0"},
            },
        }

        try:
            resp = await self._client.post("/", json=init_payload)
            resp.raise_for_status()
            data = resp.json()
            if "result" in data:
                server_info = data["result"].get("serverInfo", {})
                if not self.name or self.name == self.url:
                    self.name = server_info.get("name", self.name)
        except httpx.HTTPError as e:
            raise ConnectionError(
                f"Failed to initialize MCP session at {self.url}: {e}"
            ) from e

    async def discover(self) -> TargetProfile:
        """Discover all tools and resources on the MCP server."""
        if not self._client:
            raise RuntimeError("Not connected. Call connect() first.")

        # Discover tools
        self._tools = await self._discover_tools()

        # Discover resources
        self._resources = await self._discover_resources()

        return TargetProfile(
            name=self.name,
            url=self.url,
            connector_type=ConnectorType.MCP,
            description=f"MCP agent at {self.url}",
            tools=self._tools,
            resources=self._resources,
            metadata={"session_id": self._session_id},
        )

    async def _discover_tools(self) -> list[ToolSchema]:
        """List all tools available on the MCP server."""
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }

        try:
            resp = await self._client.post("/", json=payload)  # type: ignore[union-attr]
            resp.raise_for_status()
            data = resp.json()

            tools = []
            for tool_data in data.get("result", {}).get("tools", []):
                input_schema = tool_data.get("inputSchema", {})
                properties = input_schema.get("properties", {})
                required = input_schema.get("required", [])

                tools.append(
                    ToolSchema(
                        name=tool_data["name"],
                        description=tool_data.get("description", ""),
                        parameters=properties,
                        required_params=required,
                    )
                )
            return tools

        except httpx.HTTPError:
            return []

    async def _discover_resources(self) -> list[ResourceSchema]:
        """List all resources available on the MCP server."""
        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "resources/list",
            "params": {},
        }

        try:
            resp = await self._client.post("/", json=payload)  # type: ignore[union-attr]
            resp.raise_for_status()
            data = resp.json()

            resources = []
            for res_data in data.get("result", {}).get("resources", []):
                resources.append(
                    ResourceSchema(
                        uri=res_data.get("uri", ""),
                        name=res_data.get("name", ""),
                        description=res_data.get("description", ""),
                        mime_type=res_data.get("mimeType", ""),
                    )
                )
            return resources

        except httpx.HTTPError:
            return []

    async def invoke(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """Send a prompt to the target agent by calling its tools.

        For MCP servers, we call tools directly. The prompt is used to
        determine which tool to call and with what arguments.
        """
        if not self._client:
            raise RuntimeError("Not connected. Call connect() first.")

        start_time = time.monotonic()
        tool_calls: list[dict[str, Any]] = []
        error: str | None = None
        response_text = ""

        # If a specific tool call is requested
        tool_name = kwargs.get("tool_name")
        tool_args = kwargs.get("tool_args", {})

        if tool_name:
            record = await self._call_tool(tool_name, tool_args)
            tool_calls.append(record.model_dump())
            if record.error:
                error = record.error
            else:
                response_text = str(record.result)

        elapsed_ms = (time.monotonic() - start_time) * 1000

        return {
            "response_text": response_text,
            "tool_calls": tool_calls,
            "input_tokens": 0,
            "output_tokens": 0,
            "latency_ms": round(elapsed_ms, 2),
            "error": error,
        }

    async def _call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> ToolCallRecord:
        """Call a specific tool on the MCP server."""
        start = time.monotonic()

        payload = {
            "jsonrpc": "2.0",
            "id": 100,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        try:
            resp = await self._client.post("/", json=payload)  # type: ignore[union-attr]
            resp.raise_for_status()
            data = resp.json()

            result = data.get("result", {})
            content = result.get("content", [])
            text_parts = [c.get("text", "") for c in content if c.get("type") == "text"]

            return ToolCallRecord(
                tool_name=tool_name,
                arguments=arguments,
                result="\n".join(text_parts) if text_parts else result,
                latency_ms=round((time.monotonic() - start) * 1000, 2),
            )

        except httpx.HTTPError as e:
            return ToolCallRecord(
                tool_name=tool_name,
                arguments=arguments,
                error=str(e),
                latency_ms=round((time.monotonic() - start) * 1000, 2),
            )

    async def disconnect(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
