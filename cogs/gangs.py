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


# ══════════════════════════════════════════════════════════
#  GANG CREATION (modal + confirm view)
# ══════════════════════════════════════════════════════════

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
            description=f"Вы собрали со всего дикого запада бродяг и кочевников чтобы работать сообща? Тогда вашему вниманию предоставлена механика банд, изначальной стоимостью 50 {get_gold_emoji()}.",
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


# ══════════════════════════════════════════════════════════
#  INVITE VIEW (accept/decline buttons sent to DM)
# ══════════════════════════════════════════════════════════

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
                member_role_id = gangs[self.gang_name].get("discord_member_role_id")
                save_economy()

            # Выдаем роль
            if member_role_id:
                guild = self.bot.get_guild(self.guild_id)
                if guild:
                    member = guild.get_member(interaction.user.id)
                    if member:
                        role = guild.get_role(member_role_id)
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


# ══════════════════════════════════════════════════════════
#  DISBAND CONFIRM VIEW
# ══════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════
#  HELPER: disband_gang
# ══════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════
#  LEADER PANEL — Modals
# ══════════════════════════════════════════════════════════

class GangEditNameModal(discord.ui.Modal, title='Изменить название банды'):
    new_name = discord.ui.TextInput(
        label='Новое название', placeholder='Введите новое название банды',
        min_length=3, max_length=32, required=True
    )

    def __init__(self, guild_id: int, gang_name: str):
        super().__init__()
        self.guild_id = guild_id
        self.gang_name = gang_name
        self.new_name.default = gang_name

    async def on_submit(self, interaction: discord.Interaction):
        token = set_economy_guild_id(self.guild_id)
        try:
            new_name = self.new_name.value.strip()
            if len(new_name) < 3 or len(new_name) > 32:
                await interaction.response.send_message("Название должно быть от 3 до 32 символов.", ephemeral=True)
                return

            async with economy_lock:
                gangs = get_gangs(self.guild_id)
                if self.gang_name not in gangs:
                    await interaction.response.send_message("Банда больше не существует.", ephemeral=True)
                    return
                gang = gangs[self.gang_name]
                if gang["leader"] != interaction.user.id:
                    await interaction.response.send_message("Вы больше не лидер этой банды.", ephemeral=True)
                    return

                if new_name == self.gang_name:
                    await interaction.response.send_message("Название не изменилось.", ephemeral=True)
                    return

                if new_name.lower() in (g.lower() for g in gangs.keys() if g != self.gang_name):
                    await interaction.response.send_message(f"Банда с именем **{new_name}** уже существует.", ephemeral=True)
                    return

                # Переименование
                gangs[new_name] = gangs.pop(self.gang_name)
                guild_data = economy_data.current()
                for mem_id in gang["members"]:
                    mem_account = guild_data["users"].get(str(mem_id))
                    if mem_account and mem_account.get("gang_name") == self.gang_name:
                        mem_account["gang_name"] = new_name

                member_role_id = gang.get("discord_member_role_id")
                leader_role_id = gang.get("discord_leader_role_id")
                leader_title = gang.get("leader_role_name", "Лидер")
                save_economy()

            # Обновить Discord-роли
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

            await interaction.response.send_message(f"✅ Банда переименована: **{self.gang_name}** → **{new_name}**", ephemeral=True)
        finally:
            reset_economy_guild_id(token)


class GangEditIconModal(discord.ui.Modal, title='Изменить иконку банды'):
    icon_url = discord.ui.TextInput(
        label='URL иконки/логотипа', placeholder='https://...',
        required=True
    )

    def __init__(self, guild_id: int, gang_name: str, current_url: str = ""):
        super().__init__()
        self.guild_id = guild_id
        self.gang_name = gang_name
        if current_url:
            self.icon_url.default = current_url

    async def on_submit(self, interaction: discord.Interaction):
        token = set_economy_guild_id(self.guild_id)
        try:
            async with economy_lock:
                gangs = get_gangs(self.guild_id)
                if self.gang_name not in gangs:
                    await interaction.response.send_message("Банда больше не существует.", ephemeral=True)
                    return
                gang = gangs[self.gang_name]
                if gang["leader"] != interaction.user.id:
                    await interaction.response.send_message("Вы больше не лидер этой банды.", ephemeral=True)
                    return
                gang["logo_url"] = self.icon_url.value.strip()
                save_economy()
            await interaction.response.send_message("✅ Иконка банды обновлена!", ephemeral=True)
        finally:
            reset_economy_guild_id(token)


class GangEditBannerModal(discord.ui.Modal, title='Изменить баннер банды'):
    banner_url = discord.ui.TextInput(
        label='URL баннера/фона', placeholder='https://...',
        required=True
    )

    def __init__(self, guild_id: int, gang_name: str, current_url: str = ""):
        super().__init__()
        self.guild_id = guild_id
        self.gang_name = gang_name
        if current_url:
            self.banner_url.default = current_url

    async def on_submit(self, interaction: discord.Interaction):
        token = set_economy_guild_id(self.guild_id)
        try:
            async with economy_lock:
                gangs = get_gangs(self.guild_id)
                if self.gang_name not in gangs:
                    await interaction.response.send_message("Банда больше не существует.", ephemeral=True)
                    return
                gang = gangs[self.gang_name]
                if gang["leader"] != interaction.user.id:
                    await interaction.response.send_message("Вы больше не лидер этой банды.", ephemeral=True)
                    return
                gang["bg_url"] = self.banner_url.value.strip()
                save_economy()
            await interaction.response.send_message("✅ Баннер банды обновлён!", ephemeral=True)
        finally:
            reset_economy_guild_id(token)


class GangEditDescModal(discord.ui.Modal, title='Изменить описание банды'):
    description_input = discord.ui.TextInput(
        label='Описание', style=discord.TextStyle.paragraph,
        max_length=1000, required=False
    )
    criteria_input = discord.ui.TextInput(
        label='Критерии отбора', style=discord.TextStyle.paragraph,
        max_length=1000, required=False
    )

    def __init__(self, guild_id: int, gang_name: str, current_desc: str = "", current_criteria: str = ""):
        super().__init__()
        self.guild_id = guild_id
        self.gang_name = gang_name
        if current_desc:
            self.description_input.default = current_desc
        if current_criteria:
            self.criteria_input.default = current_criteria

    async def on_submit(self, interaction: discord.Interaction):
        token = set_economy_guild_id(self.guild_id)
        try:
            async with economy_lock:
                gangs = get_gangs(self.guild_id)
                if self.gang_name not in gangs:
                    await interaction.response.send_message("Банда больше не существует.", ephemeral=True)
                    return
                gang = gangs[self.gang_name]
                if gang["leader"] != interaction.user.id:
                    await interaction.response.send_message("Вы больше не лидер этой банды.", ephemeral=True)
                    return
                if self.description_input.value:
                    gang["description"] = self.description_input.value.strip()
                if self.criteria_input.value:
                    gang["criteria"] = self.criteria_input.value.strip()
                save_economy()
            await interaction.response.send_message("✅ Описание и критерии обновлены!", ephemeral=True)
        finally:
            reset_economy_guild_id(token)


