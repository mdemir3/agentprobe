"""Test runner — Executes test cases against target agents and captures results."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from agentprobe.connectors.api_connector import APIConnector
from agentprobe.connectors.base import BaseConnector
from agentprobe.connectors.mcp_connector import MCPConnector
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


async def execute_test_run(
    plan: TestPlan,
    target: TargetProfile,
    max_concurrent: int = 5,
) -> TestRun:
    """Execute all test cases in a plan against the target agent.

    Args:
        plan: The test plan containing test cases to execute
        target: The target agent profile
        max_concurrent: Maximum number of concurrent test executions

    Returns:
        TestRun with all results populated
    """
    run = TestRun(
        plan_id=plan.id,
        target_id=target.id,
        status=TestStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )

    # Create connector based on target type
    connector = _create_connector(target)

    try:
        await connector.connect()

        # Execute tests with concurrency limit
        semaphore = asyncio.Semaphore(max_concurrent)
        tasks = [
            _execute_single_test(connector, test_case, run.id, semaphore)
            for test_case in plan.test_cases
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
    run.completed_at = datetime.now(timezone.utc)
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
) -> TestResult:
    """Execute a single test case and return the result."""
    async with semaphore:
        result = TestResult(
            test_case_id=test_case.id,
            run_id=run_id,
            started_at=datetime.now(timezone.utc),
        )

        try:
            response = await connector.invoke(test_case.input_prompt)

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

        result.completed_at = datetime.now(timezone.utc)
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
    else:
        return APIConnector(
            url=target.url,
            name=target.name,
            auth_token=target.metadata.get("auth_token", ""),
            chat_endpoint=target.metadata.get("chat_endpoint", "/chat"),
            tools_endpoint=target.metadata.get("tools_endpoint", "/tools"),
        )
