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
    can_manage: bool = False
    bot_present: bool = False


class MeResponse(BaseModel):
    """Response for GET /api/me."""
    authenticated: bool
    user: UserResponse | None = None
    guilds: list[GuildBrief] = []
    client_id: str | None = None
    invite_url: str | None = None
