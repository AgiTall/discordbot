"""Утилита для проверки состояния БД (PostgreSQL).

Запуск: python check_db.py
"""
import json
import os
import psycopg2
import psycopg2.extras


def _normalize_url(url):
    if not url:
        return url
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    url = url.replace("postgresql+psycopg2://", "postgresql://")
    url = url.replace("postgres://", "postgresql://")
    return url


def main():
    # Загружаем .env если он есть
    env_file = ".env"
    if os.path.exists(env_file):
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    db_url = _normalize_url(os.environ.get("DATABASE_URL"))
    if not db_url:
        print("ERROR: DATABASE_URL не задан в окружении или .env")
        return

    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor)

    print("=== ECONOMY GUILDS ===")
    with conn.cursor() as cur:
        cur.execute("SELECT guild_id FROM economy_guilds ORDER BY guild_id")
        rows = cur.fetchall()
        for row in rows:
            print(f"  guild_id={row['guild_id']}")
        print(f"  Всего: {len(rows)}")

    print("\n=== ECONOMY USERS (по гильдиям) ===")
    with conn.cursor() as cur:
        cur.execute(
            "SELECT guild_id, COUNT(*) AS cnt FROM economy_users GROUP BY guild_id ORDER BY guild_id"
        )
        for row in cur:
            print(f"  Guild {row['guild_id']}: {row['cnt']} игроков")

    print("\n=== LEVELING USERS (по гильдиям) ===")
    with conn.cursor() as cur:
        try:
            cur.execute(
                "SELECT guild_id, COUNT(*) AS cnt FROM leveling_users GROUP BY guild_id ORDER BY guild_id"
            )
            for row in cur:
                print(f"  Guild {row['guild_id']}: {row['cnt']} игроков")
        except Exception as e:
            print(f"  (таблица leveling_users не найдена или ошибка: {e})")

    conn.close()


if __name__ == "__main__":
    main()
