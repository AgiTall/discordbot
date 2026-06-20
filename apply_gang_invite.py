import sys

with open('cogs/gangs.py', encoding='utf-8') as f:
    lines = f.readlines()

with open('scratch_gang_invite_view.py', encoding='utf-8') as f:
    view_content = f.read()

start_idx = -1
end_idx = -1
for i, line in enumerate(lines):
    if 'async def gang_invite(' in line:
        start_idx = i - 2  # Include decorators
    if start_idx != -1 and 'def gang_join' in line:
        end_idx = i - 1  # Before next command
        break

new_invite = '''
    @app_commands.command(name="gang-invite", description="Пригласить игрока в банду (только для лидера)")
    @app_commands.describe(member="Кого пригласить")
    async def gang_invite(self, interaction: discord.Interaction, member: discord.Member):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            if member.bot:
                await interaction.response.send_message("Нельзя приглашать ботов.", ephemeral=True)
                return

            async with economy_lock:
                account = get_account(interaction.user.id)
                gang_name = user_in_gang(account)
                gangs = get_gangs(interaction.guild_id)

                if not gang_name or gang_name not in gangs:
                    await interaction.response.send_message("Вы не состоите в банде.", ephemeral=True)
                    return

                if gangs[gang_name]["leader"] != interaction.user.id:
                    await interaction.response.send_message("Только лидер банды может приглашать новых участников.", ephemeral=True)
                    return

                target_account = get_account(member.id)
                if user_in_gang(target_account):
                    await interaction.response.send_message("Этот игрок уже состоит в банде.", ephemeral=True)
                    return

                guild_invites = GANG_INVITES.setdefault(interaction.guild_id, {})
                guild_invites[member.id] = gang_name

            embed = discord.Embed(
                title="Приглашение в банду",
                description=f"Игрок **{interaction.user.display_name}** приглашает вас присоединиться к банде **{gang_name}** на сервере **{interaction.guild.name}**!\\n\\nНажмите кнопку ниже, чтобы принять или отклонить приглашение.",
                color=discord.Color.green()
            )
            view = GangInviteView(interaction.guild_id, gang_name, interaction.user.id, self.bot)
            try:
                await member.send(embed=embed, view=view)
                await interaction.response.send_message(f"✅ Вы успешно отправили приглашение {member.mention} в ЛС!", ephemeral=False)
            except discord.Forbidden:
                await interaction.response.send_message(f"⚠️ Приглашение отправлено, но у {member.mention} **закрыты личные сообщения**!\\n\\nИгроку придётся принять приглашение вручную, введя команду `/gang-join name:{gang_name}` здесь на сервере.", ephemeral=False)

        finally:
            reset_economy_guild_id(token)
'''

new_lines = lines[:start_idx] + [view_content + '\n'] + [new_invite + '\n'] + lines[end_idx:]

with open('cogs/gangs.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print('Replaced gang_invite and added View')
