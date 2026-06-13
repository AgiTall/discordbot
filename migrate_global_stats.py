import json
import os

ECONOMY_FILE = 'economy.json'

def migrate_global_to_server():
    if not os.path.exists(ECONOMY_FILE):
        print("economy.json not found.")
        return

    with open(ECONOMY_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if 'global' not in data['guilds']:
        print("No global data found to migrate.")
        return

    print("Available servers (guilds) to migrate to:")
    guilds = [g for g in data['guilds'].keys() if g != 'global']
    for idx, guild_id in enumerate(guilds):
        print(f"{idx + 1}. {guild_id}")

    if not guilds:
        print("No specific server data found. Please run the bot in your server at least once before migrating.")
        return

    target_idx = input("Enter the number of the server to migrate to: ")
    try:
        target_guild_id = guilds[int(target_idx) - 1]
    except (ValueError, IndexError):
        print("Invalid selection.")
        return

    print(f"\nMigrating users from 'global' to '{target_guild_id}'...")
    
    global_users = data['guilds']['global'].get('users', {})
    target_users = data['guilds'][target_guild_id].setdefault('users', {})

    migrated_count = 0
    for user_id, global_stats in global_users.items():
        if user_id in target_users:
            print(f"Skipping user {user_id} - they already have data in the target server.")
        else:
            target_users[user_id] = global_stats
            print(f"Migrated user {user_id}")
            migrated_count += 1

    if migrated_count > 0:
        backup_file = 'economy_backup.json'
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        with open(ECONOMY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        print(f"\nMigration complete! {migrated_count} users migrated.")
        print(f"A backup of the old data was saved to '{backup_file}'.")
    else:
        print("\nNo new users needed migration.")

if __name__ == '__main__':
    migrate_global_to_server()
