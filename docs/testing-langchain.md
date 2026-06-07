# Testing LangChain Agents

AgentProbe treats any agent as a black box behind an HTTP contract, so testing a
LangChain agent just means exposing it over a small REST endpoint and pointing
`agentprobe` at it.

## The REST contract

The `api` connector expects the target to expose:

| Method | Path      | Purpose                                              |
|--------|-----------|------------------------------------------------------|
| `GET`  | `/tools`  | List the agent's tools (name, description, params)   |
| `POST` | `/chat`   | Accept `{ "message": "..." }`, return the response   |

The `/chat` response should look like:

```json
{
  "response": "The order shipped on Tuesday.",
  "tool_calls": [{ "name": "get_order_status", "arguments": { "order_id": "ORD-123" } }],
  "usage": { "input_tokens": 42, "output_tokens": 18 }
}
```

`tool_calls` is what powers the **tool accuracy** metric, and `usage` powers cost
and token tracking.

## Wrap your LangChain agent

A minimal FastAPI shim around a LangChain `AgentExecutor`:

```python
from fastapi import FastAPI
from pydantic import BaseModel
# from your project:
from my_agent import build_agent  # returns a LangChain AgentExecutor

app = FastAPI()
agent = build_agent()

class ChatRequest(BaseModel):
    message: str

@app.get("/tools")
def tools():
    return [
        {"name": t.name, "description": t.description, "parameters": {}}
        for t in agent.tools
    ]

@app.post("/chat")
def chat(req: ChatRequest):
    result = agent.invoke({"input": req.message})
    return {
        "response": result["output"],
        "tool_calls": [
            {"name": step[0].tool, "arguments": step[0].tool_input}
            for step in result.get("intermediate_steps", [])
        ],
        "usage": {},
    }
```

Run it (e.g. `uvicorn app:app --port 8100`) and probe it:

```bash
agentprobe connect http://localhost:8100 --type api --name "LangChain ReAct"
agentprobe probe   http://localhost:8100 --type api --tests 30 -o report.json
```

## Grounded hallucination detection

To score factual accuracy, ingest your agent's source-of-truth documents so
AgentProbe can verify claims against them. See the
[hallucination integration guide](../src/INTEGRATION_GUIDE.md).

## Reference shim

`benchmarks/agents/langchain_react.py` is a deterministic stand-in that
implements exactly this contract — useful as a template and for the
[benchmark suite](../benchmarks/README.md).
