"""Base connector interface for target agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from agentprobe.probe.models import TargetProfile


class BaseConnector(ABC):
    """Abstract base class for connecting to target AI agents."""

    def __init__(self, url: str, name: str = "", **kwargs: Any):
        self.url = url
        self.name = name or url
        self.kwargs = kwargs

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the target agent."""
        ...

    @abstractmethod
    async def discover(self) -> TargetProfile:
        """Discover the target agent's tools, resources, and capabilities."""
        ...

    @abstractmethod
    async def invoke(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """Send a prompt to the target agent and capture the full response.

        Returns:
            dict with keys:
                - response_text: str
                - tool_calls: list[dict] (each with name, arguments, result)
                - input_tokens: int
                - output_tokens: int
                - latency_ms: float
                - error: str | None
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Clean up connection."""
        ...

    async def __aenter__(self) -> BaseConnector:
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.disconnect()
