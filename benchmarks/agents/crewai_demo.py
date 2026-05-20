"""CrewAI demo-style benchmark wrapper."""

from benchmarks.agents.registry import get_app

app = get_app("crewai_demo")

if __name__ == "__main__":
    import uvicorn

    from benchmarks.agents.registry import AGENT_BY_ID

    spec = AGENT_BY_ID["crewai_demo"]
    uvicorn.run(app, host="127.0.0.1", port=spec.port, log_level="warning")
