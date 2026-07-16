"""Alembic env.py — configures the migration environment.

Reads the database URL from app.config.settings (which loads .env)
so there's a single source of truth for connection strings.
"""

from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from asyncpg import InvalidPasswordError

# ── Load our app models so that Base.metadata is populated ────
from app.database import Base
from app.models.user import UserSession  # noqa: F401
from app.models.guild import Guild  # noqa: F401
from app.models.guild_settings import GuildSettings  # noqa: F401

from app.config import settings as app_settings

config = context.config

# Override the URL from alembic.ini with the real one from .env
config.set_main_option("sqlalchemy.url", app_settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emit SQL to stdout."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using an async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    try:
        asyncio.run(run_async_migrations())
    except InvalidPasswordError:
        print(
            "\nОшибка подключения к PostgreSQL: сервер отклонил пароль.\n"
            "Проверьте DATABASE_URL в .env. Значение должно содержать реально "
            "существующих пользователя, пароль и базу данных.\n"
            "Пример: postgresql+asyncpg://USER:PASSWORD@localhost:5432/DATABASE\n",
            file=sys.stderr,
        )
        raise SystemExit(2) from None


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
