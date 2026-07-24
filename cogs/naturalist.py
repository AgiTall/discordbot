import discord
from discord.ext import commands
from discord import app_commands
import random
from datetime import timedelta
from src.naturalist_logic import *
from src.weapon_system import normalize_weapon_state


class NaturalistOwnerView(discord.ui.View):
    def __init__(self, bot, user_id, timeout=600):
        self.bot = bot
        super().__init__(timeout=timeout)
        self.user_id = user_id

    async def interaction_check(self, interaction):
        self.bot.set_economy_guild_id(interaction.guild_id)
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Это меню натуралиста открыто не для вас.", ephemeral=True
            )
            return False
        return True


class NaturalistMainView(NaturalistOwnerView):
    def __init__(self, bot, user_id):
        super().__init__(bot, user_id)
        self.sample_button.emoji    = get_naturalist_button_emoji("sample")
        self.sell_button.emoji      = get_naturalist_button_emoji("sell")
        self.collection_button.emoji = get_naturalist_button_emoji("collection")
        self.legendary_button.emoji = get_naturalist_button_emoji("legendary")
        self.pelt_button.emoji       = "🦌"
        self.shop_button.emoji       = get_naturalist_button_emoji("shop")
        self.refresh_button.emoji   = get_naturalist_button_emoji("refresh")

    @discord.ui.button(label="Взять образец", style=discord.ButtonStyle.primary, row=0)
    async def sample_button(self, interaction, button):
        embed = build_bot_embed(
            "Выбор региона",
            "Выберите регион, где хотите искать животное.",
            color=discord.Color.dark_green(),
        )
        if os.path.exists(NATURALIST_IMAGE_FILE):
            embed.set_image(url=f"attachment://{NATURALIST_IMAGE_ATTACHMENT_NAME}")
        await interaction.response.edit_message(
            embed=embed, view=NaturalistRegionView(self.bot, interaction.user.id)
        )

    @discord.ui.button(label="Сдать образцы", style=discord.ButtonStyle.success, row=0)
    async def sell_button(self, interaction, button):
        async with self.bot.economy_lock:
            account = self.bot.get_account(interaction.user.id)
            naturalist = get_naturalist_account(account)
            harriet_cooldown = get_harriet_anger_cooldown(naturalist)
            if harriet_cooldown > 0:
                self.bot.save_economy()
                await interaction.response.send_message(
                    "Гарриет сердится из-за убийства животного и не принимает "
                    f"образцы ещё **{format_duration(harriet_cooldown)}**.",
                    ephemeral=True,
                )
                return
            samples = dict(naturalist.get("samples", {}))
            if not samples:
                self.bot.save_economy()
                await interaction.response.send_message(
                    "У вас пока нет образцов для сдачи.", ephemeral=True
                )
                return

            multiplier = get_naturalist_sale_multiplier(naturalist)
            cash_total = 0.0
            xp_total = 0
            sold_count = 0
            for sample_key, amount in samples.items():
                if sample_key in ANIMALS:
                    item = ANIMALS[sample_key]
                    cash_total += item["cash"] * amount
                    xp_total += item["xp"] * amount
                else:
                    item = LEGENDARY_ANIMALS[sample_key]
                    cash_total += item["cash"] * amount
                    xp_total += item["xp"] * amount
                sold_count += amount
            cash_total = round(cash_total * multiplier, 2)
            account["cash"] += cash_total
            stamp_naturalist_samples(naturalist, samples)
            naturalist["samples"] = {}
            levels = apply_role_xp(naturalist, xp_total, NATURALIST_MAX_LEVEL, 180)
            interaction.client.dispatch("leveling_add_xp", interaction.user, xp_total, "jobs")
            self.bot.save_economy()

            note = (
                f"Гарриет приняла **{format_integer(sold_count)}** образцов: "
                f"**{self.bot.format_money(cash_total)}**"
            )
            note += f". Опыт: **+{xp_total}**."
            if levels:
                note += f"\nНовый уровень натуралиста: **{naturalist['level']}**."

            from cogs.catalog import CATALOG_ITEMS
            normalize_weapon_state(account, CATALOG_ITEMS)
            gear = get_naturalist_gear(account, CATALOG_ITEMS)
            embed = build_naturalist_embed(interaction.guild, account, note=note, gear=gear)

        await interaction.response.edit_message(
            embed=embed, view=NaturalistMainView(self.bot, interaction.user.id)
        )

    @discord.ui.button(label="Справочник", style=discord.ButtonStyle.secondary, row=0)
    async def collection_button(self, interaction, button):
        async with self.bot.economy_lock:
            account = self.bot.get_account(interaction.user.id)
            naturalist = get_naturalist_account(account)
            embed = build_naturalist_collection_embed(naturalist)
            self.bot.save_economy()
        await interaction.response.edit_message(
            embed=embed, view=NaturalistCollectionView(self.bot, interaction.user.id, naturalist)
        )

    @discord.ui.button(label="Легендарное животное", style=discord.ButtonStyle.primary, row=1)
    async def legendary_button(self, interaction, button):
        async with self.bot.economy_lock:
            account = self.bot.get_account(interaction.user.id)
            naturalist = get_naturalist_account(account)
            harriet_cooldown = get_harriet_anger_cooldown(naturalist)
            if harriet_cooldown > 0:
                self.bot.save_economy()
                await interaction.response.send_message(
                    "Гарриет не выдаёт задания ещё "
                    f"**{format_duration(harriet_cooldown)}**.",
                    ephemeral=True,
                )
                return
            embed = build_naturalist_legendary_embed(naturalist)
            self.bot.save_economy()
        await interaction.response.edit_message(
            embed=embed, view=NaturalistLegendaryView(self.bot, interaction.user.id, naturalist)
        )

    @discord.ui.button(label="Магазин Гарриет", style=discord.ButtonStyle.secondary, row=1)
    async def shop_button(self, interaction, button):
        async with self.bot.economy_lock:
            account = self.bot.get_account(interaction.user.id)
            naturalist = get_naturalist_account(account)
            harriet_cooldown = get_harriet_anger_cooldown(naturalist)
            if harriet_cooldown > 0:
                self.bot.save_economy()
                await interaction.response.send_message(
                    "Гарриет отказывается торговать ещё "
                    f"**{format_duration(harriet_cooldown)}**.",
                    ephemeral=True,
                )
                return
            self.bot.save_economy()
        embed = build_bot_embed(
            "Магазин Гарриет",
            (
                f"💉 **Снотворные патроны x{NATURALIST_TRANQ_PACK_SIZE}** — "
                f"{self.bot.format_money(NATURALIST_TRANQ_PACK_PRICE)}\n"
                f"🧪 **Оживитель животных** — "
                f"{self.bot.format_money(NATURALIST_REVIVER_PRICE)}\n"
                f"🐾 **Легендарные звериные феромоны** — "
                f"{self.bot.format_money(NATURALIST_PHEROMONE_PRICE)}\n"
                f"🏕️ **Походный лагерь** — "
                f"{self.bot.format_money(NATURALIST_CAMP_PRICE)}\n\n"
                f"Патроны: **{naturalist['inventory']['tranquilizers']}/"
                f"{get_naturalist_tranq_cap(naturalist)}** · "
                f"феромоны: **{naturalist['inventory']['pheromones']}**"
            ),
            color=discord.Color.dark_green(),
        )
        await interaction.response.edit_message(
            embed=embed,
            view=NaturalistShopView(self.bot, interaction.user.id, naturalist),
        )

    @discord.ui.button(label="Обновить", style=discord.ButtonStyle.secondary, row=1)
    async def refresh_button(self, interaction, button):
        async with self.bot.economy_lock:
            account = self.bot.get_account(interaction.user.id)
            from cogs.catalog import CATALOG_ITEMS
            normalize_weapon_state(account, CATALOG_ITEMS)
            gear = get_naturalist_gear(account, CATALOG_ITEMS)
            embed = build_naturalist_embed(interaction.guild, account, gear=gear)
            self.bot.save_economy()
        await interaction.response.edit_message(
            embed=embed, view=NaturalistMainView(self.bot, interaction.user.id)
        )

    @discord.ui.button(
        label="Добыть легендарную шкуру",
        emoji="🦌",
        style=discord.ButtonStyle.danger,
        row=2,
    )
    async def pelt_button(self, interaction, button):
        async with self.bot.economy_lock:
            account = self.bot.get_account(interaction.user.id)
            naturalist = get_naturalist_account(account)
            embed = build_naturalist_pelt_embed(naturalist)
            self.bot.save_economy()
        await interaction.response.edit_message(
            embed=embed,
            view=NaturalistPeltView(self.bot, interaction.user.id, naturalist),
        )


