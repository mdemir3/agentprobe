"""OpenAI Assistants API-style benchmark wrapper."""

from benchmarks.agents.registry import get_app

app = get_app("openai_assistants")

if __name__ == "__main__":
    import uvicorn

    from benchmarks.agents.registry import AGENT_BY_ID

    spec = AGENT_BY_ID["openai_assistants"]
    uvicorn.run(app, host="127.0.0.1", port=spec.port, log_level="warning")
