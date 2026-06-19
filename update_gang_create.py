
import re

with open("cogs/gangs.py", "r", encoding="utf-8") as f:
    text = f.read()

view_code = """class GangCreateConfirmView(discord.ui.View):
    def __init__(self, guild_id, member, gang_name):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.member = member
        self.gang_name = gang_name

    @discord.ui.button(label="Подтвердить покупку 50 🪙", style=discord.ButtonStyle.success, custom_id="confirm_gang_create")
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        token = set_economy_guild_id(self.guild_id)
        try:
            if interaction.user.id != self.member.id:
                await interaction.response.send_message("Это не ваш запрос!", ephemeral=True)
                return
                
            async with economy_lock:
                account = get_account(interaction.user.id)
                gangs = get_gangs(interaction.guild_id)
                
                if user_in_gang(account):
                    await interaction.response.send_message("Вы уже состоите в банде!", ephemeral=True)
                    return
                
                if self.gang_name.lower() in (g.lower() for g in gangs.keys()):
                    await interaction.response.send_message(f"Банда с именем **{self.gang_name}** уже существует.", ephemeral=True)
                    return
                
                if account.get("gold", 0.0) < GANG_CREATE_COST:
                    await interaction.response.send_message(f"Для создания банды нужно {GANG_CREATE_COST} золота.", ephemeral=True)
                    return
                
                # Create Gang
                account["gold"] -= GANG_CREATE_COST
                account["gang_name"] = self.gang_name
                
                max_id = max([g.get("id", 0) for g in gangs.values()] + [0])
                gang_id = max_id + 1

                gangs[self.gang_name] = {
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
                }
                
                save_economy()
                
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)
            await interaction.response.send_message(f"🏴‍☠️ Вы успешно основали банду **{self.gang_name}**! Поздравляем!")
        finally:
            reset_economy_guild_id(token)

class GangsCog(commands.Cog):"""

text = text.replace("class GangsCog(commands.Cog):", view_code)

old_gang_create = """    @app_commands.command(name="gang-create", description="Создать банду (Цена: 50 Золота)")
    async def gang_create(self, interaction: discord.Interaction, name: str):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            name = name.strip()
            if len(name) < 3 or len(name) > 32:
                await interaction.response.send_message("Имя банды должно быть от 3 до 32 символов.", ephemeral=True)
                return
                
            async with economy_lock:
                account = get_account(interaction.user.id)
                gangs = get_gangs(interaction.guild_id)
                
                if user_in_gang(account):
                    await interaction.response.send_message("Вы уже состоите в банде! Сначала покиньте её.", ephemeral=True)
                    return
                
                if name.lower() in (g.lower() for g in gangs.keys()):
                    await interaction.response.send_message(f"Банда с именем **{name}** уже существует.", ephemeral=True)
                    return
                
                if account.get("gold", 0.0) < GANG_CREATE_COST:
                    await interaction.response.send_message(f"Для создания банды нужно {GANG_CREATE_COST} золота.", ephemeral=True)
                    return
                
                # Auto-incrementing ID
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
                }
                
                save_economy()
                
            await interaction.response.send_message(f"🏴‍☠️ Вы успешно основали банду **{name}**! Поздравляем!")
        finally:
            reset_economy_guild_id(token)"""

new_gang_create = """    @app_commands.command(name="gang-create", description="Создать банду (Цена: 50 Золота)")
    async def gang_create(self, interaction: discord.Interaction, name: str):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            name = name.strip()
            if len(name) < 3 or len(name) > 32:
                await interaction.response.send_message("Имя банды должно быть от 3 до 32 символов.", ephemeral=True)
                return
                
            async with economy_lock:
                account = get_account(interaction.user.id)
                gangs = get_gangs(interaction.guild_id)
                
                if user_in_gang(account):
                    await interaction.response.send_message("Вы уже состоите в банде! Сначала покиньте её.", ephemeral=True)
                    return
                
                if name.lower() in (g.lower() for g in gangs.keys()):
                    await interaction.response.send_message(f"Банда с именем **{name}** уже существует.", ephemeral=True)
                    return
                
                if account.get("gold", 0.0) < GANG_CREATE_COST:
                    await interaction.response.send_message(f"Для создания банды нужно {GANG_CREATE_COST} золота.", ephemeral=True)
                    return
                    
            embed = discord.Embed(
                title="Создание банды",
                description="Вы собрали со всего дикого запада бродяг и кочевников чтобы работать сообща? Тогда вашему вниманию предоставлена механика банд, изначальной стоимостью 50 слитков.",
                color=discord.Color.dark_gold()
            )
            view = GangCreateConfirmView(interaction.guild_id, interaction.user, name)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=False)
            
        finally:
            reset_economy_guild_id(token)"""

text = text.replace(old_gang_create, new_gang_create)

with open("cogs/gangs.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Done")

