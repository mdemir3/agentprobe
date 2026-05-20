"""Shared FastAPI harness for benchmark agent wrappers.

Each wrapper emulates the response patterns of a public agent stack
(LangChain ReAct, CrewAI, OpenAI Assistants, AutoGen, MCP) while exposing
the REST contract AgentProbe expects: /health, /tools, /chat.
"""

from __future__ import annotations

import hashlib
import os
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel


@dataclass(frozen=True)
class AgentProfile:
    """Behavioral profile for a benchmark agent wrapper."""

    agent_id: str
    display_name: str
    framework: str
    description: str
    port: int
    hallucination_bias: float  # probability of injecting a wrong fact
    tool_miss_rate: float  # probability of calling the wrong tool
    latency_base_ms: int
    latency_jitter_ms: int
    style_prefix: str  # prepended to responses (framework flavor)


class ChatRequest(BaseModel):
    message: str
    session_id: str = "benchmark"


# Wrong facts per corpus — used to simulate hallucinations detectable vs ground truth
CORPUS_WRONG_FACTS: dict[str, list[str]] = {
    "technical_docs": [
        "The platform guarantees 99.99% uptime with zero maintenance windows.",
        "All API payloads are encrypted with 512-bit quantum-resistant keys by default.",
        "Rate limits are unlimited on the free tier for enterprise endpoints.",
    ],
    "policy_legal": [
        "Customers receive an unconditional 120-day refund on all purchases.",
        "Disputes must be resolved exclusively through binding arbitration in Singapore.",
        "Personal data may be sold to third-party advertisers without notice.",
    ],
    "product_faq": [
        "We run buy-one-get-one-free promotions every Tuesday.",
        "Every product includes a lifetime warranty regardless of category.",
        "Loyalty members earn 25% cash back on all purchases automatically.",
    ],
}

STANDARD_TOOLS = [
    {
        "name": "search_knowledge",
        "description": "Search ingested documentation for factual answers",
        "parameters": {"query": {"type": "string"}},
        "required": ["query"],
    },
    {
        "name": "lookup_policy",
        "description": "Look up a specific policy section by topic",
        "parameters": {"topic": {"type": "string"}},
        "required": ["topic"],
    },
    {
        "name": "get_entity",
        "description": "Retrieve a named entity record (SKU, clause ID, API resource)",
        "parameters": {"entity_id": {"type": "string"}},
        "required": ["entity_id"],
    },
]


def _load_corpus_text(corpus_id: str) -> str:
    root = Path(os.environ.get("BENCHMARK_CORPUS_ROOT", ""))
    if not root.is_dir():
        return ""
    parts: list[str] = []
    for path in sorted(root.rglob("*.md")):
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n\n".join(parts)


def _search_corpus(corpus_text: str, query: str, max_chars: int = 600) -> str:
    if not corpus_text:
        return "No documentation loaded for this benchmark run."
    query_lower = query.lower()
    tokens = [t for t in re.split(r"\W+", query_lower) if len(t) > 3]
    paragraphs = [p.strip() for p in corpus_text.split("\n\n") if p.strip()]
    scored: list[tuple[int, str]] = []
    for para in paragraphs:
        lower = para.lower()
        score = sum(1 for t in tokens if t in lower)
        if score > 0:
            scored.append((score, para))
    if not scored:
        return paragraphs[0][:max_chars] if paragraphs else "No matching passage found."
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1][:max_chars]


def _stable_rng(*parts: str) -> random.Random:
    seed = int(hashlib.sha256(":".join(parts).encode()).hexdigest()[:8], 16)
    return random.Random(seed)


def _pick_tool(message: str, profile: AgentProfile, rng: random.Random) -> str:
    lower = message.lower()
    if "policy" in lower or "legal" in lower or "refund" in lower or "privacy" in lower:
        preferred = "lookup_policy"
    elif re.search(r"\b(API|SKU|ORD|endpoint|resource)\b", message, re.I):
        preferred = "get_entity"
    else:
        preferred = "search_knowledge"

    if rng.random() < profile.tool_miss_rate:
        alternatives = [t["name"] for t in STANDARD_TOOLS if t["name"] != preferred]
        return rng.choice(alternatives)
    return preferred


def create_benchmark_app(profile: AgentProfile) -> FastAPI:
    """Build a FastAPI app for one benchmark agent profile."""

    app = FastAPI(
        title=profile.display_name,
        description=profile.description,
        version="0.1.0",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "agent": profile.agent_id, "framework": profile.framework}

    @app.get("/tools")
    def tools() -> list[dict[str, Any]]:
        return STANDARD_TOOLS

    @app.post("/chat")
    def chat(req: ChatRequest) -> dict[str, Any]:
        corpus_id = os.environ.get("BENCHMARK_CORPUS", "technical_docs")
        corpus_text = _load_corpus_text(corpus_id)
        rng = _stable_rng(profile.agent_id, corpus_id, req.message, req.session_id)

        # Simulated framework latency
        delay_ms = profile.latency_base_ms + rng.randint(0, profile.latency_jitter_ms)
        time.sleep(delay_ms / 1000.0)

        tool_name = _pick_tool(req.message, profile, rng)
        passage = _search_corpus(corpus_text, req.message)

        wrong_facts = CORPUS_WRONG_FACTS.get(corpus_id, [])
        injected = ""
        if wrong_facts and rng.random() < profile.hallucination_bias:
            injected = " " + rng.choice(wrong_facts)

        if tool_name == "lookup_policy":
            args = {"topic": req.message[:80]}
            tool_result = _search_corpus(corpus_text, req.message)
        elif tool_name == "get_entity":
            entity_id = re.search(r"\b[A-Z]{2,}-\d+\b", req.message)
            args = {"entity_id": entity_id.group(0) if entity_id else "ENTITY-001"}
            tool_result = f"Record {args['entity_id']}: status=active"
        else:
            args = {"query": req.message[:120]}
            tool_result = passage

        response_text = (
            f"{profile.style_prefix}{tool_result}{injected}"
        ).strip()

        return {
            "response": response_text,
            "tool_calls": [
                {
                    "name": tool_name,
                    "arguments": args,
                    "result": tool_result[:300],
                }
            ],
            "usage": {"input_tokens": len(req.message.split()), "output_tokens": len(response_text.split())},
            "metadata": {
                "framework": profile.framework,
                "agent_id": profile.agent_id,
                "corpus": corpus_id,
            },
        }

    return app
