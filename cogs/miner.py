"""Коги: шахтёрская мини-игра «Глубокая жила» — единое меню /mine."""

import discord
from discord.ext import commands
from discord import app_commands
import random
import logging
from datetime import date

from src.mine_logic import (
    MineDB,
    MINER_ROLE_KEY,
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
    ATMOSPHERE_TAGS,
    get_depth_layer,
    inv_get,
    inv_add,
    inv_remove,
    reset_daily_if_needed,
    roll_mine,
    make_jewelry_key,
    get_jewelry_name,
    get_jewelry_sell_price,
    get_jewelry_emoji,
    get_item_name,
    get_item_price,
)

from bot import (
    economy_lock,
    economy_data,
    get_account,
    get_gold_emoji,
    get_cash_emoji,
    format_money_plain,
    save_economy,
    set_economy_guild_id,
    reset_economy_guild_id,
    has_game_role,
    get_custom_message,
)
from emoji_config import (
    EMOJI_BAR_IRON,
    EMOJI_GEM_DIAMOND,
    EMOJI_MINE_BACK,
    EMOJI_MINE_BUY,
    EMOJI_MINE_DIG,
    EMOJI_MINE_FIND,
    EMOJI_MINE_FORGE,
    EMOJI_MINE_SELL,
    EMOJI_MINE_SMELT,
    EMOJI_WARNING,
)

MINER_IMAGE_FILE = "assets/images/miner.png"
MINER_IMAGE_ATTACHMENT_NAME = "miner.png"

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ─────────────────────────────────────────────────

def get_miner_image_file():
    import os
    if not os.path.exists(MINER_IMAGE_FILE):
        return None
    return discord.File(MINER_IMAGE_FILE, filename=MINER_IMAGE_ATTACHMENT_NAME)


def build_mine_embed(
    title: str,
    description: str,
    color: discord.Color = discord.Color.from_rgb(110, 80, 40),
    with_image: bool = False,
) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    if with_image:
        embed.set_image(url=f"attachment://{MINER_IMAGE_ATTACHMENT_NAME}")
    embed.set_footer(text=random.choice(ATMOSPHERE_TAGS))
    return embed


def format_inventory(player: dict) -> str:
    inv = player.get("inventory", {})
    sections = []
    cash_e = get_cash_emoji()

    ore_lines = [
        f"  {ORE_EMOJIS.get(k, '')} {ORE_NAMES[k]}: **{inv[k]}** шт. · {ORE_SELL_PRICE[k]} {cash_e}/шт."
        for k in ORE_NAMES if inv.get(k, 0) > 0
    ]
    if ore_lines:
        sections.append(f"{EMOJI_MINE_DIG} **Руда:**\n" + "\n".join(ore_lines))

    bar_lines = [
        f"  {BAR_EMOJIS.get(k, '')} {BAR_NAMES[k]}: **{inv[k]}** шт. · {BAR_SELL_PRICE[k]} {cash_e}/шт."
        for k in BAR_NAMES if inv.get(k, 0) > 0
    ]
    if bar_lines:
        sections.append(f"{EMOJI_BAR_IRON} **Слитки:**\n" + "\n".join(bar_lines))

    gem_lines = [
        f"  {GEMS[k].get('emoji', '')} {GEMS[k]['name']}: **{inv[k]}** шт. · {GEMS[k]['sell']} {cash_e}/шт."
        for k in GEMS if inv.get(k, 0) > 0
    ]
    if gem_lines:
        sections.append(f"{EMOJI_GEM_DIAMOND} **Камни:**\n" + "\n".join(gem_lines))

    jewel_lines = [
        f"  {get_jewelry_emoji(k)} {get_jewelry_name(k)}: **{qty}** шт. · {get_jewelry_sell_price(k)} {cash_e}/шт."
        for k, qty in inv.items()
        if k.startswith(JEWELRY_KEY_PREFIX) and qty > 0
    ]
    if jewel_lines:
        sections.append(f"{EMOJI_MINE_FORGE} **Украшения:**\n" + "\n".join(jewel_lines))

    find_lines = [
        f"  {f['name']}: **{inv[f['key']]}** шт. · {f['sell']} {cash_e}/шт."
        for f in RARE_FINDS if inv.get(f["key"], 0) > 0
    ]
    if find_lines:
        sections.append(f"{EMOJI_MINE_FIND} **Находки:**\n" + "\n".join(find_lines))

    return "\n\n".join(sections) if sections else "— пусто —"


def durability_bar(current: int, max_dur: int) -> str:
    pct = max(0, min(100, int(current / max_dur * 100)))
    filled = pct // 10
    return "█" * filled + "░" * (10 - filled) + f" {pct}%"