class GangEditColorModal(discord.ui.Modal, title='Изменить цвет банды'):
    hex_color = discord.ui.TextInput(
        label='HEX-цвет', placeholder='#FF0000',
        max_length=7, required=True
    )

    def __init__(self, guild_id: int, gang_name: str, current_color: str = ""):
        super().__init__()
        self.guild_id = guild_id
        self.gang_name = gang_name
        if current_color:
            self.hex_color.default = current_color

    async def on_submit(self, interaction: discord.Interaction):
        token = set_economy_guild_id(self.guild_id)
        try:
            color_val = self.hex_color.value.strip()
            if not color_val.startswith('#') or len(color_val) not in (4, 7):
                await interaction.response.send_message("Цвет должен быть в формате HEX (#FF0000).", ephemeral=True)
                return

            try:
                color_int = int(color_val.lstrip('#'), 16)
            except ValueError:
                await interaction.response.send_message("Некорректный HEX-цвет.", ephemeral=True)
                return

            async with economy_lock:
                gangs = get_gangs(self.guild_id)
                if self.gang_name not in gangs:
                    await interaction.response.send_message("Банда больше не существует.", ephemeral=True)
                    return
                gang = gangs[self.gang_name]
                if gang["leader"] != interaction.user.id:
                    await interaction.response.send_message("Вы больше не лидер этой банды.", ephemeral=True)
                    return
                gang["hex_color"] = color_val
                member_role_id = gang.get("discord_member_role_id")
                leader_role_id = gang.get("discord_leader_role_id")
                save_economy()

            # Обновить Discord-роли
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

            await interaction.response.send_message(f"✅ Цвет банды изменён на **{color_val}**!", ephemeral=True)
        finally:
            reset_economy_guild_id(token)


