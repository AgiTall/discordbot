"""
src/role_utils.py
Утилиты для работы с игровыми ролями Discord:
поиск, проверка, создание, buy-flow, UI-компоненты магазина.
"""

import logging
import os
import discord

from src.constants import (
    ROLE_DEFINITIONS, HANGUL_FILLER, ROLE_DISPLAY_SUFFIX,
    WILDWEST_HEADER_ROLE_NAME, WILDWEST_HEADER_ROLE_COLOR, ROLE_DISPLAY_COLOR,
    ROLE_BASE_PRICE, ROLE_DISCOUNT_DAYS, DEALER_ROLE_KEY,
    DEFAULT_CUSTOM_MESSAGES,
)

# Ключи ролей для удобного импорта в других модулях
MOONSHINER_ROLE_KEY  = "moonshiner"
BOUNTY_ROLE_KEY      = "bounty_hunter"
NATURALIST_ROLE_KEY  = "naturalist"


# ──────────────────────────────────────────────────────────────
#  ВСПОМОГАТЕЛЬНЫЕ ГЕТТЕРЫ (state-зависимые)
# ──────────────────────────────────────────────────────────────

def _economy():
    from src import state
    return state.economy_data


def _economy_lock():
    from src import state
    return state.economy_lock


# ──────────────────────────────────────────────────────────────
#  НОРМАЛИЗАЦИЯ / ПОИСК РОЛЕЙ
# ──────────────────────────────────────────────────────────────

def normalize_role_name(name: str) -> str:
    stripped = str(name).strip(HANGUL_FILLER).strip()
    return " ".join(stripped.split()).casefold()


def role_text_matches(role_text: str, role_definition: dict) -> bool:
    normalized = normalize_role_name(role_text)
    names = [role_definition["name"], *role_definition.get("aliases", [])]
    return normalized in {normalize_role_name(n) for n in names}


def role_name_matches(role: discord.Role, role_definition: dict) -> bool:
    return role_text_matches(role.name, role_definition)


def find_role_definition_by_name(role_name: str) -> dict | None:
    for rd in ROLE_DEFINITIONS:
        if role_text_matches(role_name, rd):
            return rd
    return None


def get_role_definition(role_key: str) -> dict | None:
    for rd in ROLE_DEFINITIONS:
        if rd["key"] == role_key:
            return rd
    return None


def get_role_definition_for_role(role: discord.Role) -> dict | None:
    for rd in ROLE_DEFINITIONS:
        if role_name_matches(role, rd):
            return rd
    return None


def find_guild_role(guild: discord.Guild | None, role_definition: dict) -> discord.Role | None:
    if guild is None:
        return None
    for role in guild.roles:
        if role_name_matches(role, role_definition):
            return role
    return None


def find_guild_role_by_name(guild: discord.Guild | None, role_name: str) -> discord.Role | None:
    if guild is None:
        return None
    normalized = normalize_role_name(role_name)
    for role in guild.roles:
        if normalize_role_name(role.name) == normalized:
            return role
    return None


def find_member_role(member, role_definition: dict) -> discord.Role | None:
    for role in getattr(member, "roles", []):
        if role_name_matches(role, role_definition):
            return role
    return None


def resolve_configurable_role(guild, role_name: str):
    """Возвращает (discord_role, role_definition) по имени или None если не найдено."""
    role_definition = find_role_definition_by_name(role_name)
    if role_definition is not None:
        return find_guild_role(guild, role_definition), role_definition
    role = find_guild_role_by_name(guild, role_name)
    if role is None:
        return None, None
    return role, get_role_definition_for_role(role)


# ──────────────────────────────────────────────────────────────
#  ИКОНКИ / СКИДКИ / ЦЕНЫ
# ──────────────────────────────────────────────────────────────

