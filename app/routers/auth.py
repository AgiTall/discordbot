"""Auth router — Discord OAuth2 login/logout and /api/me."""

from __future__ import annotations

import json
import logging
import secrets
import urllib.parse
from pathlib import Path

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import settings
from app.schemas.auth import GuildBrief, MeResponse, UserResponse
from app.services import auth_service
from app.services import discord_api as _dapi
from app.services.auth_service import _can_manage_guild, _build_guild_icon_url
from app.utils.dependencies import CurrentUser, DbSession

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

DISCORD_AUTHORIZE_URL = "https://discord.com/api/v10/oauth2/authorize"


@router.get("/api/config")
async def api_public_config():
    """Public, non-secret values used by the static website."""
    try:
        version = (Path(__file__).resolve().parents[2] / "VERSION").read_text(
            encoding="utf-8"
        ).strip()
    except OSError:
        version = ""
    return {
        "version": version,
        "inviteUrl": (
            "https://discord.com/oauth2/authorize"
            f"?client_id={settings.discord_client_id}"
            "&scope=bot%20applications.commands&permissions=8"
        ),
        "supportUrl": settings.support_url or None,
    }


@router.get("/auth/discord")
async def auth_discord(request: Request):
    """Redirect the user to Discord's OAuth2 authorization page."""
    state = secrets.token_urlsafe(16)
    # Store state in a short-lived cookie for CSRF verification
    params = urllib.parse.urlencode({
        "client_id": settings.discord_client_id,
        "redirect_uri": settings.oauth_redirect_uri,
        "response_type": "code",
        "scope": "identify guilds",
        "state": state,
    })
    response = RedirectResponse(url=f"{DISCORD_AUTHORIZE_URL}?{params}")
    response.set_cookie(
        "oauth_state",
        state,
        httponly=True,
        secure=settings.render,
        samesite="lax",
        max_age=600,  # 10 minutes
    )
    return response


@router.get("/auth/discord/callback")
async def auth_discord_callback(
    request: Request,
    db: DbSession,
):
    """Handle the OAuth2 callback from Discord."""
    error = request.query_params.get("error")
    if error:
        return RedirectResponse(url=f"{settings.frontend_url}/dashboard.html?error=oauth_denied")

    state = request.query_params.get("state")
    expected_state = request.cookies.get("oauth_state")
    if not state or state != expected_state:
        return RedirectResponse(url=f"{settings.frontend_url}/dashboard.html?error=oauth_state")

    code = request.query_params.get("code")
    if not code:
        return RedirectResponse(url=f"{settings.frontend_url}/dashboard.html?error=oauth_code")

    try:
        # Get bot guild IDs for botPresent flag
        bot = request.app.state.bot
        bot_guild_ids = {str(g.id) for g in bot.guilds} if bot else set()

        session_row, signed_cookie = await auth_service.create_session_from_code(
            code, db, bot_guild_ids
        )
    except Exception as e:
        logger.error("OAuth callback failed: %s", e, exc_info=True)
        return RedirectResponse(url=f"{settings.frontend_url}/dashboard.html?error=oauth_token")

    response = RedirectResponse(url=f"{settings.frontend_url}/dashboard.html")
    response.set_cookie(
        "session_token",
        signed_cookie,
        httponly=True,
        secure=settings.render,
        samesite="lax",
        max_age=auth_service.SESSION_MAX_AGE,
    )
    # Clear the oauth_state cookie
    response.delete_cookie("oauth_state")
    return response


@router.post("/auth/logout")
async def auth_logout(
    request: Request,
    user: CurrentUser,
    db: DbSession,
):
    """Log out the current user — delete session and clear cookie."""
    await auth_service.delete_session(user, db)
    response = JSONResponse(content={"status": "ok"})
    response.delete_cookie("session_token")
    return response


@router.get("/api/me", response_model=MeResponse)
async def api_me(
    request: Request,
    db: DbSession,
):
    """Return the current user's info, or {authenticated: false}."""
    signed_token = request.cookies.get("session_token")
    if not signed_token:
        return MeResponse(authenticated=False)

    raw_token = auth_service.unsign_session_token(signed_token)
    if raw_token is None:
        return MeResponse(authenticated=False)

    session_row = await auth_service.get_session_by_token(raw_token, db)
    if session_row is None:
        return MeResponse(authenticated=False)

    # Build avatar URL
    avatar_url = None
    if session_row.avatar:
        avatar_url = f"https://cdn.discordapp.com/avatars/{session_row.discord_id}/{session_row.avatar}.png"

    # Parse guilds and refresh botPresent
    bot = request.app.state.bot
    bot_guild_ids = {str(g.id) for g in bot.guilds} if bot else set()

    guilds = []
    if session_row.guilds_json:
        try:
            raw_guilds = json.loads(session_row.guilds_json)
        except (json.JSONDecodeError, TypeError):
            raw_guilds = []
        for g in raw_guilds:
            guilds.append(GuildBrief(
                id=str(g["id"]),
                name=g.get("name", "Сервер"),
                icon=g.get("icon"),
                canManage=g.get("canManage", False),
                botPresent=str(g["id"]) in bot_guild_ids,
            ))

    return MeResponse(
        authenticated=True,
        user=UserResponse(
            id=session_row.discord_id,
            username=session_row.username,
            global_name=session_row.global_name,
            avatar=session_row.avatar,
            avatar_url=avatar_url,
        ),
        guilds=guilds,
        clientId=settings.discord_client_id,
        inviteUrl=(
            f"https://discord.com/oauth2/authorize"
            f"?client_id={settings.discord_client_id}"
            f"&scope=bot%20applications.commands&permissions=8"
        ),
    )


@router.post("/api/me/refresh")
async def api_me_refresh(
    request: Request,
    user: CurrentUser,
    db: DbSession,
):
    """Обновить список гильдий пользователя через Discord API.

    Вызывается после добавления бота на сервер, чтобы список серверов
    обновился без повторного логина.
    """
    bot = request.app.state.bot
    bot_guild_ids = {str(g.id) for g in bot.guilds} if bot else set()

    try:
        guilds_data = await _dapi.get_user_guilds(user.access_token)
        refreshed_guilds = []
        for g in guilds_data:
            gid = str(g["id"])
            refreshed_guilds.append({
                "id": gid,
                "name": g.get("name", "Сервер"),
                "icon": _build_guild_icon_url(gid, g.get("icon")),
                "canManage": _can_manage_guild(g.get("permissions", 0)),
                "botPresent": gid in bot_guild_ids,
            })
        user.guilds_json = json.dumps(refreshed_guilds, ensure_ascii=False)
        await db.commit()
    except Exception as e:
        logger.warning("Не удалось обновить список гильдий: %s", e)
        # Не падаем — просто вернём текущее с актуальным botPresent

    # Вернём актуальный ответ с обновлёнными данными
    raw_guilds = []
    if user.guilds_json:
        try:
            raw_guilds = json.loads(user.guilds_json)
        except Exception:
            raw_guilds = []

    guilds_out = []
    for g in raw_guilds:
        guilds_out.append({
            "id": str(g["id"]),
            "name": g.get("name", "Сервер"),
            "icon": g.get("icon"),
            "canManage": g.get("canManage", False),
            "botPresent": str(g["id"]) in bot_guild_ids,
        })

    return {"status": "ok", "guilds": guilds_out}
