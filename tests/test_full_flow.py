"""Integration tests for the full AgentProbe flow.

Tests: connect to dummy agent → discover tools → generate plan → run tests → evaluate

Planner behavior (see ``generate_test_plan``):

- If ``AGENTPROBE_USE_MCP_BRIDGE`` is true (or ``AGENTPROBE_MCP_BRIDGE_URL`` is set),
  planner generation is delegated to an MCP tool bridge.
- If ``AGENTPROBE_USE_OLLAMA`` is true (or ``OLLAMA_MODEL`` is set), local Ollama
  is used without API keys.
- If ``ANTHROPIC_API_KEY`` is set, Claude generates up to ``max_cases`` diverse prompts
  (edge cases, adversarial, multi-step, etc.).
- Else if ``OPENAI_API_KEY`` is set, OpenAI is used the same way.
- Otherwise a rule-based fallback runs (small set of template cases; no API calls).

Override case count with ``AGENTPROBE_TEST_PLAN_MAX_CASES`` (optional).
"""

from __future__ import annotations

import multiprocessing
import os
import time

import pytest
import uvicorn

from agentprobe.connectors.api_connector import APIConnector
from agentprobe.eval.pipeline import evaluate_run
from agentprobe.probe.planner import generate_test_plan
from agentprobe.probe.runner import execute_test_run

DUMMY_AGENT_URL = "http://127.0.0.1:8001"


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _ollama_enabled() -> bool:
    return _truthy(os.environ.get("AGENTPROBE_USE_OLLAMA")) or bool(os.environ.get("OLLAMA_MODEL"))


def _mcp_bridge_enabled() -> bool:
    return _truthy(os.environ.get("AGENTPROBE_USE_MCP_BRIDGE")) or bool(
        os.environ.get("AGENTPROBE_MCP_BRIDGE_URL")
    )


def _plan_max_cases() -> int:
    """How many cases to ask the planner for in these tests."""
    raw = os.environ.get("AGENTPROBE_TEST_PLAN_MAX_CASES")
    if raw:
        return int(raw)
    if (
        _mcp_bridge_enabled()
        or _ollama_enabled()
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    ):
        return 50
    return 10


def _run_dummy_agent():
    """Run the dummy agent in a subprocess."""
    import sys

    sys.path.insert(0, ".")
    from examples.dummy_tool_agent.app import app

    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="error")


def _wait_until_ready(url: str, timeout: float = 20.0) -> bool:
    """Poll the agent's health endpoint until it responds or times out."""
    import httpx

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(f"{url}/health", timeout=1.0)
            if resp.status_code < 500:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    return False


@pytest.fixture(scope="module")
def dummy_agent():
    """Start the dummy agent server for the test session."""
    proc = multiprocessing.Process(target=_run_dummy_agent, daemon=True)
    proc.start()
    if not _wait_until_ready(DUMMY_AGENT_URL):
        proc.terminate()
        proc.join(timeout=3)
        pytest.fail(f"Dummy agent did not become ready at {DUMMY_AGENT_URL}")
    yield
    proc.terminate()
    proc.join(timeout=3)


@pytest.mark.asyncio
async def test_connect_and_discover(dummy_agent):
    """Test connecting to the dummy agent and discovering its tools."""
    async with APIConnector(url=DUMMY_AGENT_URL, name="Test Agent") as connector:
        profile = await connector.discover()

    assert profile.name == "Test Agent"
    assert len(profile.tools) >= 3

    tool_names = profile.tool_names
    assert "search_knowledge" in tool_names
    assert "get_order_status" in tool_names
    assert "calculate_discount" in tool_names


@pytest.mark.asyncio
async def test_invoke_chat(dummy_agent):
    """Test sending a prompt to the dummy agent."""
    async with APIConnector(url=DUMMY_AGENT_URL, name="Test Agent") as connector:
        result = await connector.invoke("What is the status of order ORD-12345?")

    assert result["response_text"]
    assert result["latency_ms"] > 0
    assert len(result["tool_calls"]) > 0
    assert result["tool_calls"][0]["name"] == "get_order_status"


@pytest.mark.asyncio
async def test_generate_plan(dummy_agent):
    """Test generating a test plan (Claude/OpenAI when API keys are set; else rule-based)."""
    async with APIConnector(url=DUMMY_AGENT_URL, name="Test Agent") as connector:
        profile = await connector.discover()

    plan = await generate_test_plan(
        target=profile,
        name="Test Plan",
        max_cases=_plan_max_cases(),
    )

    assert plan.name == "Test Plan"
    assert plan.total_cases > 0
    assert plan.target_id == profile.id

    # Should have multiple categories
    categories = {tc.category for tc in plan.test_cases}
    assert len(categories) >= 2


@pytest.mark.asyncio
async def test_full_flow(dummy_agent, capsys):
    """Test the complete flow: discover → plan → run → evaluate."""

    # 1. Connect and discover
    async with APIConnector(url=DUMMY_AGENT_URL, name="Test Agent") as connector:
        profile = await connector.discover()

    assert len(profile.tools) >= 3

    # 2. Generate plan
    plan = await generate_test_plan(
        target=profile,
        name="Full Flow Test",
        max_cases=_plan_max_cases(),
    )
    assert plan.total_cases > 0

    # 3. Run tests
    run = await execute_test_run(plan=plan, target=profile, max_concurrent=3)

    assert len(run.results) > 0
    assert run.completed_at is not None
    assert run.passed + run.failed + run.error_count == len(run.results)

    # 4. Evaluate
    report = await evaluate_run(run=run, plan=plan, target=profile)

    assert report.total_tests > 0
    assert 0.0 <= report.overall_score <= 1.0
    assert report.grade in ("A", "B", "C", "D", "F")
    assert len(report.recommendations) > 0

    # Bypass pytest's stdout capture so the report is visible without `pytest -s`
    with capsys.disabled():
        print(f"\n{'='*60}")
        print("AgentProbe Quality Report")
        print(f"{'='*60}")
        print(f"Target: {report.target_name}")
        print(f"Overall Score: {report.overall_score:.1%} (Grade: {report.grade})")
        print(
            f"Tests: {report.passed_tests} passed / "
            f"{report.failed_tests} failed / {report.error_tests} errors"
        )
        print(f"Hallucination Rate: {report.hallucination_rate:.1%}")
        print(f"Tool Accuracy: {report.tool_accuracy:.1%}")
        print(f"Safety Pass Rate: {report.safety_pass_rate:.1%}")
        print(f"Avg Latency: {report.avg_latency_ms:.0f}ms")
        print("\nRecommendations:")
        for rec in report.recommendations:
            print(f"  → {rec}")
        print(f"{'='*60}\n")
