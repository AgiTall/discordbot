"""FastAPI application factory.

Creates the app, registers routers, configures static files,
and sets up startup/shutdown hooks for the database and httpx client.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings

logger = logging.getLogger(__name__)


def create_app(bot=None) -> FastAPI:
    """Build and return a configured FastAPI application.

    Parameters
    ----------
    bot : commands.Bot | None
        The discord.py bot instance.  Stored in ``app.state.bot`` so
        that routers can access guild data (roles, channels, etc.)
        without importing the bot module directly.
    """
    app = FastAPI(
        title="PchevBot API",
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url=None,
    )

    # ── Store bot reference ───────────────────────────────────
    app.state.bot = bot

    # ── CORS (needed if frontend is served separately) ────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            settings.frontend_url,
            "http://localhost:10000",
            "https://pchev.me",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────
    from app.routers import auth, billing, guilds, settings as settings_router, gangs

    app.include_router(auth.router)
    app.include_router(guilds.router)
    app.include_router(settings_router.router)
    app.include_router(billing.router)
    app.include_router(gangs.router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    # ── Static files (dashboard + docs) ───────────────────────
    # Mount docs directory at root so that all HTML, CSS, and JS files resolve correctly.
    # html=True automatically serves index.html for the root route.
    app.mount("/", StaticFiles(directory="docs", html=True), name="static")

    # ── Startup / Shutdown ────────────────────────────────────

    @app.on_event("startup")
    async def on_startup():
        from app.database import init_db
        logger.info("Initializing database tables...")
        await init_db()
        logger.info("Database ready.")

    @app.on_event("shutdown")
    async def on_shutdown():
        from app.database import close_db
        from app.services.discord_api import close_client

        await close_client()
        await close_db()
        logger.info("Shutdown complete.")

    return app
