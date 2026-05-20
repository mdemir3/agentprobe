"""AgentProbe MCP Server — Exposes AgentProbe as an MCP-compatible tool.

This lets n8n, Claude Desktop, or any MCP client trigger AgentProbe
operations (connect, plan, run, evaluate) as tool calls.

Run with: python -m agentprobe.mcp_server.server
"""

from __future__ import annotations

import json
import os
import asyncio
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="AgentProbe MCP Server", version="0.1.0")

# ─── MCP Protocol Implementation ────────────────────────────────────────────

SERVER_INFO = {
    "name": "agentprobe",
    "version": "0.1.0",
}

TOOLS = [
    {
        "name": "probe_connect",
        "description": "Connect to a target AI agent and discover its tools and capabilities. Returns the target profile with all discovered tools.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL of the target agent (e.g., http://localhost:8001)"},
                "name": {"type": "string", "description": "Friendly name for the target agent"},
                "connector_type": {"type": "string", "enum": ["api", "mcp"], "description": "Connection type: api or mcp"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "probe_generate_plan",
        "description": "Generate a test plan for a target agent. Creates test cases across categories: happy_path, edge_case, adversarial, multi_step, safety, tool_reliability.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_url": {"type": "string", "description": "URL of the target agent to test"},
                "max_cases": {"type": "integer", "description": "Maximum number of test cases to generate (default: 20)"},
            },
            "required": ["target_url"],
        },
    },
    {
        "name": "probe_run_tests",
        "description": "Execute a full test cycle: connect to agent, generate test plan, run all tests, evaluate results, and return the quality report with hallucination rate, tool accuracy, safety score, and recommendations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_url": {"type": "string", "description": "URL of the target agent to test"},
                "target_name": {"type": "string", "description": "Name of the target agent"},
                "max_cases": {"type": "integer", "description": "Number of test cases (default: 15)"},
            },
            "required": ["target_url"],
        },
    },
    {
        "name": "probe_quick_check",
        "description": "Send a single prompt to a target agent and return the raw response with tool calls and latency. Good for spot-checking agent behavior.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_url": {"type": "string", "description": "URL of the target agent"},
                "prompt": {"type": "string", "description": "The prompt to send to the agent"},
            },
            "required": ["target_url", "prompt"],
        },
    },
]


async def handle_probe_connect(args: dict) -> str:
    from agentprobe.connectors.api_connector import APIConnector
    from agentprobe.connectors.mcp_connector import MCPConnector

    url = args["url"]
    name = args.get("name", url)
    conn_type = args.get("connector_type", "api")

    if conn_type == "mcp":
        connector = MCPConnector(url=url, name=name)
    else:
        connector = APIConnector(url=url, name=name)

    async with connector:
        profile = await connector.discover()

    return json.dumps({
        "name": profile.name,
        "url": profile.url,
        "tools_discovered": len(profile.tools),
        "tools": [{"name": t.name, "description": t.description} for t in profile.tools],
        "resources": len(profile.resources),
    }, indent=2)


async def handle_probe_generate_plan(args: dict) -> str:
    from agentprobe.connectors.api_connector import APIConnector
    from agentprobe.probe.planner import generate_test_plan

    url = args["target_url"]
    max_cases = args.get("max_cases", 20)

    async with APIConnector(url=url, name=url) as connector:
        profile = await connector.discover()

    plan = await generate_test_plan(target=profile, max_cases=max_cases)

    categories = {}
    for tc in plan.test_cases:
        cat = tc.category.value
        categories[cat] = categories.get(cat, 0) + 1

    return json.dumps({
        "plan_id": plan.id,
        "total_cases": plan.total_cases,
        "categories": categories,
        "sample_cases": [
            {"category": tc.category.value, "description": tc.description, "prompt": tc.input_prompt[:100]}
            for tc in plan.test_cases[:5]
        ],
    }, indent=2)


async def handle_probe_run_tests(args: dict) -> str:
    from agentprobe.connectors.api_connector import APIConnector
    from agentprobe.probe.planner import generate_test_plan
    from agentprobe.probe.runner import execute_test_run
    from agentprobe.eval.pipeline import evaluate_run

    url = args["target_url"]
    name = args.get("target_name", url)
    max_cases = args.get("max_cases", 15)

    # Step 1: Connect and discover
    async with APIConnector(url=url, name=name) as connector:
        profile = await connector.discover()

    # Step 2: Generate test plan
    plan = await generate_test_plan(target=profile, max_cases=max_cases)

    # Step 3: Run tests
    run = await execute_test_run(plan=plan, target=profile, max_concurrent=5)

    # Step 4: Evaluate
    report = await evaluate_run(run=run, plan=plan, target=profile)

    return json.dumps({
        "target": name,
        "grade": report.grade,
        "overall_score": f"{report.overall_score:.1%}",
        "hallucination_rate": f"{report.hallucination_rate:.1%}",
        "tool_accuracy": f"{report.tool_accuracy:.1%}",
        "safety_pass_rate": f"{report.safety_pass_rate:.1%}",
        "tests": {
            "total": report.total_tests,
            "passed": report.passed_tests,
            "failed": report.failed_tests,
            "errors": report.error_tests,
        },
        "avg_latency_ms": round(report.avg_latency_ms),
        "total_cost_usd": round(report.total_cost_usd, 4),
        "scores_by_category": {k: f"{v:.1%}" for k, v in report.scores_by_category.items()},
        "worst_areas": report.worst_performing_areas,
        "recommendations": report.recommendations,
    }, indent=2)


async def handle_probe_quick_check(args: dict) -> str:
    from agentprobe.connectors.api_connector import APIConnector

    url = args["target_url"]
    prompt = args["prompt"]

    async with APIConnector(url=url, name=url) as connector:
        result = await connector.invoke(prompt)

    return json.dumps({
        "response": result.get("response_text", "")[:500],
        "tool_calls": [
            {"tool": tc.get("name", tc.get("tool_name", "")), "args": tc.get("arguments", {})}
            for tc in result.get("tool_calls", [])
        ],
        "latency_ms": round(result.get("latency_ms", 0)),
        "error": result.get("error"),
    }, indent=2)


TOOL_HANDLERS = {
    "probe_connect": handle_probe_connect,
    "probe_generate_plan": handle_probe_generate_plan,
    "probe_run_tests": handle_probe_run_tests,
    "probe_quick_check": handle_probe_quick_check,
}


# ─── MCP JSON-RPC endpoint ──────────────────────────────────────────────────

@app.post("/")
async def mcp_endpoint(request: Request):
    """Handle MCP JSON-RPC requests."""
    body = await request.json()
    method = body.get("method", "")
    req_id = body.get("id")
    params = body.get("params", {})

    if method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            },
        })

    elif method == "tools/list":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS},
        })

    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
            })

        try:
            result_text = await handler(tool_args)
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": result_text}],
                },
            })
        except Exception as e:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                    "isError": True,
                },
            })

    else:
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        })


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "agentprobe-mcp-server", "tools": len(TOOLS)}


if __name__ == "__main__":
    import uvicorn
    print("Starting AgentProbe MCP Server on port 9100")
    print("Tools: probe_connect, probe_generate_plan, probe_run_tests, probe_quick_check")
    uvicorn.run(app, host="0.0.0.0", port=9100)
