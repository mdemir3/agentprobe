"""Core data models for AgentProbe."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ─── Enums ───────────────────────────────────────────────────────────────────


class TestCategory(str, Enum):
    HAPPY_PATH = "happy_path"
    EDGE_CASE = "edge_case"
    ADVERSARIAL = "adversarial"
    MULTI_STEP = "multi_step"
    SAFETY = "safety"
    TOOL_RELIABILITY = "tool_reliability"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TestStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class ConnectorType(str, Enum):
    MCP = "mcp"
    REST_API = "rest_api"
    LANGCHAIN = "langchain"


# ─── Target Agent Models ─────────────────────────────────────────────────────


class ToolSchema(BaseModel):
    """A tool/capability discovered on a target agent."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    required_params: list[str] = Field(default_factory=list)


class ResourceSchema(BaseModel):
    """A resource discovered on an MCP target."""

    uri: str
    name: str
    description: str = ""
    mime_type: str = ""


class TargetProfile(BaseModel):
    """Complete profile of a target agent's capabilities."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    url: str
    connector_type: ConnectorType
    description: str = ""
    tools: list[ToolSchema] = Field(default_factory=list)
    resources: list[ResourceSchema] = Field(default_factory=list)
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def tool_names(self) -> list[str]:
        return [t.name for t in self.tools]

    @property
    def capability_summary(self) -> str:
        lines = [f"Target: {self.name} ({self.connector_type.value})"]
        lines.append(f"URL: {self.url}")
        lines.append(f"Tools ({len(self.tools)}):")
        for tool in self.tools:
            params = ", ".join(tool.required_params) if tool.required_params else "none"
            lines.append(f"  - {tool.name}: {tool.description} (required: {params})")
        if self.resources:
            lines.append(f"Resources ({len(self.resources)}):")
            for res in self.resources:
                lines.append(f"  - {res.name}: {res.description}")
        return "\n".join(lines)


# ─── Test Case Models ────────────────────────────────────────────────────────


class TestCase(BaseModel):
    """A single test case to run against a target agent."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str = ""
    category: TestCategory
    description: str
    input_prompt: str
    expected_behavior: str
    ground_truth: str | None = None
    tools_expected: list[str] = Field(default_factory=list)
    tool_args_expected: dict[str, Any] | None = None
    risk_level: RiskLevel = RiskLevel.MEDIUM
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TestPlan(BaseModel):
    """A collection of test cases for a target agent."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    target_id: str
    name: str
    description: str = ""
    test_cases: list[TestCase] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ground_truth_docs: list[str] = Field(default_factory=list)

    @property
    def total_cases(self) -> int:
        return len(self.test_cases)

    @property
    def by_category(self) -> dict[TestCategory, list[TestCase]]:
        result: dict[TestCategory, list[TestCase]] = {}
        for tc in self.test_cases:
            result.setdefault(tc.category, []).append(tc)
        return result


# ─── Test Result Models ──────────────────────────────────────────────────────


class ToolCallRecord(BaseModel):
    """Record of a single tool call made by the target agent."""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    error: str | None = None
    latency_ms: float = 0.0


class TestResult(BaseModel):
    """Result of executing a single test case."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    test_case_id: str
    run_id: str
    status: TestStatus = TestStatus.PENDING
    response_text: str = ""
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    error_message: str | None = None
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0


class TestRun(BaseModel):
    """A complete execution of a test plan."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str
    target_id: str
    results: list[TestResult] = Field(default_factory=list)
    status: TestStatus = TestStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_cost_usd: float = 0.0
    total_tokens: int = 0

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.PASSED)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.FAILED)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.ERROR)

    @property
    def pass_rate(self) -> float:
        total = len(self.results)
        return self.passed / total if total > 0 else 0.0


# ─── Evaluation Models ───────────────────────────────────────────────────────


class EvalScore(BaseModel):
    """Score from a single evaluation metric."""

    metric_name: str
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class TestCaseEval(BaseModel):
    """Evaluation results for a single test case."""

    test_case_id: str
    test_result_id: str
    scores: list[EvalScore] = Field(default_factory=list)
    overall_pass: bool = False
    overall_score: float = 0.0

    @property
    def score_by_metric(self) -> dict[str, float]:
        return {s.metric_name: s.score for s in self.scores}


class QualityReport(BaseModel):
    """Complete quality report for a test run."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    target_id: str
    target_name: str = ""
    overall_score: float = 0.0
    hallucination_rate: float = 0.0
    tool_accuracy: float = 0.0
    safety_pass_rate: float = 0.0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    error_tests: int = 0
    scores_by_category: dict[str, float] = Field(default_factory=dict)
    failures_by_category: dict[str, int] = Field(default_factory=dict)
    worst_performing_areas: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    test_case_evals: list[TestCaseEval] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def pass_rate(self) -> float:
        return self.passed_tests / self.total_tests if self.total_tests > 0 else 0.0

    @property
    def grade(self) -> str:
        if self.overall_score >= 0.9:
            return "A"
        if self.overall_score >= 0.8:
            return "B"
        if self.overall_score >= 0.7:
            return "C"
        if self.overall_score >= 0.6:
            return "D"
        return "F"