class NaturalistRegionSelect(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(
                label=f"{region['emoji']} {region['name']}",
                value=region_key,
                description=", ".join(ANIMALS[key]["name"] for key in CATEGORIES[region_key]),
            )
            for region_key, region in NATURALIST_REGIONS.items()
        ]
        super().__init__(
            placeholder="Выберите регион",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction):
        region_key = self.values[0]
        region = NATURALIST_REGIONS[region_key]
        lines = []
        for animal_key in CATEGORIES[region_key]:
            animal = ANIMALS[animal_key]
            lines.append(
                f"**{animal['name']}** — "
                f"базовый шанс {format_percent(animal['base_chance'] * 100)}, "
                f"сдача {self.bot.format_money(animal['cash'])}, опыт {animal['xp']}"
            )
        embed = build_bot_embed(
            f"{region['emoji']} {region['name']}",
            "\n".join(lines),
            color=discord.Color.dark_green(),
        )
        if os.path.exists(NATURALIST_IMAGE_FILE):
            embed.set_image(url=f"attachment://{NATURALIST_IMAGE_ATTACHMENT_NAME}")
        await interaction.response.edit_message(
            embed=embed, view=NaturalistAnimalView(self.bot, interaction.user.id, region_key)
        )


class NaturalistRegionView(NaturalistOwnerView):
    def __init__(self, bot, user_id):
        super().__init__(bot, user_id)
        self.add_item(NaturalistRegionSelect(self.bot))


