import discord
from discord.ext import commands
from discord import app_commands
import random
from src.naturalist_logic import *

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
        self.sample_button.emoji = get_naturalist_button_emoji("sample")
        self.sell_button.emoji = get_naturalist_button_emoji("sell")
        self.collection_button.emoji = get_naturalist_button_emoji("collection")
        self.legendary_button.emoji = get_naturalist_button_emoji("legendary")
        self.shop_button.emoji = get_naturalist_button_emoji("shop")
        self.refresh_button.emoji = get_naturalist_button_emoji("refresh")

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
            samples = dict(naturalist.get("samples", {}))
            if not samples:
                self.bot.save_economy()
                await interaction.response.send_message(
                    "У вас пока нет образцов для сдачи.", ephemeral=True
                )
                return

            multiplier = get_naturalist_sale_multiplier(naturalist)
            cash_total = 0.0
            gold_total = 0.0
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
                    gold_total += item["gold"] * amount
                    xp_total += item["xp"] * amount
                sold_count += amount
            cash_total = round(cash_total * multiplier, 2)
            account["cash"] += cash_total
            account["gold"] += gold_total
            naturalist["samples"] = {}
            levels = apply_role_xp(naturalist, xp_total, NATURALIST_MAX_LEVEL, 180)
            interaction.client.dispatch("leveling_add_xp", interaction.user, xp_total, "jobs")
            self.bot.save_economy()

            note = (
                f"Гарриет приняла **{format_integer(sold_count)}** образцов: "
                f"**{self.bot.format_money(cash_total)}**"
            )
            if gold_total > 0:
                note += f" и **{format_gold(gold_total)}**"
            note += f". Опыт: **+{xp_total}**."
            if levels:
                note += f"\nНовый уровень натуралиста: **{naturalist['level']}**."
            embed = build_naturalist_embed(interaction.guild, account, note=note)

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
            if naturalist["level"] < 5:
                self.bot.save_economy()
                await interaction.response.send_message(
                    "Легендарные животные открываются с 5 уровня натуралиста.",
                    ephemeral=True,
                )
                return
            embed = build_naturalist_legendary_embed(naturalist)
            self.bot.save_economy()
        await interaction.response.edit_message(
            embed=embed, view=NaturalistLegendaryView(self.bot, interaction.user.id, naturalist)
        )

    @discord.ui.button(label="Магазин", style=discord.ButtonStyle.secondary, row=1)
    async def shop_button(self, interaction, button):
        async with self.bot.economy_lock:
            account = self.bot.get_account(interaction.user.id)
            naturalist = get_naturalist_account(account)
            embed = build_naturalist_shop_embed(account, naturalist)
            self.bot.save_economy()
        await interaction.response.edit_message(
            embed=embed, view=NaturalistShopView(self.bot, interaction.user.id)
        )

    @discord.ui.button(label="Обновить", style=discord.ButtonStyle.secondary, row=1)
    async def refresh_button(self, interaction, button):
        async with self.bot.economy_lock:
            account = self.bot.get_account(interaction.user.id)
            embed = build_naturalist_embed(interaction.guild, account)
            self.bot.save_economy()
        await interaction.response.edit_message(
            embed=embed, view=NaturalistMainView(self.bot, interaction.user.id)
        )


class NaturalistRegionSelect(discord.ui.Select):
    def __init__(self):
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
                f"**{animal['name']}** — {animal['shots']} патр., "
                f"шанс {format_percent(animal['chance'] * 100)}, "
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
                        f"{animal['shots']} патр. · шанс {format_percent(animal['chance'] * 100)} · "
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
            if naturalist["inventory"]["tranquilizers"] < animal["shots"]:
                self.bot.save_economy()
                await interaction.response.send_message(
                    "Не хватает транквилизаторов. Купите их в магазине натуралиста.",
                    ephemeral=True,
                )
                return

            naturalist["inventory"]["tranquilizers"] -= animal["shots"]
            naturalist["last_sample_at"] = now_local().isoformat(timespec="seconds")
            chance = get_naturalist_success_chance(naturalist, animal["chance"])
            success = random.random() <= chance
            if success:
                naturalist["samples"][animal_key] = naturalist["samples"].get(animal_key, 0) + 1
                xp_reward = random.randint(20, 30)
                levels = apply_role_xp(
                    naturalist, xp_reward, NATURALIST_MAX_LEVEL, 180
                )
                interaction.client.dispatch("leveling_add_xp", interaction.user, xp_reward, "jobs")
                note = (
                    f"Образец **{animal['name']}** получен. "
                    f"Потрачено патронов: **{animal['shots']}**. "
                    f"Опыт: **+{xp_reward}**."
                )
                if levels:
                    note += f"\nНовый уровень натуралиста: **{naturalist['level']}**."
            else:
                note = (
                    f"**{animal['name']}** убежал. "
                    f"Потрачено патронов: **{animal['shots']}**. "
                    f"Шанс был **{format_percent(chance * 100)}**."
                )
            self.bot.save_economy()
            embed = build_naturalist_embed(interaction.guild, account, note=note)

        await interaction.response.edit_message(
            embed=embed, view=NaturalistMainView(self.bot, interaction.user.id)
        )


