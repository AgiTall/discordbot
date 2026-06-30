"""Pydantic schemas for authentication endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class UserResponse(BaseModel):
    """Public user info returned by /api/me."""
    id: str
    username: str
    global_name: str | None = None
    avatar: str | None = None
    avatar_url: str | None = None


class GuildBrief(BaseModel):
    """Abbreviated guild info for the user's guild list."""
    id: str
    name: str
    icon: str | None = None
    canManage: bool = False
    botPresent: bool = False


class MeResponse(BaseModel):
    """Response for GET /api/me."""
    authenticated: bool
    user: UserResponse | None = None
    guilds: list[GuildBrief] = []
    clientId: str | None = None
    inviteUrl: str | None = None