def build_main_embed(player: dict, account: dict, guild) -> discord.Embed:
    """Главный embed /mine — состояние шахтёра."""
    layer = get_depth_layer(player["current_depth"])
    pickaxe = PICKAXES.get(player.get("pickaxe_type", "basic"), PICKAXES["basic"])
    dur = player.get("pickaxe_durability", 0)
    max_dur = pickaxe["max_durability"]
    dbar = durability_bar(dur, max_dur)
    cash_e = get_cash_emoji()

    desc = (
        f"**Глубина:** {player['current_depth']} м · _{layer['name']}_\n"
        f"**Баланс:** {account['cash']} {cash_e}\n\n"
        f"**Инструмент:** {pickaxe['name']}\n"
        f"`{dbar}`\n\n"
        f"**Расходники:**\n"
        f"🪔 Масло: **{player.get('oil_units', 0)}** фл."
        f" · 🪵 Лес: **{player.get('wood_count', 0)}** бр."
        f" · 💣 Динамит: **{player.get('dynamite_count', 0)}** пт."
        f" · 🐦 Канарейки: **{player.get('canary_count', 0)}** шт.\n\n"
        f"**Попытки сегодня:** {player['daily_mines_left']} / {DAILY_MINE_LIMIT}"
    )
    return build_mine_embed(f"{EMOJI_MINE_DIG} Шахта Аннесберга", desc, with_image=True)


# ─────────────────────────────────────────────────
#  OWNER-CHECK VIEW
# ─────────────────────────────────────────────────

class MinerOwnerView(discord.ui.View):
    def __init__(self, bot, db: MineDB, user_id: int, gid: str, uid: str, timeout=600):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.db = db
        self.user_id = user_id
        self.gid = gid
        self.uid = uid

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        set_economy_guild_id(interaction.guild_id)
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=build_mine_embed(
                    f"{EMOJI_MINE_DIG} Чужая выработка",
                    "Это меню шахтёра открыто не для вас.",
                    color=discord.Color.dark_red(),
                ),
                ephemeral=True,
            )
            return False
        return True


# ─────────────────────────────────────────────────
#  УТИЛИТЫ: «Назад» и «только кнопка назад»
# ─────────────────────────────────────────────────

async def _go_back_to_main(interaction: discord.Interaction, db: MineDB, gid: str, uid: str, bot):
    """Редактирует текущее сообщение, заменяя его главным меню шахты."""
    token = set_economy_guild_id(interaction.guild_id)
    try:
        async with economy_lock:
            account = get_account(interaction.user.id)
            save_economy()
    finally:
        reset_economy_guild_id(token)

    player = db.get_player(gid, uid)
    reset_daily_if_needed(player)
    db.save_player(gid, uid, player)

    embed = build_main_embed(player, account, interaction.guild)
    view = MinerMainView(bot, db, interaction.user.id, gid, uid)
    image = get_miner_image_file()
    if image:
        await interaction.response.edit_message(embed=embed, view=view, attachments=[image])
    else:
        await interaction.response.edit_message(embed=embed, view=view, attachments=[])


class BackToMainButton(discord.ui.Button):
    def __init__(self, row: int = 4):
        super().__init__(label="Назад", emoji=EMOJI_MINE_BACK, style=discord.ButtonStyle.secondary, row=row)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        await _go_back_to_main(interaction, view.db, view.gid, view.uid, view.bot)


def _make_back_only_view(bot, db, user_id, gid, uid):
    """View только с кнопкой «◀️ Назад»."""
    view = MinerOwnerView(bot, db, user_id, gid, uid)
    view.add_item(BackToMainButton(row=0))
    return view


class MineResultView(MinerOwnerView):
    """Result screen keeps the primary action available without a detour home."""

    @discord.ui.button(label="Копать ещё", emoji=EMOJI_MINE_DIG, style=discord.ButtonStyle.primary, row=0)
    async def dig_again_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _do_mine(interaction, self.db, self.gid, self.uid, self.bot)

    @discord.ui.button(label="К меню шахты", emoji=EMOJI_MINE_BACK, style=discord.ButtonStyle.secondary, row=0)
    async def menu_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _go_back_to_main(interaction, self.db, self.gid, self.uid, self.bot)


# ─────────────────────────────────────────────────
#  ЛОГИКА КОПКИ
# ─────────────────────────────────────────────────

