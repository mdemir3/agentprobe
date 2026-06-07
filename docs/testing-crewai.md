# Testing CrewAI Crews

A CrewAI crew is tested the same way as any other agent: expose it over the
`/tools` + `/chat` REST contract and point `agentprobe` at it. See
[Testing LangChain Agents](testing-langchain.md) for the full contract details.

## Wrap your crew

```python
from fastapi import FastAPI
from pydantic import BaseModel
# from your project:
from my_crew import build_crew  # returns a CrewAI Crew

app = FastAPI()
crew = build_crew()

class ChatRequest(BaseModel):
    message: str

@app.get("/tools")
def tools():
    # Surface the tools your agents are allowed to call
    return [{"name": t.name, "description": t.description, "parameters": {}}
            for agent in crew.agents for t in agent.tools]

@app.post("/chat")
def chat(req: ChatRequest):
    result = crew.kickoff(inputs={"query": req.message})
    return {"response": str(result), "tool_calls": [], "usage": {}}
```

Run it and probe:

```bash
uvicorn app:app --port 8102
agentprobe probe http://localhost:8102 --type api --tests 30 -o report.json
```

## Notes for crews

- **Multi-step workflows** map naturally to AgentProbe's `multi_step` test
  category — the planner generates prompts that require chaining tools/agents.
- If your crew streams or runs long, raise the timeout in front of `/chat`;
  AgentProbe records per-test latency and reports a p95.
- Populate `tool_calls` in the response if you want the **tool accuracy** metric
  to reflect which tools the crew actually used.

## Reference shim

`benchmarks/agents/crewai_demo.py` is a deterministic CrewAI-profile stand-in
that implements the contract and is used in the
[benchmark matrix](../benchmarks/README.md).
