import discord
from discord import app_commands
from discord.ext import commands
import math
from datetime import datetime, timedelta
from typing import Literal, Optional

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
    reset_economy_guild_id,
)

# ─── Категории каталога (в стиле Wheeler, Rawson & Co.) ───

CATALOG_CATEGORIES = {
    "weapons": {
        "name": "Оружие",
        "emoji": "🔫",
        "description": "Огнестрельное и холодное оружие для защиты и нападения.",
    },
    "hunting": {
        "name": "Охота и рыбалка",
        "emoji": "🎣",
        "description": "Снаряжение для охотника и рыбака.",
    },
    "ammo": {
        "name": "Боеприпасы",
        "emoji": "💥",
        "description": "Патроны, стрелы и порох для любого оружия.",
    },
    "horses": {
        "name": "Лошади и сбруя",
        "emoji": "🐴",
        "description": "Лошади, сёдла, уздечки и аксессуары для ваших скакунов.",
    },
    "weapon_equipment": {
        "name": "Оружейное снаряжение",
        "emoji": "⚔️",
        "description": "Кобуры, ремни, патронташи и улучшения для оружия.",
    },
    "provisions": {
        "name": "Провиант",
        "emoji": "🍖",
        "description": "Еда, табак и предметы повседневного потребления.",
    },
    "tonics": {
        "name": "Тоники",
        "emoji": "🧪",
        "description": "Лечебные и укрепляющие тоники, эликсиры.",
    },
}

# ─── Товары каталога ───
# Каждый товар привязан к категории через ключ category.
# type: "unique" — покупается один раз (как сейф), "consumable" — можно покупать много раз.

CATALOG_ITEMS = {
    # === Оружейное снаряжение ===
    "safe": {
        "name": "Сейф",
        "description": "Надёжно хранит деньги и золото от грабителей.",
        "base_price": 30,
        "currency": "gold",
        "emoji_func": get_safe_emoji,
        "category": "weapon_equipment",
        "type": "unique",
    },
    # === Оружие (заготовки) ===
    # "revolver_cattleman": {
    #     "name": "Револьвер Cattleman",
    #     "description": "Надёжный шестизарядный револьвер.",
    #     "base_price": 50,
    #     "currency": "cash",
    #     "emoji_func": None,
    #     "category": "weapons",
    #     "type": "unique",
    # },
    # === Охота и рыбалка (заготовки) ===
    # === Боеприпасы (заготовки) ===
    # === Лошади и сбруя (заготовки) ===
    # === Провиант (заготовки) ===
    # === Тоники (заготовки) ===
}

SAFE_COOLDOWN_HOURS = 3


def get_item_emoji(item_data):
    """Получить эмодзи товара."""
    func = item_data.get("emoji_func")
    if func:
        return func()
    return item_data.get("emoji", "📦")


def get_category_items(category_key):
    """Получить все товары для указанной категории."""
    return {
        key: item for key, item in CATALOG_ITEMS.items()
        if item["category"] == category_key
    }


def build_catalog_embed(category_key, account, guild_id):
    """Создать embed для страницы категории каталога."""
    cat = CATALOG_CATEGORIES[category_key]
    items = get_category_items(category_key)

    guild_data = economy_data.current()
    discounts = guild_data.get("shop_discounts", {})

    embed = discord.Embed(
        title=f"📖 Каталог — {cat['emoji']} {cat['name']}",
        description=cat["description"],
        color=discord.Color.from_rgb(139, 109, 68),  # Тёплый коричневый, стиль RDR2
    )

    if not items:
        embed.add_field(
            name="Скоро в продаже",
            value="*Товары этой категории пока не завезли. Следите за обновлениями!*",
            inline=False,
        )
    else:
        for item_key, item_data in items.items():
            discount_percent = discounts.get(item_key, 0)
            price = item_data["base_price"]
            if discount_percent > 0:
                price = math.floor(price * (1 - discount_percent / 100))

            emoji = get_gold_emoji() if item_data["currency"] == "gold" else get_cash_emoji()
            item_emoji = get_item_emoji(item_data)
            price_text = f"**{price}** {emoji}"
            if discount_percent > 0:
                price_text += f" *(Скидка {discount_percent}%)*"

            # Показать статус владения для unique товаров
            status = ""
            if item_data["type"] == "unique":
                inventory = account.get("inventory", {})
                if inventory.get(item_key, 0) > 0:
                    status = " ✅ *Куплено*"

            embed.add_field(
                name=f"{item_emoji} {item_data['name']}{status}",
                value=f"{item_data['description']}\nЦена: {price_text}",
                inline=False,
            )

    # Навигация
    cat_names = [f"{c['emoji']} {c['name']}" for c in CATALOG_CATEGORIES.values()]
    embed.set_footer(text=f"Wheeler, Rawson & Co. • {' · '.join(cat_names)}")

    return embed