async def _do_mine(interaction: discord.Interaction, db: MineDB, gid: str, uid: str, bot):
    """Выполняет одну копку и редактирует текущее сообщение."""
    player = db.get_player(gid, uid)
    reset_daily_if_needed(player)
    cash_e = get_cash_emoji()

    if player["daily_mines_left"] <= 0:
        embed = build_mine_embed(
            "🌒 Смена окончена",
            f"На сегодня отведено **{DAILY_MINE_LIMIT} куба** — всё потрачено.\n"
            "Лимит сбрасывается каждый день по UTC+0.",
            color=discord.Color.dark_grey(),
        )
        view = _make_back_only_view(bot, db, interaction.user.id, gid, uid)
        await interaction.response.edit_message(embed=embed, view=view, attachments=[])
        return

    if player["pickaxe_durability"] <= 0:
        embed = build_mine_embed(
            "🔧 Сломанный инструмент",
            f"Инструмент сломан — работать невозможно.\nКупите новую через кнопку **{EMOJI_MINE_BUY} Купить**.",
            color=discord.Color.dark_red(),
        )
        view = _make_back_only_view(bot, db, interaction.user.id, gid, uid)
        await interaction.response.edit_message(embed=embed, view=view, attachments=[])
        return

    has_oil = player.get("oil_units", 0) > 0
    new_total = player.get("total_mined", 0) + 1
    player["total_mined"] = new_total
    if new_total % 3 == 0 and player.get("oil_units", 0) > 0:
        player["oil_units"] -= 1

    player["current_depth"] += 1
    player["daily_mines_left"] -= 1
    player["last_mine_date"] = date.today().isoformat()

    shaft = db.get_guild_shaft(gid)
    if player["current_depth"] > shaft:
        db.set_guild_shaft(gid, player["current_depth"])

    result = roll_mine(player, has_oil=has_oil)
    db.save_player(gid, uid, player)

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
            f"{EMOJI_MINE_FIND} **Редкая находка: {find['name']}!**",
            f"_{find['desc']}_",
            f"Оценка фактории: **{find['sell']} {cash_e}**",
        ]
        color = discord.Color.gold()
        found_something = True

    elif result["ore"] and result["ore_amount"] > 0:
        ore_key = result["ore"]
        ore_name = ORE_NAMES[ore_key]
        ore_emoji = ORE_EMOJIS.get(ore_key, EMOJI_MINE_DIG)
        qty = result["ore_amount"]
        sell_direct = f"{ORE_SELL_PRICE[ore_key] * qty} {cash_e}"
        smelt_hint = ""
        if ore_key in SMELT_RECIPES:
            recipe = SMELT_RECIPES[ore_key]
            if qty >= recipe["ore_per_bar"]:
                smelt_hint = f" · или переплавить — **{EMOJI_MINE_SMELT} Кузнец**"
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
        gem_emoji = gem_data.get("emoji", EMOJI_GEM_DIAMOND)
        lines += [
            "",
            f"{gem_emoji} **{gem_data['name'].capitalize()}!**",
            f"Цена фактории: **{gem_data['sell']} {cash_e}** · отнести ювелиру — **{EMOJI_MINE_FORGE} Ювелир**",
        ]
        if not found_something and not (result["gas"] and not result["gas_blocked"]):
            color = discord.Color.from_rgb(100, 180, 220)

    mines_left = player["daily_mines_left"]
    oil_left = player.get("oil_units", 0)
    lines.append("")
    lines.append(f"▫️ Попыток сегодня: **{mines_left}** из {DAILY_MINE_LIMIT}")
    if oil_left == 0:
        lines.append(f"🪔 **Масло закончилось!** Купите через **{EMOJI_MINE_BUY} Купить**")
    elif oil_left <= 2:
        lines.append(f"🪔 Масло: **{oil_left}** фл. — скоро кончится.")

    embed = build_mine_embed(f"{EMOJI_MINE_DIG} Забой Аннесберга", "\n".join(lines), color=color)
    view = MineResultView(bot, db, interaction.user.id, gid, uid)
    await interaction.response.edit_message(embed=embed, view=view, attachments=[])


# ─────────────────────────────────────────────────
#  ГЛАВНОЕ МЕНЮ
# ─────────────────────────────────────────────────

