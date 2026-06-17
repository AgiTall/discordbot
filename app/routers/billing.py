"""Billing router — mock payment flow."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app.schemas.billing import (
    CreateSessionRequest,
    CreateSessionResponse,
    WebhookPayload,
    WebhookResponse,
)
from app.services import billing_service
from app.utils.dependencies import DbSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/create-session", response_model=CreateSessionResponse)
async def create_session(body: CreateSessionRequest, db: DbSession):
    """Create a mock payment session and return a payment link."""
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
    result = await billing_service.process_webhook(
        session_id=body.session_id,
        guild_id=body.guild_id,
        db=db,
    )
    return WebhookResponse(**result)