class NaturalistAnimalView(NaturalistOwnerView):
    def __init__(self, bot, user_id, region_key):
        super().__init__(bot, user_id)
        self.add_item(NaturalistAnimalSelect(region_key))


class NaturalistCategoryButton(discord.ui.Button):
    def __init__(self, region_key, naturalist):
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
                    "Для сдачи категории нужен хотя бы один образец каждого животного.",
                    ephemeral=True,
                )
                return
            for animal_key in CATEGORIES[self.region_key]:
                naturalist["samples"][animal_key] -= 1
                if naturalist["samples"][animal_key] <= 0:
                    naturalist["samples"].pop(animal_key, None)
            cash_reward = round(100.0 * get_naturalist_sale_multiplier(naturalist), 2)
            gold_reward = 0.5
            xp_reward = 300
            account["cash"] += cash_reward
            account["gold"] += gold_reward
            levels = apply_role_xp(naturalist, xp_reward, NATURALIST_MAX_LEVEL, 180)
            interaction.client.dispatch("leveling_add_xp", interaction.user, xp_reward, "jobs")
            self.bot.save_economy()
            region = NATURALIST_REGIONS[self.region_key]
            note = (
                f"Категория **{region['name']}** сдана: "
                f"**{self.bot.format_money(cash_reward)}**, **{format_gold(gold_reward)}**, "
                f"опыт **+{xp_reward}**."
            )
            if levels:
                note += f"\nНовый уровень натуралиста: **{naturalist['level']}**."
            embed = build_naturalist_embed(interaction.guild, account, note=note)

        await interaction.response.edit_message(
            embed=embed, view=NaturalistMainView(self.bot, interaction.user.id)
        )


class NaturalistCollectionView(NaturalistOwnerView):
    def __init__(self, bot, user_id, naturalist):
        super().__init__(bot, user_id)
        for region_key in NATURALIST_REGIONS:
            self.add_item(NaturalistCategoryButton(region_key, naturalist))


