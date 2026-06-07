# 🔍 AgentProbe

[![CI](https://github.com/mdemir3/agentprobe/actions/workflows/ci.yml/badge.svg)](https://github.com/mdemir3/agentprobe/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**The first open-source AI agent that tests other AI agents.**

> Selenium was for testing web apps. AgentProbe is for testing AI agents.

---

## What is AgentProbe?

AgentProbe is an autonomous QA platform that **discovers**, **probes**, and **evaluates** any LLM-powered agent. It connects to your AI agent via MCP or REST API, automatically generates test cases (happy paths, edge cases, adversarial prompts, multi-step tool chains), executes them, and produces a quality report with hallucination rates, tool accuracy, safety scores, and cost analysis.

**Every company is shipping AI agents. Nobody has an automated way to test them. Until now.**

## Key Features

- **Auto-Discovery** — Connects to any agent via MCP or REST API, maps all tools and capabilities automatically
- **Intelligent Test Generation** — LLM-powered probe agent creates test cases: happy paths, edge cases, adversarial inputs, multi-step chains
- **RAG-Grounded Evaluation** — Compares agent responses against ground truth documents to detect hallucinations
- **Tool Call Validation** — Verifies correct tool selection, argument accuracy, and call ordering
- **Safety Scanning** — Detects PII leakage, prompt injection vulnerabilities, and unsafe outputs
- **Cost & Latency Tracking** — Per-test-case token usage, cost breakdown, and latency metrics
- **React Dashboard** — Live test execution view, hallucination heatmaps, quality scorecards
- **CI/CD Integration** — GitHub Actions and GitLab CI plugins for automated quality gates
- **n8n Workflows** — Trigger probe runs from n8n with Slack alerts on failures

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/mdemir3/agentprobe.git
cd agentprobe
cp .env.example .env
# Edit .env with your API keys
```

### 2. Start with Docker

```bash
docker compose up
```

### 3. Connect to a target agent (discover its tools)

```bash
# REST API agent
agentprobe connect http://localhost:8001 --type api --name "My Agent"

# MCP agent
agentprobe connect http://localhost:9000/mcp --type mcp
```

### 4. Probe it end-to-end (plan → run → evaluate → report)

The `probe` command generates a test plan, executes it, and prints a quality
report in one step:

```bash
agentprobe probe http://localhost:8001 --type api --tests 20 -o report.json
```

> **Granular flow & dashboard:** the separate *discover → plan → run → evaluate*
> steps (and run history) are exposed through the REST API
> (`POST /targets`, `POST /plans`, `POST /runs`, `GET /reports/{id}`) and the
> React dashboard, both started by `docker compose up`. The CLI ships the
> `connect`, `probe`, and `version` commands.

### Day one: probe local Ollama (zero API cost)

```bash
# Terminal 1 — pull & run the model
ollama run llama3.1

# Terminal 2 — full probe + quality report (20 tests)
pip install -e ".[dev]"
agentprobe probe http://localhost:11434 --type rest --tests 50 --runs 3 --model llama3.1
```

Uses Ollama for test-plan generation and (when configured) claim judging. No cloud API keys required.

`--runs 3` executes **each test 3 times** with seeds `seed`, `seed+1`, `seed+2`. The report shows **mean ± std** and a **95% confidence_interval** in JSON (`-o report.json`) — not a single point estimate.

### Try with the included dummy agent

```bash
# Terminal 1: Start the dummy agent
python examples/dummy_tool_agent/app.py

# Terminal 2: Probe it
agentprobe probe http://localhost:8001 --type api --tests 20
```

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    AgentProbe                         │
│                                                      │
│  ┌─────────────┐    ┌──────────────────────────────┐ │
│  │   Probe     │    │      Target Connector        │ │
│  │   Agent     │───>│  (MCP / REST API / Ollama)   │─┼──> Target Agent
│  │ (LLM-based) │    └──────────────────────────────┘ │
│  └──────┬──────┘                                     │
│         │ test cases                                 │
│  ┌──────▼──────┐    ┌──────────────────────────────┐ │
│  │  Execution  │    │      RAG Eval Engine          │ │
│  │   Engine    │───>│  (LLM judge + custom scorers) │ │
│  │  (async)    │    └──────────┬───────────────────┘ │
│  └─────────────┘               │                     │
│                       ┌────────▼────────┐            │
│                       │ Quality Report  │            │
│                       │  + Dashboard    │            │
│                       └────────┬────────┘            │
│                                │                     │
│  ┌─────────────┐    ┌─────────▼────────────────────┐ │
│  │   n8n       │    │     CI/CD Plugin             │ │
│  │ Workflows   │    │  (GitHub Actions / GitLab)   │ │
│  └─────────────┘    └──────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Probe orchestration | Python `asyncio` + `httpx` |
| LLM Providers | Anthropic Claude, OpenAI, Ollama (local) |
| Target Discovery | MCP, REST API, Ollama |
| Vector Database | ChromaDB |
| Evaluation | Custom RAG-grounded scorers + LLM judge |
| Backend API | FastAPI |
| Frontend | React + Tailwind + Recharts |
| Storage | In-memory store (PostgreSQL planned) |
| Orchestration | n8n |
| CI/CD | GitHub Actions, GitLab CI |
| Containerization | Docker Compose |

## Integration tests (full flow)

With **`AGENTPROBE_USE_MCP_BRIDGE=true`**, planner generation is delegated to an MCP tool bridge (no provider API key in AgentProbe). The bridge should expose a `tools/call` tool (default name: `generate_test_plan`) and return JSON test cases as text content.  

If MCP bridge is not enabled, **`AGENTPROBE_USE_OLLAMA=true`** (or `OLLAMA_MODEL=...`) uses local **Ollama**. Otherwise, if **`ANTHROPIC_API_KEY`** (or **`OPENAI_API_KEY`**) is set, it uses that provider to generate up to **50** diverse cases by default in `tests/test_full_flow.py` — richer prompts such as empty order IDs, adversarial instructions, and multi-step tool chains. Provider settings are read from the environment: **`tests/conftest.py` loads a project-root `.env`** (if present). Without MCP bridge, Ollama, or API keys, the same tests use the **rule-based fallback** (~10 template cases) so CI stays fast and free.

```bash
pytest tests/test_full_flow.py -v
```

**How to tell which path ran:** rule-based runs stay ~10 probe tests and finish in a few seconds; LLM planning usually yields dozens of cases and a longer run, and you will see network time when generating the plan.

Optional: `AGENTPROBE_TEST_PLAN_MAX_CASES=30` overrides the case count.

### MCP bridge env vars

- `AGENTPROBE_USE_MCP_BRIDGE=true`
- `AGENTPROBE_MCP_BRIDGE_URL=http://127.0.0.1:9000`
- `AGENTPROBE_MCP_BRIDGE_TOOL=generate_test_plan`
- `AGENTPROBE_MCP_BRIDGE_AUTH_TOKEN=` (optional bearer token)

## Documentation

- [Quick Start Guide](docs/quickstart.md)
- [Testing LangChain Agents](docs/testing-langchain.md)
- [Testing CrewAI Crews](docs/testing-crewai.md)
- [Testing n8n AI Workflows](docs/testing-n8n.md)
- [Writing Custom Eval Scorers](docs/custom-scorers.md)
- [CI/CD Integration](docs/ci-cd-integration.md)

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.

---

**Built by [Hikmet Demir](https://linkedin.com/in/hikmetdemir)** — 7 years of test automation experience, now applied to the AI agent era.
