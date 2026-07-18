"""Unified administrator controls for player economy and professions."""

from __future__ import annotations

from datetime import date

import discord
from discord import app_commands
from discord.ext import commands

from bot import (
    ROLE_DEFINITIONS,
    economy_data,
    economy_lock,
    ensure_guild_roles,
    find_guild_role,
    format_duration,
    format_number,
    get_account,
    get_cash_emoji,
    get_gold_emoji,
    reset_economy_guild_id,
    save_economy,
    set_economy_guild_id,
)
from cogs.catalog import CATALOG_ITEMS
from src.admin_logic import (
    PROFESSION_NAMES,
    change_quantity,
    reset_account_cooldowns,
    reset_mechanic,
    set_profession_progress,
)
from src.bounty_logic import get_bounty_cooldown, normalize_bounty_data
from src.collector_logic import (
    COLLECTIONS,
    COLLECTION_ITEMS,
    item_display_name,
    normalize_collector_data,
    total_items as collector_total_items,
)
from src.company_logic import (
    COMPANY_DEFINITIONS,
    WHEELER_RAWSON,
    get_company_state,
    normalize_company_state,
)
from src.mine_logic import ALL_SELLABLE_NAMES, DAILY_MINE_LIMIT, PICKAXES
from src.moonshiner_logic import (
    get_moonshine_level,
    normalize_moonshine_data,
)
from src.naturalist_logic import (
    ANIMALS,
    LEGENDARY_ANIMALS,
    count_naturalist_samples,
    get_naturalist_legendary_cooldown,
    get_naturalist_sample_cooldown,
    get_naturalist_tranq_cap,
    normalize_naturalist_data,
)
from src.weapon_system import (
    ammo_total,
    normalize_weapon_state,
    owned_weapon_keys,
)


ADMIN_COLOR = discord.Color.dark_gold()

ACTION_CHOICES = [
    app_commands.Choice(name="Добавить", value="add"),
    app_commands.Choice(name="Убрать", value="remove"),
    app_commands.Choice(name="Установить", value="set"),
]

STORAGE_CHOICES = [
    app_commands.Choice(name="Каталог / оружие / патроны", value="catalog"),
    app_commands.Choice(name="Карты коллекционера", value="collector_map"),
    app_commands.Choice(name="Находки коллекционера", value="collector_item"),
    app_commands.Choice(name="Инструменты коллекционера", value="collector_tool"),
    app_commands.Choice(name="Образцы натуралиста", value="naturalist_sample"),
    app_commands.Choice(name="Транквилизаторы натуралиста", value="naturalist_supply"),
    app_commands.Choice(name="Добыча шахтёра", value="mine_inventory"),
]

COOLDOWN_CHOICES = [
    app_commands.Choice(name="Все активности", value="all"),
    app_commands.Choice(name="Обычная работа", value="work"),
    app_commands.Choice(name="Торговец", value="trader"),
    app_commands.Choice(name="Охотник за головами", value="bounty"),
    app_commands.Choice(name="Натуралист: обычная охота", value="naturalist"),
    app_commands.Choice(name="Натуралист: легендарная охота", value="naturalist_legendary"),
    app_commands.Choice(name="Ограбление игрока", value="robbery"),
    app_commands.Choice(name="Сейф", value="safe"),
    app_commands.Choice(name="Ограбление банды", value="gang"),
    app_commands.Choice(name="Шахта: дневные попытки", value="mine"),
]

PROGRESS_CHOICES = [
    app_commands.Choice(name="Общий ранг", value="rank"),
    app_commands.Choice(name="Охотник за головами", value="bounty"),
    app_commands.Choice(name="Натуралист", value="naturalist"),
    app_commands.Choice(name="Коллекционер", value="collector"),
]

RESET_CHOICES = [
    app_commands.Choice(name="Все профессии", value="all_professions"),
    app_commands.Choice(name="Охотник за головами", value="bounty"),
    app_commands.Choice(name="Натуралист", value="naturalist"),
    app_commands.Choice(name="Коллекционер", value="collector"),
    app_commands.Choice(name="Самогонщик", value="moonshine"),
    app_commands.Choice(name="Торговец", value="trader"),
    app_commands.Choice(name="Шахтёр", value="miner"),
]

