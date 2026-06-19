
import re

with open("cogs/gangs.py", "r", encoding="utf-8") as f:
    text = f.read()

# Update gang-create
old_create = """                gangs[name] = {
                    "leader": interaction.user.id,
                    "members": [interaction.user.id],
                    "cash": 0.0,
                    "gold": 0.0,
                    "level": 1,
                    "influence": 0,
                    "created_at": now_local().isoformat(timespec="seconds"),
                    "last_rob_at": None
                }"""
new_create = """                # Auto-incrementing ID
                max_id = max([g.get("id", 0) for g in gangs.values()] + [0])
                gang_id = max_id + 1

                gangs[name] = {
                    "id": gang_id,
                    "leader": interaction.user.id,
                    "members": [interaction.user.id],
                    "cash": 0.0,
                    "gold": 0.0,
                    "level": 1,
                    "influence": 0,
                    "leader_role_name": "Лидер",
                    "member_role_name": "Участник",
                    "created_at": now_local().isoformat(timespec="seconds"),
                    "last_rob_at": None
                }"""
text = text.replace(old_create, new_create)

# Update gang-info embed
old_info = """                embed = discord.Embed(title=f"🏴‍☠️ Банда: {actual_gang_name}", color=discord.Color.dark_red())
                embed.add_field(name="👑 Лидер", value=leader_name, inline=True)"""
new_info = """                gang_id = gang.get("id", "N/A")
                leader_role = gang.get("leader_role_name", "Лидер")
                member_role = gang.get("member_role_name", "Участник")
                
                embed = discord.Embed(title=f"🏴‍☠️ Банда: {actual_gang_name} [#{gang_id}]", color=discord.Color.dark_red())
                embed.add_field(name=f"👑 {leader_role}", value=leader_name, inline=True)
                embed.add_field(name=f"👥 {member_role}ов", value=str(members_count), inline=True)"""
text = text.replace(old_info, new_info)

# Add gang-set-roles command
set_roles_cmd = """    @app_commands.command(name="gang-set-roles", description="Настроить названия ролей в банде (только для лидера)")
    async def gang_set_roles(self, interaction: discord.Interaction, leader_role: str, member_role: str):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            if len(leader_role) > 30 or len(member_role) > 30:
                await interaction.response.send_message("Названия ролей не должны превышать 30 символов.", ephemeral=True)
                return
                
            async with economy_lock:
                account = get_account(interaction.user.id)
                gang_name = user_in_gang(account)
                gangs = get_gangs(interaction.guild_id)
                
                if not gang_name or gang_name not in gangs:
                    await interaction.response.send_message("Вы не состоите в банде.", ephemeral=True)
                    return
                    
                if gangs[gang_name]["leader"] != interaction.user.id:
                    await interaction.response.send_message("Только лидер банды может менять названия ролей.", ephemeral=True)
                    return
                    
                gangs[gang_name]["leader_role_name"] = leader_role
                gangs[gang_name]["member_role_name"] = member_role
                save_economy()
                
            await interaction.response.send_message(f"✅ Названия ролей успешно обновлены! Теперь лидер — **{leader_role}**, а участники — **{member_role}**.")
        finally:
            reset_economy_guild_id(token)

"""
text = text.replace("    @app_commands.command(name=\"gang-deposit\"", set_roles_cmd + "    @app_commands.command(name=\"gang-deposit\"")

with open("cogs/gangs.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Done")