class MinerMainView(MinerOwnerView):
    def __init__(self, bot, db, user_id, gid, uid):
        super().__init__(bot, db, user_id, gid, uid)

    @discord.ui.button(label="Копать", emoji=EMOJI_MINE_DIG, style=discord.ButtonStyle.primary, row=0)
    async def dig_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _do_mine(interaction, self.db, self.gid, self.uid, self.bot)

    @discord.ui.button(label="Купить", emoji=EMOJI_MINE_BUY, style=discord.ButtonStyle.secondary, row=0)
    async def buy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cash_e = get_cash_emoji()
        options = []
        for key, info in SHOP_ITEMS.items():
            label = f"{info['name']} — {info['price']} {cash_e}/{info['unit']}"
            options.append(discord.SelectOption(
                label=label[:100],
                value=key,
                description=info.get("description", "")[:100],
            ))
        embed = build_mine_embed(
            f"{EMOJI_MINE_BUY} Лавка шахтёра",
            "Выберите товар для покупки. Кирки заменяют текущую.",
            with_image=True,
        )
        view = MinerBuyView(self.bot, self.db, self.user_id, self.gid, self.uid, options)
        image = get_miner_image_file()
        if image:
            await interaction.response.edit_message(embed=embed, view=view, attachments=[image])
        else:
            await interaction.response.edit_message(embed=embed, view=view, attachments=[])

    @discord.ui.button(label="Продать", emoji=EMOJI_MINE_SELL, style=discord.ButtonStyle.success, row=1)
    async def sell_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self.db.get_player(self.gid, self.uid)
        inv = player.get("inventory", {})
        cash_e = get_cash_emoji()
        options = []
        for key, qty in inv.items():
            if not isinstance(qty, int) or qty <= 0:
                continue
            name = get_item_name(key)
            if not name:
                continue
            price = get_item_price(key)
            label = f"{name} ×{qty} — {price} {cash_e}/шт."
            emoji = get_jewelry_emoji(key) if key.startswith(JEWELRY_KEY_PREFIX) else None
            options.append(discord.SelectOption(label=label[:100], value=key, emoji=emoji))

        if not options:
            embed = build_mine_embed(
                f"{EMOJI_MINE_SELL} Фактория",
                "Инвентарь пуст — нечего продавать в факторию.",
                color=discord.Color.dark_grey(),
            )
            back_view = _make_back_only_view(self.bot, self.db, self.user_id, self.gid, self.uid)
            await interaction.response.edit_message(embed=embed, view=back_view, attachments=[])
            return

        embed = build_mine_embed(
            f"{EMOJI_MINE_SELL} Фактория",
            "Выберите предмет для продажи. Продаётся весь запас.",
            with_image=True,
        )
        view = MinerSellView(self.bot, self.db, self.user_id, self.gid, self.uid, options)
        image = get_miner_image_file()
        if image:
            await interaction.response.edit_message(embed=embed, view=view, attachments=[image])
        else:
            await interaction.response.edit_message(embed=embed, view=view, attachments=[])

    @discord.ui.button(label="Кузнец", emoji=EMOJI_MINE_SMELT, style=discord.ButtonStyle.secondary, row=1)
    async def smelt_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self.db.get_player(self.gid, self.uid)
        inv = player.get("inventory", {})
        cash_e = get_cash_emoji()
        options = []
        for ore_key, recipe in SMELT_RECIPES.items():
            qty = inv.get(ore_key, 0)
            if qty < recipe["ore_per_bar"]:
                continue
            batches = qty // recipe["ore_per_bar"]
            ore_name = ORE_NAMES.get(ore_key, ore_key)
            if recipe.get("economy_gold"):
                earned = batches * MINE_GOLD_TO_ECONOMY_RATE
                desc = f"{ore_name} ×{qty} → {earned:.4g} золота (такса {recipe['fee'] * batches} {cash_e})"
            else:
                desc = (
                    f"{ore_name} ×{qty} → {batches}× {recipe['bar_name']}"
                    f" (такса {recipe['fee'] * batches} {cash_e})"
                )
            options.append(discord.SelectOption(
                label=ore_name[:100],
                value=ore_key,
                description=desc[:100],
            ))

        if not options:
            embed = build_mine_embed(
                f"{EMOJI_MINE_SMELT} Кузнец",
                "Нет руды для переплавки.",
                color=discord.Color.dark_grey(),
            )
            back_view = _make_back_only_view(self.bot, self.db, self.user_id, self.gid, self.uid)
            await interaction.response.edit_message(embed=embed, view=back_view, attachments=[])
            return

        embed = build_mine_embed(
            f"{EMOJI_MINE_SMELT} Кузнец",
            "Выберите руду для переплавки. Переплавляется весь доступный запас.",
            with_image=True,
        )
        view = MinerSmeltView(self.bot, self.db, self.user_id, self.gid, self.uid, options)
        image = get_miner_image_file()
        if image:
            await interaction.response.edit_message(embed=embed, view=view, attachments=[image])
        else:
            await interaction.response.edit_message(embed=embed, view=view, attachments=[])

    @discord.ui.button(label="Ювелир", emoji=EMOJI_MINE_FORGE, style=discord.ButtonStyle.secondary, row=1)
    async def forge_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self.db.get_player(self.gid, self.uid)
        inv = player.get("inventory", {})
        cash_e = get_cash_emoji()

        bar_options = []
        for bar_key in ("gold_bar", "silver_bar"):
            qty = inv.get(bar_key, 0)
            if qty <= 0:
                continue
            name = BAR_NAMES.get(bar_key, bar_key)
            bar_options.append(discord.SelectOption(label=f"{name} ×{qty}", value=bar_key))

        gem_options = []
        for gem_key, gem in GEMS.items():
            qty = inv.get(gem_key, 0)
            if qty <= 0:
                continue
            gem_options.append(discord.SelectOption(
                label=f"{gem['name']} ×{qty} — {gem['sell']} {cash_e}/шт.",
                value=gem_key,
            ))

        if not bar_options:
            embed = build_mine_embed(
                f"{EMOJI_MINE_FORGE} Ювелир",
                "Нет золотых или серебряных слитков для ювелира.",
                color=discord.Color.dark_grey(),
            )
            back_view = _make_back_only_view(self.bot, self.db, self.user_id, self.gid, self.uid)
            await interaction.response.edit_message(embed=embed, view=back_view, attachments=[])
            return
        if not gem_options:
            embed = build_mine_embed(
                f"{EMOJI_MINE_FORGE} Ювелир",
                "Нет драгоценных камней для ювелира.",
                color=discord.Color.dark_grey(),
            )
            back_view = _make_back_only_view(self.bot, self.db, self.user_id, self.gid, self.uid)
            await interaction.response.edit_message(embed=embed, view=back_view, attachments=[])
            return

        embed = build_mine_embed(
            f"{EMOJI_MINE_FORGE} Ювелир",
            f"Выберите слиток и камень для создания украшения.\n"
            f"Такса ювелира: {int(JEWELRY_FEE_PCT * 100)}% от стоимости материалов.",
            with_image=True,
        )
        view = MinerForgeView(
            self.bot, self.db, self.user_id, self.gid, self.uid,
            bar_options, gem_options
        )
        image = get_miner_image_file()
        if image:
            await interaction.response.edit_message(embed=embed, view=view, attachments=[image])
        else:
            await interaction.response.edit_message(embed=embed, view=view, attachments=[])