class NaturalistAnimalSelect(discord.ui.Select):
    def __init__(self, bot, region_key):
        self.bot = bot
        options = []
        for animal_key in CATEGORIES[region_key]:
            animal = ANIMALS[animal_key]
            options.append(
                discord.SelectOption(
                    label=animal["name"],
                    value=animal_key,
                    description=(
                        f"Базовый шанс {format_percent(animal['base_chance'] * 100)} · "
                        f"{format_number(animal['cash'])}$"
                    ),
                )
            )
        super().__init__(
            placeholder="Выберите животное",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction):
        animal_key = self.values[0]
        animal = ANIMALS[animal_key]
        async with self.bot.economy_lock:
            account = self.bot.get_account(interaction.user.id)
            naturalist = get_naturalist_account(account)
            cooldown = get_naturalist_sample_cooldown(naturalist)
            if cooldown > 0:
                self.bot.save_economy()
                await interaction.response.send_message(
                    f"Следующий образец можно брать через **{format_duration(cooldown)}**.",
                    ephemeral=True,
                )
                return

            from cogs.catalog import CATALOG_ITEMS
            normalize_weapon_state(account, CATALOG_ITEMS)
            gear = get_naturalist_gear(account, CATALOG_ITEMS)
            if not gear["varmint"] or not gear["dart"]:
                self.bot.save_economy()
                missing = []
                if not gear["varmint"]:
                    missing.append("винтовка «Варминт» в активном оружии")
                if not gear["dart"]:
                    missing.append("снотворные патроны")
                await interaction.response.send_message(
                    "Для образца нужны: **" + ", ".join(missing) + "**.",
                    ephemeral=True,
                )
                return
            chance = calculate_naturalist_chance(animal["base_chance"], gear)

            # Тратим расходники
            consume_naturalist_gear(account, gear)
            naturalist["last_sample_at"] = now_local().isoformat(timespec="seconds")

            success = random.random() <= chance
            if success:
                naturalist["samples"][animal_key] = naturalist["samples"].get(animal_key, 0) + 1
                note = (
                    f"✅ Образец **{animal['name']}** получен! "
                    f"Шанс был **{format_percent(chance * 100)}**. "
                    "Продайте его Гарриет, чтобы получить деньги, опыт и штамп."
                )
            else:
                note = (
                    f"❌ **{animal['name']}** убежал. "
                    f"Шанс был **{format_percent(chance * 100)}**. "
                    f"Улучшите снаряжение, чтобы повысить шанс!"
                )
            self.bot.save_economy()
            embed = build_naturalist_embed(interaction.guild, account, note=note, gear=gear)

        await interaction.response.edit_message(
            embed=embed, view=NaturalistMainView(self.bot, interaction.user.id)
        )


