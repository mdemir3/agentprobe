"""Quality report routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from agentprobe.api.store import Store
from agentprobe.eval.pipeline import evaluate_run
from agentprobe.probe.models import QualityReport

router = APIRouter()


@router.post("/{run_id}", response_model=QualityReport)
async def generate_report(run_id: str):
    """Generate a quality report for a completed test run."""
    run = Store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    target = Store.get_target(run.target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    plan = Store.get_plan(run.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    report = await evaluate_run(run=run, plan=plan, target=target)
    Store.save_report(report)
    return report


@router.get("/", response_model=list[QualityReport])
async def list_reports(target_id: str | None = None):
    """List all quality reports."""
    return Store.list_reports(target_id=target_id)


@router.get("/{report_id}", response_model=QualityReport)
async def get_report(report_id: str):
    """Get a specific quality report."""
    report = Store.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
