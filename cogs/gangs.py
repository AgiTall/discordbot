import discord
from discord import app_commands
from discord.ext import commands
import math
import random
from typing import Literal, Optional
from datetime import datetime, timedelta

from bot import (
    economy_lock,
    economy_data,
    get_account,
    get_gold_emoji,
    get_cash_emoji,
    save_economy,
    format_money_plain,
    now_local,
    parse_local_datetime,
    set_economy_guild_id,
    reset_economy_guild_id
)

GANG_CREATE_COST = 50  # 50 gold
GANG_ROB_COOLDOWN_HOURS = 6

# Transient invites dict: guild_id -> user_id -> gang_name
GANG_INVITES = {}

def get_gangs(guild_id: int):
    guild_data = economy_data.current()
    return guild_data.setdefault("gangs", {})

def user_in_gang(account):
    return account.get("gang_name")

class GangSetupModal(discord.ui.Modal, title='Данные для агитации'):
    logo_url = discord.ui.TextInput(label='Логотип (URL)', placeholder='https://...', required=False)
    bg_url = discord.ui.TextInput(label='Фон (URL)', placeholder='https://...', required=False)
    description = discord.ui.TextInput(label='Что мы предлагаем? (Описание)', style=discord.TextStyle.paragraph, max_length=1000, required=True)
    criteria = discord.ui.TextInput(label='Критерии отбора', style=discord.TextStyle.paragraph, max_length=1000, required=True)

    def __init__(self, gang_name: str, hex_color: str, leader_title: str):
        super().__init__()
        self.gang_name = gang_name
        self.hex_color = hex_color
        self.leader_title = leader_title

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Создание банды",
            description="Вы собрали со всего дикого запада бродяг и кочевников чтобы работать сообща? Тогда вашему вниманию предоставлена механика банд, изначальной стоимостью 50 слитков.",
            color=discord.Color.dark_gold()
        )
        view = GangCreateConfirmView(
            interaction.guild_id, interaction.user, self.gang_name, 
            self.hex_color, self.logo_url.value, self.bg_url.value, 
            self.description.value, self.criteria.value, self.leader_title
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class GangCreateConfirmView(discord.ui.View):
    def __init__(self, guild_id, member, gang_name, hex_color, logo_url, bg_url, description, criteria, leader_title):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.member = member
        self.gang_name = gang_name
        self.hex_color = hex_color
        self.logo_url = logo_url
        self.bg_url = bg_url
        self.description = description
        self.criteria = criteria
        self.leader_title = leader_title
        for child in self.children:
            if getattr(child, "custom_id", None) == "confirm_gang_create":
                child.label = f"Подтвердить покупку 50 {get_gold_emoji()}"

    @discord.ui.button(label="Подтвердить", style=discord.ButtonStyle.success, custom_id="confirm_gang_create")
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
                
                try:
                    color_int = int(self.hex_color.lstrip('#'), 16) if self.hex_color else 0
                except ValueError:
                    color_int = 0
                
                r = (color_int >> 16) & 255
                g = (color_int >> 8) & 255
                b = color_int & 255
                dark_r, dark_g, dark_b = int(r * 0.7), int(g * 0.7), int(b * 0.7)
                dark_color_int = (dark_r << 16) + (dark_g << 8) + dark_b

                leader_role = None
                member_role = None
                try:
                    role_title = self.leader_title if self.leader_title else "Лидер"
                    leader_role = await interaction.guild.create_role(name=f"{role_title} {self.gang_name}", color=discord.Color(dark_color_int))
                    member_role = await interaction.guild.create_role(name=self.gang_name, color=discord.Color(color_int))
                    await interaction.user.add_roles(leader_role, member_role)
                except discord.Forbidden:
                    await interaction.response.send_message("❌ У бота нет прав на создание или выдачу ролей. Убедитесь, что у бота есть право 'Управлять ролями'.", ephemeral=True)
                    return
                except discord.HTTPException:
                    pass

                guild_data = economy_data.current()
                agitation_channel_id = guild_data.get("agitation_channel_id")
                agitation_channel = None
                if agitation_channel_id:
                    agitation_channel = interaction.guild.get_channel(int(agitation_channel_id))
                
                if not agitation_channel:
                    try:
                        agitation_channel = await interaction.guild.create_text_channel("агитация-банд")
                        guild_data["agitation_channel_id"] = agitation_channel.id
                    except discord.Forbidden:
                        pass
                
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
                    "leader_role_name": role_title,
                    "member_role_name": "Участник",
                    "created_at": now_local().isoformat(timespec="seconds"),
                    "last_rob_at": None,
                    "hex_color": self.hex_color,
                    "logo_url": self.logo_url,
                    "bg_url": self.bg_url,
                    "description": self.description,
                    "criteria": self.criteria,
                    "discord_member_role_id": member_role.id if member_role else None,
                    "discord_leader_role_id": leader_role.id if leader_role else None
                }
                
                save_economy()
                
            if agitation_channel:
                embed = discord.Embed(title=self.gang_name, color=discord.Color(color_int))
                if self.logo_url:
                    embed.set_thumbnail(url=self.logo_url)
                if self.bg_url:
                    embed.set_image(url=self.bg_url)
                if self.description:
                    embed.add_field(name="Что мы предлагаем?", value=self.description, inline=False)
                if self.criteria:
                    embed.add_field(name="Критерии отбора:", value=self.criteria, inline=False)
                try:
                    mention_text = member_role.mention if member_role else f"**{self.gang_name}**"
                    await agitation_channel.send(content=mention_text, embed=embed)
                except Exception:
                    pass
                
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)
            await interaction.response.send_message(f"🏴‍☠️ Вы успешно основали банду **{self.gang_name}**! Поздравляем!")
        finally:
            reset_economy_guild_id(token)

class GangsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="set-agitation-channel", description="Установить канал для агитаций банд (только для админов)")
    @app_commands.default_permissions(administrator=True)
    async def set_agitation_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                guild_data = economy_data.current()
                guild_data["agitation_channel_id"] = channel.id
                save_economy()
            await interaction.response.send_message(f"✅ Канал для агитации успешно установлен на {channel.mention}!", ephemeral=True)
        finally:
            reset_economy_guild_id(token)

    @app_commands.command(name="gang-create", description="Создать банду (Цена: 50 Золота)")
    @app_commands.describe(name="Название банды", hex_color="Цвет (например #FF0000)", leader_title="Название роли лидера")
    @app_commands.choices(leader_title=[
        app_commands.Choice(name="Лидер", value="Лидер"),
        app_commands.Choice(name="Главарь", value="Главарь"),
        app_commands.Choice(name="Предводитель", value="Предводитель"),
        app_commands.Choice(name="Босс", value="Босс"),
        app_commands.Choice(name="Дон", value="Дон"),
        app_commands.Choice(name="Барон", value="Барон")
    ])
    async def gang_create(self, interaction: discord.Interaction, name: str, hex_color: str, leader_title: Optional[app_commands.Choice[str]] = None):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            name = name.strip()
            if len(name) < 3 or len(name) > 32:
                await interaction.response.send_message("Имя банды должно быть от 3 до 32 символов.", ephemeral=True)
                return
                
            hex_color = hex_color.strip()
            if not hex_color.startswith('#') or len(hex_color) not in (4, 7):
                await interaction.response.send_message("Цвет должен быть в формате HEX (например #FF0000).", ephemeral=True)
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
                    
            title_val = leader_title.value if leader_title else "Лидер"
            await interaction.response.send_modal(GangSetupModal(name, hex_color, title_val))
            
        finally:
            reset_economy_guild_id(token)
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
                description=f"Игрок **{interaction.user.display_name}** приглашает вас присоединиться к банде **{gang_name}** на сервере **{interaction.guild.name}**!\n\nНажмите кнопку ниже, чтобы принять или отклонить приглашение.",
                color=discord.Color.green()
            )
            view = GangInviteView(interaction.guild_id, gang_name, interaction.user.id, self.bot)
            try:
                await member.send(embed=embed, view=view)
                await interaction.response.send_message(f"✅ Вы успешно отправили приглашение {member.mention} в ЛС!", ephemeral=False)
            except discord.Forbidden:
                await interaction.response.send_message(f"⚠️ Приглашение отправлено, но у {member.mention} **закрыты личные сообщения**!\n\nИгроку придётся принять приглашение вручную, введя команду `/gang-join name:{gang_name}` здесь на сервере.", ephemeral=False)

        finally:
            reset_economy_guild_id(token)

    @app_commands.command(name="gang-join", description="Принять приглашение и вступить в банду")
    async def gang_join(self, interaction: discord.Interaction, gang_name: str):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            guild_invites = GANG_INVITES.get(interaction.guild_id, {})
            invited_gang = guild_invites.get(interaction.user.id)
            
            if not invited_gang or invited_gang.lower() != gang_name.lower():
                await interaction.response.send_message(f"У вас нет приглашения в банду **{gang_name}**.", ephemeral=True)
                return
                
            async with economy_lock:
                account = get_account(interaction.user.id)
                gangs = get_gangs(interaction.guild_id)
                
                if user_in_gang(account):
                    await interaction.response.send_message("Вы уже состоите в банде.", ephemeral=True)
                    return
                    
                actual_gang_name = None
                for g in gangs.keys():
                    if g.lower() == gang_name.lower():
                        actual_gang_name = g
                        break
                        
                if not actual_gang_name:
                    await interaction.response.send_message("Эта банда больше не существует.", ephemeral=True)
                    return
                    
                # Join
                account["gang_name"] = actual_gang_name
                gangs[actual_gang_name]["members"].append(interaction.user.id)
                save_economy()
                
                # Remove invite
                del GANG_INVITES[interaction.guild_id][interaction.user.id]
                
                role_id_to_add = gangs[actual_gang_name].get("discord_member_role_id")
                
            if role_id_to_add:
                role = interaction.guild.get_role(role_id_to_add)
                if role:
                    try:
                        await interaction.user.add_roles(role)
                    except discord.HTTPException:
                        pass
                
            await interaction.response.send_message(f"🤝 Вы успешно присоединились к банде **{actual_gang_name}**!")
        finally:
            reset_economy_guild_id(token)

    @app_commands.command(name="gang-leave", description="Покинуть свою банду")
    async def gang_leave(self, interaction: discord.Interaction):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                gang_name = user_in_gang(account)
                gangs = get_gangs(interaction.guild_id)
                
                if not gang_name or gang_name not in gangs:
                    await interaction.response.send_message("Вы не состоите в банде.", ephemeral=True)
                    return
                    
                gang = gangs[gang_name]
                if gang["leader"] == interaction.user.id:
                    await interaction.response.send_message(
                        "Вы лидер банды и не можете просто покинуть её.\n"
                        "Используйте `/gang-transfer` чтобы передать лидерство, "
                        "или `/gang-disband` чтобы распустить банду.",
                        ephemeral=True
                    )
                    return
                else:
                    gang["members"].remove(interaction.user.id)
                    account["gang_name"] = None
                    member_role_id = gang.get("discord_member_role_id")
                    save_economy()
                    
                    if member_role_id:
                        role = interaction.guild.get_role(member_role_id)
                        if role:
                            try: await interaction.user.remove_roles(role)
                            except: pass
                            
                    await interaction.response.send_message(f"Вы покинули банду **{gang_name}**.")
        finally:
            reset_economy_guild_id(token)

    @app_commands.command(name="gang-kick", description="Выгнать участника из банды (только для лидера)")
    async def gang_kick(self, interaction: discord.Interaction, member: discord.Member):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                gang_name = user_in_gang(account)
                gangs = get_gangs(interaction.guild_id)
                
                if not gang_name or gang_name not in gangs:
                    await interaction.response.send_message("Вы не состоите в банде.", ephemeral=True)
                    return
                    
                if gangs[gang_name]["leader"] != interaction.user.id:
                    await interaction.response.send_message("Только лидер может исключать игроков.", ephemeral=True)
                    return
                    
                if member.id == interaction.user.id:
                    await interaction.response.send_message("Вы не можете исключить самого себя. Используйте `/gang-leave`.", ephemeral=True)
                    return
                    
                target_account = get_account(member.id)
                if user_in_gang(target_account) != gang_name:
                    await interaction.response.send_message("Этот игрок не состоит в вашей банде.", ephemeral=True)
                    return
                    
                gangs[gang_name]["members"].remove(member.id)
                target_account["gang_name"] = None
                member_role_id = gangs[gang_name].get("discord_member_role_id")
                save_economy()
                
            if member_role_id:
                role = interaction.guild.get_role(member_role_id)
                if role:
                    try: await member.remove_roles(role)
                    except: pass
                
            await interaction.response.send_message(f"{member.mention} был исключен из банды **{gang_name}**.")
        finally:
            reset_economy_guild_id(token)

    @app_commands.command(name="gang-transfer", description="Передать лидерство в банде другому участнику (только для лидера)")
    @app_commands.describe(member="Участник, которому передается лидерство", leader_title="Новое название роли лидера")
    @app_commands.choices(leader_title=[
        app_commands.Choice(name="Лидер", value="Лидер"),
        app_commands.Choice(name="Главарь", value="Главарь"),
        app_commands.Choice(name="Предводитель", value="Предводитель"),
        app_commands.Choice(name="Босс", value="Босс"),
        app_commands.Choice(name="Дон", value="Дон"),
        app_commands.Choice(name="Барон", value="Барон")
    ])
    async def gang_transfer(self, interaction: discord.Interaction, member: discord.Member, leader_title: Optional[app_commands.Choice[str]] = None):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                gang_name = user_in_gang(account)
                gangs = get_gangs(interaction.guild_id)
                
                if not gang_name or gang_name not in gangs:
                    await interaction.response.send_message("Вы не состоите в банде.", ephemeral=True)
                    return
                    
                if gangs[gang_name]["leader"] != interaction.user.id:
                    await interaction.response.send_message("Только лидер может передать лидерство.", ephemeral=True)
                    return
                    
                if member.id == interaction.user.id:
                    await interaction.response.send_message("Вы уже являетесь лидером.", ephemeral=True)
                    return
                    
                if member.bot:
                    await interaction.response.send_message("Нельзя передать лидерство боту.", ephemeral=True)
                    return
                    
                target_account = get_account(member.id)
                if user_in_gang(target_account) != gang_name:
                    await interaction.response.send_message("Этот игрок не состоит в вашей банде.", ephemeral=True)
                    return
                    
                gangs[gang_name]["leader"] = member.id
                
                title_val = leader_title.value if leader_title else gangs[gang_name].get("leader_role_name", "Лидер")
                gangs[gang_name]["leader_role_name"] = title_val
                
                leader_role_id = gangs[gang_name].get("discord_leader_role_id")
                save_economy()
                
            if leader_role_id:
                role = interaction.guild.get_role(leader_role_id)
                if role:
                    try:
                        await interaction.user.remove_roles(role)
                        await member.add_roles(role)
                        if leader_title:
                            await role.edit(name=f"{title_val} {gang_name}")
                    except discord.Forbidden:
                        pass
                    except discord.HTTPException:
                        pass
                        
            await interaction.response.send_message(f"👑 Вы успешно передали лидерство банды **{gang_name}** игроку {member.mention}! Теперь он **{title_val}**.")
        finally:
            reset_economy_guild_id(token)

    @app_commands.command(name="gang-info", description="Статистика банды")
    async def gang_info(self, interaction: discord.Interaction, name: Optional[str] = None):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                gangs = get_gangs(interaction.guild_id)
                
                if not name:
                    account = get_account(interaction.user.id)
                    name = user_in_gang(account)
                    if not name:
                        await interaction.response.send_message("Вы не состоите в банде и не указали имя банды для поиска.", ephemeral=True)
                        return
                        
                actual_gang_name = None
                for g in gangs.keys():
                    if g.lower() == name.lower():
                        actual_gang_name = g
                        break
                        
                if not actual_gang_name:
                    await interaction.response.send_message(f"Банда **{name}** не найдена.", ephemeral=True)
                    return
                    
                gang = gangs[actual_gang_name]
                
                leader = interaction.guild.get_member(gang["leader"])
                leader_name = leader.display_name if leader else "Неизвестный"
                
                members_count = len(gang["members"])
                
                gang_id = gang.get("id", "N/A")
                leader_role = gang.get("leader_role_name", "Лидер")
                member_role = gang.get("member_role_name", "Участник")
                
                embed = discord.Embed(title=f"🏴‍☠️ Банда: {actual_gang_name} [#{gang_id}]", color=discord.Color.dark_red())
                embed.add_field(name=f"👑 {leader_role}", value=leader_name, inline=True)
                embed.add_field(name=f"👥 {member_role}ов", value=str(members_count), inline=True)
                embed.add_field(name="👥 Участников", value=str(members_count), inline=True)
                embed.add_field(name="⚔️ Влияние", value=str(gang.get("influence", 0)), inline=True)
                
                # Treasury
                embed.add_field(name="💰 Общак (Деньги)", value=f"{format_money_plain(gang['cash'])} {get_cash_emoji()}", inline=True)
                embed.add_field(name="🪙 Общак (Золото)", value=f"{gang['gold']} {get_gold_emoji()}", inline=True)
                
            await interaction.response.send_message(embed=embed)
        finally:
            reset_economy_guild_id(token)

    @app_commands.command(name="gang-set-roles", description="Настроить названия ролей в банде (только для лидера)")
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

    @app_commands.command(name="gang-deposit", description="Положить деньги или золото в общак банды")
    async def gang_deposit(self, interaction: discord.Interaction, currency: Literal["Деньги", "Золото"], amount: float):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            if amount <= 0:
                await interaction.response.send_message("Сумма должна быть больше нуля.", ephemeral=True)
                return
                
            async with economy_lock:
                account = get_account(interaction.user.id)
                gang_name = user_in_gang(account)
                gangs = get_gangs(interaction.guild_id)
                
                if not gang_name or gang_name not in gangs:
                    await interaction.response.send_message("Вы не состоите в банде.", ephemeral=True)
                    return
                    
                curr_key = "cash" if currency == "Деньги" else "gold"
                if account.get(curr_key, 0.0) < amount:
                    await interaction.response.send_message(f"Недостаточно средств. У вас {format_money_plain(account.get(curr_key, 0.0))}.", ephemeral=True)
                    return
                    
                account[curr_key] -= amount
                gangs[gang_name][curr_key] += amount
                save_economy()
                
                emoji = get_cash_emoji() if currency == "Деньги" else get_gold_emoji()
                await interaction.response.send_message(f"Вы пополнили общак банды **{gang_name}** на {amount} {emoji}.")
        finally:
            reset_economy_guild_id(token)

    @app_commands.command(name="gang-withdraw", description="Снять деньги из общака банды (только для лидера)")
    async def gang_withdraw(self, interaction: discord.Interaction, currency: Literal["Деньги", "Золото"], amount: float):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            if amount <= 0:
                await interaction.response.send_message("Сумма должна быть больше нуля.", ephemeral=True)
                return
                
            async with economy_lock:
                account = get_account(interaction.user.id)
                gang_name = user_in_gang(account)
                gangs = get_gangs(interaction.guild_id)
                
                if not gang_name or gang_name not in gangs:
                    await interaction.response.send_message("Вы не состоите в банде.", ephemeral=True)
                    return
                    
                gang = gangs[gang_name]
                if gang["leader"] != interaction.user.id:
                    await interaction.response.send_message("Только лидер может брать из общака.", ephemeral=True)
                    return
                    
                curr_key = "cash" if currency == "Деньги" else "gold"
                if gang.get(curr_key, 0.0) < amount:
                    await interaction.response.send_message(f"В общаке недостаточно средств. Там лежит {format_money_plain(gang.get(curr_key, 0.0))}.", ephemeral=True)
                    return
                    
                gang[curr_key] -= amount
                account[curr_key] += amount
                save_economy()
                
                emoji = get_cash_emoji() if currency == "Деньги" else get_gold_emoji()
                await interaction.response.send_message(f"Вы забрали из общака **{gang_name}** {amount} {emoji}.")
        finally:
            reset_economy_guild_id(token)

    @app_commands.command(name="gang-rob", description="Ограбить общак чужой банды (Шанс 30%, риск штрафа, кулдаун 6 часов)")
    async def gang_rob(self, interaction: discord.Interaction, target_gang: str):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                my_gang_name = user_in_gang(account)
                gangs = get_gangs(interaction.guild_id)
                
                if not my_gang_name or my_gang_name not in gangs:
                    await interaction.response.send_message("Вы должны состоять в банде, чтобы грабить.", ephemeral=True)
                    return
                    
                my_gang = gangs[my_gang_name]
                
                # Check cooldown
                last_rob = my_gang.get("last_rob_at")
                if last_rob:
                    last_time = parse_local_datetime(last_rob)
                    now = now_local()
                    diff = (now - last_time).total_seconds()
                    if diff < GANG_ROB_COOLDOWN_HOURS * 3600:
                        remaining = int(GANG_ROB_COOLDOWN_HOURS * 3600 - diff)
                        hours, remainder = divmod(remaining, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        await interaction.response.send_message(f"Ваша банда залегла на дно. Следующее ограбление через: **{hours} ч. {minutes} м.**", ephemeral=True)
                        return
                        
                actual_target_gang = None
                for g in gangs.keys():
                    if g.lower() == target_gang.lower():
                        actual_target_gang = g
                        break
                        
                if not actual_target_gang:
                    await interaction.response.send_message(f"Банда **{target_gang}** не найдена.", ephemeral=True)
                    return
                    
                if actual_target_gang == my_gang_name:
                    await interaction.response.send_message("Нельзя грабить собственную банду!", ephemeral=True)
                    return
                    
                target = gangs[actual_target_gang]
                if target["cash"] < 100:
                    await interaction.response.send_message(f"Общак банды **{actual_target_gang}** пуст или в нем слишком мало денег.", ephemeral=True)
                    return
                    
                # Setup robbery
                my_gang["last_rob_at"] = now_local().isoformat(timespec="seconds")
                
                success_chance = 30 # 30% chance
                roll = random.randint(1, 100)
                
                if roll <= success_chance:
                    # Success
                    stolen_percent = random.uniform(0.10, 0.20) # 10-20%
                    stolen_amount = int(target["cash"] * stolen_percent)
                    target["cash"] -= stolen_amount
                    my_gang["cash"] += stolen_amount
                    
                    # Influence changes
                    my_gang["influence"] = my_gang.get("influence", 0) + 10
                    target["influence"] = max(0, target.get("influence", 0) - 5)
                    
                    save_economy()
                    await interaction.response.send_message(f"🔫 **ОГРАБЛЕНИЕ УДАЛОСЬ!** Банда **{my_gang_name}** успешно обчистила **{actual_target_gang}** на **{stolen_amount} {get_cash_emoji()}**! Влияние выросло!")
                else:
                    # Fail
                    fine_amount = int(my_gang["cash"] * 0.10) # 10% fine from own treasury
                    if fine_amount > 0:
                        my_gang["cash"] -= fine_amount
                        save_economy()
                        await interaction.response.send_message(f"🚨 **ПРОВАЛ!** Ограбление пошло не по плану. Ваша банда потеряла **{fine_amount} {get_cash_emoji()}** из своего общака во время побега от шерифов.")
                    else:
                        save_economy()
                        await interaction.response.send_message(f"🚨 **ПРОВАЛ!** Ограбление сорвалось, но ваш общак был пуст, так что вы ничего не потеряли (кроме репутации).")
        finally:
            reset_economy_guild_id(token)

    @app_commands.command(name="admin-set-gang-leader", description="Админ: Установить лидера для выбранной банды")
    @app_commands.describe(gang_name="Название банды", member="Новый лидер банды")
    @app_commands.default_permissions(administrator=True)
    async def admin_set_gang_leader(self, interaction: discord.Interaction, gang_name: str, member: discord.Member):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                gangs = get_gangs(interaction.guild_id)

                if gang_name not in gangs:
                    await interaction.response.send_message(f"Банда '{gang_name}' не найдена.", ephemeral=True)
                    return

                if member.bot:
                    await interaction.response.send_message("Нельзя передать лидерство боту.", ephemeral=True)
                    return

                target_account = get_account(member.id)
                old_gang = user_in_gang(target_account)
                
                # Если игрок в другой банде, убираем его оттуда
                if old_gang and old_gang != gang_name and old_gang in gangs:
                    if member.id in gangs[old_gang]["members"]:
                        gangs[old_gang]["members"].remove(member.id)
                
                target_account["gang_name"] = gang_name
                if member.id not in gangs[gang_name]["members"]:
                    gangs[gang_name]["members"].append(member.id)
                
                old_leader_id = gangs[gang_name].get("leader")
                if old_leader_id == member.id:
                    await interaction.response.send_message("Этот игрок уже является лидером данной банды.", ephemeral=True)
                    return

                gangs[gang_name]["leader"] = member.id
                
                leader_role_id = gangs[gang_name].get("discord_leader_role_id")
                member_role_id = gangs[gang_name].get("discord_role_id")
                save_economy()
                
            if member_role_id:
                m_role = interaction.guild.get_role(member_role_id)
                if m_role:
                    try:
                        await member.add_roles(m_role)
                    except discord.Forbidden:
                        pass
                        
            if leader_role_id:
                l_role = interaction.guild.get_role(leader_role_id)
                if l_role:
                    try:
                        if old_leader_id:
                            old_leader = interaction.guild.get_member(old_leader_id)
                            if old_leader:
                                await old_leader.remove_roles(l_role)
                        await member.add_roles(l_role)
                    except discord.Forbidden:
                        pass
                        
            await interaction.response.send_message(f"✅ {member.mention} теперь является лидером банды **{gang_name}**!", ephemeral=True)
        finally:
            reset_economy_guild_id(token)


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

    # ── LEADER: gang-edit ──

    @app_commands.command(name="gang-edit", description="Редактировать данные вашей банды (название, цвет, лого, описание)")
    @app_commands.describe(bg_url="Новый фон (URL). Оставьте пустым, чтобы не менять.")
    async def gang_edit(self, interaction: discord.Interaction, bg_url: Optional[str] = None):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                gang_name = user_in_gang(account)
                gangs = get_gangs(interaction.guild_id)

                if not gang_name or gang_name not in gangs:
                    await interaction.response.send_message("Вы не состоите в банде.", ephemeral=True)
                    return

                if gangs[gang_name]["leader"] != interaction.user.id:
                    await interaction.response.send_message("Только лидер банды может её редактировать.", ephemeral=True)
                    return

                gang_data = gangs[gang_name]

            await interaction.response.send_modal(
                GangEditModal(gang_name, gang_data, interaction.guild_id, bg_url)
            )
        finally:
            reset_economy_guild_id(token)

    # ── LEADER: gang-disband ──

    @app_commands.command(name="gang-disband", description="Распустить вашу банду (необратимо, общак сгорает)")
    async def gang_disband(self, interaction: discord.Interaction):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                gang_name = user_in_gang(account)
                gangs = get_gangs(interaction.guild_id)

                if not gang_name or gang_name not in gangs:
                    await interaction.response.send_message("Вы не состоите в банде.", ephemeral=True)
                    return

                if gangs[gang_name]["leader"] != interaction.user.id:
                    await interaction.response.send_message("Только лидер банды может её распустить.", ephemeral=True)
                    return

                members_count = len(gangs[gang_name]["members"])
                cash = gangs[gang_name].get("cash", 0.0)
                gold = gangs[gang_name].get("gold", 0.0)

            embed = discord.Embed(
                title="⚠️ Роспуск банды",
                description=(
                    f"Вы действительно хотите распустить банду **{gang_name}**?\n\n"
                    f"👥 Участников: **{members_count}**\n"
                    f"💰 Общак: **{format_money_plain(cash)}** {get_cash_emoji()} / **{gold}** {get_gold_emoji()}\n\n"
                    "**Это действие необратимо!** Общак будет уничтожен, Discord-роли удалены."
                ),
                color=discord.Color.red()
            )
            view = GangDisbandConfirmView(interaction.guild_id, interaction.user.id, gang_name)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        finally:
            reset_economy_guild_id(token)

    # ── ADMIN: admin-gang-edit ──

    GANG_EDIT_FIELDS = [
        app_commands.Choice(name="Название", value="name"),
        app_commands.Choice(name="Цвет (HEX)", value="hex_color"),
        app_commands.Choice(name="Логотип (URL)", value="logo_url"),
        app_commands.Choice(name="Фон (URL)", value="bg_url"),
        app_commands.Choice(name="Описание", value="description"),
        app_commands.Choice(name="Критерии отбора", value="criteria"),
        app_commands.Choice(name="Название роли лидера", value="leader_role_name"),
        app_commands.Choice(name="Название роли участника", value="member_role_name"),
    ]

    @app_commands.command(name="admin-gang-edit", description="Админ: Изменить любое поле банды")
    @app_commands.describe(gang_name="Название банды", field="Что изменить", value="Новое значение")
    @app_commands.choices(field=GANG_EDIT_FIELDS)
    @app_commands.default_permissions(administrator=True)
    async def admin_gang_edit(self, interaction: discord.Interaction, gang_name: str, field: app_commands.Choice[str], value: str):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            value = value.strip()
            if not value:
                await interaction.response.send_message("Значение не может быть пустым.", ephemeral=True)
                return

            async with economy_lock:
                gangs = get_gangs(interaction.guild_id)

                if gang_name not in gangs:
                    await interaction.response.send_message(f"Банда **{gang_name}** не найдена.", ephemeral=True)
                    return

                gang = gangs[gang_name]
                field_key = field.value

                if field_key == "name":
                    new_name = value
                    if len(new_name) < 3 or len(new_name) > 32:
                        await interaction.response.send_message("Название должно быть от 3 до 32 символов.", ephemeral=True)
                        return
                    if new_name.lower() in (g.lower() for g in gangs.keys() if g != gang_name):
                        await interaction.response.send_message(f"Банда с именем **{new_name}** уже существует.", ephemeral=True)
                        return
                    # Переименование
                    gangs[new_name] = gangs.pop(gang_name)
                    guild_data = economy_data.current()
                    for mem_id in gang["members"]:
                        mem_account = guild_data["users"].get(str(mem_id))
                        if mem_account and mem_account.get("gang_name") == gang_name:
                            mem_account["gang_name"] = new_name
                    # Обновить Discord-роли
                    member_role_id = gang.get("discord_member_role_id")
                    leader_role_id = gang.get("discord_leader_role_id")
                    leader_title = gang.get("leader_role_name", "Лидер")
                    save_economy()

                    if member_role_id:
                        role = interaction.guild.get_role(member_role_id)
                        if role:
                            try: await role.edit(name=new_name)
                            except: pass
                    if leader_role_id:
                        role = interaction.guild.get_role(leader_role_id)
                        if role:
                            try: await role.edit(name=f"{leader_title} {new_name}")
                            except: pass

                elif field_key == "hex_color":
                    if not value.startswith('#') or len(value) not in (4, 7):
                        await interaction.response.send_message("Цвет должен быть в формате HEX (#FF0000).", ephemeral=True)
                        return
                    gang["hex_color"] = value
                    try:
                        color_int = int(value.lstrip('#'), 16)
                    except ValueError:
                        color_int = 0
                    # Обновить Discord-роли
                    member_role_id = gang.get("discord_member_role_id")
                    leader_role_id = gang.get("discord_leader_role_id")
                    save_economy()
                    if member_role_id:
                        role = interaction.guild.get_role(member_role_id)
                        if role:
                            try: await role.edit(color=discord.Color(color_int))
                            except: pass
                    if leader_role_id:
                        r = (color_int >> 16) & 255
                        g = (color_int >> 8) & 255
                        b = color_int & 255
                        dark_color_int = (int(r * 0.7) << 16) + (int(g * 0.7) << 8) + int(b * 0.7)
                        role = interaction.guild.get_role(leader_role_id)
                        if role:
                            try: await role.edit(color=discord.Color(dark_color_int))
                            except: pass

                elif field_key == "leader_role_name":
                    if len(value) > 30:
                        await interaction.response.send_message("Максимум 30 символов.", ephemeral=True)
                        return
                    gang["leader_role_name"] = value
                    leader_role_id = gang.get("discord_leader_role_id")
                    save_economy()
                    if leader_role_id:
                        role = interaction.guild.get_role(leader_role_id)
                        if role:
                            try: await role.edit(name=f"{value} {gang_name}")
                            except: pass

                elif field_key == "member_role_name":
                    if len(value) > 30:
                        await interaction.response.send_message("Максимум 30 символов.", ephemeral=True)
                        return
                    gang["member_role_name"] = value
                    save_economy()

                else:
                    # logo_url, bg_url, description, criteria
                    gang[field_key] = value
                    save_economy()

            await interaction.response.send_message(
                f"✅ Поле **{field.name}** банды **{gang_name}** обновлено на: `{value[:100]}`",
                ephemeral=True
            )
        finally:
            reset_economy_guild_id(token)

    # ── ADMIN: admin-gang-disband ──

    @app_commands.command(name="admin-gang-disband", description="Админ: Принудительно распустить банду")
    @app_commands.describe(gang_name="Название банды")
    @app_commands.default_permissions(administrator=True)
    async def admin_gang_disband(self, interaction: discord.Interaction, gang_name: str):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                gangs = get_gangs(interaction.guild_id)
                if gang_name not in gangs:
                    await interaction.response.send_message(f"Банда **{gang_name}** не найдена.", ephemeral=True)
                    return

            embed = discord.Embed(
                title="⚠️ Принудительный роспуск банды",
                description=f"Вы действительно хотите распустить банду **{gang_name}**?\n\n**Это действие необратимо!**",
                color=discord.Color.red()
            )
            view = GangDisbandConfirmView(interaction.guild_id, interaction.user.id, gang_name)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        finally:
            reset_economy_guild_id(token)

    # ── ADMIN: admin-gang-list ──

    @app_commands.command(name="admin-gang-list", description="Админ: Список всех банд на сервере")
    @app_commands.default_permissions(administrator=True)
    async def admin_gang_list(self, interaction: discord.Interaction):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                gangs = get_gangs(interaction.guild_id)
                if not gangs:
                    await interaction.response.send_message("На сервере нет банд.", ephemeral=True)
                    return

                embed = discord.Embed(
                    title="🏴‍☠️ Список банд",
                    color=discord.Color.dark_red()
                )

                for name, gang in gangs.items():
                    gang_id = gang.get("id", "?")
                    leader_id = gang.get("leader")
                    leader = interaction.guild.get_member(leader_id) if leader_id else None
                    leader_name = leader.display_name if leader else f"ID:{leader_id}"
                    members_count = len(gang.get("members", []))
                    cash = gang.get("cash", 0.0)
                    gold = gang.get("gold", 0.0)
                    leader_title = gang.get("leader_role_name", "Лидер")

                    embed.add_field(
                        name=f"#{gang_id} — {name}",
                        value=(
                            f"👑 {leader_title}: **{leader_name}**\n"
                            f"👥 Участников: **{members_count}**\n"
                            f"💰 Общак: **{format_money_plain(cash)}** / **{gold}** зол.\n"
                            f"⚔️ Влияние: **{gang.get('influence', 0)}**"
                        ),
                        inline=False
                    )

            await interaction.response.send_message(embed=embed, ephemeral=True)
        finally:
            reset_economy_guild_id(token)

    # ── ADMIN: admin-gang-treasury ──

    @app_commands.command(name="admin-gang-treasury", description="Админ: Добавить или снять средства из общака банды")
    @app_commands.describe(
        gang_name="Название банды",
        action="Действие",
        currency="Валюта",
        amount="Сумма"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Добавить", value="add"),
            app_commands.Choice(name="Снять", value="remove"),
        ]
    )
    @app_commands.default_permissions(administrator=True)
    async def admin_gang_treasury(
        self, interaction: discord.Interaction,
        gang_name: str,
        action: app_commands.Choice[str],
        currency: Literal["Деньги", "Золото"],
        amount: float
    ):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            if amount <= 0:
                await interaction.response.send_message("Сумма должна быть больше нуля.", ephemeral=True)
                return

            async with economy_lock:
                gangs = get_gangs(interaction.guild_id)
                if gang_name not in gangs:
                    await interaction.response.send_message(f"Банда **{gang_name}** не найдена.", ephemeral=True)
                    return

                gang = gangs[gang_name]
                curr_key = "cash" if currency == "Деньги" else "gold"
                emoji = get_cash_emoji() if currency == "Деньги" else get_gold_emoji()

                if action.value == "add":
                    gang[curr_key] = gang.get(curr_key, 0.0) + amount
                    save_economy()
                    await interaction.response.send_message(
                        f"✅ В общак **{gang_name}** добавлено **{amount}** {emoji}. Итого: **{format_money_plain(gang[curr_key])}** {emoji}.",
                        ephemeral=True
                    )
                else:
                    current = gang.get(curr_key, 0.0)
                    if current < amount:
                        await interaction.response.send_message(
                            f"В общаке только **{format_money_plain(current)}** {emoji}.",
                            ephemeral=True
                        )
                        return
                    gang[curr_key] -= amount
                    save_economy()
                    await interaction.response.send_message(
                        f"✅ Из общака **{gang_name}** снято **{amount}** {emoji}. Остаток: **{format_money_plain(gang[curr_key])}** {emoji}.",
                        ephemeral=True
                    )
        finally:
            reset_economy_guild_id(token)

