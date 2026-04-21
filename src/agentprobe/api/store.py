"""In-memory data store for AgentProbe MVP.

Provides simple dict-based storage for targets, plans, runs, and reports.
Will be replaced with PostgreSQL + SQLAlchemy in production.
"""

from __future__ import annotations

from agentprobe.probe.models import (
    QualityReport,
    TargetProfile,
    TestPlan,
    TestRun,
)


class Store:
    """Simple in-memory store. Thread-safe enough for single-process dev use."""

    targets: dict[str, TargetProfile] = {}
    plans: dict[str, TestPlan] = {}
    runs: dict[str, TestRun] = {}
    reports: dict[str, QualityReport] = {}

    @classmethod
    def initialize(cls) -> None:
        cls.targets = {}
        cls.plans = {}
        cls.runs = {}
        cls.reports = {}

    # ── Targets ──────────────────────────────────────────────────────────

    @classmethod
    def save_target(cls, target: TargetProfile) -> TargetProfile:
        cls.targets[target.id] = target
        return target

    @classmethod
    def get_target(cls, target_id: str) -> TargetProfile | None:
        return cls.targets.get(target_id)

    @classmethod
    def list_targets(cls) -> list[TargetProfile]:
        return list(cls.targets.values())

    @classmethod
    def delete_target(cls, target_id: str) -> bool:
        return cls.targets.pop(target_id, None) is not None

    # ── Plans ────────────────────────────────────────────────────────────

    @classmethod
    def save_plan(cls, plan: TestPlan) -> TestPlan:
        cls.plans[plan.id] = plan
        return plan

    @classmethod
    def get_plan(cls, plan_id: str) -> TestPlan | None:
        return cls.plans.get(plan_id)

    @classmethod
    def list_plans(cls, target_id: str | None = None) -> list[TestPlan]:
        plans = list(cls.plans.values())
        if target_id:
            plans = [p for p in plans if p.target_id == target_id]
        return plans

    # ── Runs ─────────────────────────────────────────────────────────────

    @classmethod
    def save_run(cls, run: TestRun) -> TestRun:
        cls.runs[run.id] = run
        return run

    @classmethod
    def get_run(cls, run_id: str) -> TestRun | None:
        return cls.runs.get(run_id)

    @classmethod
    def list_runs(cls, target_id: str | None = None) -> list[TestRun]:
        runs = list(cls.runs.values())
        if target_id:
            runs = [r for r in runs if r.target_id == target_id]
        return runs

    # ── Reports ──────────────────────────────────────────────────────────

    @classmethod
    def save_report(cls, report: QualityReport) -> QualityReport:
        cls.reports[report.id] = report
        return report

    @classmethod
    def get_report(cls, report_id: str) -> QualityReport | None:
        return cls.reports.get(report_id)

    @classmethod
    def get_report_by_run(cls, run_id: str) -> QualityReport | None:
        for report in cls.reports.values():
            if report.run_id == run_id:
                return report
        return None

    @classmethod
    def list_reports(cls, target_id: str | None = None) -> list[QualityReport]:
        reports = list(cls.reports.values())
        if target_id:
            reports = [r for r in reports if r.target_id == target_id]
        return reports
