"""Ollama REST connector — probe local LLMs via the Ollama HTTP API."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from agentprobe.connectors.base import BaseConnector
from agentprobe.probe.models import ConnectorType, TargetProfile, ToolSchema


class OllamaConnector(BaseConnector):
    """Connects to a model served by Ollama (default http://127.0.0.1:11434)."""

    def __init__(
        self,
        url: str,
        name: str = "",
        model: str = "",
        **kwargs: Any,
    ):
        super().__init__(url, name, **kwargs)
        self.model = model or os.environ.get("OLLAMA_MODEL", "llama3.1")
        self.temperature = float(kwargs.get("temperature", 0.7))
        self._client: httpx.AsyncClient | None = None
        self._available_models: list[str] = []

    @property
    def base_url(self) -> str:
        return self.url.rstrip("/")

    async def connect(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(300.0),
        )
        try:
            resp = await self._client.get("/api/tags")
            resp.raise_for_status()
            data = resp.json()
            self._available_models = [
                m.get("name", "")
                for m in data.get("models", [])
                if m.get("name")
            ]
        except httpx.ConnectError as e:
            raise ConnectionError(
                f"Cannot reach Ollama at {self.base_url}. "
                f"Start it with: ollama run {self.model}\n{e}"
            ) from e
        except httpx.HTTPError as e:
            raise ConnectionError(f"Ollama at {self.base_url} returned an error: {e}") from e

        if self._available_models and self.model not in self._available_models:
            # Allow partial match (e.g. llama3.1 vs llama3.1:latest)
            if not any(self.model in m or m.startswith(self.model) for m in self._available_models):
                resolved = self._available_models[0]
                self.model = resolved

    async def discover(self) -> TargetProfile:
        if not self._client:
            raise RuntimeError("Not connected. Call connect() first.")

        tools = [
            ToolSchema(
                name="chat",
                description=f"Chat completion via Ollama model {self.model}",
                parameters={"message": {"type": "string"}},
                required_params=["message"],
            )
        ]

        return TargetProfile(
            name=self.name or f"Ollama ({self.model})",
            url=self.base_url,
            connector_type=ConnectorType.OLLAMA,
            description=f"Local Ollama LLM at {self.base_url}",
            tools=tools,
            metadata={
                "model": self.model,
                "available_models": self._available_models,
                "api": "ollama",
                "temperature": self.temperature,
            },
        )

    def _chat_options(self, **kwargs: Any) -> dict[str, Any]:
        """Build Ollama ``options`` for /api/chat (temperature + optional seed)."""
        temperature = float(kwargs.get("temperature", self.temperature))
        options: dict[str, Any] = {"temperature": temperature}
        seed = kwargs.get("seed")
        if seed is not None:
            options["seed"] = int(seed)
        return options

    async def invoke(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        if not self._client:
            raise RuntimeError("Not connected. Call connect() first.")

        start = time.monotonic()
        error: str | None = None
        response_text = ""
        input_tokens = 0
        output_tokens = 0

        try:
            payload: dict[str, Any] = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": self._chat_options(**kwargs),
            }

            resp = await self._client.post("/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            message = data.get("message", {})
            response_text = message.get("content", "") if isinstance(message, dict) else str(message)
            input_tokens = int(data.get("prompt_eval_count", 0))
            output_tokens = int(data.get("eval_count", 0))
        except httpx.HTTPError as e:
            error = f"Ollama HTTP error: {e}"

        elapsed_ms = (time.monotonic() - start) * 1000

        return {
            "response_text": response_text,
            "tool_calls": [],
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": round(elapsed_ms, 2),
            "error": error,
        }

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
