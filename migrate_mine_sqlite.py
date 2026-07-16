"""One-time migration of legacy data/mine.db into PostgreSQL.

Run this once from an environment where the old SQLite file and the target
DATABASE_URL are both available:

    .venv\\Scripts\\python.exe migrate_mine_sqlite.py
"""

from __future__ import annotations

import os
import json
import sqlite3
import sys

from src.mine_logic import MineDB, MINE_DB_FILE


def main() -> int:
    if not os.path.exists(MINE_DB_FILE):
        print(f"Legacy file not found: {MINE_DB_FILE}")
        return 1
    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is required")
        return 1

    source = sqlite3.connect(MINE_DB_FILE)
    source.row_factory = sqlite3.Row
    target = MineDB()
    try:
        players = source.execute("SELECT * FROM mine_players").fetchall()
        for row in players:
            player = dict(row)
            try:
                player["inventory"] = json.loads(player.get("inventory") or "{}")
            except (TypeError, json.JSONDecodeError):
                player["inventory"] = {}
            target.save_player(player["guild_id"], player["discord_id"], player)

        shafts = source.execute("SELECT guild_id, shaft_depth FROM mine_guild").fetchall()
        for row in shafts:
            target.set_guild_shaft(row["guild_id"], row["shaft_depth"])
    except sqlite3.OperationalError as exc:
        print(f"Legacy database has an unexpected schema: {exc}")
        return 1
    finally:
        source.close()
        target.close()

    print(f"Migrated {len(players)} mine players and {len(shafts)} mine shafts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