def get_role_icon(role_definition: dict, role: discord.Role | None = None) -> str:
    if role is not None:
        configured = _economy().get("role_icons", {}).get(str(role.id))
        if configured:
            return configured
    role_key_icons = _economy().get("role_key_icons", {})
    icon = role_key_icons.get(role_definition["key"])
    if icon:
        return icon
    return role_definition.get("emoji", "")


def get_role_discount(role: discord.Role | None) -> dict | None:
    from src.economy_store import now_local, parse_local_datetime
    if role is None:
        return None
    discount = _economy().get("role_discounts", {}).get(str(role.id))
    if not isinstance(discount, dict):
        return None
    expires_at = parse_local_datetime(discount.get("expires_at"))
    if expires_at <= now_local():
        _economy()["role_discounts"].pop(str(role.id), None)
        return None
    try:
        price = max(0.0, float(discount.get("price", ROLE_BASE_PRICE)))
    except (TypeError, ValueError):
        _economy()["role_discounts"].pop(str(role.id), None)
        return None
    return {"price": price, "expires_at": expires_at}


def get_role_price(role: discord.Role | None) -> float:
    discount = get_role_discount(role)
    return discount["price"] if discount else ROLE_BASE_PRICE


def format_role_price_line(role: discord.Role | None) -> str:
    from src.constants import ROLE_DISCOUNT_DAYS
    from src.economy_store import MSK_TZ
    from src.formatters import format_role_price
    discount = get_role_discount(role)
    if not discount:
        return f"Цена: **{format_role_price(ROLE_BASE_PRICE)}**"
    expires_text = discount["expires_at"].astimezone(MSK_TZ).strftime("%d.%m.%Y")
    return (
        f"Цена: ~~{format_role_price(ROLE_BASE_PRICE)}~~ "
        f"**{format_role_price(discount['price'])}**\n"
        f"Скидка действует до **{expires_text}**."
    )


def get_role_display_name(role_definition: dict) -> str:
    return role_definition["name"] + ROLE_DISPLAY_SUFFIX


# ──────────────────────────────────────────────────────────────
#  ПРОВЕРКА / УПРАВЛЕНИЕ РОЛЯМИ ИГРОКА
# ──────────────────────────────────────────────────────────────

def has_game_role(member, role_key: str, account: dict | None = None) -> bool:
    role_definition = get_role_definition(role_key)
    if role_definition is None:
        return False
    if account and role_key in account.get("owned_roles", []):
        return True
    return find_member_role(member, role_definition) is not None


def add_owned_role(account: dict, role_key: str):
    if role_key not in account["owned_roles"]:
        account["owned_roles"].append(role_key)


def remove_expired_role_discounts():
    expired_ids = []
    for role_id, discount in _economy().get("role_discounts", {}).items():
        from src.economy_store import parse_local_datetime, now_local
        if not isinstance(discount, dict):
            expired_ids.append(role_id)
            continue
        if parse_local_datetime(discount.get("expires_at")) <= now_local():
            expired_ids.append(role_id)
    for role_id in expired_ids:
        _economy()["role_discounts"].pop(role_id, None)


# ──────────────────────────────────────────────────────────────
#  ПОДСКАЗКА О КОМАНДАХ РОЛИ
# ──────────────────────────────────────────────────────────────

def get_role_command_hint(role_key: str) -> str:
    if role_key == DEALER_ROLE_KEY:
        return (
            "\n\nКоманды торговца:\n"
            "`/dealer` — заполнить повозку на 10–35% раз в час.\n"
            "`/dealer-delivery` — доставить полную повозку и получить 500–625."
        )
    if role_key == MOONSHINER_ROLE_KEY:
        return (
            "\n\nКоманды самогонщика:\n"
            "`/moonshine` — открыть меню предприятия, выбрать бражку за 50, "
            "добавить особые ингредиенты, купить улучшения и отвезти повозку."
        )
    if role_key == "miner":
        return (
            "\n\nКоманды шахтёра:\n"
            "`/mine` — копать один куб породы (лимит 3 в день).\n"
            "`/mine-status` — глубина, инвентарь, состояние кирки.\n"
            "`/mine-buy` — купить расходники и кирки.\n"
            "`/mine-sell` — продать руду, слитки и находки.\n"
            "`/mine-smelt` — переплавить руду у кузнеца.\n"
            "`/mine-forge` — создать украшение у ювелира."
        )
    return ""


# ──────────────────────────────────────────────────────────────
#  СОЗДАНИЕ / ОБНОВЛЕНИЕ РОЛЕЙ НА СЕРВЕРЕ
# ──────────────────────────────────────────────────────────────

async def ensure_guild_roles(guild: discord.Guild) -> dict:
    """Создаёт/обновляет игровые роли и заголовочную роль на сервере."""
    created   = []
    updated   = []
    skipped   = []
    errors    = []
    game_roles = []

    for role_definition in ROLE_DEFINITIONS:
        display_name = get_role_display_name(role_definition)
        role         = find_guild_role(guild, role_definition)

        if role is None:
            try:
                role = await guild.create_role(
                    name=display_name,
                    color=ROLE_DISPLAY_COLOR,
                    reason="WildWest bot: создание игровой роли",
                )
                created.append(display_name)
            except (discord.Forbidden, discord.HTTPException) as e:
                errors.append(f"'{display_name}': {e}")
                continue
        else:
            needs_edit = role.name != display_name or role.color != ROLE_DISPLAY_COLOR
            if needs_edit:
                try:
                    await role.edit(
                        name=display_name,
                        color=ROLE_DISPLAY_COLOR,
                        reason="WildWest bot: обновление игровой роли",
                    )
                    updated.append(display_name)
                except (discord.Forbidden, discord.HTTPException) as e:
                    errors.append(f"'{display_name}': {e}")
            else:
                skipped.append(display_name)
        game_roles.append(role)

    # Заголовочная роль "Роли WildWest:"
    header_role = discord.utils.find(
        lambda r: normalize_role_name(r.name) == normalize_role_name(WILDWEST_HEADER_ROLE_NAME),
        guild.roles,
    )
    if header_role is None:
        try:
            header_role = await guild.create_role(
                name=WILDWEST_HEADER_ROLE_NAME,
                color=WILDWEST_HEADER_ROLE_COLOR,
                reason="WildWest bot: создание заголовочной роли",
            )
            created.append(WILDWEST_HEADER_ROLE_NAME)
        except (discord.Forbidden, discord.HTTPException) as e:
            errors.append(f"'{WILDWEST_HEADER_ROLE_NAME}': {e}")
            header_role = None
    else:
        needs_edit = (
            header_role.name  != WILDWEST_HEADER_ROLE_NAME
            or header_role.color != WILDWEST_HEADER_ROLE_COLOR
        )
        if needs_edit:
            try:
                await header_role.edit(
                    name=WILDWEST_HEADER_ROLE_NAME,
                    color=WILDWEST_HEADER_ROLE_COLOR,
                    reason="WildWest bot: обновление заголовочной роли",
                )
                updated.append(WILDWEST_HEADER_ROLE_NAME)
            except (discord.Forbidden, discord.HTTPException) as e:
                errors.append(f"'{WILDWEST_HEADER_ROLE_NAME}': {e}")
        else:
            skipped.append(WILDWEST_HEADER_ROLE_NAME)

    # Разместить заголовочную роль выше игровых
    if header_role is not None and game_roles:
        try:
            max_pos = max(r.position for r in game_roles)
            if header_role.position <= max_pos:
                await guild.edit_role_positions(
                    positions={header_role: max_pos + 1},
                    reason="WildWest bot: позиционирование заголовочной роли",
                )
        except (discord.Forbidden, discord.HTTPException):
            pass

    # Выдать заголовочную роль всем участникам (не ботам)
    assigned_count = 0
    if header_role is not None:
        for member in guild.members:
            if member.bot:
                continue
            if header_role not in member.roles:
                try:
                    await member.add_roles(
                        header_role, reason="WildWest bot: выдача заголовочной роли"
                    )
                    assigned_count += 1
                except (discord.Forbidden, discord.HTTPException):
                    pass

    return {
        "created": created, "updated": updated,
        "skipped": skipped, "errors":  errors,
        "assigned": assigned_count,
    }


