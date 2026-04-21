"""Load project env files during pytest; report which planner backend tests will use."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_env_files() -> None:
    # override=False: real shell exports win over file values
    for name in (".env", ".env.local"):
        load_dotenv(_PROJECT_ROOT / name, override=False)


_load_env_files()


def pytest_report_header(config) -> str:
    """Tell users whether LLM keys are visible to tests (must be in `.env`, not only `.env.example`)."""
    env_files = [p.name for p in (_PROJECT_ROOT / ".env", _PROJECT_ROOT / ".env.local") if p.is_file()]
    ak = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    ok = os.environ.get("OPENAI_API_KEY", "").strip()
    use_mcp_bridge = os.environ.get("AGENTPROBE_USE_MCP_BRIDGE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    mcp_bridge_url = os.environ.get("AGENTPROBE_MCP_BRIDGE_URL", "").strip()
    mcp_bridge_tool = os.environ.get("AGENTPROBE_MCP_BRIDGE_TOOL", "").strip() or "generate_test_plan"
    use_ollama = os.environ.get("AGENTPROBE_USE_OLLAMA", "").strip().lower() in {"1", "true", "yes", "on"}
    ollama_model = os.environ.get("OLLAMA_MODEL", "").strip()
    ollama_base = os.environ.get("OLLAMA_BASE_URL", "").strip() or "http://127.0.0.1:11434"

    if use_mcp_bridge or mcp_bridge_url:
        url = mcp_bridge_url or "http://127.0.0.1:9000"
        backend = f"MCP bridge ({mcp_bridge_tool} @ {url})"
    elif use_ollama or ollama_model:
        model = ollama_model or "llama3.2:latest"
        backend = f"Ollama local ({model} @ {ollama_base})"
    elif ak:
        backend = (
            "Anthropic key loaded — calls Claude when the API accepts; "
            "otherwise rule-based fallback (e.g. low credits — check WARNING logs)"
        )
    elif ok:
        backend = "OpenAI key loaded"
    else:
        backend = "rule-based only (no Ollama/Anthropic/OpenAI config)"

    parts = [f"agentprobe planner: {backend}"]
    if env_files:
        parts.append(f"env loaded: {', '.join(env_files)}")
    elif ak or ok or use_ollama or ollama_model or use_mcp_bridge or mcp_bridge_url:
        parts.append("provider settings from exported shell env (no project .env file)")
    else:
        parts.append(
            f"no {_PROJECT_ROOT / '.env'} — copy .env.example to .env and set Ollama or LLM provider vars"
        )

    return " | ".join(parts)