MINE_FIELD_CHOICES = [
    app_commands.Choice(name="Попытки сегодня", value="attempts"),
    app_commands.Choice(name="Личная глубина", value="depth"),
    app_commands.Choice(name="Прочность кирки", value="durability"),
    app_commands.Choice(name="Масло", value="oil"),
    app_commands.Choice(name="Крепёжный лес", value="wood"),
    app_commands.Choice(name="Динамит", value="dynamite"),
    app_commands.Choice(name="Канарейки", value="canary"),
]

ROLE_CHOICES = [
    app_commands.Choice(name=definition["name"], value=definition["key"])
    for definition in ROLE_DEFINITIONS
]

ROLE_ACTION_CHOICES = [
    app_commands.Choice(name="Выдать", value="grant"),
    app_commands.Choice(name="Забрать", value="remove"),
    app_commands.Choice(name="Синхронизировать", value="sync"),
]


def _choice_value(value) -> str:
    return str(getattr(value, "value", value) or "")


def _ready_text(seconds: float) -> str:
    return "готово" if seconds <= 0 else format_duration(seconds)


def _matches(current: str, key: str, label: str) -> bool:
    query = current.strip().casefold()
    return not query or query in key.casefold() or query in label.casefold()


async def admin_item_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    storage = _choice_value(getattr(interaction.namespace, "storage", ""))
    rows: list[tuple[str, str]] = []
    if storage == "catalog":
        rows = [(key, data["name"]) for key, data in CATALOG_ITEMS.items()]
    elif storage == "collector_map":
        rows = [(key, data["name"]) for key, data in COLLECTIONS.items()]
    elif storage == "collector_item":
        rows = [
            (key, item_display_name(key))
            for items in COLLECTION_ITEMS.values()
            for key in items
        ]
    elif storage == "collector_tool":
        rows = [("shovel", "Лопата"), ("detector", "Металлоискатель")]
    elif storage == "naturalist_sample":
        rows = [
            (key, data["name"])
            for key, data in {**ANIMALS, **LEGENDARY_ANIMALS}.items()
        ]
    elif storage == "naturalist_supply":
        rows = [("tranquilizers", "Транквилизаторы")]
    elif storage == "mine_inventory":
        rows = list(ALL_SELLABLE_NAMES.items())

    choices = []
    seen = set()
    for key, label in rows:
        if key in seen or not _matches(current, key, label):
            continue
        seen.add(key)
        choices.append(app_commands.Choice(name=f"{label} · {key}"[:100], value=key[:100]))
        if len(choices) == 25:
            break
    return choices


def _catalog_quantity(account: dict, item_key: str, action: str, amount: int):
    item = CATALOG_ITEMS.get(item_key)
    if item is None:
        raise ValueError("Товар с таким ключом не найден в каталоге.")

    normalize_weapon_state(account, CATALOG_ITEMS)
    item_type = item.get("type")
    if item_type == "ammo":
        container = account["ammo"][item["ammo_class"]]
        old, new = change_quantity(container, item["ammo_type"], action, amount)
    elif item_type == "moonshine_ingredient":
        moonshine = normalize_moonshine_data(account.get("moonshine"))
        account["moonshine"] = moonshine
        ingredient = item["ingredient"]
        old, new = change_quantity(moonshine["ingredients"], ingredient, action, amount)
    else:
        inventory = account.setdefault("inventory", {})
        cap = 1 if item_type == "unique" else None
        old, new = change_quantity(inventory, item_key, action, amount, cap=cap)

    # Initialize condition for granted weapons and remove stale loadout records
    # after confiscation.
    normalize_weapon_state(account, CATALOG_ITEMS)
    return item["name"], old, new


