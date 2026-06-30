"""Leveling router — rank roles stored in LevelingDB (psycopg2 table rank_roles)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.utils.dependencies import CurrentUser, require_guild_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/guilds", tags=["leveling"])


def _get_leveling_db(request: Request):
    bot = getattr(request.app.state, "bot", None)
    if not bot:
        raise HTTPException(status_code=503, detail="Bot offline")
    cog = bot.get_cog("LevelingCog")
    if cog is None or cog.db is None:
        raise HTTPException(status_code=503, detail="Leveling DB недоступна")
    return cog.db


class RankRoleEntry(BaseModel):
    level: int
    role_id: str
    remove_role_id: str | None = None


@router.get("/{guild_id}/rank-roles")
async def get_rank_roles(
    guild_id: str,
    request: Request,
    user: CurrentUser,
) -> list[dict[str, Any]]:
    """Вернуть все ранговые роли гильдии из таблицы rank_roles."""
    await require_guild_access(guild_id, user)
    db = _get_leveling_db(request)

    roles: dict = await asyncio.to_thread(db.get_rank_roles, guild_id)
    result = []
    for level, data in sorted(roles.items(), key=lambda x: int(x[0])):
        result.append({
            "level": int(level),
            "role_id": data["role_id"],
            "remove_role_id": data.get("remove_role_id"),
        })
    return result


@router.put("/{guild_id}/rank-roles")
async def set_rank_roles(
    guild_id: str,
    entries: list[RankRoleEntry],
    request: Request,
    user: CurrentUser,
) -> dict:
    """Полностью заменить набор ранговых ролей для гильдии.

    Удаляет уровни, которых нет в запросе, и создаёт/обновляет переданные.
    """
    await require_guild_access(guild_id, user)
    db = _get_leveling_db(request)

    # Текущие уровни из БД
    existing: dict = await asyncio.to_thread(db.get_rank_roles, guild_id)
    new_levels = {e.level for e in entries if e.role_id}

    # Удаляем уровни, которые убрали на сайте
    for lvl in existing:
        if int(lvl) not in new_levels:
            await asyncio.to_thread(db.remove_rank_role, guild_id, int(lvl))

    # Создаём / обновляем переданные
    for entry in entries:
        if not entry.role_id:
            continue
        await asyncio.to_thread(
            db.set_rank_role,
            guild_id,
            entry.level,
            str(entry.role_id),
            str(entry.remove_role_id) if entry.remove_role_id else None,
        )

    return {"status": "ok", "count": len(entries)}


@router.delete("/{guild_id}/rank-roles/{level}")
async def delete_rank_role(
    guild_id: str,
    level: int,
    request: Request,
    user: CurrentUser,
) -> dict:
    """Удалить одну ранговую роль по уровню."""
    await require_guild_access(guild_id, user)
    db = _get_leveling_db(request)
    await asyncio.to_thread(db.remove_rank_role, guild_id, level)
    return {"status": "ok"}
