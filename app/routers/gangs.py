"""API Router for Gangs (Банды)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from app.models.gang import Gang, GangMember
from app.utils.dependencies import CurrentUser, DbSession, require_guild_access

router = APIRouter(prefix="/api", tags=["gangs"])

class GangResponse(BaseModel):
    id: int
    name: str
    balance: float
    camp_upgrades: dict[str, Any]
    member_count: int

class GangMemberResponse(BaseModel):
    user_id: str
    role: str

class PlayerGangResponse(BaseModel):
    gang: GangResponse
    my_role: str
    members: list[GangMemberResponse]

class GangUpdateRequest(BaseModel):
    name: str


@router.get("/guilds/{guild_id}/gangs", response_model=list[GangResponse])
async def get_guild_gangs(
    guild_id: str,
    user: CurrentUser,
    db: DbSession,
):
    """List all gangs for a guild (Admin only view)."""
    await require_guild_access(guild_id, user)
    
    stmt = select(Gang).where(Gang.guild_id == guild_id).options(selectinload(Gang.members))
    result = await db.execute(stmt)
    gangs = result.scalars().all()
    
    return [
        GangResponse(
            id=g.id,
            name=g.name,
            balance=g.balance,
            camp_upgrades=g.camp_upgrades,
            member_count=len(g.members)
        )
        for g in gangs
    ]

@router.patch("/guilds/{guild_id}/gangs/{gang_id}", response_model=GangResponse)
async def update_gang_name(
    guild_id: str,
    gang_id: int,
    body: GangUpdateRequest,
    user: CurrentUser,
    db: DbSession,
):
    """Admin endpoint to rename a gang."""
    await require_guild_access(guild_id, user)
    
    stmt = select(Gang).where(Gang.id == gang_id, Gang.guild_id == guild_id).options(selectinload(Gang.members))
    result = await db.execute(stmt)
    gang = result.scalar_one_or_none()
    
    if not gang:
        raise HTTPException(status_code=404, detail="Gang not found")
        
    gang.name = body.name
    await db.commit()
    
    return GangResponse(
        id=gang.id,
        name=gang.name,
        balance=gang.balance,
        camp_upgrades=gang.camp_upgrades,
        member_count=len(gang.members)
    )

@router.delete("/guilds/{guild_id}/gangs/{gang_id}")
async def delete_gang(
    guild_id: str,
    gang_id: int,
    user: CurrentUser,
    db: DbSession,
):
    """Admin endpoint to delete a gang."""
    await require_guild_access(guild_id, user)
    
    stmt = delete(Gang).where(Gang.id == gang_id, Gang.guild_id == guild_id)
    await db.execute(stmt)
    await db.commit()
    return {"status": "ok"}


@router.get("/guilds/{guild_id}/me/gang", response_model=PlayerGangResponse)
async def get_my_gang(
    guild_id: str,
    user: CurrentUser,
    db: DbSession,
):
    """Get the current user's gang in the given guild."""
    # Find the GangMember entry for this user
    stmt = select(GangMember).where(
        GangMember.guild_id == guild_id, 
        GangMember.user_id == user.id
    ).options(selectinload(GangMember.gang).selectinload(Gang.members))
    
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()
    
    if not membership:
        raise HTTPException(status_code=404, detail="You are not in a gang")
        
    gang = membership.gang
    
    return PlayerGangResponse(
        gang=GangResponse(
            id=gang.id,
            name=gang.name,
            balance=gang.balance,
            camp_upgrades=gang.camp_upgrades,
            member_count=len(gang.members)
        ),
        my_role=membership.role,
        members=[GangMemberResponse(user_id=m.user_id, role=m.role) for m in gang.members]
    )
