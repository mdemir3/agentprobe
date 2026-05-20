---
name: Bug report
about: Report something that is broken in AgentProbe
title: "[Bug]: "
labels: bug
assignees: ''
---

## Description

A clear description of what went wrong.

## Steps to reproduce

1.
2.
3.

## Expected behavior

What you expected to happen.

## Actual behavior

What happened instead (error messages, logs, screenshots).

## Environment

- **AgentProbe version:** (e.g. 0.1.0, commit SHA)
- **Python version:** (e.g. 3.12)
- **OS:**
- **How you run it:** CLI / FastAPI API / Docker Compose / pytest
- **Planner backend:** MCP bridge / Ollama / Anthropic / OpenAI / rule-based
- **Target agent:** REST API / MCP / example agent (which one?)

## Configuration (redact secrets)

Relevant `.env` flags only — do **not** paste API keys:

```
AGENTPROBE_USE_OLLAMA=
AGENTPROBE_USE_MCP_BRIDGE=
AGENTPROBE_CHROMA_USE_HTTP=
```

## Logs / stack trace

```text
Paste relevant logs here
```

## Additional context

Any other information that might help (n8n workflow, dashboard, ChromaDB, etc.).