class GangInviteModal(discord.ui.Modal, title='Пригласить в банду'):
    member_input = discord.ui.TextInput(
        label='Участник (ID или @упоминание)', placeholder='123456789012345678',
        required=True
    )

    def __init__(self, guild_id: int, gang_name: str, bot):
        super().__init__()
        self.guild_id = guild_id
        self.gang_name = gang_name
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        token = set_economy_guild_id(self.guild_id)
        try:
            raw = self.member_input.value.strip()
            # Пытаемся извлечь ID из @упоминания (<@123456>) или просто числа
            member_id = None
            if raw.startswith('<@') and raw.endswith('>'):
                raw_id = raw[2:-1].lstrip('!')
                try:
                    member_id = int(raw_id)
                except ValueError:
                    pass
            else:
                try:
                    member_id = int(raw)
                except ValueError:
                    pass

            if not member_id:
                await interaction.response.send_message("❌ Неверный формат. Введите числовой ID пользователя или @упоминание.", ephemeral=True)
                return

            member = interaction.guild.get_member(member_id)
            if not member:
                await interaction.response.send_message("❌ Пользователь не найден на сервере.", ephemeral=True)
                return

            if member.bot:
                await interaction.response.send_message("❌ Нельзя приглашать ботов.", ephemeral=True)
                return

            async with economy_lock:
                account = get_account(interaction.user.id)
                gang_name = user_in_gang(account)
                gangs = get_gangs(self.guild_id)

                if not gang_name or gang_name not in gangs:
                    await interaction.response.send_message("Вы не состоите в банде.", ephemeral=True)
                    return

                if gangs[gang_name]["leader"] != interaction.user.id:
                    await interaction.response.send_message("Только лидер банды может приглашать.", ephemeral=True)
                    return

                target_account = get_account(member.id)
                if user_in_gang(target_account):
                    await interaction.response.send_message("Этот игрок уже состоит в банде.", ephemeral=True)
                    return

                guild_invites = GANG_INVITES.setdefault(self.guild_id, {})
                guild_invites[member.id] = gang_name

            embed = discord.Embed(
                title="Приглашение в банду",
                description=f"Игрок **{interaction.user.display_name}** приглашает вас присоединиться к банде **{gang_name}** на сервере **{interaction.guild.name}**!\n\nНажмите кнопку ниже, чтобы принять или отклонить приглашение.",
                color=discord.Color.green()
            )
            view = GangInviteView(self.guild_id, gang_name, interaction.user.id, self.bot)
            try:
                await member.send(embed=embed, view=view)
                await interaction.response.send_message(f"✅ Приглашение отправлено {member.mention} в ЛС!", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message(
                    f"⚠️ У {member.mention} **закрыты личные сообщения**!\n"
                    f"Игрок может вступить вручную: `/gang-join name:{gang_name}`",
                    ephemeral=True
                )
        finally:
            reset_economy_guild_id(token)


# ══════════════════════════════════════════════════════════
#  LEADER PANEL — Member Select (for kick / transfer)
# ══════════════════════════════════════════════════════════

class GangMemberSelect(discord.ui.Select):
    def __init__(self, members_list: list, action: str, guild_id: int, gang_name: str):
        self.action = action  # "kick" or "transfer"
        self.guild_id = guild_id
        self.gang_name = gang_name

        options = []
        for m_id, m_name in members_list[:25]:
            options.append(discord.SelectOption(label=m_name, value=str(m_id)))

        placeholder = "Выберите участника для исключения" if action == "kick" else "Выберите нового лидера"
        super().__init__(placeholder=placeholder, options=options)

    async def callback(self, interaction: discord.Interaction):
        token = set_economy_guild_id(self.guild_id)
        try:
            target_id = int(self.values[0])
            
            if self.action == "kick":
                await self._do_kick(interaction, target_id)
            elif self.action == "transfer":
                await self._do_transfer(interaction, target_id)
        finally:
            reset_economy_guild_id(token)

    async def _do_kick(self, interaction: discord.Interaction, target_id: int):
        async with economy_lock:
            gangs = get_gangs(self.guild_id)
            if self.gang_name not in gangs:
                await interaction.response.send_message("Банда больше не существует.", ephemeral=True)
                return
            gang = gangs[self.gang_name]
            if gang["leader"] != interaction.user.id:
                await interaction.response.send_message("Вы больше не лидер.", ephemeral=True)
                return
            if target_id == interaction.user.id:
                await interaction.response.send_message("Вы не можете исключить себя.", ephemeral=True)
                return

            target_account = get_account(target_id)
            if user_in_gang(target_account) != self.gang_name:
                await interaction.response.send_message("Этот игрок не состоит в вашей банде.", ephemeral=True)
                return

            gang["members"].remove(target_id)
            target_account["gang_name"] = None
            member_role_id = gang.get("discord_member_role_id")
            save_economy()

        target_member = interaction.guild.get_member(target_id)
        if member_role_id and target_member:
            role = interaction.guild.get_role(member_role_id)
            if role:
                try: await target_member.remove_roles(role)
                except: pass

        name = target_member.display_name if target_member else str(target_id)
        await interaction.response.send_message(f"👢 **{name}** исключён из банды **{self.gang_name}**.", ephemeral=True)

    async def _do_transfer(self, interaction: discord.Interaction, target_id: int):
        async with economy_lock:
            gangs = get_gangs(self.guild_id)
            if self.gang_name not in gangs:
                await interaction.response.send_message("Банда больше не существует.", ephemeral=True)
                return
            gang = gangs[self.gang_name]
            if gang["leader"] != interaction.user.id:
                await interaction.response.send_message("Вы больше не лидер.", ephemeral=True)
                return
            if target_id == interaction.user.id:
                await interaction.response.send_message("Вы уже являетесь лидером.", ephemeral=True)
                return

            target_account = get_account(target_id)
            if user_in_gang(target_account) != self.gang_name:
                await interaction.response.send_message("Этот игрок не состоит в вашей банде.", ephemeral=True)
                return

            gang["leader"] = target_id
            leader_role_id = gang.get("discord_leader_role_id")
            leader_title = gang.get("leader_role_name", "Лидер")
            save_economy()

        if leader_role_id:
            role = interaction.guild.get_role(leader_role_id)
            if role:
                try:
                    await interaction.user.remove_roles(role)
                    target_member = interaction.guild.get_member(target_id)
                    if target_member:
                        await target_member.add_roles(role)
                except: pass

        target_member = interaction.guild.get_member(target_id)
        name = target_member.mention if target_member else str(target_id)
        await interaction.response.send_message(f"👑 Лидерство передано {name}! Теперь он **{leader_title}** банды **{self.gang_name}**.", ephemeral=True)


class GangMemberSelectView(discord.ui.View):
    def __init__(self, members_list: list, action: str, guild_id: int, gang_name: str):
        super().__init__(timeout=120)
        self.add_item(GangMemberSelect(members_list, action, guild_id, gang_name))


# ══════════════════════════════════════════════════════════
#  LEADER PANEL — Main View with buttons
# ══════════════════════════════════════════════════════════

class GangLeaderView(discord.ui.View):
    def __init__(self, guild_id: int, gang_name: str, leader_id: int, bot):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.gang_name = gang_name
        self.leader_id = leader_id
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.leader_id:
            await interaction.response.send_message("Эта панель доступна только лидеру банды.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Участники", style=discord.ButtonStyle.primary, emoji="📋", row=0)
    async def members_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        token = set_economy_guild_id(self.guild_id)
        try:
            async with economy_lock:
                gangs = get_gangs(self.guild_id)
                if self.gang_name not in gangs:
                    await interaction.response.send_message("Банда больше не существует.", ephemeral=True)
                    return
                gang = gangs[self.gang_name]
                member_ids = gang["members"]
                leader_id = gang["leader"]
                leader_title = gang.get("leader_role_name", "Лидер")

            lines = []
            for i, mid in enumerate(member_ids, 1):
                member = interaction.guild.get_member(mid)
                name = member.mention if member else f"ID:{mid}"
                prefix = f"👑 {leader_title}" if mid == leader_id else f"`{i}.`"
                lines.append(f"{prefix} {name}")

            embed = discord.Embed(
                title=f"📋 Участники банды «{self.gang_name}»",
                description="\n".join(lines) if lines else "Пусто",
                color=discord.Color.blurple()
            )
            embed.set_footer(text=f"Всего: {len(member_ids)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        finally:
            reset_economy_guild_id(token)

    @discord.ui.button(label="Пригласить", style=discord.ButtonStyle.success, emoji="📨", row=0)
    async def invite_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        token = set_economy_guild_id(self.guild_id)
        try:
            gangs = get_gangs(self.guild_id)
            if self.gang_name not in gangs:
                await interaction.response.send_message("Банда больше не существует.", ephemeral=True)
                return
            await interaction.response.send_modal(GangInviteModal(self.guild_id, self.gang_name, self.bot))
        finally:
            reset_economy_guild_id(token)

    @discord.ui.button(label="Кик", style=discord.ButtonStyle.danger, emoji="👢", row=0)
    async def kick_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        token = set_economy_guild_id(self.guild_id)
        try:
            async with economy_lock:
                gangs = get_gangs(self.guild_id)
                if self.gang_name not in gangs:
                    await interaction.response.send_message("Банда больше не существует.", ephemeral=True)
                    return
                gang = gangs[self.gang_name]
                # Список участников БЕЗ лидера
                members_list = []
                for mid in gang["members"]:
                    if mid != gang["leader"]:
                        member = interaction.guild.get_member(mid)
                        name = member.display_name if member else f"ID:{mid}"
                        members_list.append((mid, name))

            if not members_list:
                await interaction.response.send_message("В банде нет других участников для исключения.", ephemeral=True)
                return

            view = GangMemberSelectView(members_list, "kick", self.guild_id, self.gang_name)
            await interaction.response.send_message("Выберите участника для исключения:", view=view, ephemeral=True)
        finally:
            reset_economy_guild_id(token)

    @discord.ui.button(label="Передать", style=discord.ButtonStyle.primary, emoji="🔄", row=0)
    async def transfer_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        token = set_economy_guild_id(self.guild_id)
        try:
            async with economy_lock:
                gangs = get_gangs(self.guild_id)
                if self.gang_name not in gangs:
                    await interaction.response.send_message("Банда больше не существует.", ephemeral=True)
                    return
                gang = gangs[self.gang_name]
                members_list = []
                for mid in gang["members"]:
                    if mid != gang["leader"]:
                        member = interaction.guild.get_member(mid)
                        name = member.display_name if member else f"ID:{mid}"
                        members_list.append((mid, name))

            if not members_list:
                await interaction.response.send_message("В банде нет других участников для передачи лидерства.", ephemeral=True)
                return

            view = GangMemberSelectView(members_list, "transfer", self.guild_id, self.gang_name)
            await interaction.response.send_message("Выберите нового лидера:", view=view, ephemeral=True)
        finally:
            reset_economy_guild_id(token)

    @discord.ui.button(label="Название", style=discord.ButtonStyle.secondary, emoji="✏️", row=1)
    async def name_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GangEditNameModal(self.guild_id, self.gang_name))

    @discord.ui.button(label="Иконка", style=discord.ButtonStyle.secondary, emoji="🖼️", row=1)
    async def icon_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        token = set_economy_guild_id(self.guild_id)
        try:
            gangs = get_gangs(self.guild_id)
            current_url = gangs.get(self.gang_name, {}).get("logo_url", "")
        finally:
            reset_economy_guild_id(token)
        await interaction.response.send_modal(GangEditIconModal(self.guild_id, self.gang_name, current_url))

    @discord.ui.button(label="Баннер", style=discord.ButtonStyle.secondary, emoji="🎨", row=1)
    async def banner_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        token = set_economy_guild_id(self.guild_id)
        try:
            gangs = get_gangs(self.guild_id)
            current_url = gangs.get(self.gang_name, {}).get("bg_url", "")
        finally:
            reset_economy_guild_id(token)
        await interaction.response.send_modal(GangEditBannerModal(self.guild_id, self.gang_name, current_url))

    @discord.ui.button(label="Описание", style=discord.ButtonStyle.secondary, emoji="📝", row=1)
    async def desc_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        token = set_economy_guild_id(self.guild_id)
        try:
            gangs = get_gangs(self.guild_id)
            gang = gangs.get(self.gang_name, {})
            current_desc = gang.get("description", "")
            current_criteria = gang.get("criteria", "")
        finally:
            reset_economy_guild_id(token)
        await interaction.response.send_modal(GangEditDescModal(self.guild_id, self.gang_name, current_desc, current_criteria))

    @discord.ui.button(label="Цвет", style=discord.ButtonStyle.secondary, emoji="🎨", row=1)
    async def color_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        token = set_economy_guild_id(self.guild_id)
        try:
            gangs = get_gangs(self.guild_id)
            current_color = gangs.get(self.gang_name, {}).get("hex_color", "")
        finally:
            reset_economy_guild_id(token)
        await interaction.response.send_modal(GangEditColorModal(self.guild_id, self.gang_name, current_color))

    @discord.ui.button(label="Распустить", style=discord.ButtonStyle.danger, emoji="💀", row=2)
    async def disband_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        token = set_economy_guild_id(self.guild_id)
        try:
            async with economy_lock:
                gangs = get_gangs(self.guild_id)
                if self.gang_name not in gangs:
                    await interaction.response.send_message("Банда больше не существует.", ephemeral=True)
                    return
                gang = gangs[self.gang_name]
                members_count = len(gang["members"])
                cash = gang.get("cash", 0.0)
                gold = gang.get("gold", 0.0)

            embed = discord.Embed(
                title="⚠️ Роспуск банды",
                description=(
                    f"Вы действительно хотите распустить банду **{self.gang_name}**?\n\n"
                    f"👥 Участников: **{members_count}**\n"
                    f"💰 Общак: **{format_money_plain(cash)}** {get_cash_emoji()} / **{gold}** {get_gold_emoji()}\n\n"
                    "**Это действие необратимо!** Общак будет уничтожен, Discord-роли удалены."
                ),
                color=discord.Color.red()
            )
            view = GangDisbandConfirmView(self.guild_id, interaction.user.id, self.gang_name)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        finally:
            reset_economy_guild_id(token)


# ══════════════════════════════════════════════════════════
#  ADMIN PANEL — Views & Modals
# ══════════════════════════════════════════════════════════

class AdminGangSelect(discord.ui.Select):
    """Select-меню для выбора банды (для всех админ-действий)."""
    def __init__(self, gangs_list: list, action: str, guild_id: int, bot):
        self.action = action
        self.guild_id = guild_id
        self.bot = bot
        options = []
        for gname, gdata in gangs_list[:25]:
            gang_id = gdata.get("id", "?")
            members_count = len(gdata.get("members", []))
            options.append(discord.SelectOption(
                label=f"#{gang_id} {gname}",
                description=f"Участников: {members_count}",
                value=gname
            ))

        placeholders = {
            "edit": "Выберите банду для редактирования",
            "set_leader": "Выберите банду",
            "add_member": "Выберите банду",
            "kick_member": "Выберите банду",
            "treasury": "Выберите банду",
            "disband": "Выберите банду для роспуска",
        }
        super().__init__(placeholder=placeholders.get(action, "Выберите банду"), options=options)

    async def callback(self, interaction: discord.Interaction):
        gang_name = self.values[0]
        token = set_economy_guild_id(self.guild_id)
        try:
            if self.action == "edit":
                await self._admin_edit(interaction, gang_name)
            elif self.action == "set_leader":
                await self._admin_set_leader(interaction, gang_name)
            elif self.action == "add_member":
                await self._admin_add_member(interaction, gang_name)
            elif self.action == "kick_member":
                await self._admin_kick_member(interaction, gang_name)
            elif self.action == "treasury":
                await self._admin_treasury(interaction, gang_name)
            elif self.action == "disband":
                await self._admin_disband(interaction, gang_name)
        finally:
            reset_economy_guild_id(token)

    async def _admin_edit(self, interaction, gang_name):
        gangs = get_gangs(self.guild_id)
        if gang_name not in gangs:
            await interaction.response.send_message("Банда не найдена.", ephemeral=True)
            return
        gang = gangs[gang_name]
        # Показываем панель редактирования (как у лидера, но без проверки лидерства)
        view = AdminGangEditView(self.guild_id, gang_name, interaction.user.id, self.bot)
        embed = _build_gang_info_embed(gang_name, gang, interaction.guild)
        embed.title = f"⚙️ Админ-редактирование: {gang_name}"
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _admin_set_leader(self, interaction, gang_name):
        gangs = get_gangs(self.guild_id)
        if gang_name not in gangs:
            await interaction.response.send_message("Банда не найдена.", ephemeral=True)
            return
        await interaction.response.send_modal(AdminSetLeaderModal(self.guild_id, gang_name))

    async def _admin_add_member(self, interaction, gang_name):
        gangs = get_gangs(self.guild_id)
        if gang_name not in gangs:
            await interaction.response.send_message("Банда не найдена.", ephemeral=True)
            return
        await interaction.response.send_modal(AdminAddMemberModal(self.guild_id, gang_name))

    async def _admin_kick_member(self, interaction, gang_name):
        async with economy_lock:
            gangs = get_gangs(self.guild_id)
            if gang_name not in gangs:
                await interaction.response.send_message("Банда не найдена.", ephemeral=True)
                return
            gang = gangs[gang_name]
            members_list = []
            for mid in gang["members"]:
                member = interaction.guild.get_member(mid)
                name = member.display_name if member else f"ID:{mid}"
                prefix = " 👑" if mid == gang["leader"] else ""
                members_list.append((mid, f"{name}{prefix}"))

        if not members_list:
            await interaction.response.send_message("В банде нет участников.", ephemeral=True)
            return
        view = AdminKickMemberSelectView(members_list, self.guild_id, gang_name)
        await interaction.response.send_message("Выберите участника для исключения:", view=view, ephemeral=True)

    async def _admin_treasury(self, interaction, gang_name):
        gangs = get_gangs(self.guild_id)
        if gang_name not in gangs:
            await interaction.response.send_message("Банда не найдена.", ephemeral=True)
            return
        await interaction.response.send_modal(AdminTreasuryModal(self.guild_id, gang_name))

    async def _admin_disband(self, interaction, gang_name):
        gangs = get_gangs(self.guild_id)
        if gang_name not in gangs:
            await interaction.response.send_message("Банда не найдена.", ephemeral=True)
            return
        embed = discord.Embed(
            title="⚠️ Принудительный роспуск банды",
            description=f"Вы действительно хотите распустить банду **{gang_name}**?\n\n**Это действие необратимо!**",
            color=discord.Color.red()
        )
        view = GangDisbandConfirmView(self.guild_id, interaction.user.id, gang_name)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class AdminGangSelectView(discord.ui.View):
    def __init__(self, gangs_list: list, action: str, guild_id: int, bot):
        super().__init__(timeout=120)
        self.add_item(AdminGangSelect(gangs_list, action, guild_id, bot))


# ── Admin Edit View (like leader panel but without leader check) ──

class AdminGangEditView(discord.ui.View):
    def __init__(self, guild_id: int, gang_name: str, admin_id: int, bot):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.gang_name = gang_name
        self.admin_id = admin_id
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.admin_id:
            await interaction.response.send_message("Эта панель не для вас.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Название", style=discord.ButtonStyle.secondary, emoji="✏️", row=0)
    async def name_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AdminEditNameModal(self.guild_id, self.gang_name))

    @discord.ui.button(label="Иконка", style=discord.ButtonStyle.secondary, emoji="🖼️", row=0)
    async def icon_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        token = set_economy_guild_id(self.guild_id)
        try:
            gangs = get_gangs(self.guild_id)
            current_url = gangs.get(self.gang_name, {}).get("logo_url", "")
        finally:
            reset_economy_guild_id(token)
        await interaction.response.send_modal(AdminEditFieldModal(self.guild_id, self.gang_name, "logo_url", "Иконка (URL)", current_url))

    @discord.ui.button(label="Баннер", style=discord.ButtonStyle.secondary, emoji="🎨", row=0)
    async def banner_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        token = set_economy_guild_id(self.guild_id)
        try:
            gangs = get_gangs(self.guild_id)
            current_url = gangs.get(self.gang_name, {}).get("bg_url", "")
        finally:
            reset_economy_guild_id(token)
        await interaction.response.send_modal(AdminEditFieldModal(self.guild_id, self.gang_name, "bg_url", "Баннер (URL)", current_url))

    @discord.ui.button(label="Описание", style=discord.ButtonStyle.secondary, emoji="📝", row=0)
    async def desc_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        token = set_economy_guild_id(self.guild_id)
        try:
            gangs = get_gangs(self.guild_id)
            gang = gangs.get(self.gang_name, {})
            current_desc = gang.get("description", "")
            current_criteria = gang.get("criteria", "")
        finally:
            reset_economy_guild_id(token)
        await interaction.response.send_modal(AdminEditDescModal(self.guild_id, self.gang_name, current_desc, current_criteria))

    @discord.ui.button(label="Цвет", style=discord.ButtonStyle.secondary, emoji="🎨", row=0)
    async def color_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        token = set_economy_guild_id(self.guild_id)
        try:
            gangs = get_gangs(self.guild_id)
            current_color = gangs.get(self.gang_name, {}).get("hex_color", "")
        finally:
            reset_economy_guild_id(token)
        await interaction.response.send_modal(AdminEditColorModal(self.guild_id, self.gang_name, current_color))


