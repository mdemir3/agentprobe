# Contributing to AgentProbe

Thank you for helping improve AgentProbe — the open-source platform that discovers, probes, and evaluates LLM-powered agents.

## Dev setup

AgentProbe targets **Python 3.12** with an editable install, optional Docker for the full stack, and a separate Node.js toolchain for the dashboard.

### Prerequisites

- Python **3.12+**
- [uv](https://github.com/astral-sh/uv) or `pip` / `venv`
- Node.js **18+** (dashboard only)
- Docker & Docker Compose (optional, for Postgres, ChromaDB, and containerized services)

### Python backend (FastAPI, LangGraph, ChromaDB, DeepEval)

```bash
git clone https://github.com/mdemir3/agentprobe.git
cd agentprobe

# Recommended: Python 3.12 virtual environment
uv venv --python 3.12
source .venv/bin/activate   # Windows: .venv\Scripts\activate

uv pip install -e ".[dev]"
# or: pip install -e ".[dev]"

cp .env.example .env
# Edit .env with API keys, Ollama, or MCP bridge settings as needed
```

### Run services locally

```bash
# Terminal 1 — AgentProbe API (FastAPI + uvicorn)
uvicorn agentprobe.api.main:app --port 8000 --reload

# Terminal 2 — Example target agent (optional)
python examples/dummy_tool_agent/app.py

# Terminal 3 — MCP planner bridge (optional, when AGENTPROBE_USE_MCP_BRIDGE=true)
python examples/mcp_planner_bridge/app.py

# Terminal 4 — MCP server exposing AgentProbe tools (optional)
python mcp_server/server.py
```

### Docker (full stack)

```bash
docker compose up
```

This starts the **FastAPI** core, **PostgreSQL**, **ChromaDB**, and the **React/Tailwind** dashboard. Configure variables in `.env` before starting.

### Dashboard (React + Tailwind + Vite)

```bash
cd dashboard
npm install
npm run dev
```

Set `VITE_API_URL` if the API is not at `http://localhost:8000`.

### CLI

After installing the package:

```bash
agentprobe connect http://localhost:8001 --type api --name "My Agent"
```

## Running tests

Integration tests exercise the full probe flow (connect → plan → run → evaluate). Hallucination tests require RAG ingest setup as documented in `src/INTEGRATION_GUIDE.md`.

```bash
# Load .env automatically via tests/conftest.py
pytest tests/ -v

# Full end-to-end flow
pytest tests/test_full_flow.py -v -s

# RAG / hallucination detection
pytest tests/test_hallucination.py -v -s
```

**Planner backends** (first match wins): MCP bridge → Ollama → Anthropic → OpenAI → rule-based fallback. See `.env.example` and `README.md` for environment variables.

Optional: start the dummy agent on port `8001` before running `test_full_flow.py`.

## Code style (ruff + black)

- **ruff** — linting and import sorting (`pyproject.toml` → `[tool.ruff]`)
- **black** — line length **100** to match ruff

```bash
# Format
black src tests examples mcp_server
ruff format src tests examples mcp_server   # if using ruff format

# Lint
ruff check src tests examples mcp_server
ruff check --fix src tests examples mcp_server
```

Match existing patterns in `src/agentprobe/`: type hints, `async` where the API is async, Pydantic models in `probe/models.py`, and minimal scope per change.

## PR checklist

Before opening a pull request:

- [ ] Branch is up to date with `main`
- [ ] Changes are focused; unrelated refactors are split out
- [ ] `ruff check` passes on touched Python paths
- [ ] Code is formatted with **black** (line length 100)
- [ ] `pytest tests/` passes (or document why skipped)
- [ ] New behavior has tests when applicable
- [ ] `.env.example` updated if new configuration is introduced
- [ ] `CHANGELOG.md` updated under **Unreleased** or the target version
- [ ] No secrets, API keys, or `.env` files committed
- [ ] Dashboard changes build with `npm run build` in `dashboard/`

## Commit message convention (conventional commits)

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <short description>

[optional body]

[optional footer(s)]
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`

**Examples:**

```
feat(probe): add Ollama planner backend
fix(api): populate tool_name in connector tool_calls
docs: update MCP bridge env vars in README
test: show quality report in test_full_flow with capsys
```

Breaking changes: add `!` after the type/scope or include `BREAKING CHANGE:` in the footer.

## Questions?

Open a [GitHub issue](https://github.com/mdemir3/agentprobe/issues) for bugs or feature ideas. For security concerns, see [SECURITY.md](SECURITY.md).
