"""Target agent management routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agentprobe.api.store import Store
from agentprobe.connectors.api_connector import APIConnector
from agentprobe.connectors.mcp_connector import MCPConnector
from agentprobe.probe.models import TargetProfile

router = APIRouter()


class RegisterTargetRequest(BaseModel):
    url: str
    name: str = ""
    connector_type: str = "api"
    auth_token: str = ""
    chat_endpoint: str = "/chat"
    tools_endpoint: str = "/tools"


@router.post("/", response_model=TargetProfile)
async def register_target(req: RegisterTargetRequest):
    """Register and discover a new target agent."""
    if req.connector_type == "mcp":
        connector = MCPConnector(url=req.url, name=req.name, auth_token=req.auth_token)
    else:
        connector = APIConnector(
            url=req.url,
            name=req.name,
            auth_token=req.auth_token,
            chat_endpoint=req.chat_endpoint,
            tools_endpoint=req.tools_endpoint,
        )

    try:
        async with connector:
            profile = await connector.discover()
    except ConnectionError as e:
        raise HTTPException(status_code=502, detail=f"Cannot connect to target: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Discovery failed: {e}")

    Store.save_target(profile)
    return profile


@router.get("/", response_model=list[TargetProfile])
async def list_targets():
    """List all registered target agents."""
    return Store.list_targets()


@router.get("/{target_id}", response_model=TargetProfile)
async def get_target(target_id: str):
    """Get a specific target agent profile."""
    target = Store.get_target(target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    return target


@router.delete("/{target_id}")
async def delete_target(target_id: str):
    """Delete a registered target agent."""
    if not Store.delete_target(target_id):
        raise HTTPException(status_code=404, detail="Target not found")
    return {"deleted": True}
