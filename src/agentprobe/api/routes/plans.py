"""Test plan management routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agentprobe.api.store import Store
from agentprobe.probe.models import TestPlan
from agentprobe.probe.planner import generate_test_plan

router = APIRouter()


class GeneratePlanRequest(BaseModel):
    target_id: str
    name: str = ""
    categories: list[str] | None = None
    max_cases: int = 50


@router.post("/", response_model=TestPlan)
async def create_plan(req: GeneratePlanRequest):
    """Generate a test plan for a target agent using AI."""
    target = Store.get_target(req.target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    plan = await generate_test_plan(
        target=target,
        name=req.name or f"Test plan for {target.name}",
        categories=req.categories,
        max_cases=req.max_cases,
    )

    Store.save_plan(plan)
    return plan


@router.get("/", response_model=list[TestPlan])
async def list_plans(target_id: str | None = None):
    """List all test plans, optionally filtered by target."""
    return Store.list_plans(target_id=target_id)


@router.get("/{plan_id}", response_model=TestPlan)
async def get_plan(plan_id: str):
    """Get a specific test plan."""
    plan = Store.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan
