import discord
from discord import app_commands
from discord.ext import commands
import random
from datetime import timedelta

from bot import (
    economy_lock,
    get_account,
    save_economy,
    get_cash_emoji,
    now_local,
    parse_local_datetime,
    set_economy_guild_id,
    reset_economy_guild_id,
    format_money_plain
)

ROB_COOLDOWN_HOURS = 2
ROB_SUCCESS_CHANCE_MIN = 10
ROB_SUCCESS_CHANCE_MAX = 20

class RobberyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="rob", description="Ограбить другого игрока (риск штрафа, кулдаун 2 часа)")
    async def rob_command(self, interaction: discord.Interaction, target: discord.Member):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            if target.bot:
                await interaction.response.send_message("Ботов грабить нельзя, у них нет карманов.", ephemeral=True)
                return
                
            if target.id == interaction.user.id:
                await interaction.response.send_message("Вы не можете ограбить самого себя.", ephemeral=True)
                return
                
            async with economy_lock:
                account = get_account(interaction.user.id)
                target_account = get_account(target.id)
                
                # Check cooldown
                cooldowns = account.setdefault("cooldowns", {})
                last_rob = cooldowns.get("last_player_rob_at")
                if last_rob:
                    last_time = parse_local_datetime(last_rob)
                    now = now_local()
                    diff = (now - last_time).total_seconds()
                    if diff < ROB_COOLDOWN_HOURS * 3600:
                        remaining = int(ROB_COOLDOWN_HOURS * 3600 - diff)
                        hours, remainder = divmod(remaining, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        await interaction.response.send_message(f"Шериф всё ещё ищет вас! Залечь на дно придется еще: **{hours} ч. {minutes} м.**", ephemeral=True)
                        return
                        
                if target_account.get("cash", 0.0) < 50:
                    await interaction.response.send_message(f"У {target.mention} в карманах почти пусто. Ищите цель побогаче.", ephemeral=True)
                    return
                    
                # Setup robbery
                cooldowns["last_player_rob_at"] = now_local().isoformat(timespec="seconds")
                
                # Dynamic chance: 10% to 20%
                success_chance = random.randint(ROB_SUCCESS_CHANCE_MIN, ROB_SUCCESS_CHANCE_MAX)
                roll = random.randint(1, 100)
                
                if roll <= success_chance:
                    # Success
                    # Steal 5% to 15% of cash
                    stolen_percent = random.uniform(0.05, 0.15)
                    stolen_amount = int(target_account["cash"] * stolen_percent)
                    
                    if stolen_amount <= 0:
                        stolen_amount = 1
                        
                    target_account["cash"] -= stolen_amount
                    account["cash"] += stolen_amount
                    
                    save_economy()
                    await interaction.response.send_message(f"🔫 **УСПЕХ!** Вы подкрались к {target.mention} и вытащили из его карманов **{stolen_amount} {get_cash_emoji()}**! Настоящий бандит!")
                else:
                    # Fail
                    fine_percent = 0.05 # 5% fine
                    fine_amount = int(account.get("cash", 0.0) * fine_percent)
                    
                    if fine_amount > 0:
                        account["cash"] -= fine_amount
                        save_economy()
                        await interaction.response.send_message(f"🚨 **ПРОВАЛ!** Вас заметил шериф при попытке ограбить {target.mention}. Во время погони вы обронили **{fine_amount} {get_cash_emoji()}**.")
                    else:
                        save_economy()
                        await interaction.response.send_message(f"🚨 **ПРОВАЛ!** Вы попытались ограбить {target.mention}, но получили отпор. К счастью, ваши карманы были пусты, поэтому вы ничего не потеряли.")
        finally:
            reset_economy_guild_id(token)

async def setup(bot):
    await bot.add_cog(RobberyCog(bot))
