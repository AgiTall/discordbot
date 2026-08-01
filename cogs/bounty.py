import discord
from discord.ext import commands
from discord import app_commands
import random
from src.bounty_logic import *
from emoji_config import EMOJI_BACK, EMOJI_DICE, EMOJI_ERROR, EMOJI_LIST, EMOJI_SUCCESS, DEFAULT_MOONSHINE_WAGON_EMOJI


class BountyOwnerView(discord.ui.View):
    def __init__(self, bot, user_id, timeout=None):
        self.bot = bot
        super().__init__(timeout=timeout)
        self.user_id = user_id

    async def interaction_check(self, interaction):
        token = self.bot.set_economy_guild_id(interaction.guild_id)
        try:
            if interaction.user.id != self.user_id:
                await interaction.response.send_message(
                    "Это меню охотника открыто не для вас.", ephemeral=True
                )
                return False
        finally:
            self.bot.reset_economy_guild_id(token)
        return True


class BountyTargetButton(discord.ui.Button):
    """Кнопка выбора уровня преступника — сразу выполняет попытку поимки."""

    def __init__(self, bot, target_key):
        self.bot = bot
        target = BOUNTY_TARGETS[target_key]

        # Легендарный — особый стиль
        if target_key == "legendary":
            style = discord.ButtonStyle.danger
        elif target_key == "expensive":
            style = discord.ButtonStyle.primary
        else:
            style = discord.ButtonStyle.secondary

        super().__init__(
            label=target["name"],
            style=style,
            emoji=get_bounty_button_emoji(target_key),
            custom_id=f"bounty:target:{target_key}",
        )
        self.target_key = target_key

    async def callback(self, interaction):
        target = BOUNTY_TARGETS[self.target_key]
        contract = roll_bounty_contract(self.target_key)
        target_name = contract["name"]

        token = self.bot.set_economy_guild_id(interaction.guild_id)
        try:
            async with self.bot.economy_lock:
                account = self.bot.get_account(interaction.user.id)
                bounty = get_bounty_account(account)

                if not has_game_role(interaction.user, BOUNTY_ROLE_KEY, account):
                    self.bot.save_economy()
                    await interaction.response.send_message(
                        get_custom_message("role_required").format(
                            role="Охотник за головами"
                        ),
                        ephemeral=True,
                    )
                    return

                if self.target_key == "legendary" and not bounty["prestigious_license"]:
                    self.bot.save_economy()
                    await interaction.response.send_message(
                        "Для легендарных преступников нужна **знаменитая лицензия**. "
                        "Купите её через кнопку «Улучшение».",
                        ephemeral=True,
                    )
                    return

                cooldown = get_bounty_cooldown(bounty)
                if cooldown > 0:
                    self.bot.save_economy()
                    await interaction.response.send_message(
                        f"Следующий контракт будет доступен через **{format_duration(cooldown)}**.",
                        ephemeral=True,
                    )
                    return

                # Снаряжение входит в профессию: отдельная покупка оружия и
                # патронов больше не нужна для основного цикла.
                shot = {
                    "class": "repeater",
                    "ammo_type": "normal",
                    "condition_before": 100,
                }
                catch_chance = calculate_catch_chance(self.target_key, shot)
                roll = random.randint(1, 100)
                caught = roll <= catch_chance

                bounty["last_bounty_at"] = now_local().isoformat(timespec="seconds")

                chance_breakdown = (
                    f"Шанс поимки: **{catch_chance}%** "
                    f"(сложность контракта и снаряжение)"
                )

                if caught:
                    reward = contract["reward"]
                    gold_reward = target["gold"]
                    xp_reward = target["xp"]
                    account["cash"] += reward
                    account["gold"] += gold_reward
                    bounty["captures"] += 1
                    interaction.client.dispatch("leveling_add_xp", interaction.user, xp_reward, "jobs")

                    title = f"{EMOJI_SUCCESS} Цель поймана — {target['label']}"
                    result_text = (
                        f"Доставлено живыми: **{contract['count']}**.\n"
                        f"Награда: **{self.bot.format_money(reward)}** и **{format_gold(gold_reward)}**.\n"
                        f"Общий опыт: **+{xp_reward}**."
                    )
                    color = discord.Color.green() if self.target_key != "legendary" else discord.Color.gold()
                else:
                    xp_reward = max(20, target["xp"] // 5)
                    bounty["escaped"] += 1
                    interaction.client.dispatch("leveling_add_xp", interaction.user, xp_reward, "jobs")

                    title = f"{EMOJI_ERROR} Цель сбежала — {target['label']}"
                    result_text = f"Вы получили **+{xp_reward}** общего опыта за попытку."
                    color = discord.Color.red()

                self.bot.save_economy()
        finally:
            self.bot.reset_economy_guild_id(token)

        embed = discord.Embed(
            title=title,
            description=(
                f"Цель: **{target_name}**\n"
                f"{chance_breakdown}\n"
                f"{EMOJI_DICE} Бросок: **{roll}** из 100\n\n"
                f"{result_text}"
            ),
            color=color,
        )
        if os.path.exists(BOUNTY_IMAGE_FILE):
            embed.set_image(url=f"attachment://{BOUNTY_IMAGE_ATTACHMENT_NAME}")
        await interaction.response.edit_message(
            embed=embed,
            view=BountyMainView(self.bot, interaction.user.id, bounty),
        )


class BountyMainView(BountyOwnerView):
    def __init__(self, bot, user_id, bounty=None):
        super().__init__(bot, user_id)
        bounty = bounty or default_bounty_data()
        target_button = BountyTargetButton(
            self.bot, simple_bounty_target_key(bounty)
        )
        target_button.label = "Взять контракт"
        self.add_item(target_button)
        self.add_item(BountyEquipmentButton(self.bot))


class BountyEquipmentButton(discord.ui.Button):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(
            label="Улучшение",
            emoji=EMOJI_LIST,
            style=discord.ButtonStyle.secondary,
            custom_id="bounty:equipment",
        )

    async def callback(self, interaction):
        token = self.bot.set_economy_guild_id(interaction.guild_id)
        try:
            async with self.bot.economy_lock:
                account = self.bot.get_account(interaction.user.id)
                bounty = get_bounty_account(account)
                self.bot.save_economy()
                embed = build_bounty_embed(interaction.guild, account)
        finally:
            self.bot.reset_economy_guild_id(token)
        await interaction.response.edit_message(
            embed=embed,
            view=BountyEquipmentView(self.bot, interaction.user.id, bounty),
        )


class BountyEquipmentView(BountyOwnerView):
    def __init__(self, bot, user_id, bounty):
        super().__init__(bot, user_id)
        self.buy_license.disabled = bounty["prestigious_license"]
        self.remove_item(self.buy_wagon)

    async def buy(self, interaction, item):
        token = self.bot.set_economy_guild_id(interaction.guild_id)
        try:
            async with self.bot.economy_lock:
                account = self.bot.get_account(interaction.user.id)
                bounty = get_bounty_account(account)
                if item == "license":
                    if bounty["prestigious_license"]:
                        note = "Знаменитая лицензия уже куплена."
                    elif account["gold"] + 0.0001 < PRESTIGIOUS_LICENSE_PRICE:
                        note = (
                            f"Нужно **{format_gold(PRESTIGIOUS_LICENSE_PRICE)}**, "
                            f"у вас **{format_gold(account['gold'])}**."
                        )
                    else:
                        account["gold"] -= PRESTIGIOUS_LICENSE_PRICE
                        bounty["prestigious_license"] = True
                        note = (
                            "Знаменитая лицензия куплена: открыты "
                            "**легендарные контракты**."
                        )
                else:
                    if bounty["has_bounty_wagon"]:
                        note = "Тюремный фургон уже куплен."
                    elif account["cash"] + 0.0001 < BOUNTY_WAGON_PRICE:
                        note = (
                            f"Нужно **{self.bot.format_money(BOUNTY_WAGON_PRICE)}**, "
                            f"у вас **{self.bot.format_money(account['cash'])}**."
                        )
                    else:
                        account["cash"] -= BOUNTY_WAGON_PRICE
                        bounty["has_bounty_wagon"] = True
                        note = "Тюремный фургон куплен."
                self.bot.save_economy()
                embed = build_bounty_embed(interaction.guild, account)
                embed.description = f"{note}\n\n{embed.description}"
        finally:
            self.bot.reset_economy_guild_id(token)
        await interaction.response.edit_message(
            embed=embed,
            view=BountyEquipmentView(self.bot, interaction.user.id, bounty),
        )

    @discord.ui.button(
        label="Знаменитая лицензия · 15 золота",
        emoji=EMOJI_LIST,
        style=discord.ButtonStyle.success,
    )
    async def buy_license(self, interaction, button):
        await self.buy(interaction, "license")

    @discord.ui.button(
        label="Тюремный фургон · $875",
        emoji=DEFAULT_MOONSHINE_WAGON_EMOJI,
        style=discord.ButtonStyle.success,
    )
    async def buy_wagon(self, interaction, button):
        await self.buy(interaction, "wagon")

    @discord.ui.button(label="Назад", emoji=EMOJI_BACK, style=discord.ButtonStyle.secondary)
    async def back(self, interaction, button):
        token = self.bot.set_economy_guild_id(interaction.guild_id)
        try:
            async with self.bot.economy_lock:
                account = self.bot.get_account(interaction.user.id)
                bounty = get_bounty_account(account)
                embed = build_bounty_embed(interaction.guild, account)
                self.bot.save_economy()
        finally:
            self.bot.reset_economy_guild_id(token)
        await interaction.response.edit_message(
            embed=embed,
            view=BountyMainView(self.bot, interaction.user.id, bounty),
        )


def _bounty_leaderboard_rows():
    rows = []
    for user_id, account in economy_data["users"].items():
        if not isinstance(account, dict):
            continue
        bounty = normalize_bounty_data(account.get("bounty"))
        if bounty["captures"] <= 0 and bounty["xp"] <= 0:
            continue
        rows.append((user_id, bounty))
    rows.sort(
        key=lambda item: (
            item[1]["level"],
            item[1]["captures"],
            item[1]["xp"],
        ),
        reverse=True,
    )
    return rows


def _build_bounty_leaderboard_embed(guild, rows):
    if not rows:
        description = "Пока никто не закрыл ни одного контракта."
    else:
        lines = []
        for index, (user_id, bounty) in enumerate(rows[:10], start=1):
            member = guild.get_member(int(user_id)) if guild else None
            name = member.mention if member else f"`{user_id}`"
            lines.append(
                f"**{index}.** {name} — "
                f"поймано {format_integer(bounty['captures'])}"
            )
        description = "\n".join(lines)
    embed = build_bot_embed(
        "Лучшие охотники за головами",
        description,
        color=discord.Color.dark_gold(),
    )
    if os.path.exists(BOUNTY_IMAGE_FILE):
        embed.set_image(url=f"attachment://{BOUNTY_IMAGE_ATTACHMENT_NAME}")
    return embed


class BountyLeaderboardButton(discord.ui.Button):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(
            label="Доска охотников",
            style=discord.ButtonStyle.secondary,
            emoji=get_bounty_button_emoji("leaderboard"),
            custom_id="bounty:leaderboard",
        )

    async def callback(self, interaction):
        token = self.bot.set_economy_guild_id(interaction.guild_id)
        try:
            async with self.bot.economy_lock:
                rows = _bounty_leaderboard_rows()
                self.bot.save_economy()
        finally:
            self.bot.reset_economy_guild_id(token)
        await interaction.response.edit_message(
            embed=_build_bounty_leaderboard_embed(interaction.guild, rows),
            view=BountyMainView(self.bot, interaction.user.id),
        )


class BountyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        import traceback
        print(f"Bounty Cog error: {error}")
        traceback.print_exception(type(error), error, error.__traceback__)
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Произошла ошибка: {error}", ephemeral=True)

    @app_commands.command(name="bounty", description="Охотник за головами: открыть контракты")
    async def bounty_command(self, interaction: discord.Interaction):
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
                if not has_game_role(interaction.user, BOUNTY_ROLE_KEY, account):
                    self.bot.save_economy()
                    await interaction.response.send_message(
                        get_custom_message("role_required").format(
                            role="Охотник за головами"
                        ),
                        ephemeral=True,
                    )
                    return
                embed = build_bounty_embed(interaction.guild, account)
                self.bot.save_economy()
        finally:
            self.bot.reset_economy_guild_id(token)

        image = get_bounty_image_file()
        view = BountyMainView(
            self.bot, interaction.user.id, get_bounty_account(account)
        )
        if image:
            await interaction.response.send_message(
                embed=embed, view=view, file=image, ephemeral=True
            )
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(BountyCog(bot))