# ── Admin modals ──

class AdminEditNameModal(discord.ui.Modal, title='Админ: Изменить название'):
    new_name = discord.ui.TextInput(label='Новое название', min_length=3, max_length=32, required=True)

    def __init__(self, guild_id: int, gang_name: str):
        super().__init__()
        self.guild_id = guild_id
        self.gang_name = gang_name
        self.new_name.default = gang_name

    async def on_submit(self, interaction: discord.Interaction):
        token = set_economy_guild_id(self.guild_id)
        try:
            new_name = self.new_name.value.strip()
            if len(new_name) < 3 or len(new_name) > 32:
                await interaction.response.send_message("Название должно быть от 3 до 32 символов.", ephemeral=True)
                return

            async with economy_lock:
                gangs = get_gangs(self.guild_id)
                if self.gang_name not in gangs:
                    await interaction.response.send_message("Банда не найдена.", ephemeral=True)
                    return
                gang = gangs[self.gang_name]

                if new_name.lower() in (g.lower() for g in gangs.keys() if g != self.gang_name):
                    await interaction.response.send_message(f"Банда с именем **{new_name}** уже существует.", ephemeral=True)
                    return

                gangs[new_name] = gangs.pop(self.gang_name)
                guild_data = economy_data.current()
                for mem_id in gang["members"]:
                    mem_account = guild_data["users"].get(str(mem_id))
                    if mem_account and mem_account.get("gang_name") == self.gang_name:
                        mem_account["gang_name"] = new_name

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

            await interaction.response.send_message(f"✅ Банда переименована: **{self.gang_name}** → **{new_name}**", ephemeral=True)
        finally:
            reset_economy_guild_id(token)


