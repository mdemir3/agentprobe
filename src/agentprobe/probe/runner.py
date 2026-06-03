"""Test runner — Executes test cases against target agents and captures results."""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from typing import Any

from agentprobe.connectors.api_connector import APIConnector
from agentprobe.connectors.base import BaseConnector
from agentprobe.connectors.mcp_connector import MCPConnector
from agentprobe.connectors.ollama_connector import OllamaConnector
from agentprobe.probe.models import (
    ConnectorType,
    TargetProfile,
    TestCase,
    TestPlan,
    TestResult,
    TestRun,
    TestStatus,
    ToolCallRecord,
)

DEFAULT_TEMPERATURE = 0.7


def resolve_temperature(runs: int, temperature: float) -> float:
    """Ensure multi-run probes use non-zero temperature for meaningful variance."""
    if runs > 1 and temperature == 0:
        print(
            "Warning: --runs > 1 with temperature=0 will produce identical repetitions. "
            "Setting temperature to 0.7.",
            file=sys.stderr,
        )
        return DEFAULT_TEMPERATURE
    return temperature


async def execute_test_run(
    plan: TestPlan,
    target: TargetProfile,
    max_concurrent: int = 5,
    runs: int = 1,
    seed: int | None = None,
    temperature: float = DEFAULT_TEMPERATURE,
) -> TestRun:
    """Execute all test cases in a plan against the target agent.

    Args:
        plan: The test plan containing test cases to execute
        target: The target agent profile
        max_concurrent: Maximum number of concurrent test executions
        runs: Execute each test case this many times (different seeds per repetition)
        seed: Base random seed; repetition *i* uses ``seed + i`` when set
        temperature: Sampling temperature for targets that support it (e.g. Ollama)

    Returns:
        TestRun with all results populated
    """
    runs = max(1, runs)
    temperature = resolve_temperature(runs, temperature)
    run = TestRun(
        plan_id=plan.id,
        target_id=target.id,
        status=TestStatus.RUNNING,
        started_at=datetime.now(UTC),
    )

    # Create connector based on target type
    connector = _create_connector(target)

    try:
        await connector.connect()

        # Execute tests with concurrency limit
        semaphore = asyncio.Semaphore(max_concurrent)
        tasks = [
            _execute_single_test(
                connector,
                test_case,
                run.id,
                semaphore,
                repetition=rep,
                seed=(seed + rep) if seed is not None else None,
                temperature=temperature,
            )
            for test_case in plan.test_cases
            for rep in range(runs)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                run.results.append(
                    TestResult(
                        test_case_id="unknown",
                        run_id=run.id,
                        status=TestStatus.ERROR,
                        error_message=str(result),
                    )
                )
            else:
                run.results.append(result)

    except ConnectionError as e:
        run.status = TestStatus.ERROR
        run.results.append(
            TestResult(
                test_case_id="connection",
                run_id=run.id,
                status=TestStatus.ERROR,
                error_message=f"Connection failed: {e}",
            )
        )
    finally:
        await connector.disconnect()

    # Compute aggregates
    run.completed_at = datetime.now(UTC)
    run.total_cost_usd = sum(r.cost_usd for r in run.results)
    run.total_tokens = sum(r.total_tokens for r in run.results)

    # Determine overall status
    if run.error_count > 0 and run.passed == 0:
        run.status = TestStatus.ERROR
    elif run.failed > 0:
        run.status = TestStatus.FAILED
    else:
        run.status = TestStatus.PASSED

    return run


async def _execute_single_test(
    connector: BaseConnector,
    test_case: TestCase,
    run_id: str,
    semaphore: asyncio.Semaphore,
    repetition: int = 0,
    seed: int | None = None,
    temperature: float = DEFAULT_TEMPERATURE,
) -> TestResult:
    """Execute a single test case and return the result."""
    async with semaphore:
        result = TestResult(
            test_case_id=test_case.id,
            run_id=run_id,
            repetition=repetition,
            seed=seed,
            started_at=datetime.now(UTC),
        )

        try:
            invoke_kwargs: dict[str, Any] = {"temperature": temperature}
            if seed is not None:
                invoke_kwargs["seed"] = seed
            response = await connector.invoke(test_case.input_prompt, **invoke_kwargs)

            result.response_text = response.get("response_text", "")
            result.latency_ms = response.get("latency_ms", 0.0)
            result.input_tokens = response.get("input_tokens", 0)
            result.output_tokens = response.get("output_tokens", 0)
            result.total_tokens = result.input_tokens + result.output_tokens

            # Parse tool calls
            for tc in response.get("tool_calls", []):
                result.tool_calls.append(
                    ToolCallRecord(
                        tool_name=tc.get("tool_name", tc.get("name", "")),
                        arguments=tc.get("arguments", tc.get("args", {})),
                        result=tc.get("result", ""),
                    )
                )

            # Check for errors from the connector
            if response.get("error"):
                result.status = TestStatus.ERROR
                result.error_message = response["error"]
            else:
                # Basic pass/fail: did the agent call the expected tools?
                result.status = _check_tool_expectations(test_case, result)

        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)

        result.completed_at = datetime.now(UTC)
        return result


def _check_tool_expectations(test_case: TestCase, result: TestResult) -> TestStatus:
    """Basic check: did the agent call the expected tools?"""
    if not test_case.tools_expected:
        # No tool expectations — pass if we got a non-empty response
        return TestStatus.PASSED if result.response_text.strip() else TestStatus.FAILED

    actual_tools = {tc.tool_name for tc in result.tool_calls}
    expected_tools = set(test_case.tools_expected)

    if expected_tools.issubset(actual_tools):
        return TestStatus.PASSED
    else:
        return TestStatus.FAILED


def _create_connector(target: TargetProfile) -> BaseConnector:
    """Create the appropriate connector for a target."""
    if target.connector_type == ConnectorType.MCP:
        return MCPConnector(
            url=target.url,
            name=target.name,
            auth_token=target.metadata.get("auth_token", ""),
        )
    if target.connector_type == ConnectorType.OLLAMA:
        return OllamaConnector(
            url=target.url,
            name=target.name,
            model=target.metadata.get("model", ""),
            temperature=float(target.metadata.get("temperature", DEFAULT_TEMPERATURE)),
        )
    return APIConnector(
        url=target.url,
        name=target.name,
        auth_token=target.metadata.get("auth_token", ""),
        chat_endpoint=target.metadata.get("chat_endpoint", "/chat"),
        tools_endpoint=target.metadata.get("tools_endpoint", "/tools"),
    )
