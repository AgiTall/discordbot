"""Pydantic schemas for settings endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SettingsUpdate(BaseModel):
    """Partial update for a single category."""
    # Accept arbitrary keys — validation is loose by design so that
    # new settings can be added without changing the schema.
    data: dict[str, Any]


class SettingsCategoryResponse(BaseModel):
    """Response for a single category read."""
    category: str
    settings: dict[str, Any]


class AllSettingsResponse(BaseModel):
    """Response containing all categories."""
    guild_id: str
    settings: dict[str, dict[str, Any]]
