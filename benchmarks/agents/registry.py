"""Benchmark agent registry — ports, profiles, and launch helpers."""

from __future__ import annotations

import importlib
from dataclasses import dataclass

from benchmarks.agents._common import AgentProfile

# Port assignments for local benchmark runs
BASE_PORT = 8101


@dataclass(frozen=True)
class AgentSpec:
    agent_id: str
    module: str
    port: int
    profile: AgentProfile


def _profile(
    agent_id: str,
    display_name: str,
    framework: str,
    port: int,
    hallucination_bias: float,
    tool_miss_rate: float,
    latency_base_ms: int,
    latency_jitter_ms: int,
    style_prefix: str,
) -> AgentProfile:
    return AgentProfile(
        agent_id=agent_id,
        display_name=display_name,
        framework=framework,
        description=f"Benchmark wrapper emulating {framework} agent behavior",
        port=port,
        hallucination_bias=hallucination_bias,
        tool_miss_rate=tool_miss_rate,
        latency_base_ms=latency_base_ms,
        latency_jitter_ms=latency_jitter_ms,
        style_prefix=style_prefix,
    )


AGENTS: list[AgentSpec] = [
    AgentSpec(
        "langchain_react",
        "benchmarks.agents.langchain_react",
        BASE_PORT,
        _profile(
            "langchain_react",
            "LangChain ReAct Agent",
            "LangChain ReAct",
            BASE_PORT,
            0.10,
            0.08,
            140,
            80,
            "Thought: I should search the docs. Action: search_knowledge. Observation: ",
        ),
    ),
    AgentSpec(
        "crewai_demo",
        "benchmarks.agents.crewai_demo",
        BASE_PORT + 1,
        _profile(
            "crewai_demo",
            "CrewAI Demo Crew",
            "CrewAI",
            BASE_PORT + 1,
            0.18,
            0.12,
            220,
            120,
            "Researcher → Writer: ",
        ),
    ),
    AgentSpec(
        "openai_assistants",
        "benchmarks.agents.openai_assistants",
        BASE_PORT + 2,
        _profile(
            "openai_assistants",
            "OpenAI Assistants API",
            "OpenAI Assistants",
            BASE_PORT + 2,
            0.07,
            0.05,
            280,
            150,
            "Assistant (thread run): ",
        ),
    ),
    AgentSpec(
        "autogen",
        "benchmarks.agents.autogen_agent",
        BASE_PORT + 3,
        _profile(
            "autogen",
            "AutoGen Multi-Agent",
            "AutoGen",
            BASE_PORT + 3,
            0.22,
            0.15,
            190,
            100,
            "UserProxy → Assistant: ",
        ),
    ),
    AgentSpec(
        "mcp_server",
        "benchmarks.agents.mcp_server",
        BASE_PORT + 4,
        _profile(
            "mcp_server",
            "Basic MCP Server",
            "MCP",
            BASE_PORT + 4,
            0.05,
            0.03,
            110,
            60,
            "MCP tool result: ",
        ),
    ),
]

AGENT_BY_ID = {a.agent_id: a for a in AGENTS}


def get_app(agent_id: str):
    spec = AGENT_BY_ID[agent_id]
    return create_benchmark_app(spec.profile)


def load_agent_app(agent_id: str):
    """Import agent module (sets `app` on module) and return FastAPI instance."""
    spec = AGENT_BY_ID[agent_id]
    mod = importlib.import_module(spec.module)
    return mod.app