class NaturalistAnimalView(NaturalistOwnerView):
    def __init__(self, bot, user_id, region_key):
        super().__init__(bot, user_id)
        self.add_item(NaturalistAnimalSelect(bot, region_key))


class NaturalistCategoryButton(discord.ui.Button):
    def __init__(self, bot, region_key, naturalist):
        self.bot = bot
        region = NATURALIST_REGIONS[region_key]
        complete = has_full_naturalist_category(naturalist, region_key)
        super().__init__(
            label=f"Сдать: {region['name']}",
            style=discord.ButtonStyle.success if complete else discord.ButtonStyle.secondary,
            emoji=region["emoji"],
            disabled=not complete,
            custom_id=f"naturalist:category:{region_key}",
        )
        self.region_key = region_key

    async def callback(self, interaction):
        async with self.bot.economy_lock:
            account = self.bot.get_account(interaction.user.id)
            naturalist = get_naturalist_account(account)
            if not has_full_naturalist_category(naturalist, self.region_key):
                self.bot.save_economy()
                await interaction.response.send_message(
                    "Для сдачи страницы нужен штамп каждого животного категории.",
                    ephemeral=True,
                )
                return
            for animal_key in CATEGORIES[self.region_key]:
                naturalist["stamps"].pop(animal_key, None)
            region = NATURALIST_REGIONS[self.region_key]
            cash_reward = round(
                region["payout"] * get_naturalist_sale_multiplier(naturalist), 2
            )
            xp_reward = 1000
            account["cash"] += cash_reward
            levels = apply_role_xp(naturalist, xp_reward, NATURALIST_MAX_LEVEL, 180)
            interaction.client.dispatch("leveling_add_xp", interaction.user, xp_reward, "jobs")
            self.bot.save_economy()
            note = (
                f"Страница **{region['name']}** сдана: "
                f"**{self.bot.format_money(cash_reward)}**, "
                f"опыт **+{xp_reward}**."
            )
            if levels:
                note += f"\nНовый уровень натуралиста: **{naturalist['level']}**."
            from cogs.catalog import CATALOG_ITEMS
            normalize_weapon_state(account, CATALOG_ITEMS)
            gear = get_naturalist_gear(account, CATALOG_ITEMS)
            embed = build_naturalist_embed(interaction.guild, account, note=note, gear=gear)

        await interaction.response.edit_message(
            embed=embed, view=NaturalistMainView(self.bot, interaction.user.id)
        )


class NaturalistCollectionView(NaturalistOwnerView):
    def __init__(self, bot, user_id, naturalist):
        super().__init__(bot, user_id)
        for region_key in NATURALIST_REGIONS:
            self.add_item(NaturalistCategoryButton(bot, region_key, naturalist))


