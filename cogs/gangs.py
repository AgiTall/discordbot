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
                    # Leader leaves -> disband gang
                    members = gang["members"]
                    member_role_id = gang.get("discord_member_role_id")
                    leader_role_id = gang.get("discord_leader_role_id")
                    
                    # Remove gang from all members
                    guild_data = economy_data.current()
                    for mem_id in members:
                        mem_account = guild_data["users"].get(str(mem_id))
                        if mem_account and mem_account.get("gang_name") == gang_name:
                            mem_account["gang_name"] = None
                    del gangs[gang_name]
                    save_economy()
                    
                    if member_role_id:
                        role = interaction.guild.get_role(member_role_id)
                        if role:
                            try: await role.delete()
                            except: pass
                    if leader_role_id:
                        role = interaction.guild.get_role(leader_role_id)
                        if role:
                            try: await role.delete()
                            except: pass
                            
                    await interaction.response.send_message(f"Лидер покинул банду. Банда **{gang_name}** была распущена, общак сгорел.")
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

async def setup(bot):
    await bot.add_cog(GangsCog(bot))
