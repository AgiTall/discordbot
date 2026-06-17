"""Pydantic schemas for billing / payment endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    guild_id: str


class CreateSessionResponse(BaseModel):
    payment_url: str
    session_id: str


class WebhookPayload(BaseModel):
    session_id: str
    guild_id: str
    status: str = "completed"   # mock always succeeds


class WebhookResponse(BaseModel):
    status: str
    is_premium: bool
    subscription_ends_at: str | None = None