def _profession_quantity(
    account: dict,
    storage: str,
    item_key: str,
    action: str,
    amount: int,
):
    if storage == "collector_map":
        if item_key not in COLLECTIONS:
            raise ValueError("Неизвестная карта коллекционера.")
        data = normalize_collector_data(account.get("collector"))
        account["collector"] = data
        old, new = change_quantity(data["maps"], item_key, action, amount)
        return f"Карта: {COLLECTIONS[item_key]['name']}", old, new
    if storage == "collector_item":
        valid = {key for items in COLLECTION_ITEMS.values() for key in items}
        if item_key not in valid:
            raise ValueError("Неизвестная находка коллекционера.")
        data = normalize_collector_data(account.get("collector"))
        account["collector"] = data
        old, new = change_quantity(data["inventory"], item_key, action, amount)
        return item_display_name(item_key), old, new
    if storage == "collector_tool":
        if item_key not in {"shovel", "detector"}:
            raise ValueError("Неизвестный инструмент коллекционера.")
        data = normalize_collector_data(account.get("collector"))
        account["collector"] = data
        numeric = {key: int(value) for key, value in data["tools"].items()}
        old, new = change_quantity(numeric, item_key, action, amount, cap=1)
        data["tools"][item_key] = bool(new)
        label = "Лопата" if item_key == "shovel" else "Металлоискатель"
        return label, old, new
    if storage == "naturalist_sample":
        animals = {**ANIMALS, **LEGENDARY_ANIMALS}
        if item_key not in animals:
            raise ValueError("Неизвестный образец натуралиста.")
        data = normalize_naturalist_data(account.get("naturalist"))
        account["naturalist"] = data
        old, new = change_quantity(data["samples"], item_key, action, amount)
        return f"Образец: {animals[item_key]['name']}", old, new
    if storage == "naturalist_supply":
        if item_key != "tranquilizers":
            raise ValueError("Для этого хранилища доступен ключ tranquilizers.")
        data = normalize_naturalist_data(account.get("naturalist"))
        account["naturalist"] = data
        cap = get_naturalist_tranq_cap(data)
        old, new = change_quantity(
            data["inventory"], item_key, action, amount, cap=cap
        )
        return "Транквилизаторы", old, new
    raise ValueError("Неизвестное хранилище.")


def _reset_miner_player(player: dict) -> None:
    player.update(
        {
            "pickaxe_type": "basic",
            "pickaxe_durability": PICKAXES["basic"]["max_durability"],
            "oil_units": 5,
            "wood_count": 0,
            "dynamite_count": 0,
            "canary_count": 0,
            "daily_mines_left": DAILY_MINE_LIMIT,
            "last_mine_date": date.today().isoformat(),
            "current_depth": 0,
            "total_mined": 0,
            "inventory": {},
        }
    )