# ─────────────────────────────────────────────────
#  МЕНЮ ПОКУПКИ
# ─────────────────────────────────────────────────

class MinerBuySelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(
            placeholder="Выберите товар",
            min_values=1, max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        item = self.values[0]
        if item not in SHOP_ITEMS:
            await interaction.response.send_message("Неизвестный товар.", ephemeral=True)
            return

        info = SHOP_ITEMS[item]
        cash_e = get_cash_emoji()
        gid = view.gid
        uid = view.uid

        if item.startswith("pickaxe_"):
            pickaxe_key = item[len("pickaxe_"):]
            pickaxe_data = PICKAXES.get(pickaxe_key)
            if not pickaxe_data:
                await interaction.response.send_message("Неизвестная кирка.", ephemeral=True)
                return
            cost = pickaxe_data["price"]
            token = set_economy_guild_id(interaction.guild_id)
            try:
                async with economy_lock:
                    account = get_account(interaction.user.id)
                    if account["cash"] < cost - 0.001:
                        save_economy()
                        embed = build_mine_embed(
                            f"{EMOJI_MINE_BUY} Лавка шахтёра",
                            f"Не хватает средств. Нужно **{cost} {cash_e}**, у вас **{account['cash']} {cash_e}**.",
                            color=discord.Color.dark_red(),
                        )
                        back_view = _make_back_only_view(view.bot, view.db, view.user_id, gid, uid)
                        await interaction.response.edit_message(embed=embed, view=back_view, attachments=[])
                        return
                    account["cash"] -= cost
                    bal = account["cash"]
                    save_economy()
            finally:
                reset_economy_guild_id(token)

            player = view.db.get_player(gid, uid)
            player["pickaxe_type"] = pickaxe_key
            player["pickaxe_durability"] = pickaxe_data["max_durability"]
            view.db.save_player(gid, uid, player)

            embed = build_mine_embed(
                f"{EMOJI_MINE_BUY} Покупка в лавке",
                f"Куплена **{pickaxe_data['name']}**.\n"
                f"Прочность: {pickaxe_data['max_durability']} ед.\n"
                f"Остаток: **{bal} {cash_e}**.",
            )
            back_view = _make_back_only_view(view.bot, view.db, view.user_id, gid, uid)
            await interaction.response.edit_message(embed=embed, view=back_view, attachments=[])
            return

        quantity = 1
        total_cost = info["price"] * quantity
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                if account["cash"] < total_cost - 0.001:
                    save_economy()
                    embed = build_mine_embed(
                        f"{EMOJI_MINE_BUY} Лавка шахтёра",
                        f"Не хватает средств. Нужно **{total_cost} {cash_e}**, у вас **{account['cash']} {cash_e}**.",
                        color=discord.Color.dark_red(),
                    )
                    back_view = _make_back_only_view(view.bot, view.db, view.user_id, gid, uid)
                    await interaction.response.edit_message(embed=embed, view=back_view, attachments=[])
                    return
                account["cash"] -= total_cost
                bal = account["cash"]
                save_economy()
        finally:
            reset_economy_guild_id(token)

        field_map = {
            "oil":      "oil_units",
            "wood":     "wood_count",
            "dynamite": "dynamite_count",
            "canary":   "canary_count",
        }
        field = field_map.get(item)
        player = view.db.get_player(gid, uid)
        if field:
            player[field] = player.get(field, 0) + quantity
        view.db.save_player(gid, uid, player)

        embed = build_mine_embed(
            f"{EMOJI_MINE_BUY} Покупка в лавке",
            f"Куплено: **{info['name']}** × {quantity} {info['unit']}.\n"
            f"Потрачено: **{total_cost} {cash_e}**.\n"
            f"Остаток: **{bal} {cash_e}**.\n\n"
            f"_{info['description']}_",
        )
        back_view = _make_back_only_view(view.bot, view.db, view.user_id, gid, uid)
        await interaction.response.edit_message(embed=embed, view=back_view, attachments=[])


class MinerBuyView(MinerOwnerView):
    def __init__(self, bot, db, user_id, gid, uid, options):
        super().__init__(bot, db, user_id, gid, uid)
        self.add_item(MinerBuySelect(options))
        self.add_item(BackToMainButton(row=1))


# ─────────────────────────────────────────────────
#  МЕНЮ ПРОДАЖИ
# ─────────────────────────────────────────────────

class MinerSellSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(
            placeholder="Выберите что продать (весь запас)",
            min_values=1, max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        item = self.values[0]
        gid = view.gid
        uid = view.uid
        player = view.db.get_player(gid, uid)

        available = inv_get(player, item)
        if available <= 0:
            embed = build_mine_embed(
                f"{EMOJI_MINE_SELL} Фактория",
                "У вас нет этого предмета в инвентаре.",
                color=discord.Color.dark_red(),
            )
            back_view = _make_back_only_view(view.bot, view.db, view.user_id, gid, uid)
            await interaction.response.edit_message(embed=embed, view=back_view, attachments=[])
            return

        item_name = get_item_name(item)
        price_each = get_item_price(item)
        if not item_name or price_each <= 0:
            embed = build_mine_embed(
                f"{EMOJI_MINE_SELL} Фактория",
                "Фактория не принимает этот предмет.",
                color=discord.Color.dark_red(),
            )
            back_view = _make_back_only_view(view.bot, view.db, view.user_id, gid, uid)
            await interaction.response.edit_message(embed=embed, view=back_view, attachments=[])
            return

        qty = available
        earned = price_each * qty
        inv_remove(player, item, qty)
        view.db.save_player(gid, uid, player)

        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                account["cash"] += earned
                save_economy()
                bal = account["cash"]
        finally:
            reset_economy_guild_id(token)

        cash_e = get_cash_emoji()
        item_emoji = get_jewelry_emoji(item)
        embed = build_mine_embed(
            f"{EMOJI_MINE_SELL} Фактория",
            f"Продано: {item_emoji} **{item_name}** × {qty}\n"
            f"Выручка: **{earned} {cash_e}**\n"
            f"Баланс: **{bal} {cash_e}**",
            color=discord.Color.from_rgb(180, 140, 40),
        )
        back_view = _make_back_only_view(view.bot, view.db, view.user_id, gid, uid)
        await interaction.response.edit_message(embed=embed, view=back_view, attachments=[])


class MinerSellView(MinerOwnerView):
    def __init__(self, bot, db, user_id, gid, uid, options):
        super().__init__(bot, db, user_id, gid, uid)
        self.add_item(MinerSellSelect(options))
        self.add_item(BackToMainButton(row=1))


# ─────────────────────────────────────────────────
#  МЕНЮ ПЕРЕПЛАВКИ
# ─────────────────────────────────────────────────

class MinerSmeltSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(
            placeholder="Выберите руду для переплавки",
            min_values=1, max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        ore = self.values[0]
        gid = view.gid
        uid = view.uid
        player = view.db.get_player(gid, uid)
        cash_e = get_cash_emoji()

        recipe = SMELT_RECIPES.get(ore)
        if recipe is None:
            embed = build_mine_embed(
                f"{EMOJI_MINE_SMELT} Кузнец",
                "Эту руду нельзя переплавить.",
                color=discord.Color.dark_red(),
            )
            back_view = _make_back_only_view(view.bot, view.db, view.user_id, gid, uid)
            await interaction.response.edit_message(embed=embed, view=back_view, attachments=[])
            return

        available = inv_get(player, ore)
        max_batches = available // recipe["ore_per_bar"]
        if max_batches == 0:
            embed = build_mine_embed(
                f"{EMOJI_MINE_SMELT} Кузнец",
                f"Недостаточно руды. Нужно минимум **{recipe['ore_per_bar']} шт.** для одной партии, "
                f"у вас **{available}** шт.",
                color=discord.Color.dark_red(),
            )
            back_view = _make_back_only_view(view.bot, view.db, view.user_id, gid, uid)
            await interaction.response.edit_message(embed=embed, view=back_view, attachments=[])
            return

        batches = max_batches
        ore_used = batches * recipe["ore_per_bar"]
        total_fee = recipe["fee"] * batches

        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                if account["cash"] < total_fee - 0.001:
                    save_economy()
                    embed = build_mine_embed(
                        f"{EMOJI_MINE_SMELT} Кузнец",
                        f"Не хватает на оплату кузнецу. Нужно **{total_fee} {cash_e}**, "
                        f"у вас **{account['cash']} {cash_e}**.",
                        color=discord.Color.dark_red(),
                    )
                    back_view = _make_back_only_view(view.bot, view.db, view.user_id, gid, uid)
                    await interaction.response.edit_message(embed=embed, view=back_view, attachments=[])
                    return
                account["cash"] -= total_fee
                save_economy()
        finally:
            reset_economy_guild_id(token)

        ore_name = ORE_NAMES.get(ore, ore)
        inv_remove(player, ore, ore_used)
        view.db.save_player(gid, uid, player)

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
                f"{EMOJI_MINE_SMELT} Кузнец",
                f"Переплавлено: **{ore_name}** ×{ore_used}\n"
                f"Получено: **{earned_gold:.4g}** {gold_emoji} (экономическое золото)\n"
                f"Такса кузнеца: **{total_fee} {cash_e}**\n"
                f"Баланс: **{account['cash']} {cash_e}**",
                color=discord.Color.from_rgb(200, 160, 20),
            )
            back_view = _make_back_only_view(view.bot, view.db, view.user_id, gid, uid)
            await interaction.response.edit_message(embed=embed, view=back_view, attachments=[])
            return

        inv_add(player, recipe["bar_key"], batches)
        view.db.save_player(gid, uid, player)

        sell_hint = f"{recipe['bar_sell'] * batches} {cash_e}"
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                bal = account["cash"]
        finally:
            reset_economy_guild_id(token)

        embed = build_mine_embed(
            f"{EMOJI_MINE_SMELT} Кузнец",
            f"Переплавлено: **{ore_name}** × {ore_used}\n"
            f"Получено: **{recipe['bar_name']}** × {batches}\n"
            f"Такса кузнеца: **{total_fee} {cash_e}**\n"
            f"Баланс: **{bal} {cash_e}**\n\n"
            f"Продайте слитки через **{EMOJI_MINE_SELL} Продать** · выручка ~{sell_hint}",
            color=discord.Color.from_rgb(200, 100, 20),
        )
        back_view = _make_back_only_view(view.bot, view.db, view.user_id, gid, uid)
        await interaction.response.edit_message(embed=embed, view=back_view, attachments=[])


class MinerSmeltView(MinerOwnerView):
    def __init__(self, bot, db, user_id, gid, uid, options):
        super().__init__(bot, db, user_id, gid, uid)
        self.add_item(MinerSmeltSelect(options))
        self.add_item(BackToMainButton(row=1))


# ─────────────────────────────────────────────────
#  МЕНЮ ЮВЕЛИРА
# ─────────────────────────────────────────────────

class MinerForgeBarSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(
            placeholder="1. Выберите слиток",
            min_values=1, max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_bar = self.values[0]
        await interaction.response.defer()


class MinerForgeGemSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(
            placeholder="2. Выберите камень",
            min_values=1, max_values=1,
            options=options,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_gem = self.values[0]
        await interaction.response.defer()


class MinerForgeConfirmButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Создать украшение",
            emoji=EMOJI_MINE_FORGE,
            style=discord.ButtonStyle.success,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        gid = view.gid
        uid = view.uid
        bar = view.selected_bar
        gem = view.selected_gem
        cash_e = get_cash_emoji()

        if bar is None or gem is None:
            await interaction.response.send_message(
                "Сначала выберите и слиток, и камень.", ephemeral=True
            )
            return

        if bar not in ("gold_bar", "silver_bar"):
            await interaction.response.send_message(
                "Ювелир работает только с золотыми или серебряными слитками.", ephemeral=True
            )
            return
        if gem not in GEMS:
            await interaction.response.send_message("Неизвестный камень.", ephemeral=True)
            return

        player = view.db.get_player(gid, uid)

        if inv_get(player, bar) < 1:
            bar_name = BAR_NAMES.get(bar, bar)
            embed = build_mine_embed(
                f"{EMOJI_MINE_FORGE} Ювелир",
                f"Нет **{bar_name}** в инвентаре.",
                color=discord.Color.dark_red(),
            )
            back_view = _make_back_only_view(view.bot, view.db, view.user_id, gid, uid)
            await interaction.response.edit_message(embed=embed, view=back_view, attachments=[])
            return
        if inv_get(player, gem) < 1:
            gem_name = GEMS[gem]["name"]
            embed = build_mine_embed(
                f"{EMOJI_MINE_FORGE} Ювелир",
                f"Нет **{gem_name}** в инвентаре.",
                color=discord.Color.dark_red(),
            )
            back_view = _make_back_only_view(view.bot, view.db, view.user_id, gid, uid)
            await interaction.response.edit_message(embed=embed, view=back_view, attachments=[])
            return

        bar_val = BAR_SELL_PRICE.get(bar, 0.0)
        gem_val = GEMS[gem]["sell"]
        fee = round((bar_val + gem_val) * JEWELRY_FEE_PCT, 2)

        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                if account["cash"] < fee - 0.001:
                    save_economy()
                    embed = build_mine_embed(
                        f"{EMOJI_MINE_FORGE} Ювелир",
                        f"Не хватает на такса ювелира. Нужно **{fee} {cash_e}**, "
                        f"у вас **{account['cash']} {cash_e}**.",
                        color=discord.Color.dark_red(),
                    )
                    back_view = _make_back_only_view(view.bot, view.db, view.user_id, gid, uid)
                    await interaction.response.edit_message(embed=embed, view=back_view, attachments=[])
                    return
                account["cash"] -= fee
                save_economy()
                bal = account["cash"]
        finally:
            reset_economy_guild_id(token)

        metal = bar.replace("_bar", "")
        type_key = random.choice(list(FORGE_TEMPLATES.keys()))
        jewel_key = make_jewelry_key(metal, gem, type_key)
        jewel_name = get_jewelry_name(jewel_key)
        jewel_price = get_jewelry_sell_price(jewel_key)
        jewel_emoji = get_jewelry_emoji(jewel_key)

        inv_remove(player, bar, 1)
        inv_remove(player, gem, 1)
        inv_add(player, jewel_key, 1)
        view.db.save_player(gid, uid, player)

        bar_name = BAR_NAMES.get(bar, bar)
        gem_name = GEMS[gem]["name"]
        flavor = random.choice(FORGE_DONE_LINES)
        desc = (
            f"_{flavor}_\n\n"
            f"Слиток: **{bar_name}** + камень: **{gem_name}**\n"
            f"Создано: {jewel_emoji} **{jewel_name}**\n"
            f"Такса ювелира: **{fee} {cash_e}**\n"
            f"Баланс: **{bal} {cash_e}**\n\n"
            f"Цена продажи: **{jewel_price} {cash_e}** · продать через **{EMOJI_MINE_SELL} Продать**"
        )
        embed = build_mine_embed(
            f"{EMOJI_MINE_FORGE} Ювелир",
            desc,
            color=discord.Color.from_rgb(220, 180, 60),
        )
        back_view = _make_back_only_view(view.bot, view.db, view.user_id, gid, uid)
        await interaction.response.edit_message(embed=embed, view=back_view, attachments=[])


class MinerForgeView(MinerOwnerView):
    def __init__(self, bot, db, user_id, gid, uid, bar_options, gem_options):
        super().__init__(bot, db, user_id, gid, uid)
        self.selected_bar = None
        self.selected_gem = None
        self.add_item(MinerForgeBarSelect(bar_options))
        self.add_item(MinerForgeGemSelect(gem_options))
        self.add_item(MinerForgeConfirmButton())
        self.add_item(BackToMainButton(row=3))


# ─────────────────────────────────────────────────
#  КОГ
# ─────────────────────────────────────────────────

class MinerCog(commands.Cog, name="MinerCog"):
    """Шахтёрская мини-игра — единое меню /mine."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = MineDB()

    def cog_unload(self):
        self.db.close()

    def _gid(self, interaction: discord.Interaction) -> str:
        return str(interaction.guild_id or "global")

    def _uid(self, interaction: discord.Interaction) -> str:
        return str(interaction.user.id)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        import traceback
        log.error(f"MinerCog error: {error}")
        traceback.print_exception(type(error), error, error.__traceback__)
        message = "Шахта временно недоступна. Попробуйте ещё раз через минуту."
        if interaction.response.is_done():
            try:
                await interaction.edit_original_response(content=message, embed=None, view=None)
            except discord.HTTPException:
                await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="mine", description="Шахтёр: открыть меню шахты")
    async def mine_cmd(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "Команда доступна только на сервере.", ephemeral=True
            )
            return

        # PostgreSQL and economy storage are synchronous. Acknowledge the
        # interaction first so Discord does not expire it while they respond.
        await interaction.response.defer(ephemeral=True, thinking=True)

        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                if not has_game_role(interaction.user, MINER_ROLE_KEY, account):
                    save_economy()
                    await interaction.edit_original_response(
                        content=get_custom_message("role_required").format(
                            role="Шахтёр"
                        ),
                    )
                    return
                save_economy()
        finally:
            reset_economy_guild_id(token)

        gid = self._gid(interaction)
        uid = self._uid(interaction)
        player = self.db.get_player(gid, uid)
        reset_daily_if_needed(player)
        self.db.save_player(gid, uid, player)

        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                save_economy()
        finally:
            reset_economy_guild_id(token)

        embed = build_main_embed(player, account, interaction.guild)
        view = MinerMainView(self.bot, self.db, interaction.user.id, gid, uid)
        image = get_miner_image_file()
        if image:
            await interaction.edit_original_response(
                embed=embed, view=view, attachments=[image]
            )
        else:
            await interaction.edit_original_response(embed=embed, view=view)


# ─────────────────────────────────────────────────
#  SETUP
# ─────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(MinerCog(bot))
