"""Коги: шахтёрская мини-игра «Глубокая жила» (1898 г., Этап 1).

Команды:
  /mine          — копать один куб (лимит 3 в день)
  /mine-status   — глубина, инвентарь, состояние инструмента
  /mine-buy      — купить расходники и кирки
  /mine-sell     — продать руду, слитки, находки, камни, украшения в факторию
  /mine-smelt    — переплавить руду в слитки у кузнеца
  /mine-forge    — отдать слиток + камень ювелиру для создания украшения
"""

import discord
from discord.ext import commands
from discord import app_commands
import random
import logging
from datetime import date

from src.mine_logic import (
    MineDB,
    MINE_DB_FILE,
    DAILY_MINE_LIMIT,
    MINE_GOLD_TO_ECONOMY_RATE,
    PICKAXES,
    SHOP_ITEMS,
    DEPTH_LAYERS,
    ORE_NAMES,
    ORE_SELL_PRICE,
    ORE_EMOJIS,
    SMELT_RECIPES,
    BAR_NAMES,
    BAR_SELL_PRICE,
    BAR_EMOJIS,
    RARE_FINDS,
    FIND_NAMES,
    FIND_SELL,
    GEMS,
    GEM_NAMES,
    GEM_SELL,
    JEWELRY_KEY_PREFIX,
    JEWELRY_FEE_PCT,
    FORGE_TEMPLATES,
    FORGE_DONE_LINES,
    ALL_SELLABLE_NAMES,
    ALL_SELL_PRICES,
    ATMOSPHERE_TAGS,
    format_rubles,
    get_depth_layer,
    inv_get,
    inv_add,
    inv_remove,
    reset_daily_if_needed,
    roll_mine,
    make_jewelry_key,
    get_jewelry_name,
    get_jewelry_sell_price,
    get_item_name,
    get_item_price,
)

from bot import (
    economy_lock,
    economy_data,
    get_account,
    get_gold_emoji,
    save_economy,
    set_economy_guild_id,
    reset_economy_guild_id,
)


# ─────────────────────────────────────────────────
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ОТВЕТОВ
# ─────────────────────────────────────────────────

def build_mine_embed(
    title: str,
    description: str,
    color: discord.Color = discord.Color.from_rgb(110, 80, 40),
) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text=random.choice(ATMOSPHERE_TAGS))
    return embed


def format_inventory(player: dict) -> str:
    inv = player.get("inventory", {})
    sections = []

    ore_lines = [
        f"  {ORE_EMOJIS.get(k, '')} {ORE_NAMES[k]}: **{inv[k]}** шт. · {format_rubles(ORE_SELL_PRICE[k])}/шт."
        for k in ORE_NAMES if inv.get(k, 0) > 0
    ]
    if ore_lines:
        sections.append("⚒️ **Руда:**\n" + "\n".join(ore_lines))

    bar_lines = [
        f"  {BAR_EMOJIS.get(k, '')} {BAR_NAMES[k]}: **{inv[k]}** шт. · {format_rubles(BAR_SELL_PRICE[k])}/шт."
        for k in BAR_NAMES if inv.get(k, 0) > 0
    ]
    if bar_lines:
        sections.append("🧱 **Слитки:**\n" + "\n".join(bar_lines))

    gem_lines = [
        f"  {GEMS[k].get('emoji', '')} {GEMS[k]['name']}: **{inv[k]}** шт. · {format_rubles(GEMS[k]['sell'])}/шт."
        for k in GEMS if inv.get(k, 0) > 0
    ]
    if gem_lines:
        sections.append("💎 **Драгоценные камни:**\n" + "\n".join(gem_lines))

    jewel_lines = [
        f"  {get_jewelry_name(k)}: **{qty}** шт. · {format_rubles(get_jewelry_sell_price(k))}/шт."
        for k, qty in inv.items()
        if k.startswith(JEWELRY_KEY_PREFIX) and qty > 0
    ]
    if jewel_lines:
        sections.append("✨ **Украшения:**\n" + "\n".join(jewel_lines))

    find_lines = [
        f"  {f['name']}: **{inv[f['key']]}** шт. · {format_rubles(f['sell'])}/шт."
        for f in RARE_FINDS if inv.get(f["key"], 0) > 0
    ]
    if find_lines:
        sections.append("🔍 **Редкие находки:**\n" + "\n".join(find_lines))

    return "\n\n".join(sections) if sections else "  — пусто —"


