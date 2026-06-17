"""Pydantic schemas for guild endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class RoleItem(BaseModel):
    id: str
    name: str
    color: str
    position: int


class ChannelItem(BaseModel):
    id: str
    name: str
    type: int           # discord.ChannelType value
    category: str | None = None
    position: int = 0
