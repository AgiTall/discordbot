"""Make one OAuth session row authoritative per Discord user.

Revision ID: 20260716_01
Revises:
Create Date: 2026-07-16
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260716_01"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A brand-new Render database has not seen SQLAlchemy's create_all() yet.
    # Create the table here as well so the first deploy can run migrations
    # before the application process starts.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_sessions (
            id SERIAL PRIMARY KEY,
            discord_id VARCHAR(32) NOT NULL,
            username VARCHAR(128) NOT NULL,
            global_name VARCHAR(128),
            avatar VARCHAR(256),
            access_token TEXT NOT NULL,
            refresh_token TEXT,
            token_expires_at TIMESTAMP WITH TIME ZONE,
            session_token VARCHAR(256) NOT NULL,
            guilds_json TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_user_sessions_session_token
        ON user_sessions (session_token)
        """
    )

    # Existing installations may already contain duplicate rows from
    # concurrent OAuth callbacks. Keep the newest row before enforcing the
    # invariant used by scalar_one_or_none().
    op.execute(
        """
        DELETE FROM user_sessions AS older
        USING user_sessions AS newer
        WHERE older.discord_id = newer.discord_id
          AND older.id < newer.id
        """
    )
    op.execute("DROP INDEX IF EXISTS ix_user_sessions_discord_id")
    op.execute(
        """
        CREATE UNIQUE INDEX ix_user_sessions_discord_id
        ON user_sessions (discord_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_user_sessions_discord_id")
    op.execute(
        """
        CREATE INDEX ix_user_sessions_discord_id
        ON user_sessions (discord_id)
        """
    )