class NaturalistLegendarySelect(discord.ui.Select):
    def __init__(self, bot, naturalist):
        self.bot = bot
        options = []
        for animal_key, animal in LEGENDARY_ANIMALS.items():
            locked = naturalist["level"] < animal["required_level"]
            options.append(
                discord.SelectOption(
                    label=f"{'🔒 ' if locked else ''}{animal['name']}",
                    value=animal_key,
                    description=(
                        f"{animal['cash']:g}$ · "
                        f"{animal['xp']} XP · с {animal['required_level']} уровня"
                    ),
                )
            )
        super().__init__(
            placeholder="Выберите легендарное животное",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction):
        animal_key = self.values[0]
        animal = LEGENDARY_ANIMALS[animal_key]
        async with self.bot.economy_lock:
            account = self.bot.get_account(interaction.user.id)
            naturalist = get_naturalist_account(account)
            harriet_cooldown = get_harriet_anger_cooldown(naturalist)
            if harriet_cooldown > 0:
                self.bot.save_economy()
                await interaction.response.send_message(
                    "Гарриет не выдаёт задания ещё "
                    f"**{format_duration(harriet_cooldown)}**.",
                    ephemeral=True,
                )
                return
            if naturalist["level"] < animal["required_level"]:
                self.bot.save_economy()
                await interaction.response.send_message(
                    f"Легендарные животные открываются с "
                    f"**{animal['required_level']} уровня**.",
                    ephemeral=True,
                )
                return
            cooldown = get_naturalist_legendary_cooldown(naturalist)
            if cooldown > 0:
                self.bot.save_economy()
                await interaction.response.send_message(
                    f"Следующая легендарная охота будет доступна через **{format_duration(cooldown)}**.",
                    ephemeral=True,
                )
                return

            from cogs.catalog import CATALOG_ITEMS
            normalize_weapon_state(account, CATALOG_ITEMS)
            gear = get_naturalist_gear(account, CATALOG_ITEMS)
            if not gear["varmint"] or not gear["dart"]:
                self.bot.save_economy()
                await interaction.response.send_message(
                    "Для легендарного образца нужны **винтовка «Варминт»** "
                    "и **снотворные патроны**.",
                    ephemeral=True,
                )
                return

            # Базовый шанс легендарной охоты + снаряжение
            legendary_base = 0.40
            chance = calculate_naturalist_chance(
                legendary_base, gear, legendary=True
            )

            # Тратим расходники
            consume_naturalist_gear(account, gear, legendary=True)
            naturalist["legendary_cooldown_until"] = (
                now_local() + timedelta(seconds=NATURALIST_LEGENDARY_COOLDOWN_SECONDS)
            ).isoformat(timespec="seconds")

            success = random.random() <= chance
            if success:
                naturalist["samples"][animal_key] = naturalist["samples"].get(animal_key, 0) + 1
                note = (
                    f"⭐ Легендарный образец **{animal['name']}** получен! "
                    f"Шанс был **{format_percent(chance * 100)}**. "
                    "Продайте его Гарриет за награду и 350 XP."
                )
            else:
                note = (
                    f"❌ **{animal['name']}** ушёл от вас. "
                    f"Шанс был **{format_percent(chance * 100)}**."
                )
            self.bot.save_economy()
            embed = build_naturalist_embed(interaction.guild, account, note=note, gear=gear)

        await interaction.response.edit_message(
            embed=embed, view=NaturalistMainView(self.bot, interaction.user.id)
        )


class NaturalistLegendaryView(NaturalistOwnerView):
    def __init__(self, bot, user_id, naturalist):
        super().__init__(bot, user_id)
        self.add_item(NaturalistLegendarySelect(bot, naturalist))


