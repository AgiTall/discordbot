"""Async Discord API client using httpx.

Replaces the old urllib-based synchronous helper from web_routes.py
with a proper async client that supports connection pooling.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

DISCORD_API = "https://discord.com/api/v10"
USER_AGENT = "DiscordBot (https://pchev.me, 1.0.0)"

# Shared async client — created once, reused across requests
_client: httpx.AsyncClient | None = None


async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": USER_AGENT},
        )
    return _client


async def close_client() -> None:
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


async def exchange_code(code: str) -> dict[str, Any]:
    """Exchange an OAuth2 authorization code for access/refresh tokens."""
    client = await get_client()
    resp = await client.post(
        f"{DISCORD_API}/oauth2/token",
        data={
            "client_id": settings.discord_client_id,
            "client_secret": settings.discord_client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.oauth_redirect_uri,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    return resp.json()


async def get_user(access_token: str) -> dict[str, Any]:
    """Fetch the authenticated user's profile."""
    client = await get_client()
    resp = await client.get(
        f"{DISCORD_API}/users/@me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    resp.raise_for_status()
    return resp.json()


async def get_user_guilds(access_token: str) -> list[dict[str, Any]]:
    """Fetch the authenticated user's guild list."""
    client = await get_client()
    resp = await client.get(
        f"{DISCORD_API}/users/@me/guilds",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    resp.raise_for_status()
    return resp.json()