class NaturalistLegendarySelect(discord.ui.Select):
    def __init__(self, naturalist):
        options = []
        for animal_key, animal in LEGENDARY_ANIMALS.items():
            if naturalist["level"] < animal["required_level"]:
                continue
            options.append(
                discord.SelectOption(
                    label=animal["name"],
                    value=animal_key,
                    description=(
                        f"10 патр. · {format_number(animal['cash'])}$ · "
                        f"{format_number(animal['gold'])} зол."
                    ),
                )
            )
        if not options:
            options.append(
                discord.SelectOption(
                    label="Нет доступных легендарных животных",
                    value="none",
                    description="Повысьте уровень натуралиста",
                )
            )
        super().__init__(
            placeholder="Выберите легендарное животное",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction):
        if self.values[0] == "none":
            await interaction.response.send_message(
                "Пока нет доступных легендарных животных.", ephemeral=True
            )
            return

        animal_key = self.values[0]
        animal = LEGENDARY_ANIMALS[animal_key]
        async with self.bot.economy_lock:
            account = self.bot.get_account(interaction.user.id)
            naturalist = get_naturalist_account(account)
            cooldown = get_naturalist_legendary_cooldown(naturalist)
            if cooldown > 0:
                self.bot.save_economy()
                await interaction.response.send_message(
                    f"Следующая легендарная охота будет доступна через **{format_duration(cooldown)}**.",
                    ephemeral=True,
                )
                return
            if naturalist["level"] < animal["required_level"]:
                self.bot.save_economy()
                await interaction.response.send_message(
                    "Уровень натуралиста пока слишком низкий.", ephemeral=True
                )
                return
            if naturalist["inventory"]["tranquilizers"] < 10:
                self.bot.save_economy()
                await interaction.response.send_message(
                    "Для легендарной охоты нужно 10 транквилизаторов.",
                    ephemeral=True,
                )
                return

            naturalist["inventory"]["tranquilizers"] -= 10
            naturalist["legendary_cooldown_until"] = (
                now_local() + timedelta(seconds=NATURALIST_LEGENDARY_COOLDOWN_SECONDS)
            ).isoformat(timespec="seconds")
            chance = min(0.70, 0.50 + naturalist["level"] * 0.01)
            success = random.random() <= chance
            if success:
                naturalist["samples"][animal_key] = naturalist["samples"].get(animal_key, 0) + 1
                xp_reward = max(20, animal["xp"] // 3)
                levels = apply_role_xp(
                    naturalist, xp_reward, NATURALIST_MAX_LEVEL, 180
                )
                interaction.client.dispatch("leveling_add_xp", interaction.user, xp_reward, "jobs")
                note = (
                    f"Легендарный образец **{animal['name']}** получен. "
                    f"Опыт: **+{xp_reward}**."
                )
                if levels:
                    note += f"\nНовый уровень натуралиста: **{naturalist['level']}**."
            else:
                note = (
                    f"**{animal['name']}** ушёл от вас. "
                    f"Шанс был **{format_percent(chance * 100)}**."
                )
            self.bot.save_economy()
            embed = build_naturalist_embed(interaction.guild, account, note=note)

        await interaction.response.edit_message(
            embed=embed, view=NaturalistMainView(self.bot, interaction.user.id)
        )


class NaturalistLegendaryView(NaturalistOwnerView):
    def __init__(self, bot, user_id, naturalist):
        super().__init__(bot, user_id)
        self.add_item(NaturalistLegendarySelect(naturalist))


class NaturalistShopButton(discord.ui.Button):
    def __init__(self, amount, label):
        super().__init__(
            label=label,
            style=discord.ButtonStyle.success,
            emoji=get_naturalist_button_emoji("shop"),
        )
        self.amount = amount

    async def callback(self, interaction):
        async with self.bot.economy_lock:
            account = self.bot.get_account(interaction.user.id)
            naturalist = get_naturalist_account(account)
            cap = get_naturalist_tranq_cap(naturalist)
            current = naturalist["inventory"]["tranquilizers"]
            space = max(0, cap - current)
            if space <= 0:
                self.bot.save_economy()
                await interaction.response.send_message(
                    "Сумка транквилизаторов уже заполнена.", ephemeral=True
                )
                return
            if self.amount == "max":
                affordable = int(account["cash"] // NATURALIST_TRANQ_PRICE)
                amount = min(space, affordable)
            else:
                amount = min(space, int(self.amount))
            cost = amount * NATURALIST_TRANQ_PRICE
            if amount <= 0 or account["cash"] + 0.0001 < cost:
                self.bot.save_economy()
                await interaction.response.send_message(
                    "Не хватает денег на покупку транквилизаторов.", ephemeral=True
                )
                return
            account["cash"] -= cost
            naturalist["inventory"]["tranquilizers"] += amount
            self.bot.save_economy()
            note = f"Куплено **{amount}** транквилизаторов за **{self.bot.format_money(cost)}**."
            embed = build_naturalist_embed(interaction.guild, account, note=note)

        await interaction.response.edit_message(
            embed=embed, view=NaturalistMainView(self.bot, interaction.user.id)
        )


class NaturalistShopView(NaturalistOwnerView):
    def __init__(self, bot, user_id):
        super().__init__(bot, user_id)
        self.add_item(NaturalistShopButton(10, "Купить 10"))
        self.add_item(NaturalistShopButton(50, "Купить 50"))
        self.add_item(NaturalistShopButton("max", "Купить максимум"))


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
                embed = build_naturalist_embed(interaction.guild, account)
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
