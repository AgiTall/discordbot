import discord
from discord.ext import commands
from discord import app_commands
import random
from src.weapon_system import (
    AMMO_TYPE_NAMES,
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


class BountyDifficultyButton(discord.ui.Button):
    def __init__(self, bot, difficulty_key):
        self.bot = bot

        difficulty = BOUNTY_DIFFICULTIES[difficulty_key]
        super().__init__(
            label=difficulty["name"],
            style=discord.ButtonStyle.primary,
            emoji=get_bounty_button_emoji(difficulty_key),
            custom_id=f"bounty:difficulty:{difficulty_key}",
        )
        self.difficulty_key = difficulty_key

    async def callback(self, interaction):
        difficulty = BOUNTY_DIFFICULTIES[self.difficulty_key]
        target_name = random.choice(difficulty["targets"])
        embed = build_bot_embed(
            "Выбор тактики",
            (
                f"Цель: **{target_name}**\n"
                f"Сложность броска преступника: **d20 + {difficulty['mod']}**\n\n"
                "Выберите подход: нужно выиграть 2 из 3 бросков."
            ),
            color=discord.Color.dark_gold(),
        )
        if os.path.exists(BOUNTY_IMAGE_FILE):
            embed.set_image(url=f"attachment://{BOUNTY_IMAGE_ATTACHMENT_NAME}")
        await interaction.response.edit_message(
            embed=embed,
            view=BountyTacticView(self.bot, interaction.user.id, self.difficulty_key, target_name),
        )


class BountyMainView(BountyOwnerView):
    def __init__(self, bot, user_id):
        super().__init__(bot, user_id)
        for difficulty_key in BOUNTY_DIFFICULTIES:
            self.add_item(BountyDifficultyButton(self.bot, difficulty_key))
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


class BountyTacticButton(discord.ui.Button):
    def __init__(self, bot, tactic_key):
        self.bot = bot

        tactic = BOUNTY_TACTICS[tactic_key]
        super().__init__(
            label=tactic["name"],
            style=discord.ButtonStyle.secondary,
            emoji=get_bounty_button_emoji(tactic_key),
            custom_id=f"bounty:tactic:{tactic_key}",
        )
        self.tactic_key = tactic_key

    async def callback(self, interaction):
        view = self.view
        difficulty = BOUNTY_DIFFICULTIES[view.difficulty_key]
        tactic = BOUNTY_TACTICS[self.tactic_key]

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

                # Combat contracts use the active catalog loadout. Importing here
                # avoids coupling the pure bounty logic to the catalog extension.
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

                level_mod = bounty["level"] // 5
                rounds = []
                player_wins = 0
                target_wins = 0
                for round_number in range(1, 4):
                    shot = use_weapon_shot(account, CATALOG_ITEMS)
                    if not shot:
                        target_wins = 2
                        rounds.append("Боезапас закончился — цель воспользовалась заминкой и ушла.")
                        break
                    player_roll = random.randint(1, 20)
                    target_roll = random.randint(1, 20)
                    weapon_mod = shot["ammo_bonus"] + shot["condition_modifier"]
                    player_total = player_roll + tactic["mod"] + level_mod + weapon_mod
                    target_total = target_roll + difficulty["mod"]
                    if player_total >= target_total:
                        player_wins += 1
                        outcome = "успех"
                    else:
                        target_wins += 1
                        outcome = "провал"
                    rounds.append(
                        f"{round_number}. Вы: {player_roll}+{tactic['mod']}+{level_mod}"
                        f"{weapon_mod:+d} = "
                        f"**{player_total}**; цель: {target_roll}+{difficulty['mod']} = "
                        f"**{target_total}** — {outcome}\n"
                        f"   {CATALOG_ITEMS[shot['weapon']]['name']} · "
                        f"{AMMO_TYPE_NAMES[shot['ammo_type']]} · "
                        f"состояние {shot['condition_after']:g}%"
                    )
                    if self.tactic_key == "ambush" and outcome == "провал":
                        target_wins = 2
                        rounds.append("Засада сорвалась: цель сразу ушла от преследования.")
                        break
                    if player_wins >= 2 or target_wins >= 2:
                        break

                bounty["last_bounty_at"] = now_local().isoformat(timespec="seconds")
                if player_wins >= 2:
                    reward = random.randint(
                        difficulty["reward_min"], difficulty["reward_max"]
                    )
                    reward = round(reward * tactic["reward_multiplier"], 2)
                    gold_reward = difficulty["gold"]
                    xp_reward = difficulty["xp"]
                    account["cash"] += reward
                    account["gold"] += gold_reward
                    bounty["captures"] += 1
                    levels = apply_role_xp(bounty, xp_reward, BOUNTY_MAX_LEVEL, 140)
                    interaction.client.dispatch("leveling_add_xp", interaction.user, xp_reward, "jobs")
                    title = "Цель поймана"
                    result = (
                        f"Награда: **{self.bot.format_money(reward)}** и **{format_gold(gold_reward)}**.\n"
                        f"Опыт охотника: **+{xp_reward}**."
                    )
                    if levels:
                        result += f"\nНовый уровень: **{bounty['level']}**."
                else:
                    xp_reward = max(20, difficulty["xp"] // 5)
                    bounty["escaped"] += 1
                    levels = apply_role_xp(bounty, xp_reward, BOUNTY_MAX_LEVEL, 140)
                    interaction.client.dispatch("leveling_add_xp", interaction.user, xp_reward, "jobs")
                    title = "Цель сбежала"
                    result = f"Вы получили **+{xp_reward}** опыта за попытку."
                    if levels:
                        result += f"\nНовый уровень: **{bounty['level']}**."

                self.bot.save_economy()
        finally:
            self.bot.reset_economy_guild_id(token)

        embed = discord.Embed(
            title=title,
            description=(
                f"Цель: **{view.target_name}**\n"
                f"Тактика: **{tactic['name']}** — {tactic['description']}\n\n"
                + "\n".join(rounds)
                + f"\n\n{result}"
            ),
            color=discord.Color.dark_gold(),
        )
        if os.path.exists(BOUNTY_IMAGE_FILE):
            embed.set_image(url=f"attachment://{BOUNTY_IMAGE_ATTACHMENT_NAME}")
        await interaction.response.edit_message(
            embed=embed, view=BountyMainView(self.bot, interaction.user.id)
        )


class BountyTacticView(BountyOwnerView):
    def __init__(self, bot, user_id, difficulty_key, target_name):
        super().__init__(bot, user_id)
        self.difficulty_key = difficulty_key
        self.target_name = target_name
        for tactic_key in BOUNTY_TACTICS:
            self.add_item(BountyTacticButton(self.bot, tactic_key))


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