class AdminEditFieldModal(discord.ui.Modal, title='Админ: Изменить поле'):
    field_value = discord.ui.TextInput(label='Значение', required=True)

    def __init__(self, guild_id: int, gang_name: str, field_key: str, field_label: str, current_value: str = ""):
        super().__init__()
        self.guild_id = guild_id
        self.gang_name = gang_name
        self.field_key = field_key
        self.field_value.label = field_label
        if current_value:
            self.field_value.default = current_value

    async def on_submit(self, interaction: discord.Interaction):
        token = set_economy_guild_id(self.guild_id)
        try:
            async with economy_lock:
                gangs = get_gangs(self.guild_id)
                if self.gang_name not in gangs:
                    await interaction.response.send_message("Банда не найдена.", ephemeral=True)
                    return
                gangs[self.gang_name][self.field_key] = self.field_value.value.strip()
                save_economy()
            await interaction.response.send_message(f"✅ Поле обновлено!", ephemeral=True)
        finally:
            reset_economy_guild_id(token)


class AdminEditDescModal(discord.ui.Modal, title='Админ: Описание и критерии'):
    description_input = discord.ui.TextInput(label='Описание', style=discord.TextStyle.paragraph, max_length=1000, required=False)
    criteria_input = discord.ui.TextInput(label='Критерии отбора', style=discord.TextStyle.paragraph, max_length=1000, required=False)

    def __init__(self, guild_id: int, gang_name: str, current_desc: str = "", current_criteria: str = ""):
        super().__init__()
        self.guild_id = guild_id
        self.gang_name = gang_name
        if current_desc:
            self.description_input.default = current_desc
        if current_criteria:
            self.criteria_input.default = current_criteria

    async def on_submit(self, interaction: discord.Interaction):
        token = set_economy_guild_id(self.guild_id)
        try:
            async with economy_lock:
                gangs = get_gangs(self.guild_id)
                if self.gang_name not in gangs:
                    await interaction.response.send_message("Банда не найдена.", ephemeral=True)
                    return
                gang = gangs[self.gang_name]
                if self.description_input.value:
                    gang["description"] = self.description_input.value.strip()
                if self.criteria_input.value:
                    gang["criteria"] = self.criteria_input.value.strip()
                save_economy()
            await interaction.response.send_message("✅ Описание и критерии обновлены!", ephemeral=True)
        finally:
            reset_economy_guild_id(token)


class AdminEditColorModal(discord.ui.Modal, title='Админ: Изменить цвет'):
    hex_color = discord.ui.TextInput(label='HEX-цвет', placeholder='#FF0000', max_length=7, required=True)

    def __init__(self, guild_id: int, gang_name: str, current_color: str = ""):
        super().__init__()
        self.guild_id = guild_id
        self.gang_name = gang_name
        if current_color:
            self.hex_color.default = current_color

    async def on_submit(self, interaction: discord.Interaction):
        token = set_economy_guild_id(self.guild_id)
        try:
            color_val = self.hex_color.value.strip()
            if not color_val.startswith('#') or len(color_val) not in (4, 7):
                await interaction.response.send_message("Цвет должен быть в формате HEX (#FF0000).", ephemeral=True)
                return
            try:
                color_int = int(color_val.lstrip('#'), 16)
            except ValueError:
                await interaction.response.send_message("Некорректный HEX-цвет.", ephemeral=True)
                return

            async with economy_lock:
                gangs = get_gangs(self.guild_id)
                if self.gang_name not in gangs:
                    await interaction.response.send_message("Банда не найдена.", ephemeral=True)
                    return
                gang = gangs[self.gang_name]
                gang["hex_color"] = color_val
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

            await interaction.response.send_message(f"✅ Цвет банды изменён на **{color_val}**!", ephemeral=True)
        finally:
            reset_economy_guild_id(token)


