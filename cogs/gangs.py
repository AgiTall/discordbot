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

class GangsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="gang-create", description="Создать банду (Цена: 50 Золота)")
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
                
                # Create Gang
                account["gold"] -= GANG_CREATE_COST
                account["gang_name"] = name
                
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
            reset_economy_guild_id(token)

    @app_commands.command(name="gang-invite", description="Пригласить игрока в банду (только для лидера)")
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
                    
                # Add invite
                guild_invites = GANG_INVITES.setdefault(interaction.guild_id, {})
                guild_invites[member.id] = gang_name
                
            await interaction.response.send_message(f"Вы отправили приглашение {member.mention} в банду **{gang_name}**! Игрок должен использовать `/gang-join {gang_name}`.")
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
                    # Remove gang from all members
                    guild_data = economy_data.current()
                    for mem_id in members:
                        mem_account = guild_data["users"].get(str(mem_id))
                        if mem_account and mem_account.get("gang_name") == gang_name:
                            mem_account["gang_name"] = None
                    del gangs[gang_name]
                    save_economy()
                    await interaction.response.send_message(f"Лидер покинул банду. Банда **{gang_name}** была распущена, общак сгорел.")
                else:
                    gang["members"].remove(interaction.user.id)
                    account["gang_name"] = None
                    save_economy()
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
                save_economy()
                
            await interaction.response.send_message(f"{member.mention} был исключен из банды **{gang_name}**.")
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

async def setup(bot):
    await bot.add_cog(GangsCog(bot))