# ──────────────────────────────────────────────────────────────
#  EMBED-СТРОИТЕЛИ
# ──────────────────────────────────────────────────────────────

def build_roles_embed(guild, member=None, account=None) -> discord.Embed:
    from src.constants import ROLE_IMAGE_FILE, ROLE_IMAGE_ATTACHMENT_NAME
    from src.formatters import get_custom_message

    embed = discord.Embed(
        title=       "Роли",
        description= get_custom_message("roles_description"),
        color=       discord.Color.gold(),
    )
    if os.path.exists(ROLE_IMAGE_FILE):
        embed.set_image(url=f"attachment://{ROLE_IMAGE_ATTACHMENT_NAME}")

    for role_definition in ROLE_DEFINITIONS:
        role      = find_guild_role(guild, role_definition)
        icon      = get_role_icon(role_definition, role)
        owns_role = (
            member is not None
            and has_game_role(member, role_definition["key"], account)
        )
        if owns_role:
            status = f"{icon} Куплено"
        else:
            status = "доступно" if role_definition["available"] else "пока недоступно"
        price_line = format_role_price_line(role)
        role_note  = "" if role is not None else "\nDiscord-роль на сервере не найдена."
        embed.add_field(
            name=  f"{icon} {role_definition['name']}",
            value= (
                f"{role_definition['description']}\n"
                f"{price_line}\n"
                f"Статус: **{status}**.{role_note}"
            ),
            inline=False,
        )
    embed.set_footer(text=get_custom_message("roles_footer"))
    return embed