class NaturalistPeltSelect(discord.ui.Select):
    def __init__(self, bot, naturalist):
        self.bot = bot
        options = [
            discord.SelectOption(
                label=animal["name"],
                value=animal_key,
                description=(
                    f"{animal['pelt_materials']:g} материалов Криппса · "
                    f"с {animal['required_level']} уровня"
                ),
            )
            for animal_key, animal in LEGENDARY_ANIMALS.items()
        ]
        super().__init__(
            placeholder="Выберите животное для охоты",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction):
        animal_key = self.values[0]
        animal = LEGENDARY_ANIMALS[animal_key]
        async with self.bot.economy_lock:
            account = self.bot.get_account(interaction.user.id)
            naturalist = get_naturalist_account(account)
            if naturalist["level"] < animal["required_level"]:
                self.bot.save_economy()
                await interaction.response.send_message(
                    f"Охота откроется с **{animal['required_level']} уровня**.",
                    ephemeral=True,
                )
                return
            cooldown = get_naturalist_legendary_cooldown(naturalist)
            if cooldown > 0:
                self.bot.save_economy()
                await interaction.response.send_message(
                    "Следующая легендарная охота будет доступна через "
                    f"**{format_duration(cooldown)}**.",
                    ephemeral=True,
                )
                return

            materials = add_legendary_pelt(naturalist, animal_key)
            anger_seconds = anger_harriet(naturalist)
            naturalist["legendary_cooldown_until"] = (
                now_local() + timedelta(seconds=NATURALIST_LEGENDARY_COOLDOWN_SECONDS)
            ).isoformat(timespec="seconds")
            self.bot.save_economy()

            from cogs.catalog import CATALOG_ITEMS
            normalize_weapon_state(account, CATALOG_ITEMS)
            gear = get_naturalist_gear(account, CATALOG_ITEMS)
            note = (
                f"🦌 Добыта шкура **{animal['name']}** стоимостью "
                f"**{format_number(materials)} материалов** для Криппса.\n"
                f"Гарриет сердится **{format_duration(anger_seconds)}**."
            )
            embed = build_naturalist_embed(
                interaction.guild, account, note=note, gear=gear
            )

        await interaction.response.edit_message(
            embed=embed,
            view=NaturalistMainView(self.bot, interaction.user.id),
        )


class NaturalistPeltView(NaturalistOwnerView):
    def __init__(self, bot, user_id, naturalist):
        super().__init__(bot, user_id)
        self.add_item(NaturalistPeltSelect(bot, naturalist))


