"""Basic MCP server-style benchmark wrapper (REST shim for AgentProbe)."""

from benchmarks.agents.registry import get_app

app = get_app("mcp_server")

if __name__ == "__main__":
    import uvicorn

    from benchmarks.agents.registry import AGENT_BY_ID

    spec = AGENT_BY_ID["mcp_server"]
    uvicorn.run(app, host="127.0.0.1", port=spec.port, log_level="warning")
