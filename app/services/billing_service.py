"""Billing service — mock payment flow.

In production this would integrate with Stripe/YooKassa/etc.
For now it simulates the full lifecycle:
    create-session → payment page → webhook → premium activated.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import guild_service

logger = logging.getLogger(__name__)

# In-memory store for pending payment sessions (replace with DB/Redis in prod)
_pending_sessions: dict[str, dict] = {}


async def create_payment_session(
    guild_id: str,
    db: AsyncSession,
) -> tuple[str, str]:
    """Create a mock payment session. Returns (session_id, payment_url)."""
    session_id = secrets.token_urlsafe(32)
    _pending_sessions[session_id] = {
        "guild_id": guild_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
    }
    payment_url = f"/billing/mock-pay/{session_id}"
    logger.info("Created payment session %s for guild %s", session_id, guild_id)
    return session_id, payment_url


async def process_webhook(
    session_id: str,
    guild_id: str,
    db: AsyncSession,
    days: int = 30,
) -> dict:
    """Process a mock payment webhook — activate premium.

    Returns dict with result details.
    """
    # A payment session must have been created first and must belong to the
    # guild in the webhook.  Without this check any public POST could grant
    # premium to an arbitrary server.
    session_data = _pending_sessions.pop(session_id, None)
    if session_data is None or session_data.get("guild_id") != guild_id:
        raise ValueError("Unknown or mismatched payment session")
    logger.info("Processing webhook for session %s", session_id)

    guild = await guild_service.activate_premium(db, guild_id, days=days)

    return {
        "status": "ok",
        "is_premium": guild.is_premium,
        "subscription_ends_at": guild.subscription_ends_at.isoformat() if guild.subscription_ends_at else None,
    }
