class GangInviteView(discord.ui.View):
    def __init__(self, guild_id: int, gang_name: str, inviter_id: int, bot):
        super().__init__(timeout=86400) # 24 часа
        self.guild_id = guild_id
        self.gang_name = gang_name
        self.inviter_id = inviter_id
        self.bot = bot

    @discord.ui.button(label="Принять", style=discord.ButtonStyle.success, emoji="🟢")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        token = set_economy_guild_id(self.guild_id)
        try:
            async with economy_lock:
                guild_invites = GANG_INVITES.get(self.guild_id, {})
                if guild_invites.get(interaction.user.id) != self.gang_name:
                    await interaction.response.edit_message(content="❌ Это приглашение больше не действительно или было отозвано.", view=None, embed=None)
                    return

                gangs = get_gangs(self.guild_id)
                if self.gang_name not in gangs:
                    await interaction.response.edit_message(content="❌ Эта банда больше не существует.", view=None, embed=None)
                    del guild_invites[interaction.user.id]
                    return

                account = get_account(interaction.user.id)
                if user_in_gang(account):
                    await interaction.response.edit_message(content="❌ Вы уже состоите в другой банде.", view=None, embed=None)
                    del guild_invites[interaction.user.id]
                    return

                # Добавляем в банду
                account["gang_name"] = self.gang_name
                if interaction.user.id not in gangs[self.gang_name]["members"]:
                    gangs[self.gang_name]["members"].append(interaction.user.id)
                
                del guild_invites[interaction.user.id]
                role_id = gangs[self.gang_name].get("discord_role_id")
                save_economy()

            # Выдаем роль
            if role_id:
                guild = self.bot.get_guild(self.guild_id)
                if guild:
                    member = guild.get_member(interaction.user.id)
                    if member:
                        role = guild.get_role(role_id)
                        if role:
                            try:
                                await member.add_roles(role)
                            except discord.Forbidden:
                                pass

            await interaction.response.edit_message(content=f"✅ Вы успешно присоединились к банде **{self.gang_name}**!", view=None, embed=None)
        finally:
            reset_economy_guild_id(token)

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.danger, emoji="🔴")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_invites = GANG_INVITES.get(self.guild_id, {})
        if guild_invites.get(interaction.user.id) == self.gang_name:
            del guild_invites[interaction.user.id]
        await interaction.response.edit_message(content=f"❌ Вы отклонили приглашение в банду **{self.gang_name}**.", view=None, embed=None)
