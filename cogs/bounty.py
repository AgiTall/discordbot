import discord
from discord.ext import commands
from discord import app_commands
import random
from src.weapon_system import (
    AMMO_TYPE_NAMES,
    WEAPON_CLASS_NAMES,
    has_usable_ammo,
    normalize_weapon_state,
    use_weapon_shot,
)
from src.bounty_logic import *


class BountyOwnerView(discord.ui.View):
    def __init__(self, bot, user_id, timeout=600):
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
        target_name = random.choice(target["targets"])

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

                cooldown = get_bounty_cooldown(bounty)
                if cooldown > 0:
                    self.bot.save_economy()
                    await interaction.response.send_message(
                        f"Следующий контракт будет доступен через **{format_duration(cooldown)}**.",
                        ephemeral=True,
                    )
                    return

                # Проверяем наличие оружия и патронов
                from cogs.catalog import CATALOG_ITEMS
                normalize_weapon_state(account, CATALOG_ITEMS)
                if not any(account["weapon_loadout"].values()):
                    self.bot.save_economy()
                    await interaction.response.send_message(
                        "Возьмите купленное оружие через `/balance` → «Оружие».", ephemeral=True
                    )
                    return
                if not has_usable_ammo(account, CATALOG_ITEMS):
                    self.bot.save_economy()
                    await interaction.response.send_message(
                        "Для оружия в руках нет подходящих патронов. "
                        "Купите их в `/catalog` или смените оружие через `/balance`.",
                        ephemeral=True,
                    )
                    return

                # Один выстрел — одна попытка
                shot = use_weapon_shot(account, CATALOG_ITEMS)
                if not shot:
                    self.bot.save_economy()
                    await interaction.response.send_message(
                        "Боезапас закончился прямо в самый неподходящий момент.",
                        ephemeral=True,
                    )
                    return

                # Рассчитываем шанс поимки
                catch_chance = calculate_catch_chance(self.target_key, shot, bounty["level"])
                roll = random.randint(1, 100)
                caught = roll <= catch_chance

                bounty["last_bounty_at"] = now_local().isoformat(timespec="seconds")

                weapon_name = CATALOG_ITEMS[shot["weapon"]]["name"]
                weapon_class_name = WEAPON_CLASS_NAMES.get(shot["class"], shot["class"])
                ammo_name = AMMO_TYPE_NAMES[shot["ammo_type"]]

                weapon_line = (
                    f"🔫 **{weapon_name}** ({weapon_class_name}) · "
                    f"патроны: {ammo_name} · "
                    f"состояние: {shot['condition_after']:g}%"
                )

                chance_breakdown = (
                    f"Шанс поимки: **{catch_chance}%** "
                    f"(база {target['base_chance']}% + оружие + патроны + уровень)"
                )

                if caught:
                    reward = round(
                        random.randint(target["reward_min"], target["reward_max"]), 2
                    )
                    gold_reward = target["gold"]
                    xp_reward = target["xp"]
                    account["cash"] += reward
                    account["gold"] += gold_reward
                    bounty["captures"] += 1
                    levels = apply_role_xp(bounty, xp_reward, BOUNTY_MAX_LEVEL, 140)
                    interaction.client.dispatch("leveling_add_xp", interaction.user, xp_reward, "jobs")

                    title = f"✅ Цель поймана — {target['label']}"
                    result_text = (
                        f"Награда: **{self.bot.format_money(reward)}** и **{format_gold(gold_reward)}**.\n"
                        f"Опыт охотника: **+{xp_reward}**."
                    )
                    if levels:
                        result_text += f"\nНовый уровень: **{bounty['level']}**! 🎉"
                    color = discord.Color.green() if self.target_key != "legendary" else discord.Color.gold()
                else:
                    xp_reward = max(20, target["xp"] // 5)
                    bounty["escaped"] += 1
                    levels = apply_role_xp(bounty, xp_reward, BOUNTY_MAX_LEVEL, 140)
                    interaction.client.dispatch("leveling_add_xp", interaction.user, xp_reward, "jobs")

                    title = f"❌ Цель сбежала — {target['label']}"
                    result_text = f"Вы получили **+{xp_reward}** опыта за попытку."
                    if levels:
                        result_text += f"\nНовый уровень: **{bounty['level']}**."
                    color = discord.Color.red()

                self.bot.save_economy()
        finally:
            self.bot.reset_economy_guild_id(token)

        embed = discord.Embed(
            title=title,
            description=(
                f"Цель: **{target_name}**\n"
                f"{weapon_line}\n"
                f"{chance_breakdown}\n"
                f"🎲 Бросок: **{roll}** из 100\n\n"
                f"{result_text}"
            ),
            color=color,
        )
        if os.path.exists(BOUNTY_IMAGE_FILE):
            embed.set_image(url=f"attachment://{BOUNTY_IMAGE_ATTACHMENT_NAME}")
        await interaction.response.edit_message(
            embed=embed, view=BountyMainView(self.bot, interaction.user.id)
        )


class BountyMainView(BountyOwnerView):
    def __init__(self, bot, user_id):
        super().__init__(bot, user_id)
        for target_key in BOUNTY_TARGETS:
            self.add_item(BountyTargetButton(self.bot, target_key))
        self.add_item(BountyLeaderboardButton(self.bot))


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
                f"**{index}.** {name} — ур. {bounty['level']}, "
                f"поймано {format_integer(bounty['captures'])}, опыт {bounty['xp']}"
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
        view = BountyMainView(self.bot, interaction.user.id)
        if image:
            await interaction.response.send_message(
                embed=embed, view=view, file=image, ephemeral=True
            )
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(BountyCog(bot))
