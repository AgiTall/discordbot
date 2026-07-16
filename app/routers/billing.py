"""Billing router — mock payment flow."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from app.schemas.billing import (
    CreateSessionRequest,
    CreateSessionResponse,
    WebhookPayload,
    WebhookResponse,
)
from app.services import billing_service
from app.config import settings
from app.utils.dependencies import CurrentUser, DbSession, require_guild_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/create-session", response_model=CreateSessionResponse)
async def create_session(
    body: CreateSessionRequest,
    request: Request,
    user: CurrentUser,
    db: DbSession,
):
    """Create a mock payment session and return a payment link."""
    await require_guild_access(body.guild_id, user, request)
    session_id, payment_url = await billing_service.create_payment_session(
        body.guild_id, db
    )
    return CreateSessionResponse(
        session_id=session_id,
        payment_url=payment_url,
    )


@router.post("/webhook", response_model=WebhookResponse)
async def payment_webhook(body: WebhookPayload, db: DbSession):
    """Simulate a payment webhook — activates premium for 30 days."""
    # Mock callbacks must never be exposed as a production payment endpoint.
    # A real provider integration must verify the provider's signed webhook.
    if settings.render:
        raise HTTPException(status_code=503, detail="Payment provider is not configured")
    try:
        result = await billing_service.process_webhook(
            session_id=body.session_id,
            guild_id=body.guild_id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WebhookResponse(**result)
