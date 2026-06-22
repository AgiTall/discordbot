import discord
from discord import app_commands
from discord.ext import commands
import math
from datetime import datetime, timedelta
from typing import Literal

from bot import (
    economy_lock,
    economy_data,
    get_account,
    get_gold_emoji,
    get_cash_emoji,
    get_safe_emoji,
    save_economy,
    format_money_plain,
    now_local,
    parse_local_datetime,
    set_economy_guild_id,
    reset_economy_guild_id
)

ITEMS = {
    "safe": {
        "name": "Сейф",
        "description": "Позволяет надежно хранить деньги и золото от грабителей.",
        "base_price": 30,
        "currency": "gold",
        "emoji": get_safe_emoji()
    }
}

SAFE_COOLDOWN_HOURS = 3

class ShopView(discord.ui.View):
    def __init__(self, guild_id, member, account):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.member = member
        self.account = account

        # Get discounts
        guild_data = economy_data.current()
        discounts = guild_data.get("shop_discounts", {})

        for item_key, item_data in ITEMS.items():
            discount_percent = discounts.get(item_key, 0)
            price = item_data["base_price"]
            if discount_percent > 0:
                price = math.floor(price * (1 - discount_percent / 100))

            currency_name = "золота" if item_data["currency"] == "gold" else "долларов"
            label = f"Купить {item_data['name']} ({price} {currency_name})"
            if discount_percent > 0:
                label += f" [-{discount_percent}%]"
            
            # Disable if already owned
            inventory = self.account.get("inventory", {})
            already_owned = inventory.get(item_key, 0) > 0
            
            button = discord.ui.Button(
                label="Уже куплено" if already_owned else label,
                style=discord.ButtonStyle.secondary if already_owned else discord.ButtonStyle.success,
                custom_id=f"buy_{item_key}",
                emoji=item_data["emoji"],
                disabled=already_owned
            )
            button.callback = self.make_callback(item_key, price, item_data["currency"], item_data["name"])
            self.add_item(button)

    async def interaction_check(self, interaction):
        set_economy_guild_id(interaction.guild_id)
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("Это не ваш магазин!", ephemeral=True)
            return False
        return True

    def make_callback(self, item_key, price, currency, item_name):
        async def callback(interaction: discord.Interaction):
            async with economy_lock:
                account = get_account(interaction.user.id)
                inventory = account.setdefault("inventory", {})
                
                if inventory.get(item_key, 0) > 0:
                    await interaction.response.send_message(f"У вас уже есть {item_name}!", ephemeral=True)
                    return
                
                if account.get(currency, 0.0) < price:
                    currency_name = "золота" if currency == "gold" else "долларов"
                    await interaction.response.send_message(f"Недостаточно средств. Нужно {price} {currency_name}.", ephemeral=True)
                    return
                
                # Deduct
                account[currency] -= price
                inventory[item_key] = 1
                save_economy()
                
                await interaction.response.send_message(f"✅ Вы успешно купили **{item_name}** за {price} {get_gold_emoji() if currency == 'gold' else get_cash_emoji()}!", ephemeral=True)
                
                # Update view
                for child in self.children:
                    if child.custom_id == f"buy_{item_key}":
                        child.disabled = True
                        child.label = "Уже куплено"
                        child.style = discord.ButtonStyle.secondary
                await interaction.message.edit(view=self)
        return callback

class ShopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="shop", description="Открыть магазин предметов")
    async def shop_cmd(self, interaction: discord.Interaction):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            account = get_account(interaction.user.id)
            view = ShopView(interaction.guild_id, interaction.user, account)
            
            embed = discord.Embed(
                title="🛒 Магазин",
                description="Здесь вы можете приобрести полезные предметы.",
                color=discord.Color.dark_gold()
            )
            
            guild_data = economy_data.current()
            discounts = guild_data.get("shop_discounts", {})

            for item_key, item_data in ITEMS.items():
                discount_percent = discounts.get(item_key, 0)
                price = item_data["base_price"]
                if discount_percent > 0:
                    price = math.floor(price * (1 - discount_percent / 100))
                
                emoji = get_gold_emoji() if item_data["currency"] == "gold" else get_cash_emoji()
                price_text = f"**{price}** {emoji}"
                if discount_percent > 0:
                    price_text += f" *(Скидка {discount_percent}%)*"
                    
                embed.add_field(
                    name=f"{item_data['emoji']} {item_data['name']}",
                    value=f"{item_data['description']}\nЦена: {price_text}",
                    inline=False
                )

            await interaction.response.send_message(embed=embed, view=view)
        finally:
            reset_economy_guild_id(token)

    @app_commands.command(name="set-discount-shop", description="Установить скидку на товар в магазине")
    @app_commands.default_permissions(administrator=True)
    async def set_discount_cmd(self, interaction: discord.Interaction, item: str, discount: int):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            if item not in ITEMS:
                items_list = ", ".join(ITEMS.keys())
                await interaction.response.send_message(f"Товар не найден. Доступные товары: {items_list}", ephemeral=True)
                return
            
            if discount < 0 or discount > 100:
                await interaction.response.send_message("Скидка должна быть от 0 до 100.", ephemeral=True)
                return
                
            async with economy_lock:
                guild_data = economy_data.current()
                discounts = guild_data.setdefault("shop_discounts", {})
                if discount == 0:
                    if item in discounts:
                        del discounts[item]
                else:
                    discounts[item] = discount
                save_economy()
                
            await interaction.response.send_message(f"Скидка на **{ITEMS[item]['name']}** установлена: {discount}%", ephemeral=True)
        finally:
            reset_economy_guild_id(token)
            
    # -- SAFE MECHANICS --
    
    @app_commands.command(name="safe-money", description="Положить деньги или золото в сейф")
    async def safe_money_cmd(self, interaction: discord.Interaction, currency: Literal["Деньги", "Золото"], amount: float):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            if amount <= 0:
                await interaction.response.send_message("Сумма должна быть больше нуля.", ephemeral=True)
                return
                
            async with economy_lock:
                account = get_account(interaction.user.id)
                inventory = account.get("inventory", {})
                
                if inventory.get("safe", 0) <= 0:
                    await interaction.response.send_message("У вас нет сейфа! Вы можете купить его в `/shop`.", ephemeral=True)
                    return
                
                curr_key = "cash" if currency == "Деньги" else "gold"
                safe_key = "safe_cash" if currency == "Деньги" else "safe_gold"
                
                balance = account.get(curr_key, 0.0)
                if balance < amount:
                    await interaction.response.send_message(f"Недостаточно средств. У вас {format_money_plain(balance)} {currency.lower()}.", ephemeral=True)
                    return
                    
                account[curr_key] -= amount
                account.setdefault(safe_key, 0.0)
                account[safe_key] += amount
                save_economy()
                
                emoji = get_cash_emoji() if currency == "Деньги" else get_gold_emoji()
                await interaction.response.send_message(f"Вы положили {amount} {emoji} в сейф. Теперь в сейфе: {account[safe_key]} {emoji}.")
        finally:
            reset_economy_guild_id(token)

    @app_commands.command(name="safe-take-money", description="Взять деньги или золото из сейфа (кулдаун 3 часа)")
    async def safe_take_money_cmd(self, interaction: discord.Interaction, currency: Literal["Деньги", "Золото"], amount: float):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            if amount <= 0:
                await interaction.response.send_message("Сумма должна быть больше нуля.", ephemeral=True)
                return
                
            async with economy_lock:
                account = get_account(interaction.user.id)
                inventory = account.get("inventory", {})
                
                if inventory.get("safe", 0) <= 0:
                    await interaction.response.send_message("У вас нет сейфа!", ephemeral=True)
                    return
                
                # Check cooldown
                cooldowns = account.setdefault("cooldowns", {})
                last_withdraw = cooldowns.get("safe_withdraw_at")
                if last_withdraw:
                    last_time = parse_local_datetime(last_withdraw)
                    now = now_local()
                    diff = (now - last_time).total_seconds()
                    if diff < SAFE_COOLDOWN_HOURS * 3600:
                        remaining = int(SAFE_COOLDOWN_HOURS * 3600 - diff)
                        hours, remainder = divmod(remaining, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        await interaction.response.send_message(f"Сейф заблокирован! Вы сможете открыть его через **{hours} ч. {minutes} м.**", ephemeral=True)
                        return
                
                safe_key = "safe_cash" if currency == "Деньги" else "safe_gold"
                curr_key = "cash" if currency == "Деньги" else "gold"
                
                safe_balance = account.get(safe_key, 0.0)
                if safe_balance < amount:
                    await interaction.response.send_message(f"В сейфе недостаточно средств. Там лежит {format_money_plain(safe_balance)} {currency.lower()}.", ephemeral=True)
                    return
                    
                account[safe_key] -= amount
                account[curr_key] += amount
                cooldowns["safe_withdraw_at"] = now_local().isoformat(timespec="seconds")
                save_economy()
                
                emoji = get_cash_emoji() if currency == "Деньги" else get_gold_emoji()
                await interaction.response.send_message(f"Вы забрали {amount} {emoji} из сейфа.")
        finally:
            reset_economy_guild_id(token)

async def setup(bot):
    await bot.add_cog(ShopCog(bot))