class AdminSetLeaderModal(discord.ui.Modal, title='Админ: Сменить лидера'):
    member_input = discord.ui.TextInput(label='ID нового лидера', placeholder='123456789012345678', required=True)

    def __init__(self, guild_id: int, gang_name: str):
        super().__init__()
        self.guild_id = guild_id
        self.gang_name = gang_name

    async def on_submit(self, interaction: discord.Interaction):
        token = set_economy_guild_id(self.guild_id)
        try:
            raw = self.member_input.value.strip()
            try:
                member_id = int(raw.strip('<@!>'))
            except ValueError:
                await interaction.response.send_message("Неверный формат ID.", ephemeral=True)
                return

            member = interaction.guild.get_member(member_id)
            if not member:
                await interaction.response.send_message("Пользователь не найден на сервере.", ephemeral=True)
                return
            if member.bot:
                await interaction.response.send_message("Нельзя передать лидерство боту.", ephemeral=True)
                return

            async with economy_lock:
                gangs = get_gangs(self.guild_id)
                if self.gang_name not in gangs:
                    await interaction.response.send_message("Банда не найдена.", ephemeral=True)
                    return
                gang = gangs[self.gang_name]

                target_account = get_account(member_id)
                old_gang = user_in_gang(target_account)

                # Если игрок в другой банде — не позволяем
                if old_gang and old_gang != self.gang_name and old_gang in gangs:
                    await interaction.response.send_message(f"Этот игрок состоит в другой банде: **{old_gang}**.", ephemeral=True)
                    return

                # Если не в банде — добавляем
                target_account["gang_name"] = self.gang_name
                if member_id not in gang["members"]:
                    gang["members"].append(member_id)

                old_leader_id = gang.get("leader")
                if old_leader_id == member_id:
                    await interaction.response.send_message("Этот игрок уже лидер.", ephemeral=True)
                    return

                gang["leader"] = member_id
                leader_role_id = gang.get("discord_leader_role_id")
                member_role_id = gang.get("discord_member_role_id")
                save_economy()

            if member_role_id:
                m_role = interaction.guild.get_role(member_role_id)
                if m_role:
                    try: await member.add_roles(m_role)
                    except: pass
            if leader_role_id:
                l_role = interaction.guild.get_role(leader_role_id)
                if l_role:
                    try:
                        if old_leader_id:
                            old_leader = interaction.guild.get_member(old_leader_id)
                            if old_leader:
                                await old_leader.remove_roles(l_role)
                        await member.add_roles(l_role)
                    except: pass

            await interaction.response.send_message(f"✅ {member.mention} теперь лидер банды **{self.gang_name}**!", ephemeral=True)
        finally:
            reset_economy_guild_id(token)


class AdminAddMemberModal(discord.ui.Modal, title='Админ: Добавить участника'):
    member_input = discord.ui.TextInput(label='ID участника', placeholder='123456789012345678', required=True)

    def __init__(self, guild_id: int, gang_name: str):
        super().__init__()
        self.guild_id = guild_id
        self.gang_name = gang_name

    async def on_submit(self, interaction: discord.Interaction):
        token = set_economy_guild_id(self.guild_id)
        try:
            raw = self.member_input.value.strip()
            try:
                member_id = int(raw.strip('<@!>'))
            except ValueError:
                await interaction.response.send_message("Неверный формат ID.", ephemeral=True)
                return

            member = interaction.guild.get_member(member_id)
            if not member:
                await interaction.response.send_message("Пользователь не найден на сервере.", ephemeral=True)
                return
            if member.bot:
                await interaction.response.send_message("Нельзя добавить бота.", ephemeral=True)
                return

            async with economy_lock:
                gangs = get_gangs(self.guild_id)
                if self.gang_name not in gangs:
                    await interaction.response.send_message("Банда не найдена.", ephemeral=True)
                    return
                gang = gangs[self.gang_name]
                target_account = get_account(member_id)
                old_gang = user_in_gang(target_account)

                if old_gang == self.gang_name:
                    await interaction.response.send_message("Игрок уже в этой банде.", ephemeral=True)
                    return

                if old_gang and old_gang != self.gang_name and old_gang in gangs:
                    if gangs[old_gang].get("leader") == member_id:
                        await interaction.response.send_message(f"⚠️ Игрок является лидером банды **{old_gang}**. Сначала смените лидера.", ephemeral=True)
                        return
                    gangs[old_gang]["members"].remove(member_id)

                target_account["gang_name"] = self.gang_name
                if member_id not in gang["members"]:
                    gang["members"].append(member_id)

                member_role_id = gang.get("discord_member_role_id")
                save_economy()

            if member_role_id:
                role = interaction.guild.get_role(member_role_id)
                if role:
                    try: await member.add_roles(role)
                    except: pass

            await interaction.response.send_message(f"✅ {member.mention} добавлен в банду **{self.gang_name}**!", ephemeral=True)
        finally:
            reset_economy_guild_id(token)


class AdminKickMemberSelect(discord.ui.Select):
    def __init__(self, members_list: list, guild_id: int, gang_name: str):
        self.guild_id = guild_id
        self.gang_name = gang_name
        options = [discord.SelectOption(label=name, value=str(mid)) for mid, name in members_list[:25]]
        super().__init__(placeholder="Выберите участника для исключения", options=options)

    async def callback(self, interaction: discord.Interaction):
        token = set_economy_guild_id(self.guild_id)
        try:
            target_id = int(self.values[0])
            async with economy_lock:
                gangs = get_gangs(self.guild_id)
                if self.gang_name not in gangs:
                    await interaction.response.send_message("Банда не найдена.", ephemeral=True)
                    return
                gang = gangs[self.gang_name]
                target_account = get_account(target_id)
                if user_in_gang(target_account) != self.gang_name:
                    await interaction.response.send_message("Этот игрок уже не в банде.", ephemeral=True)
                    return

                if target_id in gang["members"]:
                    gang["members"].remove(target_id)
                target_account["gang_name"] = None

                # Если кикнули лидера — банда остаётся без лидера (или назначить первого)
                was_leader = gang["leader"] == target_id
                if was_leader and gang["members"]:
                    gang["leader"] = gang["members"][0]

                member_role_id = gang.get("discord_member_role_id")
                leader_role_id = gang.get("discord_leader_role_id")
                save_economy()

            target_member = interaction.guild.get_member(target_id)
            if member_role_id and target_member:
                role = interaction.guild.get_role(member_role_id)
                if role:
                    try: await target_member.remove_roles(role)
                    except: pass
            if was_leader and leader_role_id and target_member:
                role = interaction.guild.get_role(leader_role_id)
                if role:
                    try: await target_member.remove_roles(role)
                    except: pass

            name = target_member.display_name if target_member else str(target_id)
            extra = " (был лидером)" if was_leader else ""
            await interaction.response.send_message(f"✅ **{name}**{extra} исключён из банды **{self.gang_name}**.", ephemeral=True)
        finally:
            reset_economy_guild_id(token)