def durability_bar(current: int, max_dur: int) -> str:
    pct = max(0, min(100, int(current / max_dur * 100)))
    filled = pct // 10
    return "█" * filled + "░" * (10 - filled) + f" {pct}%"


# ─────────────────────────────────────────────────
#  КОГ
# ─────────────────────────────────────────────────

class MinerCog(commands.Cog, name="MinerCog"):
    """Шахтёрская мини-игра."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = MineDB(MINE_DB_FILE)

    def cog_unload(self):
        self.db.close()

    def _gid(self, interaction: discord.Interaction) -> str:
        return str(interaction.guild_id or "global")

    def _uid(self, interaction: discord.Interaction) -> str:
        return str(interaction.user.id)

    # ── autocomplete ─────────────────────────────

    async def _ac_buy(self, interaction: discord.Interaction, current: str):
        choices = []
        for key, info in SHOP_ITEMS.items():
            label = f"{info['name']} — {format_rubles(info['price'])}/{info['unit']}"
            if current.lower() in label.lower() or current.lower() in key.lower():
                choices.append(app_commands.Choice(name=label[:100], value=key))
        return choices[:25]

    async def _ac_sell(self, interaction: discord.Interaction, current: str):
        try:
            player = self.db.get_player(self._gid(interaction), self._uid(interaction))
        except Exception:
            return []
        inv = player.get("inventory", {})
        choices = []
        for key, qty in inv.items():
            if not isinstance(qty, int) or qty <= 0:
                continue
            name = get_item_name(key)
            if not name:
                continue
            price = get_item_price(key)
            label = f"{name} ×{qty} — {format_rubles(price)}/шт."
            if current.lower() in label.lower() or current.lower() in key.lower():
                choices.append(app_commands.Choice(name=label[:100], value=key))
        return choices[:25]

    async def _ac_smelt(self, interaction: discord.Interaction, current: str):
        try:
            player = self.db.get_player(self._gid(interaction), self._uid(interaction))
        except Exception:
            return []
        inv = player.get("inventory", {})
        choices = []
        for ore_key, recipe in SMELT_RECIPES.items():
            qty = inv.get(ore_key, 0)
            if qty < recipe["ore_per_bar"]:
                continue
            batches = qty // recipe["ore_per_bar"]
            ore_name = ORE_NAMES.get(ore_key, ore_key)
            if recipe.get("economy_gold"):
                earned = batches * MINE_GOLD_TO_ECONOMY_RATE
                label = (
                    f"{ore_name} ×{qty} → {earned:.4g} золота"
                    f" (такса {format_rubles(recipe['fee'] * batches)})"
                )
            else:
                label = (
                    f"{ore_name} ×{qty} → {batches}× {recipe['bar_name']}"
                    f" (такса {format_rubles(recipe['fee'] * batches)})"
                )
            if current.lower() in label.lower() or current.lower() in ore_key.lower():
                choices.append(app_commands.Choice(name=label[:100], value=ore_key))
        return choices[:25]

    async def _ac_forge_bar(self, interaction: discord.Interaction, current: str):
        try:
            player = self.db.get_player(self._gid(interaction), self._uid(interaction))
        except Exception:
            return []
        inv = player.get("inventory", {})
        choices = []
        for bar_key in ("gold_bar", "silver_bar"):
            qty = inv.get(bar_key, 0)
            if qty <= 0:
                continue
            name = BAR_NAMES.get(bar_key, bar_key)
            label = f"{name} ×{qty}"
            if current.lower() in label.lower() or current.lower() in bar_key.lower():
                choices.append(app_commands.Choice(name=label[:100], value=bar_key))
        return choices

    async def _ac_forge_gem(self, interaction: discord.Interaction, current: str):
        try:
            player = self.db.get_player(self._gid(interaction), self._uid(interaction))
        except Exception:
            return []
        inv = player.get("inventory", {})
        choices = []
        for gem_key, gem in GEMS.items():
            qty = inv.get(gem_key, 0)
            if qty <= 0:
                continue
            label = f"{gem['name']} ×{qty} — {format_rubles(gem['sell'])}/шт."
            if current.lower() in label.lower() or current.lower() in gem_key.lower():
                choices.append(app_commands.Choice(name=label[:100], value=gem_key))
        return choices

    # ──────────────────────────────────────────────
    #  /mine
    # ──────────────────────────────────────────────

    @app_commands.command(name="mine", description="Копать один куб породы (лимит 3 в день)")
    async def mine_cmd(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "Команда доступна только на сервере.", ephemeral=True
            )
            return

        await interaction.response.defer()
        gid = self._gid(interaction)
        uid = self._uid(interaction)

        player = self.db.get_player(gid, uid)
        reset_daily_if_needed(player)

        # ── Лимит ────
        if player["daily_mines_left"] <= 0:
            embed = build_mine_embed(
                "⛏️ Дневной лимит исчерпан",
                f"На сегодня отведено **{DAILY_MINE_LIMIT} куба** — всё потрачено.\n"
                "Лимит сбрасывается каждый день по UTC+0.\n\n"
                "Используйте **/mine-smelt** или **/mine-sell** чтобы не терять время.",
                color=discord.Color.dark_grey(),
            )
            await interaction.followup.send(embed=embed)
            return

        # ── Кирка сломана? ────
        if player["pickaxe_durability"] <= 0:
            embed = build_mine_embed(
                "⛏️ Кирка пришла в негодность",
                "Инструмент сломан — работать невозможно.\n"
                "Купите новую через **/mine-buy**.",
                color=discord.Color.dark_red(),
            )
            await interaction.followup.send(embed=embed)
            return

        # ── Учёт масла ────
        has_oil = player.get("oil_units", 0) > 0

        # Расход масла: каждые 3 куба минус 1 фляга
        new_total = player.get("total_mined", 0) + 1
        player["total_mined"] = new_total
        if new_total % 3 == 0 and player.get("oil_units", 0) > 0:
            player["oil_units"] -= 1

        # ── Углубление ────
        player["current_depth"] += 1
        player["daily_mines_left"] -= 1
        player["last_mine_date"] = date.today().isoformat()

        # Обновить ствол сервера
        shaft = self.db.get_guild_shaft(gid)
        if player["current_depth"] > shaft:
            self.db.set_guild_shaft(gid, player["current_depth"])

        # ── Бросок добычи ────
        result = roll_mine(player, has_oil=has_oil)
        self.db.save_player(gid, uid, player)

        # ── Формирование ответа ────
        layer = get_depth_layer(player["current_depth"])
        rock_desc = random.choice(layer["rock"])
        depth_m = player["current_depth"]

        lines = [
            f"**Глубина: {depth_m} м** · _{layer['name']}_",
            f"*{rock_desc}.*",
            "",
        ]

        found_something = False
        color = discord.Color.dark_grey()

        for event in result["events"]:
            lines.append(event)

        if result["find"]:
            find = result["find"]
            lines += [
                "",
                f"✨ **Редкая находка: {find['name']}!**",
                f"_{find['desc']}_",
                f"Оценка фактории: **{format_rubles(find['sell'])}**",
                "Продать: **/mine-sell**",
            ]
            color = discord.Color.gold()
            found_something = True

        elif result["ore"] and result["ore_amount"] > 0:
            ore_key = result["ore"]
            ore_name = ORE_NAMES[ore_key]
            ore_emoji = ORE_EMOJIS.get(ore_key, "⛏️")
            qty = result["ore_amount"]
            sell_direct = format_rubles(ORE_SELL_PRICE[ore_key] * qty)
            smelt_hint = ""
            if ore_key in SMELT_RECIPES:
                recipe = SMELT_RECIPES[ore_key]
                if qty >= recipe["ore_per_bar"]:
                    smelt_hint = " · или переплавить → **/mine-smelt**"
            lines += [
                "",
                f"{ore_emoji} Добыто: **{ore_name}** ×{qty}",
                f"Продать сырьём: **{sell_direct}**{smelt_hint}",
            ]
            color = discord.Color.from_rgb(140, 100, 50)
            found_something = True

        elif result["gas"] and not result["gas_blocked"]:
            color = discord.Color.dark_red()

        if result.get("gem"):
            gem_data = result["gem"]
            gem_emoji = gem_data.get("emoji", "💎")
            lines += [
                "",
                f"{gem_emoji} **{gem_data['name'].capitalize()}!**",
                f"Цена фактории: **{format_rubles(gem_data['sell'])}**"
                " · отнести ювелиру: **/mine-forge**",
            ]
            if not found_something and not (result["gas"] and not result["gas_blocked"]):
                color = discord.Color.from_rgb(100, 180, 220)

        # ── Строка итогов ────
        mines_left = player["daily_mines_left"]
        oil_left = player.get("oil_units", 0)
        lines.append("")
        lines.append(f"▫️ Попыток сегодня: **{mines_left}** из {DAILY_MINE_LIMIT}")
        if oil_left == 0:
            lines.append("🪔 **Масло закончилось!** Купите в **/mine-buy**")
        elif oil_left <= 2:
            lines.append(f"🪔 Масло: **{oil_left}** фл. — скоро кончится.")

        embed = build_mine_embed("⛏️ Копка", "\n".join(lines), color=color)
        await interaction.followup.send(embed=embed)

    # ──────────────────────────────────────────────
    #  /mine-status
    # ──────────────────────────────────────────────

    @app_commands.command(
        name="mine-status",
        description="Показать состояние шахтёра: глубина, инвентарь, инструмент",
    )
    async def mine_status_cmd(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        gid = self._gid(interaction)
        uid = self._uid(interaction)

        player = self.db.get_player(gid, uid)
        reset_daily_if_needed(player)
        self.db.save_player(gid, uid, player)

        shaft = self.db.get_guild_shaft(gid)
        layer = get_depth_layer(player["current_depth"])
        pickaxe = PICKAXES.get(player.get("pickaxe_type", "basic"), PICKAXES["basic"])
        dur = player.get("pickaxe_durability", 0)
        max_dur = pickaxe["max_durability"]
        dbar = durability_bar(dur, max_dur)
        inv_text = format_inventory(player)

        description = (
            f"**Глубина:** {player['current_depth']} м · _{layer['name']}_\n"
            f"**Ствол сервера:** {shaft} м\n\n"
            f"**Баланс:** {format_rubles(player['balance'])}\n\n"
            f"**Инструмент:** {pickaxe['name']}\n"
            f"`{dbar}`\n\n"
            f"**Расходники:**\n"
            f"🪔 Масло: **{player.get('oil_units', 0)}** фл."
            f" · 🪵 Лес: **{player.get('wood_count', 0)}** бр."
            f" · 💣 Динамит: **{player.get('dynamite_count', 0)}** пт."
            f" · 🐦 Канарейки: **{player.get('canary_count', 0)}** шт.\n\n"
            f"**Попытки сегодня:** {player['daily_mines_left']} / {DAILY_MINE_LIMIT}\n\n"
            f"**Инвентарь:**\n{inv_text}"
        )

        embed = build_mine_embed(
            f"⛏️ Шахтёр: {interaction.user.display_name}", description
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ──────────────────────────────────────────────
    #  /mine-buy
    # ──────────────────────────────────────────────

    @app_commands.command(
        name="mine-buy",
        description="Купить расходники и инструменты в лавке шахтёра",
    )
    @app_commands.describe(item="Что купить", quantity="Сколько штук (по умолч. 1)")
    @app_commands.autocomplete(item=_ac_buy)
    async def mine_buy_cmd(
        self,
        interaction: discord.Interaction,
        item: str,
        quantity: int = 1,
    ):
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        if quantity < 1:
            await interaction.followup.send("Количество должно быть не менее 1.", ephemeral=True)
            return

        if item not in SHOP_ITEMS:
            await interaction.followup.send(
                "Такого товара нет в лавке. Используйте автодополнение.", ephemeral=True
            )
            return

        gid = self._gid(interaction)
        uid = self._uid(interaction)
        player = self.db.get_player(gid, uid)
        info = SHOP_ITEMS[item]

        # ── Кирки — заменяют текущую ────
        if item.startswith("pickaxe_"):
            pickaxe_key = item[len("pickaxe_"):]
            pickaxe_data = PICKAXES.get(pickaxe_key)
            if not pickaxe_data:
                await interaction.followup.send("Неизвестная кирка.", ephemeral=True)
                return

            cost = pickaxe_data["price"]
            if player["balance"] < cost - 0.001:
                await interaction.followup.send(
                    f"Не хватает средств. Нужно **{format_rubles(cost)}**, "
                    f"у вас **{format_rubles(player['balance'])}**.",
                    ephemeral=True,
                )
                return

            player["balance"] -= cost
            player["pickaxe_type"] = pickaxe_key
            player["pickaxe_durability"] = pickaxe_data["max_durability"]
            self.db.save_player(gid, uid, player)

            embed = build_mine_embed(
                "🛒 Покупка в лавке",
                f"Куплена **{pickaxe_data['name']}**.\n"
                f"Прочность: {pickaxe_data['max_durability']} ед.\n"
                f"Остаток: **{format_rubles(player['balance'])}**.",
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # ── Расходники ────
        total_cost = info["price"] * quantity
        if player["balance"] < total_cost - 0.001:
            await interaction.followup.send(
                f"Не хватает средств. Нужно **{format_rubles(total_cost)}**, "
                f"у вас **{format_rubles(player['balance'])}**.",
                ephemeral=True,
            )
            return

        player["balance"] -= total_cost
        field_map = {
            "oil":      "oil_units",
            "wood":     "wood_count",
            "dynamite": "dynamite_count",
            "canary":   "canary_count",
        }
        field = field_map.get(item)
        if field:
            player[field] = player.get(field, 0) + quantity

        self.db.save_player(gid, uid, player)
        embed = build_mine_embed(
            "🛒 Покупка в лавке",
            f"Куплено: **{info['name']}** × {quantity} {info['unit']}.\n"
            f"Потрачено: **{format_rubles(total_cost)}**.\n"
            f"Остаток: **{format_rubles(player['balance'])}**.\n\n"
            f"_{info['description']}_",
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ──────────────────────────────────────────────
    #  /mine-sell
    # ──────────────────────────────────────────────

    @app_commands.command(
        name="mine-sell",
        description="Продать руду, слитки или редкие находки в факторию",
    )
    @app_commands.describe(
        item="Что продать (выберите из инвентаря)",
        quantity="Сколько продать (0 = всё)",
    )
    @app_commands.autocomplete(item=_ac_sell)
    async def mine_sell_cmd(
        self,
        interaction: discord.Interaction,
        item: str,
        quantity: int = 0,
    ):
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        gid = self._gid(interaction)
        uid = self._uid(interaction)
        player = self.db.get_player(gid, uid)

        available = inv_get(player, item)
        if available <= 0:
            await interaction.followup.send(
                "У вас нет этого предмета в инвентаре.", ephemeral=True
            )
            return

        if item not in ALL_SELL_PRICES:
            await interaction.followup.send(
                "Фактория не принимает этот предмет.", ephemeral=True
            )
            return

        qty = available if quantity == 0 else min(quantity, available)
        if qty <= 0:
            await interaction.followup.send("Укажите корректное количество.", ephemeral=True)
            return

        price_each = ALL_SELL_PRICES[item]
        earned = price_each * qty
        inv_remove(player, item, qty)
        player["balance"] += earned
        self.db.save_player(gid, uid, player)

        item_name = ALL_SELLABLE_NAMES.get(item, item)
        embed = build_mine_embed(
            "💰 Фактория",
            f"Продано: **{item_name}** × {qty}\n"
            f"Выручка: **{format_rubles(earned)}**\n"
            f"Баланс: **{format_rubles(player['balance'])}**",
            color=discord.Color.from_rgb(180, 140, 40),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ──────────────────────────────────────────────
    #  /mine-smelt
    # ──────────────────────────────────────────────

    @app_commands.command(
        name="mine-smelt",
        description="Сдать руду кузнецу на переплавку в слитки",
    )
    @app_commands.describe(
        ore="Руда для переплавки",
        quantity="Количество партий (0 = максимум)",
    )
    @app_commands.autocomplete(ore=_ac_smelt)
    async def mine_smelt_cmd(
        self,
        interaction: discord.Interaction,
        ore: str,
        quantity: int = 0,
    ):
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        gid = self._gid(interaction)
        uid = self._uid(interaction)
        player = self.db.get_player(gid, uid)

        recipe = SMELT_RECIPES.get(ore)
        if recipe is None:
            await interaction.followup.send(
                "Эту руду нельзя переплавить. Уголь продают сырьём.", ephemeral=True
            )
            return

        available = inv_get(player, ore)
        max_batches = available // recipe["ore_per_bar"]
        if max_batches == 0:
            await interaction.followup.send(
                f"Недостаточно руды. Нужно минимум **{recipe['ore_per_bar']} шт.** для одной партии, "
                f"у вас **{available}** шт.",
                ephemeral=True,
            )
            return

        batches = max_batches if quantity == 0 else min(quantity, max_batches)
        ore_used = batches * recipe["ore_per_bar"]
        total_fee = recipe["fee"] * batches

        if player["balance"] < total_fee - 0.001:
            await interaction.followup.send(
                f"Не хватает на оплату кузнецу. Нужно **{format_rubles(total_fee)}**, "
                f"у вас **{format_rubles(player['balance'])}**.",
                ephemeral=True,
            )
            return

        ore_name = ORE_NAMES.get(ore, ore)
        inv_remove(player, ore, ore_used)
        player["balance"] -= total_fee
        self.db.save_player(gid, uid, player)

        # Золото: идёт прямо в экономическое золото (не в слиток шахты)
        if recipe.get("economy_gold"):
            earned_gold = round(batches * MINE_GOLD_TO_ECONOMY_RATE, 4)
            token = set_economy_guild_id(interaction.guild_id)
            try:
                async with economy_lock:
                    account = get_account(interaction.user.id)
                    account["gold"] += earned_gold
                    save_economy()
            finally:
                reset_economy_guild_id(token)
            gold_emoji = get_gold_emoji()
            embed = build_mine_embed(
                "🔥 Кузнец",
                f"Переплавлено: **{ore_name}** ×{ore_used}\n"
                f"Получено: **{earned_gold:.4g}** {gold_emoji} (экономическое золото)\n"
                f"Такса кузнеца: **{format_rubles(total_fee)}**\n"
                f"Баланс шахты: **{format_rubles(player['balance'])}**",
                color=discord.Color.from_rgb(200, 160, 20),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Остальные руды: выдают слиток
        inv_add(player, recipe["bar_key"], batches)
        self.db.save_player(gid, uid, player)

        ore_name = ORE_NAMES.get(ore, ore)
        sell_hint = format_rubles(recipe["bar_sell"] * batches)
        embed = build_mine_embed(
            "🔥 Кузнец",
            f"Переплавлено: **{ore_name}** × {ore_used}\n"
            f"Получено: **{recipe['bar_name']}** × {batches}\n"
            f"Такса кузнеца: **{format_rubles(total_fee)}**\n"
            f"Баланс: **{format_rubles(player['balance'])}**\n\n"
            f"Продайте слитки: **/mine-sell** · выручка ~{sell_hint}",
            color=discord.Color.from_rgb(200, 100, 20),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


    # ──────────────────────────────────────────────
    #  /mine-forge
    # ──────────────────────────────────────────────

    @app_commands.command(
        name="mine-forge",
        description="Сдать слиток + камень ювелиру для создания украшения",
    )
    @app_commands.describe(
        bar="Слиток (золотой или серебряный)",
        gem="Драгоценный камень из инвентаря",
    )
    @app_commands.autocomplete(bar=_ac_forge_bar, gem=_ac_forge_gem)
    async def mine_forge_cmd(
        self,
        interaction: discord.Interaction,
        bar: str,
        gem: str,
    ):
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        gid = self._gid(interaction)
        uid = self._uid(interaction)
        player = self.db.get_player(gid, uid)

        if bar not in ("gold_bar", "silver_bar"):
            await interaction.followup.send(
                "Ювелир работает только с золотыми или серебряными слитками.", ephemeral=True
            )
            return
        if gem not in GEMS:
            await interaction.followup.send(
                "Неизвестный камень. Используйте автодополнение.", ephemeral=True
            )
            return
        if inv_get(player, bar) < 1:
            bar_name = BAR_NAMES.get(bar, bar)
            await interaction.followup.send(
                f"Нет **{bar_name}** в инвентаре.", ephemeral=True
            )
            return
        if inv_get(player, gem) < 1:
            gem_name = GEMS[gem]["name"]
            await interaction.followup.send(
                f"Нет **{gem_name}** в инвентаре.", ephemeral=True
            )
            return

        bar_val = BAR_SELL_PRICE.get(bar, 0.0)
        gem_val = GEMS[gem]["sell"]
        fee = round((bar_val + gem_val) * JEWELRY_FEE_PCT, 2)

        if player["balance"] < fee - 0.001:
            await interaction.followup.send(
                f"Не хватает на такса ювелира. Нужно **{format_rubles(fee)}**, "
                f"у вас **{format_rubles(player['balance'])}**.",
                ephemeral=True,
            )
            return

        metal = bar.replace("_bar", "")
        type_key = random.choice(list(FORGE_TEMPLATES.keys()))
        jewel_key = make_jewelry_key(metal, gem, type_key)
        jewel_name = get_jewelry_name(jewel_key)
        jewel_price = get_jewelry_sell_price(jewel_key)

        inv_remove(player, bar, 1)
        inv_remove(player, gem, 1)
        player["balance"] -= fee
        inv_add(player, jewel_key, 1)
        self.db.save_player(gid, uid, player)

        bar_name = BAR_NAMES.get(bar, bar)
        gem_name = GEMS[gem]["name"]
        flavor = random.choice(FORGE_DONE_LINES)
        desc = (
            f"_{flavor}_\n\n"
            f"Слиток: **{bar_name}** + камень: **{gem_name}**\n"
            f"Создано: **{jewel_name}**\n"
            f"Такса ювелира: **{format_rubles(fee)}**\n"
            f"Баланс: **{format_rubles(player['balance'])}**\n\n"
            f"Цена продажи: **{format_rubles(jewel_price)}** · **/mine-sell**"
        )
        embed = build_mine_embed(
            "💍 Ювелир",
            desc,
            color=discord.Color.from_rgb(220, 180, 60),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


# ─────────────────────────────────────────────────
#  SETUP
# ─────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(MinerCog(bot))
