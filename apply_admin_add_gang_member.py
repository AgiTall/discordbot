import sys

with open('cogs/gangs.py', encoding='utf-8') as f:
    lines = f.readlines()

new_command = '''
    @app_commands.command(name="admin-add-gang-member", description="Админ: Добавить игрока в банду без приглашения")
    @app_commands.describe(gang_name="Название банды", member="Кого добавить")
    @app_commands.default_permissions(administrator=True)
    async def admin_add_gang_member(self, interaction: discord.Interaction, gang_name: str, member: discord.Member):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                gangs = get_gangs(interaction.guild_id)

                if gang_name not in gangs:
                    await interaction.response.send_message(f"Банда '{gang_name}' не найдена.", ephemeral=True)
                    return

                if member.bot:
                    await interaction.response.send_message("Нельзя добавить ботов в банду.", ephemeral=True)
                    return

                target_account = get_account(member.id)
                old_gang = user_in_gang(target_account)
                
                if old_gang == gang_name:
                    await interaction.response.send_message("Этот игрок уже состоит в выбранной банде.", ephemeral=True)
                    return

                # Если игрок в другой банде, убираем его оттуда
                if old_gang and old_gang != gang_name and old_gang in gangs:
                    if member.id in gangs[old_gang]["members"]:
                        gangs[old_gang]["members"].remove(member.id)
                    if gangs[old_gang].get("leader") == member.id:
                        await interaction.response.send_message(f"⚠️ Игрок {member.mention} является лидером банды **{old_gang}**. Вы не можете просто перевести его. Сначала смените лидера той банды или распустите её.", ephemeral=True)
                        return
                
                target_account["gang_name"] = gang_name
                if member.id not in gangs[gang_name]["members"]:
                    gangs[gang_name]["members"].append(member.id)
                
                role_id = gangs[gang_name].get("discord_role_id")
                save_economy()
                
            if role_id:
                role = interaction.guild.get_role(role_id)
                if role:
                    try:
                        await member.add_roles(role)
                    except discord.Forbidden:
                        pass
                        
            await interaction.response.send_message(f"✅ Игрок {member.mention} принудительно добавлен в банду **{gang_name}**!", ephemeral=True)
        finally:
            reset_economy_guild_id(token)
'''

for i, line in enumerate(lines):
    if 'async def setup(bot):' in line:
        idx = i
        break

new_lines = lines[:idx] + [new_command + '\n'] + lines[idx:]

with open('cogs/gangs.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print('Added admin_add_gang_member')