class AdminKickMemberSelectView(discord.ui.View):
    def __init__(self, members_list, guild_id, gang_name):
        super().__init__(timeout=120)
        self.add_item(AdminKickMemberSelect(members_list, guild_id, gang_name))


class AdminTreasuryModal(discord.ui.Modal, title='Админ: Управление казной'):
    action_input = discord.ui.TextInput(label='Действие (add / remove)', placeholder='add', max_length=6, required=True)
    currency_input = discord.ui.TextInput(label='Валюта (cash / gold)', placeholder='cash', max_length=4, required=True)
    amount_input = discord.ui.TextInput(label='Сумма', placeholder='1000', required=True)

    def __init__(self, guild_id: int, gang_name: str):
        super().__init__()
        self.guild_id = guild_id
        self.gang_name = gang_name

    async def on_submit(self, interaction: discord.Interaction):
        token = set_economy_guild_id(self.guild_id)
        try:
            action = self.action_input.value.strip().lower()
            currency = self.currency_input.value.strip().lower()
            try:
                amount = float(self.amount_input.value.strip())
            except ValueError:
                await interaction.response.send_message("Некорректная сумма.", ephemeral=True)
                return

            if action not in ("add", "remove"):
                await interaction.response.send_message("Действие должно быть `add` или `remove`.", ephemeral=True)
                return
            if currency not in ("cash", "gold"):
                await interaction.response.send_message("Валюта должна быть `cash` или `gold`.", ephemeral=True)
                return
            if amount <= 0:
                await interaction.response.send_message("Сумма должна быть больше нуля.", ephemeral=True)
                return

            async with economy_lock:
                gangs = get_gangs(self.guild_id)
                if self.gang_name not in gangs:
                    await interaction.response.send_message("Банда не найдена.", ephemeral=True)
                    return
                gang = gangs[self.gang_name]
                emoji = get_cash_emoji() if currency == "cash" else get_gold_emoji()

                if action == "add":
                    gang[currency] = gang.get(currency, 0.0) + amount
                    save_economy()
                    await interaction.response.send_message(
                        f"✅ В общак **{self.gang_name}** добавлено **{amount}** {emoji}. Итого: **{format_money_plain(gang[currency])}** {emoji}.",
                        ephemeral=True
                    )
                else:
                    current = gang.get(currency, 0.0)
                    if current < amount:
                        await interaction.response.send_message(f"В общаке только **{format_money_plain(current)}** {emoji}.", ephemeral=True)
                        return
                    gang[currency] -= amount
                    save_economy()
                    await interaction.response.send_message(
                        f"✅ Из общака **{self.gang_name}** снято **{amount}** {emoji}. Остаток: **{format_money_plain(gang[currency])}** {emoji}.",
                        ephemeral=True
                    )
        finally:
            reset_economy_guild_id(token)