# ─── Вспомогательная функция роспуска банды ───

async def disband_gang(guild, gang_name, gangs):
    """Роспуск банды: очистка данных участников и удаление Discord-ролей."""
    gang = gangs[gang_name]
    members = gang.get("members", [])
    member_role_id = gang.get("discord_member_role_id")
    leader_role_id = gang.get("discord_leader_role_id")

    # Убираем банду у всех участников
    guild_data = economy_data.current()
    for mem_id in members:
        mem_account = guild_data["users"].get(str(mem_id))
        if mem_account and mem_account.get("gang_name") == gang_name:
            mem_account["gang_name"] = None
    del gangs[gang_name]
    save_economy()

    # Удаляем Discord-роли
    if member_role_id and guild:
        role = guild.get_role(member_role_id)
        if role:
            try: await role.delete()
            except: pass
    if leader_role_id and guild:
        role = guild.get_role(leader_role_id)
        if role:
            try: await role.delete()
            except: pass


# ─── Modal для редактирования банды ───

class GangEditModal(discord.ui.Modal, title='Редактирование банды'):
    gang_name_input = discord.ui.TextInput(
        label='Название банды',
        placeholder='Новое название (или оставьте текущее)',
        max_length=32,
        required=True
    )
    hex_color_input = discord.ui.TextInput(
        label='Цвет (HEX)',
        placeholder='#FF0000',
        max_length=7,
        required=False
    )
    logo_url_input = discord.ui.TextInput(
        label='Логотип (URL)',
        placeholder='https://...',
        required=False
    )
    description_input = discord.ui.TextInput(
        label='Описание',
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=False
    )
    criteria_input = discord.ui.TextInput(
        label='Критерии отбора',
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=False
    )

    def __init__(self, current_gang_name: str, gang_data: dict, guild_id: int, bg_url: Optional[str] = None):
        super().__init__()
        self.current_gang_name = current_gang_name
        self.guild_id = guild_id
        self.new_bg_url = bg_url  # bg_url передаётся как параметр команды

        # Заполняем текущими значениями
        self.gang_name_input.default = current_gang_name
        self.hex_color_input.default = gang_data.get("hex_color", "")
        self.logo_url_input.default = gang_data.get("logo_url", "")
        self.description_input.default = gang_data.get("description", "")
        self.criteria_input.default = gang_data.get("criteria", "")

    async def on_submit(self, interaction: discord.Interaction):
        token = set_economy_guild_id(self.guild_id)
        try:
            new_name = self.gang_name_input.value.strip()
            new_color = self.hex_color_input.value.strip() if self.hex_color_input.value else None
            new_logo = self.logo_url_input.value.strip() if self.logo_url_input.value else None
            new_desc = self.description_input.value.strip() if self.description_input.value else None
            new_criteria = self.criteria_input.value.strip() if self.criteria_input.value else None

            if len(new_name) < 3 or len(new_name) > 32:
                await interaction.response.send_message("Название банды должно быть от 3 до 32 символов.", ephemeral=True)
                return

            if new_color and (not new_color.startswith('#') or len(new_color) not in (4, 7)):
                await interaction.response.send_message("Цвет должен быть в формате HEX (например #FF0000).", ephemeral=True)
                return

            async with economy_lock:
                gangs = get_gangs(self.guild_id)

                if self.current_gang_name not in gangs:
                    await interaction.response.send_message("Банда больше не существует.", ephemeral=True)
                    return

                gang = gangs[self.current_gang_name]

                # Проверка уникальности нового имени
                name_changed = new_name != self.current_gang_name
                if name_changed:
                    if new_name.lower() in (g.lower() for g in gangs.keys() if g != self.current_gang_name):
                        await interaction.response.send_message(f"Банда с именем **{new_name}** уже существует.", ephemeral=True)
                        return

                # Обновляем данные
                if new_logo is not None:
                    gang["logo_url"] = new_logo
                if new_desc is not None:
                    gang["description"] = new_desc
                if new_criteria is not None:
                    gang["criteria"] = new_criteria
                if self.new_bg_url is not None:
                    gang["bg_url"] = self.new_bg_url

                color_changed = False
                color_int = 0
                if new_color:
                    gang["hex_color"] = new_color
                    try:
                        color_int = int(new_color.lstrip('#'), 16)
                    except ValueError:
                        color_int = 0
                    color_changed = True

                # Переименование: перенос данных в новый ключ
                if name_changed:
                    gangs[new_name] = gangs.pop(self.current_gang_name)
                    # Обновить gang_name у всех участников
                    guild_data = economy_data.current()
                    for mem_id in gang["members"]:
                        mem_account = guild_data["users"].get(str(mem_id))
                        if mem_account and mem_account.get("gang_name") == self.current_gang_name:
                            mem_account["gang_name"] = new_name

                member_role_id = gang.get("discord_member_role_id")
                leader_role_id = gang.get("discord_leader_role_id")
                leader_title = gang.get("leader_role_name", "Лидер")
                save_economy()

            # Обновить Discord-роли
            changes = []
            if name_changed:
                if member_role_id:
                    role = interaction.guild.get_role(member_role_id)
                    if role:
                        try: await role.edit(name=new_name)
                        except: pass
                if leader_role_id:
                    role = interaction.guild.get_role(leader_role_id)
                    if role:
                        try: await role.edit(name=f"{leader_title} {new_name}")
                        except: pass
                changes.append(f"Название: **{new_name}**")

            if color_changed:
                if member_role_id:
                    role = interaction.guild.get_role(member_role_id)
                    if role:
                        try: await role.edit(color=discord.Color(color_int))
                        except: pass
                if leader_role_id:
                    r = (color_int >> 16) & 255
                    g = (color_int >> 8) & 255
                    b = color_int & 255
                    dark_color_int = (int(r * 0.7) << 16) + (int(g * 0.7) << 8) + int(b * 0.7)
                    role = interaction.guild.get_role(leader_role_id)
                    if role:
                        try: await role.edit(color=discord.Color(dark_color_int))
                        except: pass
                changes.append(f"Цвет: **{new_color}**")

            if new_logo is not None:
                changes.append("Логотип обновлён")
            if new_desc is not None:
                changes.append("Описание обновлено")
            if new_criteria is not None:
                changes.append("Критерии обновлены")
            if self.new_bg_url is not None:
                changes.append("Фон обновлён")

            summary = "\n".join(f"• {c}" for c in changes) if changes else "Ничего не изменено."
            await interaction.response.send_message(f"✅ Банда обновлена:\n{summary}", ephemeral=True)
        finally:
            reset_economy_guild_id(token)


# ─── View для подтверждения роспуска ───

class GangDisbandConfirmView(discord.ui.View):
    def __init__(self, guild_id, user_id, gang_name):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.user_id = user_id
        self.gang_name = gang_name

    @discord.ui.button(label="Подтвердить роспуск", style=discord.ButtonStyle.danger, emoji="💀")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Это не ваш запрос!", ephemeral=True)
            return

        token = set_economy_guild_id(self.guild_id)
        try:
            async with economy_lock:
                gangs = get_gangs(self.guild_id)
                if self.gang_name not in gangs:
                    await interaction.response.send_message("Банда уже не существует.", ephemeral=True)
                    return

                await disband_gang(interaction.guild, self.gang_name, gangs)

            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)
            await interaction.response.send_message(f"💀 Банда **{self.gang_name}** распущена. Общак сгорел.")
        finally:
            reset_economy_guild_id(token)

    @discord.ui.button(label="Отмена", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Это не ваш запрос!", ephemeral=True)
            return
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message("Роспуск отменён.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(GangsCog(bot))