class NaturalistShopView(NaturalistOwnerView):
    def __init__(self, bot, user_id, naturalist):
        super().__init__(bot, user_id)
        self.buy_camp.disabled = naturalist["has_wilderness_camp"]

    async def buy(self, interaction, item):
        async with self.bot.economy_lock:
            account = self.bot.get_account(interaction.user.id)
            naturalist = get_naturalist_account(account)
            harriet_cooldown = get_harriet_anger_cooldown(naturalist)
            if harriet_cooldown > 0:
                self.bot.save_economy()
                await interaction.response.send_message(
                    "Гарриет отказывается торговать ещё "
                    f"**{format_duration(harriet_cooldown)}**.",
                    ephemeral=True,
                )
                return
            if item == "tranquilizers":
                cap = get_naturalist_tranq_cap(naturalist)
                current = naturalist["inventory"]["tranquilizers"]
                quantity = min(NATURALIST_TRANQ_PACK_SIZE, cap - current)
                price = NATURALIST_TRANQ_PACK_PRICE
                if quantity <= 0:
                    note = f"Сумка с патронами уже заполнена: **{current}/{cap}**."
                elif account["cash"] + 0.0001 < price:
                    note = f"Нужно **{self.bot.format_money(price)}**."
                else:
                    account["cash"] -= price
                    naturalist["inventory"]["tranquilizers"] += quantity
                    note = (
                        f"Куплено снотворных патронов: **{quantity}**. "
                        f"В сумке: **{naturalist['inventory']['tranquilizers']}/{cap}**."
                    )
            elif item == "reviver":
                price = NATURALIST_REVIVER_PRICE
                if account["cash"] + 0.0001 < price:
                    note = f"Нужно **{self.bot.format_money(price)}**."
                else:
                    account["cash"] -= price
                    inventory = account.setdefault("inventory", {})
                    inventory[NATURALIST_REVIVER_KEY] = (
                        int(inventory.get(NATURALIST_REVIVER_KEY, 0) or 0) + 1
                    )
                    note = "Оживитель животных куплен."
            elif item == "pheromone":
                price = NATURALIST_PHEROMONE_PRICE
                if account["cash"] + 0.0001 < price:
                    note = f"Нужно **{self.bot.format_money(price)}**."
                else:
                    account["cash"] -= price
                    naturalist["inventory"]["pheromones"] += 1
                    note = "Легендарные звериные феромоны куплены."
            else:
                price = NATURALIST_CAMP_PRICE
                if naturalist["has_wilderness_camp"]:
                    note = "Походный лагерь уже куплен."
                elif account["cash"] + 0.0001 < price:
                    note = f"Нужно **{self.bot.format_money(price)}**."
                else:
                    account["cash"] -= price
                    naturalist["has_wilderness_camp"] = True
                    note = "Походный лагерь куплен."
            self.bot.save_economy()
            from cogs.catalog import CATALOG_ITEMS
            normalize_weapon_state(account, CATALOG_ITEMS)
            gear = get_naturalist_gear(account, CATALOG_ITEMS)
            embed = build_naturalist_embed(
                interaction.guild, account, note=note, gear=gear
            )
        await interaction.response.edit_message(
            embed=embed,
            view=NaturalistMainView(self.bot, interaction.user.id),
        )

    @discord.ui.button(label="Патроны x20 · $0.56", emoji="💉", style=discord.ButtonStyle.success)
    async def buy_tranquilizers(self, interaction, button):
        await self.buy(interaction, "tranquilizers")

    @discord.ui.button(label="Оживитель · $5", emoji="🧪", style=discord.ButtonStyle.success)
    async def buy_reviver(self, interaction, button):
        await self.buy(interaction, "reviver")

    @discord.ui.button(label="Феромоны · $20", emoji="🐾", style=discord.ButtonStyle.success)
    async def buy_pheromone(self, interaction, button):
        await self.buy(interaction, "pheromone")

    @discord.ui.button(label="Походный лагерь · $750", emoji="🏕️", style=discord.ButtonStyle.success)
    async def buy_camp(self, interaction, button):
        await self.buy(interaction, "camp")

    @discord.ui.button(label="Назад", emoji="↩️", style=discord.ButtonStyle.secondary)
    async def back(self, interaction, button):
        async with self.bot.economy_lock:
            account = self.bot.get_account(interaction.user.id)
            from cogs.catalog import CATALOG_ITEMS
            normalize_weapon_state(account, CATALOG_ITEMS)
            gear = get_naturalist_gear(account, CATALOG_ITEMS)
            embed = build_naturalist_embed(interaction.guild, account, gear=gear)
            self.bot.save_economy()
        await interaction.response.edit_message(
            embed=embed,
            view=NaturalistMainView(self.bot, interaction.user.id),
        )


class NaturalistCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        import traceback
        print(f"Naturalist Cog error: {error}")
        traceback.print_exception(type(error), error, error.__traceback__)
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Произошла ошибка: {error}", ephemeral=True)

    @app_commands.command(name="naturalist", description="Натуралист: образцы, справочник и магазин")
    async def naturalist_command(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Эту команду можно использовать только на сервере.", ephemeral=True
            )
            return

        token = self.bot.set_economy_guild_id(interaction.guild_id)
        try:
            async with self.bot.economy_lock:
                update_gold_rate()
                account = self.bot.get_account(interaction.user.id)
                if not has_game_role(interaction.user, NATURALIST_ROLE_KEY, account):
                    self.bot.save_economy()
                    await interaction.response.send_message(
                        get_custom_message("role_required").format(role="Натуралист"),
                        ephemeral=True,
                    )
                    return
                from cogs.catalog import CATALOG_ITEMS
                normalize_weapon_state(account, CATALOG_ITEMS)
                gear = get_naturalist_gear(account, CATALOG_ITEMS)
                embed = build_naturalist_embed(interaction.guild, account, gear=gear)
                self.bot.save_economy()
        finally:
            self.bot.reset_economy_guild_id(token)

        image = get_naturalist_image_file()
        view = NaturalistMainView(self.bot, interaction.user.id)
        if image:
            await interaction.response.send_message(
                embed=embed, view=view, file=image, ephemeral=True
            )
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(NaturalistCog(bot))
