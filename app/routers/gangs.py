"""API Router for Gangs (Банды) — reads from economy_store (bot's JSON data).

The bot stores gangs in economy_store.guild_data(guild_id)["gangs"],
so this router reads/writes there directly instead of PostgreSQL.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.utils.dependencies import CurrentUser, require_guild_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["gangs"])


def _get_economy_store(request: Request):
    store = getattr(request.app.state, "economy_data", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Economy store not available")
    return store


@router.get("/guilds/{guild_id}/gangs")
async def get_guild_gangs(
    guild_id: str,
    request: Request,
    user: CurrentUser,
) -> list[dict[str, Any]]:
    """List all gangs for a guild from economy_store."""
    await require_guild_access(guild_id, user)

    economy_store = _get_economy_store(request)
    guild_data = economy_store.guild_data(guild_id)
    gangs = guild_data.get("gangs", {})

    result = []
    for g_name, g_data in gangs.items():
        members = g_data.get("members", [])
        if isinstance(members, dict):
            member_count = len(members)
        elif isinstance(members, list):
            member_count = len(members)
        else:
            member_count = 0

        result.append({
            "id": g_data.get("id", hash(g_name) % 10000),
            "name": g_name,
            "balance": float(g_data.get("cash", 0.0)),
            "camp_upgrades": g_data.get("camp_upgrades", {}),
            "member_count": member_count,
        })

    return result


@router.delete("/guilds/{guild_id}/gangs/{gang_id}")
async def delete_gang(
    guild_id: str,
    gang_id: int,
    request: Request,
    user: CurrentUser,
):
    """Delete a gang from economy_store by its ID."""
    await require_guild_access(guild_id, user)

    economy_store = _get_economy_store(request)
    guild_data = economy_store.guild_data(guild_id)
    gangs = guild_data.get("gangs", {})

    # Find the gang by ID
    target_name = None
    for g_name, g_data in gangs.items():
        if g_data.get("id") == gang_id:
            target_name = g_name
            break

    if target_name is None:
        raise HTTPException(status_code=404, detail="Gang not found")

    del gangs[target_name]
    economy_store.save_all()

    return {"status": "ok"}