def build_balance_embed(guild, member, account: dict, rate: float) -> discord.Embed:
    from src.economy_store import get_account
    from src.formatters import (
        format_money_plain, format_gold_plain, format_treasure_maps_plain,
        format_number, format_exchange_rate, format_balance_role_sections,
        get_cash_emoji, get_gold_emoji, get_map_emoji, get_stats_emoji,
        get_safe_emoji, get_lock_emoji,
    )
    from src.constants import (
        BALANCE_IMAGE_FILE, BALANCE_IMAGE_ATTACHMENT_NAME,
    )
    from emoji_config import (
        DEFAULT_BALANCE_FINANCE_EMOJI, DEFAULT_BALANCE_ROLES_EMOJI,
        DEFAULT_BALANCE_ECONOMY_EMOJI, DEFAULT_BALANCE_GANG_EMOJI,
    )

    cash           = account["cash"]
    gold           = account["gold"]
    treasure_maps  = account["treasure_maps"]
    role_sections, unavailable_role_sections = format_balance_role_sections(
        guild, member, account
    )
    from src.weapon_system import WEAPON_DISPLAY_NAMES, weapon_emoji
    loadout = account.get("weapon_loadout", {"sidearms": [], "longarms": []})
    condition = account.get("weapon_condition", {})

    def weapon_slot_text(keys):
        if not keys:
            return "*пусто*"
        return " · ".join(
            f"{weapon_emoji(key)} **{WEAPON_DISPLAY_NAMES.get(key, key)}** "
            f"({condition.get(key, 100):g}%)"
            for key in keys
        )

    weapon_section = (
        "🔫 Активное оружие\n"
        f"├─ Короткоствольное: {weapon_slot_text(loadout.get('sidearms', []))}\n"
        f"├─ Крупное: {weapon_slot_text(loadout.get('longarms', []))}\n"
        "└─ Снаряжение и боезапас: `/weapons`"
    )

    gang_name  = account.get("gang_name")
    gang_str   = ""
    gang_emoji = _economy().get("balance_ui_gang", DEFAULT_BALANCE_GANG_EMOJI)
    if gang_name:
        guild_data = _economy().current()
        gang       = guild_data.get("gangs", {}).get(gang_name, {})
        gang_id    = gang.get("id", "N/A")
        is_leader  = gang.get("leader") == member.id
        role_name  = (
            gang.get("leader_role_name", "Лидер")
            if is_leader else gang.get("member_role_name", "Участник")
        )
        gang_str = f"{gang_emoji} Фракция: **{gang_name}** [#{gang_id}] ({role_name})\n\n"

    has_safe  = account.get("inventory", {}).get("safe", 0) > 0
    safe_icon = "" if has_safe else f"{get_lock_emoji()} "

    fin_emoji   = _economy().get("balance_ui_finance", DEFAULT_BALANCE_FINANCE_EMOJI)
    roles_emoji = _economy().get("balance_ui_roles",   DEFAULT_BALANCE_ROLES_EMOJI)
    eco_emoji   = _economy().get("balance_ui_economy", DEFAULT_BALANCE_ECONOMY_EMOJI)

    description = (
        f"{fin_emoji} Финансы\n"
        f"├─ {get_cash_emoji()} Деньги: {format_money_plain(cash)}\n"
        f"├─ {get_gold_emoji()} Золото: {format_gold_plain(gold)}\n"
        f"├─ {safe_icon}{get_safe_emoji()}Сейф: "
        f"{format_number(account.get('safe_cash', 0.0))}{get_cash_emoji()}/"
        f"{format_number(account.get('safe_gold', 0.0))}{get_gold_emoji()}\n"
        f"└─ {get_map_emoji()} Карты: {format_treasure_maps_plain(treasure_maps)}\n\n"
        f"{gang_str}"
        f"{roles_emoji} Роли\n"
        f"{role_sections}\n"
        f"\n{weapon_section}\n\n"
        f"{eco_emoji} Экономика\n"
        f"└─ Курс: 1 {get_gold_emoji()} = {format_exchange_rate(rate)}\n\n"
        f"{get_lock_emoji()} Недоступные роли\n"
        f"{unavailable_role_sections}\n"
    )
    embed = discord.Embed(
        title=       f"{get_stats_emoji()}Статистика: {member.display_name}",
        description= description,
        color=       discord.Color.dark_gold(),
    )
    if os.path.exists(BALANCE_IMAGE_FILE):
        embed.set_image(url=f"attachment://{BALANCE_IMAGE_ATTACHMENT_NAME}")
    return embed


# ──────────────────────────────────────────────────────────────
#  UI: КНОПКИ / VIEW МАГАЗИНА РОЛЕЙ
# ──────────────────────────────────────────────────────────────

class RoleBuyButton(discord.ui.Button):
    def __init__(self, role_definition: dict, guild, member=None, account=None):
        role  = find_guild_role(guild, role_definition)
        price = get_role_price(role)
        icon  = get_role_icon(role_definition, role)
        owns_role = (
            member is not None
            and has_game_role(member, role_definition["key"], account)
        )

        if owns_role:
            label       = "Куплено"
            style       = discord.ButtonStyle.secondary
            disabled    = True
            emoji_to_use = icon or None
        elif role_definition["available"]:
            from src.formatters import format_gold_price_value
            label    = f"Купить за {format_gold_price_value(price)}"
            style    = discord.ButtonStyle.success
            disabled = False
            if icon:
                emoji_to_use = icon
            else:
                from src.formatters import get_gold_emoji
                gold_raw = get_gold_emoji()
                try:
                    emoji_to_use = discord.PartialEmoji.from_str(gold_raw)
                except Exception:
                    emoji_to_use = gold_raw
        else:
            label       = "Пока недоступно"
            style       = discord.ButtonStyle.secondary
            disabled    = True
            emoji_to_use = icon or None

        super().__init__(
            label=     label,
            style=     style,
            emoji=     emoji_to_use,
            disabled=  disabled,
            custom_id= f"role_shop:{role_definition['key']}",
        )
        self.role_key = role_definition["key"]

    async def callback(self, interaction: discord.Interaction):
        await buy_game_role(interaction, self.role_key)