class AdminCog(commands.Cog):
    admin = app_commands.Group(
        name="admin",
        description="Полное управление игроками и механиками бота",
        default_permissions=discord.Permissions(administrator=True),
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            message = "У вас недостаточно прав. Требуется право администратора."
        else:
            message = f"Админ-команда не выполнена: {error}"
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    @admin.command(name="inspect", description="Показать полное игровое состояние участника")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(member="Участник для проверки")
    async def inspect(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer(ephemeral=True)
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(member.id)
                bounty = normalize_bounty_data(account.get("bounty"))
                naturalist = normalize_naturalist_data(account.get("naturalist"))
                collector = normalize_collector_data(account.get("collector"))
                moonshine = normalize_moonshine_data(account.get("moonshine"))
                account["bounty"] = bounty
                account["naturalist"] = naturalist
                account["collector"] = collector
                account["moonshine"] = moonshine
                normalize_weapon_state(account, CATALOG_ITEMS)
                guild_data = economy_data.current()
                gang_name = account.get("gang_name") or "нет"
                inventory_count = sum(
                    max(0, int(value or 0))
                    for value in account.get("inventory", {}).values()
                    if isinstance(value, (int, float))
                )
                save_economy()

                embed = discord.Embed(
                    title=f"Админ-проверка: {member.display_name}",
                    description=f"{member.mention} · ID `{member.id}`",
                    color=ADMIN_COLOR,
                )
                embed.add_field(
                    name="Экономика",
                    value=(
                        f"Наличные: **{format_number(account['cash'])} {get_cash_emoji()}**\n"
                        f"Золото: **{format_number(account['gold'])} {get_gold_emoji()}**\n"
                        f"Сейф: **{format_number(account.get('safe_cash', 0))} {get_cash_emoji()} / "
                        f"{format_number(account.get('safe_gold', 0))} {get_gold_emoji()}**\n"
                        f"Карты сокровищ: **{account.get('treasure_maps', 0)}**\n"
                        f"Предметов каталога: **{inventory_count}**"
                    ),
                    inline=True,
                )
                embed.add_field(
                    name="Социальное",
                    value=(
                        f"Банда: **{gang_name}**\n"
                        f"Купленные профессии: **{len(account.get('owned_roles', []))}**\n"
                        f"Инвестиции: **{sum(int(c.get('investors', {}).get(str(member.id), 0) or 0) for c in guild_data.get('companies', {}).values())}**"
                    ),
                    inline=True,
                )
                embed.add_field(
                    name="Охотник",
                    value=(
                        f"Ур. **{bounty['level']}**, XP **{bounty['xp']}**\n"
                        f"Поймано/сбежало: **{bounty['captures']}/{bounty['escaped']}**\n"
                        f"Контракт: **{_ready_text(get_bounty_cooldown(bounty))}**"
                    ),
                    inline=True,
                )
                embed.add_field(
                    name="Натуралист",
                    value=(
                        f"Ур. **{naturalist['level']}**, XP **{naturalist['xp']}**\n"
                        f"Образцы: **{count_naturalist_samples(naturalist)}** · "
                        f"транквилизаторы: **{naturalist['inventory']['tranquilizers']}**\n"
                        f"Охота: **{_ready_text(get_naturalist_sample_cooldown(naturalist))}** · "
                        f"легендарка: **{_ready_text(get_naturalist_legendary_cooldown(naturalist))}**"
                    ),
                    inline=False,
                )
                embed.add_field(
                    name="Коллекционер",
                    value=(
                        f"Ур. **{collector['level']}**, XP **{collector['xp']}** · "
                        f"находок: **{collector_total_items(collector)}**\n"
                        f"Карт: **{sum(collector['maps'].values())}** · "
                        f"лопата: **{'да' if collector['tools']['shovel'] else 'нет'}** · "
                        f"металлоискатель: **{'да' if collector['tools']['detector'] else 'нет'}**"
                    ),
                    inline=False,
                )
                batch = moonshine.get("batch")
                embed.add_field(
                    name="Самогонщик и торговец",
                    value=(
                        f"Самогон ур. **{get_moonshine_level(moonshine)}** · бутылки **{moonshine['bottles']}/20** · "
                        f"партия: **{batch.get('name', 'варится') if batch else 'нет'}**\n"
                        f"Ингредиенты: **{sum(moonshine['ingredients'].values())}** · "
                        f"повозка торговца: **{float(account.get('dealer_wagon', 0)):.0f}%**"
                    ),
                    inline=False,
                )
                weapons = owned_weapon_keys(account, CATALOG_ITEMS)
                ammo = sum(ammo_total(account, key) for key in account.get("ammo", {}))
                embed.add_field(
                    name="Оружие",
                    value=f"Куплено: **{len(weapons)}** · всего патронов: **{ammo}**",
                    inline=False,
                )

            leveling_cog = self.bot.get_cog("LevelingCog")
            if leveling_cog:
                rank = leveling_cog.db.get_user(str(interaction.guild_id), str(member.id))
                embed.add_field(
                    name="Общий ранг",
                    value=f"Уровень **{rank['level']}** · всего XP **{rank['xp']}**",
                    inline=True,
                )

            miner_cog = self.bot.get_cog("MinerCog")
            if miner_cog:
                player = miner_cog.db.get_player(str(interaction.guild_id), str(member.id))
                embed.add_field(
                    name="Шахтёр",
                    value=(
                        f"Глубина **{player['current_depth']} м** · попытки **{player['daily_mines_left']}**\n"
                        f"Кирка **{player['pickaxe_type']}**, прочность **{player['pickaxe_durability']}** · "
                        f"добычи в сумке **{sum(player.get('inventory', {}).values())}**"
                    ),
                    inline=False,
                )
        finally:
            reset_economy_guild_id(token)

        await interaction.followup.send(embed=embed, ephemeral=True)

    @admin.command(name="cooldown", description="Сбросить кулдаун выбранной активности")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(member="Участник", activity="Активность для сброса")
    @app_commands.choices(activity=COOLDOWN_CHOICES)
    async def cooldown(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        activity: app_commands.Choice[str],
    ):
        await interaction.response.defer(ephemeral=True)
        selected = activity.value
        token = set_economy_guild_id(interaction.guild_id)
        labels: list[str] = []
        try:
            async with economy_lock:
                account = get_account(member.id)
                if selected not in {"gang", "mine"}:
                    labels.extend(reset_account_cooldowns(account, selected))
                if selected in {"gang", "all"}:
                    gang_name = account.get("gang_name")
                    gang = economy_data.current().setdefault("gangs", {}).get(gang_name)
                    if gang:
                        gang["last_rob_at"] = None
                        labels.append(f"Ограбление банды «{gang_name}»")
                save_economy()

            if selected in {"mine", "all"}:
                miner_cog = self.bot.get_cog("MinerCog")
                if miner_cog:
                    player = miner_cog.db.get_player(str(interaction.guild_id), str(member.id))
                    player["daily_mines_left"] = DAILY_MINE_LIMIT
                    player["last_mine_date"] = date.today().isoformat()
                    miner_cog.db.save_player(str(interaction.guild_id), str(member.id), player)
                    labels.append("Шахта: дневные попытки")
                else:
                    labels.append("Шахта недоступна: модуль не загружен")
        finally:
            reset_economy_guild_id(token)

        await interaction.followup.send(
            f"Для {member.mention} сброшено: **{', '.join(labels) or 'ничего'}**.",
            ephemeral=True,
        )

    @admin.command(name="progress", description="Установить уровень и опыт игрока")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        member="Участник",
        profession="Общий ранг или профессия",
        level="Новый уровень",
        xp="Опыт: общий для ранга, текущий для профессии",
    )
    @app_commands.choices(profession=PROGRESS_CHOICES)
    async def progress(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        profession: app_commands.Choice[str],
        level: app_commands.Range[int, 1, 1000],
        xp: app_commands.Range[int, 0, 2_000_000_000] = 0,
    ):
        await interaction.response.defer(ephemeral=True)
        selected = profession.value
        if selected == "rank":
            leveling_cog = self.bot.get_cog("LevelingCog")
            if not leveling_cog:
                await interaction.followup.send("Модуль уровней не загружен.", ephemeral=True)
                return
            leveling_cog.db.set_user(str(interaction.guild_id), str(member.id), xp, level)
            await leveling_cog.handle_level_up(member, level, notify=False)
            actual_level, actual_xp = level, xp
            label = "Общий ранг"
        else:
            token = set_economy_guild_id(interaction.guild_id)
            try:
                async with economy_lock:
                    account = get_account(member.id)
                    data = set_profession_progress(account, selected, level, xp)
                    save_economy()
                    actual_level, actual_xp = data["level"], data["xp"]
            finally:
                reset_economy_guild_id(token)
            label = PROFESSION_NAMES[selected]

        await interaction.followup.send(
            f"{member.mention}: **{label}** — уровень **{actual_level}**, XP **{actual_xp}**.",
            ephemeral=True,
        )

    @admin.command(name="item", description="Выдать, изъять или установить количество предмета")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        member="Участник",
        action="Действие",
        storage="Раздел инвентаря",
        item="Ключ предмета; начните вводить название",
        amount="Количество",
    )
    @app_commands.choices(action=ACTION_CHOICES, storage=STORAGE_CHOICES)
    @app_commands.autocomplete(item=admin_item_autocomplete)
    async def item(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        action: app_commands.Choice[str],
        storage: app_commands.Choice[str],
        item: str,
        amount: app_commands.Range[int, 0, 1_000_000],
    ):
        await interaction.response.defer(ephemeral=True)
        token = set_economy_guild_id(interaction.guild_id)
        try:
            try:
                if storage.value == "mine_inventory":
                    if item not in ALL_SELLABLE_NAMES:
                        raise ValueError("Неизвестный предмет шахтёра.")
                    miner_cog = self.bot.get_cog("MinerCog")
                    if not miner_cog:
                        raise ValueError("Модуль шахтёра не загружен.")
                    player = miner_cog.db.get_player(
                        str(interaction.guild_id), str(member.id)
                    )
                    inventory = player.setdefault("inventory", {})
                    old, new = change_quantity(inventory, item, action.value, amount)
                    miner_cog.db.save_player(
                        str(interaction.guild_id), str(member.id), player
                    )
                    label = ALL_SELLABLE_NAMES[item]
                else:
                    async with economy_lock:
                        account = get_account(member.id)
                        if storage.value == "catalog":
                            label, old, new = _catalog_quantity(
                                account, item, action.value, amount
                            )
                        else:
                            label, old, new = _profession_quantity(
                                account, storage.value, item, action.value, amount
                            )
                        save_economy()
            except ValueError as exc:
                await interaction.followup.send(str(exc), ephemeral=True)
                return
        finally:
            reset_economy_guild_id(token)

        await interaction.followup.send(
            f"{member.mention}: **{label}** — было **{old}**, стало **{new}**.",
            ephemeral=True,
        )

    @admin.command(name="role", description="Выдать, забрать или синхронизировать профессию")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        member="Участник",
        role="Игровая профессия",
        action="Действие с ролью и записью в экономике",
    )
    @app_commands.choices(role=ROLE_CHOICES, action=ROLE_ACTION_CHOICES)
    async def role(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: app_commands.Choice[str],
        action: app_commands.Choice[str],
    ):
        await interaction.response.defer(ephemeral=True)
        definition = next(
            (item for item in ROLE_DEFINITIONS if item["key"] == role.value),
            None,
        )
        if definition is None:
            await interaction.followup.send("Неизвестная игровая роль.", ephemeral=True)
            return

        role_map = await ensure_guild_roles(interaction.guild)
        discord_role = role_map.get(role.value) or find_guild_role(
            interaction.guild, definition
        )
        if discord_role is None:
            await interaction.followup.send(
                "Discord-роль не найдена и не была создана.", ephemeral=True
            )
            return

        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(member.id)
                owned = account.setdefault("owned_roles", [])
                stored = role.value in owned
            has_discord_role = discord_role in member.roles

            if action.value == "grant":
                if not has_discord_role:
                    await member.add_roles(
                        discord_role,
                        reason=f"Admin {interaction.user} granted game profession",
                    )
                stored = True
                result = "выдана"
            elif action.value == "remove":
                if has_discord_role:
                    await member.remove_roles(
                        discord_role,
                        reason=f"Admin {interaction.user} removed game profession",
                    )
                stored = False
                result = "забрана"
            else:
                # A positive record on either side is authoritative during a
                # repair: sync restores the missing side and never confiscates.
                if stored and not has_discord_role:
                    await member.add_roles(
                        discord_role,
                        reason=f"Admin {interaction.user} synchronized game profession",
                    )
                elif has_discord_role and not stored:
                    stored = True
                result = "синхронизирована"

            async with economy_lock:
                account = get_account(member.id)
                owned = account.setdefault("owned_roles", [])
                if stored and role.value not in owned:
                    owned.append(role.value)
                elif not stored:
                    account["owned_roles"] = [key for key in owned if key != role.value]
                save_economy()
        finally:
            reset_economy_guild_id(token)

        await interaction.followup.send(
            f"Профессия **{definition['name']}** {result} для {member.mention}.",
            ephemeral=True,
        )

    @admin.command(name="investment", description="Исправить учёт инвестиций игрока")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        member="Инвестор",
        action="Добавить, убрать или установить вклад",
        amount="Сумма инвестиции; баланс игрока не меняется",
    )
    @app_commands.choices(action=ACTION_CHOICES)
    async def investment(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        action: app_commands.Choice[str],
        amount: app_commands.Range[int, 0, 100_000_000],
    ):
        await interaction.response.defer(ephemeral=True)
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                guild_data = economy_data.current()
                company = get_company_state(guild_data, WHEELER_RAWSON)
                old_level = company["level"]
                old, new = change_quantity(
                    company["investors"], str(member.id), action.value, amount
                )
                company["invested"] = max(
                    0, int(company.get("invested", 0)) + (new - old)
                )
                company = normalize_company_state(WHEELER_RAWSON, company)
                guild_data.setdefault("companies", {})[WHEELER_RAWSON] = company
                save_economy()
        finally:
            reset_economy_guild_id(token)

        level_note = (
            f" Уровень компании изменился: **{old_level} → {company['level']}**."
            if old_level != company["level"]
            else ""
        )
        await interaction.followup.send(
            f"{member.mention}: инвестиции в **{COMPANY_DEFINITIONS[WHEELER_RAWSON]['name']}** — "
            f"было **{old}**, стало **{new}**. Общий фонд: **{company['invested']}**."
            f"{level_note}\nБаланс игрока этой командой не изменяется.",
            ephemeral=True,
        )

    @admin.command(name="reset", description="Полностью сбросить выбранную профессию игрока")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        member="Участник",
        mechanic="Профессия для сброса",
        confirm="Подтверждение необратимого сброса прогресса",
    )
    @app_commands.choices(mechanic=RESET_CHOICES)
    async def reset(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        mechanic: app_commands.Choice[str],
        confirm: bool,
    ):
        if not confirm:
            await interaction.response.send_message(
                "Сброс отменён: для выполнения укажите `confirm: True`.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        selected = mechanic.value
        labels: list[str] = []
        token = set_economy_guild_id(interaction.guild_id)
        try:
            if selected != "miner":
                async with economy_lock:
                    account = get_account(member.id)
                    labels.extend(reset_mechanic(account, selected))
                    save_economy()

            if selected in {"miner", "all_professions"}:
                miner_cog = self.bot.get_cog("MinerCog")
                if miner_cog:
                    player = miner_cog.db.get_player(str(interaction.guild_id), str(member.id))
                    _reset_miner_player(player)
                    miner_cog.db.save_player(str(interaction.guild_id), str(member.id), player)
                    labels.append("Шахтёр")
                else:
                    labels.append("Шахтёр не сброшен: модуль не загружен")
        finally:
            reset_economy_guild_id(token)

        await interaction.followup.send(
            f"У {member.mention} полностью сброшено: **{', '.join(labels)}**. "
            "Валюта и купленные Discord-роли сохранены.",
            ephemeral=True,
        )

    @admin.command(name="mine", description="Изменить состояние шахтёра")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        member="Участник",
        field="Параметр шахты",
        action="Действие",
        value="Значение",
    )
    @app_commands.choices(field=MINE_FIELD_CHOICES, action=ACTION_CHOICES)
    async def mine(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        field: app_commands.Choice[str],
        action: app_commands.Choice[str],
        value: app_commands.Range[int, 0, 100_000],
    ):
        await interaction.response.defer(ephemeral=True)
        miner_cog = self.bot.get_cog("MinerCog")
        if not miner_cog:
            await interaction.followup.send("Модуль шахтёра не загружен.", ephemeral=True)
            return

        player = miner_cog.db.get_player(str(interaction.guild_id), str(member.id))
        fields = {
            "attempts": ("daily_mines_left", 100, "Попытки сегодня"),
            "depth": ("current_depth", 9_999, "Личная глубина"),
            "oil": ("oil_units", 100_000, "Масло"),
            "wood": ("wood_count", 100_000, "Крепёжный лес"),
            "dynamite": ("dynamite_count", 100_000, "Динамит"),
            "canary": ("canary_count", 100_000, "Канарейки"),
        }
        if field.value == "durability":
            pickaxe = PICKAXES.get(player.get("pickaxe_type"), PICKAXES["basic"])
            key, cap, label = (
                "pickaxe_durability",
                pickaxe["max_durability"],
                "Прочность кирки",
            )
        else:
            key, cap, label = fields[field.value]

        old, new = change_quantity(player, key, action.value, value, cap=cap)
        if field.value == "attempts":
            player["last_mine_date"] = date.today().isoformat()
        miner_cog.db.save_player(str(interaction.guild_id), str(member.id), player)
        await interaction.followup.send(
            f"{member.mention}: **{label}** — было **{old}**, стало **{new}**.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
