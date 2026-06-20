import sqlite3
import json

conn = sqlite3.connect('data/economy.db')
conn.row_factory = sqlite3.Row

print("=== GUILDS ===")
for row in conn.execute("SELECT guild_id FROM guilds"):
    print(row['guild_id'])

print("\n=== USERS ===")
for row in conn.execute("SELECT guild_id, count(*) as c FROM users GROUP BY guild_id"):
    print(f"Guild {row['guild_id']}: {row['c']} users")
