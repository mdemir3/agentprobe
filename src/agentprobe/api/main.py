"""AgentProbe API — FastAPI backend for the AgentProbe platform."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agentprobe.api.routes import health, targets, plans, runs, reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup: initialize stores
    from agentprobe.api.store import Store
    Store.initialize()
    yield
    # Shutdown: cleanup
    pass


app = FastAPI(
    title="AgentProbe API",
    description="The first open-source AI agent that tests other AI agents.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(health.router, tags=["Health"])
app.include_router(targets.router, prefix="/targets", tags=["Targets"])
app.include_router(plans.router, prefix="/plans", tags=["Plans"])
app.include_router(runs.router, prefix="/runs", tags=["Runs"])
app.include_router(reports.router, prefix="/reports", tags=["Reports"])