# ─── Кнопки покупки ───

class CatalogBuyButton(discord.ui.Button):
    def __init__(self, item_key, item_data, price, already_owned, discount_percent=0):
        self.item_key = item_key
        self.item_data = item_data
        self.price = price

        currency_name = "золота" if item_data["currency"] == "gold" else "долларов"
        label = f"Купить {item_data['name']} ({price} {currency_name})"
        if discount_percent > 0:
            label += f" [-{discount_percent}%]"

        item_emoji = get_item_emoji(item_data)

        super().__init__(
            label="Уже куплено" if already_owned else label,
            style=discord.ButtonStyle.secondary if already_owned else discord.ButtonStyle.success,
            custom_id=f"catalog_buy_{item_key}",
            emoji=item_emoji,
            disabled=already_owned,
        )

    async def callback(self, interaction: discord.Interaction):
        async with economy_lock:
            account = get_account(interaction.user.id)
            inventory = account.setdefault("inventory", {})

            if self.item_data["type"] == "unique" and inventory.get(self.item_key, 0) > 0:
                await interaction.response.send_message(
                    f"У вас уже есть {self.item_data['name']}!", ephemeral=True
                )
                return

            if account.get(self.item_data["currency"], 0.0) < self.price:
                currency_name = "золота" if self.item_data["currency"] == "gold" else "долларов"
                await interaction.response.send_message(
                    f"Недостаточно средств. Нужно {self.price} {currency_name}.",
                    ephemeral=True,
                )
                return

            account[self.item_data["currency"]] -= self.price
            if self.item_data["type"] == "unique":
                inventory[self.item_key] = 1
            else:
                inventory[self.item_key] = inventory.get(self.item_key, 0) + 1
            save_economy()

            emoji = get_gold_emoji() if self.item_data["currency"] == "gold" else get_cash_emoji()
            await interaction.response.send_message(
                f"✅ Вы успешно купили **{self.item_data['name']}** за {self.price} {emoji}!",
                ephemeral=True,
            )

            # Обновить кнопку если unique
            if self.item_data["type"] == "unique":
                self.disabled = True
                self.label = "Уже куплено"
                self.style = discord.ButtonStyle.secondary
                await interaction.message.edit(view=self.view)


# ─── Селектор категорий ───

class CatalogCategorySelect(discord.ui.Select):
    def __init__(self, current_category):
        options = []
        for key, cat in CATALOG_CATEGORIES.items():
            options.append(
                discord.SelectOption(
                    label=cat["name"],
                    value=key,
                    emoji=cat["emoji"],
                    description=cat["description"][:100],
                    default=(key == current_category),
                )
            )
        super().__init__(
            placeholder="Выберите раздел каталога...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        account = get_account(interaction.user.id)
        embed = build_catalog_embed(selected, account, interaction.guild_id)
        view = CatalogView(interaction.guild_id, interaction.user, account, selected)
        await interaction.response.edit_message(embed=embed, view=view)


# ─── Главный View каталога ───

class CatalogView(discord.ui.View):
    def __init__(self, guild_id, member, account, current_category="weapons"):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.member = member
        self.account = account
        self.current_category = current_category

        # Селектор категорий
        self.add_item(CatalogCategorySelect(current_category))

        # Кнопки покупки для текущей категории
        items = get_category_items(current_category)
        guild_data = economy_data.current()
        discounts = guild_data.get("shop_discounts", {})

        for item_key, item_data in items.items():
            discount_percent = discounts.get(item_key, 0)
            price = item_data["base_price"]
            if discount_percent > 0:
                price = math.floor(price * (1 - discount_percent / 100))

            inventory = account.get("inventory", {})
            already_owned = (
                item_data["type"] == "unique" and inventory.get(item_key, 0) > 0
            )

            self.add_item(
                CatalogBuyButton(item_key, item_data, price, already_owned, discount_percent)
            )

    async def interaction_check(self, interaction):
        set_economy_guild_id(interaction.guild_id)
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "Это не ваш каталог!", ephemeral=True
            )
            return False
        return True


# ─── Cog ───

class CatalogCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="catalog", description="Открыть каталог товаров Wheeler, Rawson & Co.")
    async def catalog_cmd(self, interaction: discord.Interaction):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            account = get_account(interaction.user.id)
            current_category = "weapons"  # Начинаем с оружия

            embed = build_catalog_embed(current_category, account, interaction.guild_id)
            view = CatalogView(interaction.guild_id, interaction.user, account, current_category)

            await interaction.response.send_message(embed=embed, view=view)
        finally:
            reset_economy_guild_id(token)

    @app_commands.command(
        name="set-discount-shop",
        description="Установить скидку на товар в каталоге",
    )
    @app_commands.default_permissions(administrator=True)
    async def set_discount_cmd(
        self, interaction: discord.Interaction, item: str, discount: int
    ):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            if item not in CATALOG_ITEMS:
                items_list = ", ".join(CATALOG_ITEMS.keys())
                await interaction.response.send_message(
                    f"Товар не найден. Доступные товары: {items_list}",
                    ephemeral=True,
                )
                return

            if discount < 0 or discount > 100:
                await interaction.response.send_message(
                    "Скидка должна быть от 0 до 100.", ephemeral=True
                )
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

            await interaction.response.send_message(
                f"Скидка на **{CATALOG_ITEMS[item]['name']}** установлена: {discount}%",
                ephemeral=True,
            )
        finally:
            reset_economy_guild_id(token)

    # ── SAFE MECHANICS (перенесено из shop.py) ──

    @app_commands.command(
        name="safe-money", description="Положить деньги или золото в сейф"
    )
    async def safe_money_cmd(
        self,
        interaction: discord.Interaction,
        currency: Literal["Деньги", "Золото"],
        amount: float,
    ):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            if amount <= 0:
                await interaction.response.send_message(
                    "Сумма должна быть больше нуля.", ephemeral=True
                )
                return

            async with economy_lock:
                account = get_account(interaction.user.id)
                inventory = account.get("inventory", {})

                if inventory.get("safe", 0) <= 0:
                    await interaction.response.send_message(
                        "У вас нет сейфа! Вы можете купить его в `/catalog`.",
                        ephemeral=True,
                    )
                    return

                curr_key = "cash" if currency == "Деньги" else "gold"
                safe_key = "safe_cash" if currency == "Деньги" else "safe_gold"

                balance = account.get(curr_key, 0.0)
                if balance < amount:
                    await interaction.response.send_message(
                        f"Недостаточно средств. У вас {format_money_plain(balance)} {currency.lower()}.",
                        ephemeral=True,
                    )
                    return

                account[curr_key] -= amount
                account.setdefault(safe_key, 0.0)
                account[safe_key] += amount
                save_economy()

                emoji = (
                    get_cash_emoji() if currency == "Деньги" else get_gold_emoji()
                )
                await interaction.response.send_message(
                    f"Вы положили {amount} {emoji} в сейф. Теперь в сейфе: {account[safe_key]} {emoji}."
                )
        finally:
            reset_economy_guild_id(token)

    @app_commands.command(
        name="safe-take-money",
        description="Взять деньги или золото из сейфа (кулдаун 3 часа)",
    )
    async def safe_take_money_cmd(
        self,
        interaction: discord.Interaction,
        currency: Literal["Деньги", "Золото"],
        amount: float,
    ):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            if amount <= 0:
                await interaction.response.send_message(
                    "Сумма должна быть больше нуля.", ephemeral=True
                )
                return

            async with economy_lock:
                account = get_account(interaction.user.id)
                inventory = account.get("inventory", {})

                if inventory.get("safe", 0) <= 0:
                    await interaction.response.send_message(
                        "У вас нет сейфа!", ephemeral=True
                    )
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
                        await interaction.response.send_message(
                            f"Сейф заблокирован! Вы сможете открыть его через **{hours} ч. {minutes} м.**",
                            ephemeral=True,
                        )
                        return

                safe_key = "safe_cash" if currency == "Деньги" else "safe_gold"
                curr_key = "cash" if currency == "Деньги" else "gold"

                safe_balance = account.get(safe_key, 0.0)
                if safe_balance < amount:
                    await interaction.response.send_message(
                        f"В сейфе недостаточно средств. Там лежит {format_money_plain(safe_balance)} {currency.lower()}.",
                        ephemeral=True,
                    )
                    return

                account[safe_key] -= amount
                account[curr_key] += amount
                cooldowns["safe_withdraw_at"] = now_local().isoformat(
                    timespec="seconds"
                )
                save_economy()

                emoji = (
                    get_cash_emoji() if currency == "Деньги" else get_gold_emoji()
                )
                await interaction.response.send_message(
                    f"Вы забрали {amount} {emoji} из сейфа."
                )
        finally:
            reset_economy_guild_id(token)


async def setup(bot):
    await bot.add_cog(CatalogCog(bot))
