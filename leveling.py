import discord
from discord.ext import commands, tasks
from discord import app_commands
import sqlite3
import time
import logging
import math

LEVELING_DB = "leveling.db"
DEFAULT_XP_RATE = 1.0

def calculate_xp_for_level(level: int) -> int:
    """Возвращает количество XP, необходимое для ДОСТИЖЕНИЯ указанного уровня с предыдущего.
    Либо можно сделать абсолютное количество XP для уровня."""
    # Для уровня 1 нужно 0 XP. 
    # Для уровня 2 нужно 100 XP.
    # Для уровня 3 нужно 282 XP.
    if level <= 1:
        return 0
    return int(100 * (level ** 1.5))

def calculate_total_xp_for_level(level: int) -> int:
    total = 0
    for i in range(1, level + 1):
        total += calculate_xp_for_level(i)
    return total

class LevelingDB:
    def __init__(self, db_path=LEVELING_DB):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    guild_id TEXT, 
                    user_id TEXT, 
                    xp INTEGER, 
                    level INTEGER, 
                    PRIMARY KEY(guild_id, user_id)
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS rank_roles (
                    guild_id TEXT, 
                    level INTEGER, 
                    role_id TEXT, 
                    PRIMARY KEY(guild_id, level)
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    guild_id TEXT, 
                    key TEXT, 
                    value TEXT, 
                    PRIMARY KEY(guild_id, key)
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS xp_rates (
                    guild_id TEXT, 
                    source TEXT, 
                    rate REAL, 
                    PRIMARY KEY(guild_id, source)
                )
            """)

    def get_user(self, guild_id: str, user_id: str):
        cursor = self.conn.execute("SELECT xp, level FROM users WHERE guild_id = ? AND user_id = ?", (str(guild_id), str(user_id)))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return {"xp": 0, "level": 1}

    def set_user(self, guild_id: str, user_id: str, xp: int, level: int):
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO users (guild_id, user_id, xp, level) VALUES (?, ?, ?, ?)",
                (str(guild_id), str(user_id), xp, level)
            )

    def get_top_users(self, guild_id: str, limit: int = 10):
        cursor = self.conn.execute("SELECT user_id, xp, level FROM users WHERE guild_id = ? ORDER BY xp DESC LIMIT ?", (str(guild_id), limit))
        return [dict(row) for row in cursor]

    def get_user_rank_position(self, guild_id: str, user_id: str):
        # Count users with more XP
        user_data = self.get_user(guild_id, user_id)
        cursor = self.conn.execute("SELECT COUNT(*) as pos FROM users WHERE guild_id = ? AND xp > ?", (str(guild_id), user_data["xp"]))
        row = cursor.fetchone()
        return row["pos"] + 1

    def set_rank_role(self, guild_id: str, level: int, role_id: str):
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO rank_roles (guild_id, level, role_id) VALUES (?, ?, ?)",
                (str(guild_id), level, str(role_id))
            )

    def remove_rank_role(self, guild_id: str, level: int):
        with self.conn:
            self.conn.execute("DELETE FROM rank_roles WHERE guild_id = ? AND level = ?", (str(guild_id), level))

    def get_rank_roles(self, guild_id: str):
        cursor = self.conn.execute("SELECT level, role_id FROM rank_roles WHERE guild_id = ? ORDER BY level ASC", (str(guild_id),))
        return {row["level"]: row["role_id"] for row in cursor}

    def set_setting(self, guild_id: str, key: str, value: str):
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO settings (guild_id, key, value) VALUES (?, ?, ?)",
                (str(guild_id), key, value)
            )

    def get_setting(self, guild_id: str, key: str, default=None):
        cursor = self.conn.execute("SELECT value FROM settings WHERE guild_id = ? AND key = ?", (str(guild_id), key))
        row = cursor.fetchone()
        return row["value"] if row else default

    def set_xp_rate(self, guild_id: str, source: str, rate: float):
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO xp_rates (guild_id, source, rate) VALUES (?, ?, ?)",
                (str(guild_id), source, rate)
            )

    def get_xp_rate(self, guild_id: str, source: str) -> float:
        cursor = self.conn.execute("SELECT rate FROM xp_rates WHERE guild_id = ? AND source = ?", (str(guild_id), source))
        row = cursor.fetchone()
        return float(row["rate"]) if row else 1.0


class AntiFarm:
    def __init__(self):
        self.last_message_time = {} # user_id -> timestamp
        self.last_message_content = {} # user_id -> content

    def check_message(self, user_id: int, content: str) -> bool:
        """Returns True if user should receive XP."""
        now = time.time()
        
        # 1. Check time cooldown (60s)
        last_time = self.last_message_time.get(user_id, 0)
        if now - last_time < 60:
            return False
            
        # 2. Check identical message
        last_content = self.last_message_content.get(user_id, "")
        if content == last_content:
            return False
            
        self.last_message_time[user_id] = now
        self.last_message_content[user_id] = content
        return True


def draw_progress_bar(current_xp: int, required_xp: int, length: int = 15) -> str:
    if required_xp <= 0:
        return "🟩" * length
    fill_amount = int((current_xp / required_xp) * length)
    empty_amount = length - fill_amount
    return "🟩" * fill_amount + "⬜" * empty_amount


class LevelingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = LevelingDB()
        self.anti_farm = AntiFarm()
        
        # Default XP settings
        self.BASE_MESSAGE_XP = 15
        self.BASE_VOICE_XP = 10
        
        self.voice_xp_task.start()

    def cog_unload(self):
        self.voice_xp_task.cancel()

    async def add_xp(self, user: discord.Member, amount: float, source: str = "messages"):
        if user.bot:
            return

        guild_id = str(user.guild.id)
        user_id = str(user.id)

        # Apply multiplier
        multiplier = self.db.get_xp_rate(guild_id, source)
        final_xp = int(amount * multiplier)

        if final_xp <= 0:
            return

        data = self.db.get_user(guild_id, user_id)
        current_xp = data["xp"] + final_xp
        current_level = data["level"]

        leveled_up = False
        while True:
            next_level_xp = calculate_total_xp_for_level(current_level + 1)
            if current_xp >= next_level_xp:
                current_level += 1
                leveled_up = True
            else:
                break

        self.db.set_user(guild_id, user_id, current_xp, current_level)

        if leveled_up:
            await self.handle_level_up(user, current_level)

    async def handle_level_up(self, user: discord.Member, new_level: int, notify: bool = True):
        guild = user.guild
        guild_id = str(guild.id)

        # 1. Manage Roles
        rank_roles = self.db.get_rank_roles(guild_id)
        if rank_roles:
            # Find the highest rank role user qualifies for
            highest_qualifying_level = 0
            target_role_id = None

            for level_req, r_id in rank_roles.items():
                if new_level >= level_req and level_req > highest_qualifying_level:
                    highest_qualifying_level = level_req
                    target_role_id = r_id

            if target_role_id:
                target_role = guild.get_role(int(target_role_id))
                if target_role:
                    # Remove all other rank roles
                    roles_to_remove = []
                    for r_id in rank_roles.values():
                        if str(r_id) != target_role_id:
                            r = guild.get_role(int(r_id))
                            if r and r in user.roles:
                                roles_to_remove.append(r)
                    
                    try:
                        if roles_to_remove:
                            await user.remove_roles(*roles_to_remove, reason="Leveling: removing old rank roles")
                        if target_role not in user.roles:
                            await user.add_roles(target_role, reason="Leveling: adding new rank role")
                    except Exception as e:
                        logging.error(f"Failed to update rank roles for {user}: {e}")

        # 2. Notify
        if not notify:
            return
            
        channel_id = self.db.get_setting(guild_id, "levelup_channel")
        if channel_id:
            channel = guild.get_channel(int(channel_id))
            if channel:
                embed = discord.Embed(
                    title="🎉 Повышение уровня!",
                    description=f"Поздравляем, {user.mention}! Вы достигли **{new_level} уровня**!",
                    color=discord.Color.brand_green()
                )
                embed.set_thumbnail(url=user.display_avatar.url)
                try:
                    await channel.send(embed=embed)
                except Exception as e:
                    logging.error(f"Failed to send level up message: {e}")


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        if self.anti_farm.check_message(message.author.id, message.content):
            await self.add_xp(message.author, self.BASE_MESSAGE_XP, source="messages")

    @tasks.loop(seconds=60)
    async def voice_xp_task(self):
        for guild in self.bot.guilds:
            for voice_channel in guild.voice_channels:
                # AFK check
                if guild.afk_channel and voice_channel.id == guild.afk_channel.id:
                    continue

                members = voice_channel.members
                # Anti-farm: Only if there are other people in the channel
                valid_members = [
                    m for m in members 
                    if not m.bot and not m.voice.self_mute and not m.voice.mute and not m.voice.deaf and not m.voice.self_deaf
                ]

                if len(valid_members) > 1:
                    for member in valid_members:
                        await self.add_xp(member, self.BASE_VOICE_XP, source="voice")

    @voice_xp_task.before_loop
    async def before_voice_xp_task(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="rank", description="Показать ваш текущий уровень и количество опыта")
    async def rank_cmd(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        if target.bot:
            await interaction.response.send_message("Боты не имеют уровня!", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        user_id = str(target.id)

        data = self.db.get_user(guild_id, user_id)
        level = data["level"]
        total_xp = data["xp"]

        xp_for_current = calculate_total_xp_for_level(level)
        xp_for_next = calculate_total_xp_for_level(level + 1)

        xp_in_level = total_xp - xp_for_current
        required_for_next = xp_for_next - xp_for_current

        rank_pos = self.db.get_user_rank_position(guild_id, user_id)
        
        # Determine current rank role
        rank_roles = self.db.get_rank_roles(guild_id)
        current_rank_role = "Нет"
        if rank_roles:
            highest_qualifying_level = 0
            for level_req, r_id in rank_roles.items():
                if level >= level_req and level_req > highest_qualifying_level:
                    highest_qualifying_level = level_req
                    r = interaction.guild.get_role(int(r_id))
                    if r:
                        current_rank_role = r.mention

        progress_bar = draw_progress_bar(xp_in_level, required_for_next)

        embed = discord.Embed(title=f"Ранг {target.display_name}", color=discord.Color.blurple())
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Уровень", value=f"**{level}**", inline=True)
        embed.add_field(name="XP", value=f"**{total_xp} / {xp_for_next}**", inline=True)
        embed.add_field(name="Позиция", value=f"**#{rank_pos}**", inline=True)
        embed.add_field(name="Ранговая роль", value=current_rank_role, inline=False)
        embed.add_field(name="Прогресс до следующего уровня", value=f"{progress_bar} {xp_in_level}/{required_for_next} XP", inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Показать топ-10 игроков сервера по уровням")
    async def leaderboard_cmd(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        top_users = self.db.get_top_users(guild_id, 10)

        if not top_users:
            await interaction.response.send_message("Рейтинг пока пуст.", ephemeral=True)
            return

        embed = discord.Embed(title="🏆 Топ-10 игроков", color=discord.Color.gold())
        
        description = ""
        for i, user_data in enumerate(top_users):
            member = interaction.guild.get_member(int(user_data["user_id"]))
            name = member.mention if member else f"<@{user_data['user_id']}>"
            
            medal = ""
            if i == 0: medal = "🥇 "
            elif i == 1: medal = "🥈 "
            elif i == 2: medal = "🥉 "
            else: medal = f"**{i+1}.** "
            
            description += f"{medal}{name} — **{user_data['level']} уровень** ({user_data['xp']} XP)\n"

        embed.description = description
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="set-rank-role", description="Привязать роль к уровню")
    @app_commands.describe(level="Уровень для получения роли", role="Выдаваемая роль")
    @app_commands.default_permissions(administrator=True)
    async def set_rank_role_cmd(self, interaction: discord.Interaction, level: int, role: discord.Role):
        if level <= 0:
            await interaction.response.send_message("Уровень должен быть больше 0.", ephemeral=True)
            return
            
        self.db.set_rank_role(str(interaction.guild.id), level, str(role.id))
        await interaction.response.send_message(f"Роль {role.mention} привязана к уровню **{level}**.", ephemeral=True)

    @app_commands.command(name="remove-rank-role", description="Удалить привязку роли к уровню")
    @app_commands.describe(level="Уровень, у которого нужно удалить привязку")
    @app_commands.default_permissions(administrator=True)
    async def remove_rank_role_cmd(self, interaction: discord.Interaction, level: int):
        self.db.remove_rank_role(str(interaction.guild.id), level)
        await interaction.response.send_message(f"Привязка роли к уровню **{level}** удалена.", ephemeral=True)

    @app_commands.command(name="rank-roles", description="Показать все привязки уровней к ролям")
    @app_commands.default_permissions(administrator=True)
    async def rank_roles_cmd(self, interaction: discord.Interaction):
        roles = self.db.get_rank_roles(str(interaction.guild.id))
        if not roles:
            await interaction.response.send_message("Привязок ролей нет.", ephemeral=True)
            return

        desc = ""
        for lvl, role_id in roles.items():
            desc += f"Уровень **{lvl}** → <@&{role_id}>\n"
            
        embed = discord.Embed(title="Ранговые роли", description=desc, color=discord.Color.blue())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="set-levelup-channel", description="Установить канал для уведомлений о повышении уровня")
    @app_commands.default_permissions(administrator=True)
    async def set_levelup_channel_cmd(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.db.set_setting(str(interaction.guild.id), "levelup_channel", str(channel.id))
        await interaction.response.send_message(f"Канал уведомлений о повышении уровня установлен на {channel.mention}.", ephemeral=True)

    @app_commands.command(name="set-xp-rate", description="Настройка множителей опыта")
    @app_commands.describe(source="Источник опыта (messages, voice, jobs, events)", multiplier="Множитель (например, 2.0)")
    @app_commands.choices(source=[
        app_commands.Choice(name="Сообщения", value="messages"),
        app_commands.Choice(name="Голосовые каналы", value="voice"),
        app_commands.Choice(name="Профессии (jobs)", value="jobs"),
        app_commands.Choice(name="Ивенты (events)", value="events"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def set_xp_rate_cmd(self, interaction: discord.Interaction, source: str, multiplier: float):
        if multiplier < 0:
            await interaction.response.send_message("Множитель не может быть меньше 0.", ephemeral=True)
            return
            
        self.db.set_xp_rate(str(interaction.guild.id), source, multiplier)
        await interaction.response.send_message(f"Множитель опыта для источника **{source}** установлен на **{multiplier}**.", ephemeral=True)

    @app_commands.command(name="restart-rank", description="Перепроверить и выдать ранговую роль пользователю или всем (all)")
    @app_commands.describe(member="Пользователь для проверки", target="Или впишите 'all' для проверки всех")
    @app_commands.default_permissions(administrator=True)
    async def restart_rank_cmd(self, interaction: discord.Interaction, member: discord.Member = None, target: str = None):
        if target and target.lower() in {"all", "все", "everyone", "@everyone"}:
            await interaction.response.defer(ephemeral=True)
            guild_id = str(interaction.guild.id)
            count = 0
            import asyncio
            for m in interaction.guild.members:
                if m.bot: continue
                data = self.db.get_user(guild_id, str(m.id))
                await self.handle_level_up(m, data["level"], notify=False)
                count += 1
                await asyncio.sleep(0.1) # prevent rate limits
            await interaction.followup.send(f"Ранговые роли успешно перепроверены и выданы для {count} пользователей.")
            return

        if not member:
            await interaction.response.send_message("Укажите пользователя в параметре `member` или впишите 'all' в поле `target`.", ephemeral=True)
            return

        if member.bot:
            await interaction.response.send_message("У ботов нет рангов.", ephemeral=True)
            return
            
        guild_id = str(interaction.guild.id)
        user_id = str(member.id)
        
        data = self.db.get_user(guild_id, user_id)
        current_level = data["level"]
        
        await self.handle_level_up(member, current_level, notify=False)
        await interaction.response.send_message(f"Ранговая роль для {member.mention} (уровень {current_level}) была проверена и обновлена.", ephemeral=True)

    @app_commands.command(name="command-chat", description="Выбрать чаты для команд (админ/игрок)")
    @app_commands.describe(channel="Чат, где разрешены команды. Если не указан - текущий.", 
                           remove="Удалить чат из списка разрешённых? (True/False)")
    @app_commands.default_permissions(administrator=True)
    async def command_chat_cmd(self, interaction: discord.Interaction, channel: discord.TextChannel = None, remove: bool = False):
        target = channel or interaction.channel
        guild_id = str(interaction.guild.id)
        current_raw = self.db.get_setting(guild_id, "command_channels", "[]")
        
        import json
        try:
            current = json.loads(current_raw)
        except:
            current = []
            
        target_id = target.id
        if remove:
            if target_id in current:
                current.remove(target_id)
                self.db.set_setting(guild_id, "command_channels", json.dumps(current))
                await interaction.response.send_message(f"Канал {target.mention} удалён из списка командных.", ephemeral=True)
            else:
                await interaction.response.send_message(f"Канал {target.mention} не был в списке командных.", ephemeral=True)
        else:
            if target_id not in current:
                current.append(target_id)
                self.db.set_setting(guild_id, "command_channels", json.dumps(current))
                await interaction.response.send_message(f"Канал {target.mention} добавлен в список командных.", ephemeral=True)
            else:
                await interaction.response.send_message(f"Канал {target.mention} уже находится в списке командных.", ephemeral=True)