class RoleShopView(discord.ui.View):
    def __init__(self, guild, member=None, account=None):
        super().__init__(timeout=600)
        for role_definition in ROLE_DEFINITIONS:
            self.add_item(RoleBuyButton(role_definition, guild, member, account))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        from src.economy_store import set_economy_guild_id
        set_economy_guild_id(interaction.guild_id)
        return True


# ──────────────────────────────────────────────────────────────
#  ПОКУПКА РОЛИ
# ──────────────────────────────────────────────────────────────

async def buy_game_role(interaction: discord.Interaction, role_key: str):
    from src.economy_store import (
        set_economy_guild_id, reset_economy_guild_id, get_account, save_economy,
    )
    from src.formatters import format_gold, format_role_price

    role_definition = get_role_definition(role_key)
    if role_definition is None:
        await interaction.response.send_message("Эта роль не найдена.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    token = set_economy_guild_id(interaction.guild_id)
    try:
        if not role_definition["available"]:
            await interaction.followup.send("Эта роль пока недоступна.", ephemeral=True)
            return

        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.followup.send(
                "Роли можно покупать только на сервере.", ephemeral=True
            )
            return

        member = interaction.user
        role   = find_guild_role(interaction.guild, role_definition)

        if role is None:
            try:
                role = await interaction.guild.create_role(
                    name=  get_role_display_name(role_definition),
                    color= ROLE_DISPLAY_COLOR,
                    reason="WildWest bot: автосоздание игровой роли при покупке",
                )
            except (discord.Forbidden, discord.HTTPException) as e:
                await interaction.followup.send(
                    f"На сервере нет роли **{role_definition['name']}** и не удалось её создать: {e}. "
                    "Администратор может использовать `/restart-roles`.",
                    ephemeral=True,
                )
                return

        if (
            role not in member.roles
            and hasattr(role, "is_assignable")
            and not role.is_assignable()
        ):
            await interaction.followup.send(
                f"Я не могу выдать роль {role.mention}: она выше роли бота "
                "или управляется Discord.",
                ephemeral=True,
            )
            return

        paid_price   = 0.0
        charged      = False
        already_owned = False

        async with _economy_lock():
            remove_expired_role_discounts()
            from src.economy_store import update_gold_rate
            update_gold_rate()
            account       = get_account(member.id)
            already_owned = role_key in account["owned_roles"] or role in member.roles

            if already_owned:
                add_owned_role(account, role_key)
                save_economy()
            else:
                paid_price = get_role_price(role)
                if account["gold"] + 0.0001 < paid_price:
                    save_economy()
                    await interaction.followup.send(
                        f"Недостаточно золота. Нужно **{format_role_price(paid_price)}**, "
                        f"а у вас **{format_gold(account.get('gold', 0.0))}**.",
                        ephemeral=True,
                    )
                    return
                else:
                    account["gold"] -= paid_price
                    add_owned_role(account, role_key)
                    charged = True
                    save_economy()

        if role not in member.roles:
            try:
                await member.add_roles(role, reason="Покупка игровой роли")
            except (discord.Forbidden, discord.HTTPException) as e:
                if charged:
                    async with _economy_lock():
                        account = get_account(member.id)
                        account["gold"] += paid_price
                        if role_key in account["owned_roles"]:
                            account["owned_roles"].remove(role_key)
                        save_economy()
                await interaction.followup.send(
                    f"Не удалось выдать роль {role.mention}. Покупка отменена: {e}",
                    ephemeral=True,
                )
                return

        if already_owned:
            message = f"У вас уже есть роль {role.mention}."
        else:
            message = f"Вы купили роль {role.mention} за **{format_role_price(paid_price)}**."

        message += get_role_command_hint(role_key)
        await interaction.followup.send(message, ephemeral=True)
    finally:
        reset_economy_guild_id(token)