class AdminSetAgitationChannelView(discord.ui.View):
    def __init__(self, guild_id: int, admin_id: int):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.admin_id = admin_id
        self.add_item(AdminChannelSelect(guild_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.admin_id:
            await interaction.response.send_message("Эта панель не для вас.", ephemeral=True)
            return False
        return True


class AdminChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        super().__init__(placeholder="Выберите канал для агитации", channel_types=[discord.ChannelType.text])

    async def callback(self, interaction: discord.Interaction):
        token = set_economy_guild_id(self.guild_id)
        try:
            channel = self.values[0]
            async with economy_lock:
                guild_data = economy_data.current()
                guild_data["agitation_channel_id"] = channel.id
                save_economy()
            await interaction.response.send_message(f"✅ Канал для агитации установлен: {channel.mention}", ephemeral=True)
        finally:
            reset_economy_guild_id(token)


# ── Admin Main Panel View ──

class GangAdminView(discord.ui.View):
    def __init__(self, guild_id: int, admin_id: int, bot):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.admin_id = admin_id
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.admin_id:
            await interaction.response.send_message("Эта панель доступна только администратору.", ephemeral=True)
            return False
        return True

    def _get_gangs_list(self):
        gangs = get_gangs(self.guild_id)
        return list(gangs.items())

    @discord.ui.button(label="Список банд", style=discord.ButtonStyle.primary, emoji="📋", row=0)
    async def list_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        token = set_economy_guild_id(self.guild_id)
        try:
            async with economy_lock:
                gangs = get_gangs(self.guild_id)
                if not gangs:
                    await interaction.response.send_message("На сервере нет банд.", ephemeral=True)
                    return

                embed = discord.Embed(title="🏴‍☠️ Список банд", color=discord.Color.dark_red())
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

    @discord.ui.button(label="Редактировать", style=discord.ButtonStyle.secondary, emoji="✏️", row=0)
    async def edit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        token = set_economy_guild_id(self.guild_id)
        try:
            gangs_list = self._get_gangs_list()
            if not gangs_list:
                await interaction.response.send_message("На сервере нет банд.", ephemeral=True)
                return
            view = AdminGangSelectView(gangs_list, "edit", self.guild_id, self.bot)
            await interaction.response.send_message("Выберите банду для редактирования:", view=view, ephemeral=True)
        finally:
            reset_economy_guild_id(token)

    @discord.ui.button(label="Сменить лидера", style=discord.ButtonStyle.primary, emoji="👑", row=0)
    async def set_leader_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        token = set_economy_guild_id(self.guild_id)
        try:
            gangs_list = self._get_gangs_list()
            if not gangs_list:
                await interaction.response.send_message("На сервере нет банд.", ephemeral=True)
                return
            view = AdminGangSelectView(gangs_list, "set_leader", self.guild_id, self.bot)
            await interaction.response.send_message("Выберите банду:", view=view, ephemeral=True)
        finally:
            reset_economy_guild_id(token)

    @discord.ui.button(label="Добавить участника", style=discord.ButtonStyle.success, emoji="➕", row=1)
    async def add_member_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        token = set_economy_guild_id(self.guild_id)
        try:
            gangs_list = self._get_gangs_list()
            if not gangs_list:
                await interaction.response.send_message("На сервере нет банд.", ephemeral=True)
                return
            view = AdminGangSelectView(gangs_list, "add_member", self.guild_id, self.bot)
            await interaction.response.send_message("Выберите банду:", view=view, ephemeral=True)
        finally:
            reset_economy_guild_id(token)

    @discord.ui.button(label="Кикнуть участника", style=discord.ButtonStyle.danger, emoji="👢", row=1)
    async def kick_member_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        token = set_economy_guild_id(self.guild_id)
        try:
            gangs_list = self._get_gangs_list()
            if not gangs_list:
                await interaction.response.send_message("На сервере нет банд.", ephemeral=True)
                return
            view = AdminGangSelectView(gangs_list, "kick_member", self.guild_id, self.bot)
            await interaction.response.send_message("Выберите банду:", view=view, ephemeral=True)
        finally:
            reset_economy_guild_id(token)

    @discord.ui.button(label="Казна", style=discord.ButtonStyle.secondary, emoji="💰", row=1)
    async def treasury_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        token = set_economy_guild_id(self.guild_id)
        try:
            gangs_list = self._get_gangs_list()
            if not gangs_list:
                await interaction.response.send_message("На сервере нет банд.", ephemeral=True)
                return
            view = AdminGangSelectView(gangs_list, "treasury", self.guild_id, self.bot)
            await interaction.response.send_message("Выберите банду:", view=view, ephemeral=True)
        finally:
            reset_economy_guild_id(token)

    @discord.ui.button(label="Распустить банду", style=discord.ButtonStyle.danger, emoji="💀", row=2)
    async def disband_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        token = set_economy_guild_id(self.guild_id)
        try:
            gangs_list = self._get_gangs_list()
            if not gangs_list:
                await interaction.response.send_message("На сервере нет банд.", ephemeral=True)
                return
            view = AdminGangSelectView(gangs_list, "disband", self.guild_id, self.bot)
            await interaction.response.send_message("Выберите банду для роспуска:", view=view, ephemeral=True)
        finally:
            reset_economy_guild_id(token)

    @discord.ui.button(label="Канал агитации", style=discord.ButtonStyle.secondary, emoji="📢", row=2)
    async def agitation_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = AdminSetAgitationChannelView(self.guild_id, interaction.user.id)
        await interaction.response.send_message("Выберите текстовый канал для агитации банд:", view=view, ephemeral=True)


# ══════════════════════════════════════════════════════════
#  HELPER: build gang info embed
# ══════════════════════════════════════════════════════════

def _build_gang_info_embed(gang_name, gang, guild):
    try:
        color_int = int(gang.get("hex_color", "#000000").lstrip('#'), 16)
    except ValueError:
        color_int = 0

    embed = discord.Embed(
        title=f"🏴‍☠️ {gang_name}",
        color=discord.Color(color_int)
    )

    leader_id = gang.get("leader")
    leader = guild.get_member(leader_id) if leader_id else None
    leader_title = gang.get("leader_role_name", "Лидер")
    leader_name = leader.display_name if leader else "Неизвестный"

    members_count = len(gang.get("members", []))
    gang_id = gang.get("id", "?")
    influence = gang.get("influence", 0)
    cash = gang.get("cash", 0.0)
    gold = gang.get("gold", 0.0)

    embed.add_field(name=f"👑 {leader_title}", value=leader_name, inline=True)
    embed.add_field(name="👥 Участников", value=str(members_count), inline=True)
    embed.add_field(name="⚔️ Влияние", value=str(influence), inline=True)
    embed.add_field(name="💰 Общак", value=f"{format_money_plain(cash)} {get_cash_emoji()} / {gold} {get_gold_emoji()}", inline=False)

    if gang.get("description"):
        embed.add_field(name="📝 Описание", value=gang["description"][:1024], inline=False)

    logo_url = gang.get("logo_url")
    if logo_url:
        embed.set_thumbnail(url=logo_url)
    bg_url = gang.get("bg_url")
    if bg_url:
        embed.set_image(url=bg_url)

    embed.set_footer(text=f"ID: #{gang_id}")
    return embed


# ══════════════════════════════════════════════════════════
#  COG
# ══════════════════════════════════════════════════════════

class GangsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── /gang — main unified command ──

    @app_commands.command(name="gang", description="Панель управления бандой")
    async def gang_panel(self, interaction: discord.Interaction):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                gang_name = user_in_gang(account)
                gangs = get_gangs(interaction.guild_id)

            if not gang_name or gang_name not in gangs:
                await interaction.response.send_message(
                    "🚫 Вы не состоите в банде.\n"
                    "Используйте `/gang-create` чтобы создать свою или попросите лидера пригласить вас.",
                    ephemeral=True
                )
                return

            gang = gangs[gang_name]
            is_leader = gang["leader"] == interaction.user.id

            if is_leader:
                # Лидер — полная панель управления
                embed = _build_gang_info_embed(gang_name, gang, interaction.guild)
                embed.title = f"⚙️ Управление бандой «{gang_name}»"
                view = GangLeaderView(interaction.guild_id, gang_name, interaction.user.id, self.bot)
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            else:
                # Обычный участник — инфо-карточка
                member_role_id = gang.get("discord_member_role_id")
                role_mention = ""
                if member_role_id:
                    role = interaction.guild.get_role(member_role_id)
                    if role:
                        role_mention = f" {role.mention}"

                embed = _build_gang_info_embed(gang_name, gang, interaction.guild)
                await interaction.response.send_message(
                    content=f"Вы состоите в банде **{gang_name}**{role_mention}",
                    embed=embed,
                    ephemeral=True
                )
        finally:
            reset_economy_guild_id(token)

    # ── /gang-admin — admin panel ──

    @app_commands.command(name="gang-admin", description="Админ-панель управления бандами сервера")
    @app_commands.default_permissions(administrator=True)
    async def gang_admin_panel(self, interaction: discord.Interaction):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            embed = discord.Embed(
                title="⚙️ Админ-панель банд",
                description="Управляйте бандами сервера. Выберите действие ниже.",
                color=discord.Color.dark_gold()
            )
            async with economy_lock:
                gangs = get_gangs(interaction.guild_id)
                total_gangs = len(gangs)
                total_members = sum(len(g.get("members", [])) for g in gangs.values())

            embed.add_field(name="📊 Статистика", value=f"Банд: **{total_gangs}**\nВсего участников: **{total_members}**", inline=False)

            view = GangAdminView(interaction.guild_id, interaction.user.id, self.bot)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        finally:
            reset_economy_guild_id(token)

    # ── /gang-create ──

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

    # ── /gang-join ──

    @app_commands.command(name="gang-join", description="Принять приглашение и вступить в банду")
    @app_commands.describe(name="Название банды")
    async def gang_join(self, interaction: discord.Interaction, name: str):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            guild_invites = GANG_INVITES.get(interaction.guild_id, {})
            invited_gang = guild_invites.get(interaction.user.id)
            
            if not invited_gang or invited_gang.lower() != name.lower():
                await interaction.response.send_message(f"У вас нет приглашения в банду **{name}**.", ephemeral=True)
                return
                
            async with economy_lock:
                account = get_account(interaction.user.id)
                gangs = get_gangs(interaction.guild_id)
                
                if user_in_gang(account):
                    await interaction.response.send_message("Вы уже состоите в банде.", ephemeral=True)
                    return
                    
                actual_gang_name = None
                for g in gangs.keys():
                    if g.lower() == name.lower():
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

    # ── /gang-leave ──

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
                        "Используйте `/gang` → Передать лидерство или Распустить банду.",
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

    # ── /gang-info ──

    @app_commands.command(name="gang-info", description="Статистика банды")
    @app_commands.describe(name="Название банды (необязательно)")
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
                embed = _build_gang_info_embed(actual_gang_name, gang, interaction.guild)
                
            await interaction.response.send_message(embed=embed)
        finally:
            reset_economy_guild_id(token)

    # ── /gang-deposit ──

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

    # ── /gang-withdraw ──

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

    # ── /gang-rob ──

    @app_commands.command(name="gang-rob", description="Ограбить общак чужой банды (Шанс 30%, риск штрафа, кулдаун 6 часов)")
    @app_commands.describe(target_gang="Название банды для ограбления")
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


async def setup(bot):
    await bot.add_cog(GangsCog(bot))
