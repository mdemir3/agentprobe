"""Bad Agent — intentionally unreliable target for AgentProbe comparisons.

Run with:
    python examples/bad_agent/app.py
"""

from __future__ import annotations

import random

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="Bad Agent",
    description="An intentionally inaccurate agent for robustness testing",
    version="0.1.0",
)

TOOLS = [
    {
        "name": "get_order_status",
        "description": "Supposed to check order status by ID",
        "parameters": {"order_id": {"type": "string"}},
        "required": ["order_id"],
    },
    {
        "name": "search_knowledge",
        "description": "Supposed to look up policy info",
        "parameters": {"query": {"type": "string"}},
        "required": ["query"],
    },
]


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    response: str
    tool_calls: list[dict] = []
    usage: dict = {}


@app.get("/health")
async def health():
    return {"status": "healthy", "agent": "bad_agent", "version": "0.1.0"}


@app.get("/tools")
async def list_tools():
    return {"tools": TOOLS}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    # Intentionally incorrect behavior:
    # - returns contradictory policy data
    # - occasionally calls wrong tools
    wrong_tool = random.choice(["get_order_status", "search_knowledge"])
    hallucinated = (
        "Refunds are allowed for 365 days, free shipping starts at $500, "
        "and all orders arrive in 30 minutes."
    )
    return ChatResponse(
        response=hallucinated,
        tool_calls=[{"name": wrong_tool, "arguments": {"guess": request.message}, "result": "unknown"}],
        usage={"input_tokens": len(request.message.split()) * 2, "output_tokens": 30},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
