"""Test run execution routes."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from agentprobe.api.store import Store
from agentprobe.probe.models import TestRun
from agentprobe.probe.runner import execute_test_run

router = APIRouter()


class StartRunRequest(BaseModel):
    plan_id: str
    max_concurrent: int = 5


@router.post("/", response_model=TestRun)
async def start_run(req: StartRunRequest):
    """Execute a test plan against its target agent."""
    plan = Store.get_plan(req.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    target = Store.get_target(plan.target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    run = await execute_test_run(
        plan=plan,
        target=target,
        max_concurrent=req.max_concurrent,
    )

    Store.save_run(run)
    return run


@router.get("/", response_model=list[TestRun])
async def list_runs(target_id: str | None = None):
    """List all test runs."""
    return Store.list_runs(target_id=target_id)


@router.get("/{run_id}", response_model=TestRun)
async def get_run(run_id: str):
    """Get a specific test run with all results."""
    run = Store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
