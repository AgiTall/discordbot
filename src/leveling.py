import discord
from discord.ext import commands, tasks
from discord import app_commands
import psycopg2
import psycopg2.extras
import time
import logging
import math
import os

DEFAULT_XP_RATE = 1.0
VOICE_HOURLY_REWARD = 50
VOICE_REWARD_INTERVAL_SECONDS = 60 * 60


def format_voice_duration(total_seconds: int) -> str:
    """Format a voice-session duration for Discord leaderboard rows."""
    total_seconds = max(0, int(total_seconds or 0))
    days, remainder = divmod(total_seconds, 24 * 60 * 60)
    hours, remainder = divmod(remainder, 60 * 60)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days} д")
    if hours:
        parts.append(f"{hours} ч")
    if minutes:
        parts.append(f"{minutes} мин")
    if not parts:
        parts.append(f"{seconds} сек")
    return " ".join(parts)

def calculate_xp_for_level(level: int) -> int:
    """Return the XP needed to reach ``level`` from the previous level."""
    if level <= 1:
        return 0
    # Keep the bot in sync with the public level table in docs/js/app.js.
    return round(100 * (level ** 1.5))

def calculate_total_xp_for_level(level: int) -> int:
    total = 0
    for i in range(1, level + 1):
        total += calculate_xp_for_level(i)
    return total

def _normalize_db_url_for_psycopg2(url):
    """Нормализует DATABASE_URL для psycopg2 (убирает +asyncpg и другие SQLAlchemy-префиксы)."""
    if not url:
        return url
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    url = url.replace("postgresql+psycopg2://", "postgresql://")
    url = url.replace("postgres://", "postgresql://")
    return url


class LevelingDB:
    def __init__(self, db_url=None):
        if db_url is None:
            db_url = os.environ.get("DATABASE_URL")
        self.db_url = _normalize_db_url_for_psycopg2(db_url)
        self._connect()
        self._init_tables()

    def _connect(self):
        """Создать (или пересоздать) соединение с PostgreSQL."""
        self.conn = psycopg2.connect(self.db_url, cursor_factory=psycopg2.extras.DictCursor)
        self.conn.autocommit = True

    def _ensure_conn(self):
        """Проверить что соединение живое, переподключиться если нет."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
        except Exception:
            logging.warning("LevelingDB: соединение разорвано, переподключаемся...")
            try:
                self.conn.close()
            except Exception:
                pass
            self._connect()

    def _init_tables(self):
        """Создать таблицы leveling_users и др., мигрировать данные из старых таблиц."""
        with self.conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leveling_users (
                    guild_id TEXT, 
                    user_id TEXT, 
                    xp INTEGER, 
                    level INTEGER, 
                    PRIMARY KEY(guild_id, user_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rank_roles (
                    guild_id TEXT, 
                    level INTEGER, 
                    role_id TEXT, 
                    remove_role_id TEXT,
                    PRIMARY KEY(guild_id, level)
                )
            """)
            try:
                cursor.execute("ALTER TABLE rank_roles ADD COLUMN remove_role_id TEXT")
            except psycopg2.errors.DuplicateColumn:
                pass
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    guild_id TEXT, 
                    key TEXT, 
                    value TEXT, 
                    PRIMARY KEY(guild_id, key)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS xp_rates (
                    guild_id TEXT, 
                    source TEXT, 
                    rate REAL, 
                    PRIMARY KEY(guild_id, source)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS voice_session_stats (
                    guild_id TEXT,
                    user_id TEXT,
                    longest_session_seconds BIGINT NOT NULL DEFAULT 0,
                    PRIMARY KEY(guild_id, user_id)
                )
            """)

            # --- Миграция из старой таблицы users (если в ней есть колонка xp) ---
            try:
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'xp'
                """)
                if cursor.fetchone():
                    cursor.execute("SELECT COUNT(*) FROM leveling_users")
                    new_count = cursor.fetchone()[0]
                    if new_count == 0:
                        cursor.execute("""
                            INSERT INTO leveling_users (guild_id, user_id, xp, level)
                            SELECT guild_id, user_id, xp, level FROM users
                            WHERE xp IS NOT NULL
                            ON CONFLICT (guild_id, user_id) DO NOTHING
                        """)
                        migrated = cursor.rowcount
                        if migrated > 0:
                            logging.info(f"LevelingDB: мигрировано {migrated} пользователей из старой таблицы 'users' → 'leveling_users'")
            except Exception as e:
                logging.debug(f"LevelingDB: миграция users пропущена: {e}")

    def get_user(self, guild_id: str, user_id: str):
        self._ensure_conn()
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT xp, level FROM leveling_users WHERE guild_id = %s AND user_id = %s", (str(guild_id), str(user_id)))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {"xp": 0, "level": 1}

    def set_user(self, guild_id: str, user_id: str, xp: int, level: int):
        self._ensure_conn()
        with self.conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO leveling_users (guild_id, user_id, xp, level) VALUES (%s, %s, %s, %s) ON CONFLICT (guild_id, user_id) DO UPDATE SET xp = EXCLUDED.xp, level = EXCLUDED.level",
                (str(guild_id), str(user_id), xp, level)
            )

    def increment_user_xp(self, guild_id: str, user_id: str, amount: int):
        """Atomically add XP and return the user's updated progress.

        A read followed by ``set_user`` can lose one of two rewards arriving at
        nearly the same time.  The database-side increment makes every reward
        durable before level calculation continues.
        """
        self._ensure_conn()
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO leveling_users (guild_id, user_id, xp, level)
                VALUES (%s, %s, %s, 1)
                ON CONFLICT (guild_id, user_id) DO UPDATE
                SET xp = GREATEST(COALESCE(leveling_users.xp, 0), 0) + EXCLUDED.xp
                RETURNING xp, level
                """,
                (str(guild_id), str(user_id), int(amount)),
            )
            return dict(cursor.fetchone())

    def set_user_level_at_least(self, guild_id: str, user_id: str, level: int):
        """Raise a stored level without letting a concurrent update lower it."""
        self._ensure_conn()
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE leveling_users
                SET level = GREATEST(COALESCE(level, 1), %s)
                WHERE guild_id = %s AND user_id = %s
                """,
                (max(1, int(level)), str(guild_id), str(user_id)),
            )

    def get_top_users(self, guild_id: str, limit: int = 10, user_ids=None):
        self._ensure_conn()
        with self.conn.cursor() as cursor:
            if user_ids is not None:
                user_ids = list(dict.fromkeys(str(user_id) for user_id in user_ids))
                if not user_ids:
                    return []
                cursor.execute(
                    """
                    SELECT user_id, xp, level
                    FROM leveling_users
                    WHERE guild_id = %s AND user_id = ANY(%s)
                    ORDER BY xp DESC
                    LIMIT %s
                    """,
                    (str(guild_id), user_ids, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT user_id, xp, level
                    FROM leveling_users
                    WHERE guild_id = %s
                    ORDER BY xp DESC
                    LIMIT %s
                    """,
                    (str(guild_id), limit),
                )
            return [dict(row) for row in cursor]

    def record_voice_session(self, guild_id: str, user_id: str, duration_seconds: int):
        """Atomically preserve a user's longest continuous voice session."""
        duration_seconds = max(0, int(duration_seconds or 0))
        self._ensure_conn()
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO voice_session_stats (
                    guild_id, user_id, longest_session_seconds
                ) VALUES (%s, %s, %s)
                ON CONFLICT (guild_id, user_id) DO UPDATE
                SET longest_session_seconds = GREATEST(
                    voice_session_stats.longest_session_seconds,
                    EXCLUDED.longest_session_seconds
                )
                """,
                (str(guild_id), str(user_id), duration_seconds),
            )

    def get_top_voice_sessions(self, guild_id: str, limit: int = 10, user_ids=None):
        self._ensure_conn()
        with self.conn.cursor() as cursor:
            if user_ids is not None:
                user_ids = list(dict.fromkeys(str(user_id) for user_id in user_ids))
                if not user_ids:
                    return []
                cursor.execute(
                    """
                    SELECT user_id, longest_session_seconds
                    FROM voice_session_stats
                    WHERE guild_id = %s AND user_id = ANY(%s)
                    ORDER BY longest_session_seconds DESC, user_id ASC
                    LIMIT %s
                    """,
                    (str(guild_id), user_ids, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT user_id, longest_session_seconds
                    FROM voice_session_stats
                    WHERE guild_id = %s
                    ORDER BY longest_session_seconds DESC, user_id ASC
                    LIMIT %s
                    """,
                    (str(guild_id), limit),
                )
            return [dict(row) for row in cursor]

    def get_user_rank_position(self, guild_id: str, user_id: str):
        # Count users with more XP
        user_data = self.get_user(guild_id, user_id)
        self._ensure_conn()
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as pos FROM leveling_users WHERE guild_id = %s AND xp > %s", (str(guild_id), user_data["xp"]))
            row = cursor.fetchone()
            return row["pos"] + 1

    def set_rank_role(self, guild_id: str, level: int, role_id: str, remove_role_id: str = None):
        self._ensure_conn()
        with self.conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO rank_roles (guild_id, level, role_id, remove_role_id) VALUES (%s, %s, %s, %s) ON CONFLICT (guild_id, level) DO UPDATE SET role_id = EXCLUDED.role_id, remove_role_id = EXCLUDED.remove_role_id",
                (str(guild_id), level, str(role_id), str(remove_role_id) if remove_role_id else None)
            )

    def remove_rank_role(self, guild_id: str, level: int):
        self._ensure_conn()
        with self.conn.cursor() as cursor:
            cursor.execute("DELETE FROM rank_roles WHERE guild_id = %s AND level = %s", (str(guild_id), level))

    def get_rank_roles(self, guild_id: str):
        self._ensure_conn()
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT level, role_id, remove_role_id FROM rank_roles WHERE guild_id = %s ORDER BY level ASC", (str(guild_id),))
            return {row["level"]: {"role_id": row["role_id"], "remove_role_id": row["remove_role_id"]} for row in cursor}

    def set_setting(self, guild_id: str, key: str, value: str):
        self._ensure_conn()
        with self.conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO settings (guild_id, key, value) VALUES (%s, %s, %s) ON CONFLICT (guild_id, key) DO UPDATE SET value = EXCLUDED.value",
                (str(guild_id), key, value)
            )

    def get_setting(self, guild_id: str, key: str, default=None):
        self._ensure_conn()
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT value FROM settings WHERE guild_id = %s AND key = %s", (str(guild_id), key))
            row = cursor.fetchone()
            return row["value"] if row else default

    def set_xp_rate(self, guild_id: str, source: str, rate: float):
        rate = float(rate)
        if not math.isfinite(rate) or rate < 0:
            raise ValueError("XP rate must be a finite non-negative number")
        self._ensure_conn()
        with self.conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO xp_rates (guild_id, source, rate) VALUES (%s, %s, %s) ON CONFLICT (guild_id, source) DO UPDATE SET rate = EXCLUDED.rate",
                (str(guild_id), source, rate)
            )

    def get_xp_rate(self, guild_id: str, source: str) -> float:
        self._ensure_conn()
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT rate FROM xp_rates WHERE guild_id = %s AND source = %s", (str(guild_id), source))
            row = cursor.fetchone()
            if not row:
                return DEFAULT_XP_RATE
            rate = float(row["rate"])
            if not math.isfinite(rate) or rate < 0:
                logging.warning("LevelingDB: invalid stored XP rate %r for %s/%s", rate, guild_id, source)
                return DEFAULT_XP_RATE
            return rate


class AntiFarm:
    def __init__(self):
        self.last_message_time = {}  # user_id -> timestamp
        self.last_message_content = {}  # user_id -> content

    def check_message(self, user_key, content: str, cooldown: int = 60) -> bool:
        """Returns True if user should receive XP."""
        now = time.time()
        cooldown = max(10, int(cooldown or 60))

        last_time = self.last_message_time.get(user_key, 0)
        if now - last_time < cooldown:
            return False

        last_content = self.last_message_content.get(user_key, "")
        if content == last_content:
            return False

        self.last_message_time[user_key] = now
        self.last_message_content[user_key] = content
        return True


def draw_progress_bar(current_xp: int, required_xp: int, length: int = 15) -> str:
    length = max(0, int(length))
    if required_xp <= 0:
        return "🟩" * length
    progress = max(0.0, min(1.0, current_xp / required_xp))
    fill_amount = int(progress * length)
    empty_amount = length - fill_amount
    return "🟩" * fill_amount + "⬜" * empty_amount


class LevelingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = LevelingDB()
        self.anti_farm = AntiFarm()
        self.active_voice_sessions = {}
        
        self.voice_xp_task.start()

    def _get_int_setting(self, guild_id: str, key: str, default: int, minimum: int = 0) -> int:
        raw_value = self.db.get_setting(guild_id, key, str(default))
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            logging.warning("Leveling: invalid integer setting %s=%r for guild %s", key, raw_value, guild_id)
            value = default
        return max(minimum, value)

    def get_base_message_xp(self, guild_id: str) -> int:
        return self._get_int_setting(guild_id, "base_message_xp", 15)

    def get_base_voice_xp(self, guild_id: str) -> int:
        return self._get_int_setting(guild_id, "base_voice_xp", 10)

    def get_antifarm_cooldown(self, guild_id: str) -> int:
        return self._get_int_setting(guild_id, "antifarm_cooldown", 60, minimum=10)

    def get_min_msg_length(self, guild_id: str) -> int:
        return self._get_int_setting(guild_id, "min_msg_length", 0)

    def cog_unload(self):
        self.voice_xp_task.cancel()
        ended_at = time.time()
        for (guild_id, user_id), session in self.active_voice_sessions.items():
            duration = max(0, int(ended_at - session["started_at"]))
            self.db.record_voice_session(guild_id, user_id, duration)
        self.active_voice_sessions.clear()

    @staticmethod
    def _is_counted_voice_channel(guild, channel) -> bool:
        if channel is None:
            return False
        afk_channel = getattr(guild, "afk_channel", None)
        return afk_channel is None or channel.id != afk_channel.id

    def _start_voice_session(self, member, now=None):
        key = (str(member.guild.id), str(member.id))
        self.active_voice_sessions.setdefault(
            key,
            {
                "started_at": time.time() if now is None else float(now),
                "rewarded_hours": 0,
            },
        )
        return self.active_voice_sessions[key]

    def _finish_voice_session(self, member, now=None):
        key = (str(member.guild.id), str(member.id))
        session = self.active_voice_sessions.pop(key, None)
        if session is None:
            return 0

        ended_at = time.time() if now is None else float(now)
        duration = max(0, int(ended_at - session["started_at"]))
        self.db.record_voice_session(key[0], key[1], duration)
        return duration

    def _present_voice_members(self, guild):
        channels = list(getattr(guild, "voice_channels", ()))
        channels.extend(getattr(guild, "stage_channels", ()))
        present = {}
        for channel in channels:
            if not self._is_counted_voice_channel(guild, channel):
                continue
            for member in getattr(channel, "members", ()):
                if not member.bot:
                    present[(str(guild.id), str(member.id))] = member
        return present

    async def _award_voice_cash(self, guild, pending_rewards):
        """Credit voice rewards as one economy save and report successful rows."""
        required_bot_attrs = (
            "economy_lock",
            "set_economy_guild_id",
            "reset_economy_guild_id",
            "get_account",
            "save_economy",
        )
        if any(not hasattr(self.bot, attr) for attr in required_bot_attrs):
            logging.error("Voice rewards: bot economy helpers are unavailable")
            return {}

        # Presence is checked again at the point of payment. A member who left
        # while this task was being prepared must not receive the hourly credit.
        eligible = {}
        for key, (member, hours) in pending_rewards.items():
            voice_state = getattr(member, "voice", None)
            channel = getattr(voice_state, "channel", None)
            if hours > 0 and self._is_counted_voice_channel(guild, channel):
                eligible[key] = (member, hours)
        if not eligible:
            return {}

        previous_balances = []
        try:
            async with self.bot.economy_lock:
                token = self.bot.set_economy_guild_id(guild.id)
                try:
                    for member, hours in eligible.values():
                        account = self.bot.get_account(member.id)
                        old_cash = float(account.get("cash", 0.0))
                        if not math.isfinite(old_cash):
                            old_cash = 0.0
                        previous_balances.append((account, old_cash))
                        account["cash"] = round(
                            old_cash + VOICE_HOURLY_REWARD * hours,
                            2,
                        )
                    self.bot.save_economy()
                finally:
                    self.bot.reset_economy_guild_id(token)
        except Exception:
            for account, old_cash in previous_balances:
                account["cash"] = old_cash
            logging.exception("Voice rewards: failed to credit guild %s", guild.id)
            return {}

        return {key: hours for key, (_, hours) in eligible.items()}

    async def _update_voice_sessions(self, guild, now=None):
        now = time.time() if now is None else float(now)
        guild_id = str(guild.id)
        present = self._present_voice_members(guild)

        for key in list(self.active_voice_sessions):
            if key[0] == guild_id and key not in present:
                session = self.active_voice_sessions.pop(key)
                duration = max(0, int(now - session["started_at"]))
                self.db.record_voice_session(key[0], key[1], duration)

        pending_rewards = {}
        pending_sessions = {}
        for key, member in present.items():
            session = self._start_voice_session(member, now=now)
            duration = max(0, int(now - session["started_at"]))
            self.db.record_voice_session(key[0], key[1], duration)

            completed_hours = duration // VOICE_REWARD_INTERVAL_SECONDS
            due_hours = completed_hours - session["rewarded_hours"]
            if due_hours > 0:
                # Claim the due hours before awaiting the economy lock. This
                # prevents a simultaneous command refresh from paying twice.
                session["rewarded_hours"] += due_hours
                pending_rewards[key] = (member, due_hours)
                pending_sessions[key] = session

        awarded = await self._award_voice_cash(guild, pending_rewards)
        for key, (_, due_hours) in pending_rewards.items():
            if key in awarded:
                continue
            # Roll the claim back after a failed/skipped payment so the next
            # minute can retry. Do not mutate a replacement session.
            if self.active_voice_sessions.get(key) is pending_sessions.get(key):
                self.active_voice_sessions[key]["rewarded_hours"] -= due_hours

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot or not member.guild:
            return

        before_counted = self._is_counted_voice_channel(member.guild, before.channel)
        after_counted = self._is_counted_voice_channel(member.guild, after.channel)
        key = (str(member.guild.id), str(member.id))

        if after_counted and not before_counted:
            self._start_voice_session(member)
        elif before_counted and not after_counted:
            self._finish_voice_session(member)
        elif after_counted and key not in self.active_voice_sessions:
            # Covers a regular voice-channel move after a reconnect/reload.
            self._start_voice_session(member)

    async def add_xp(self, user: discord.Member, amount: float, source: str = "messages"):
        if user.bot:
            return

        guild_id = str(user.guild.id)
        user_id = str(user.id)

        # Apply multiplier
        multiplier = self.db.get_xp_rate(guild_id, source)
        try:
            amount = float(amount)
            multiplier = float(multiplier)
        except (TypeError, ValueError):
            logging.warning("Leveling: invalid XP reward amount=%r multiplier=%r", amount, multiplier)
            return

        if not math.isfinite(amount) or not math.isfinite(multiplier):
            logging.warning("Leveling: non-finite XP reward amount=%r multiplier=%r", amount, multiplier)
            return

        final_xp = int(amount * multiplier)

        if final_xp <= 0:
            return

        data = self.db.increment_user_xp(guild_id, user_id, final_xp)
        current_xp = max(0, int(data["xp"] or 0))
        previous_level = max(1, int(data["level"] or 1))
        current_level = previous_level

        leveled_up = False
        while True:
            next_level_xp = calculate_total_xp_for_level(current_level + 1)
            if current_xp >= next_level_xp:
                current_level += 1
                leveled_up = True
            else:
                break

        if current_level > previous_level:
            self.db.set_user_level_at_least(guild_id, user_id, current_level)

        if leveled_up:
            await self.handle_level_up(user, current_level)

    async def handle_level_up(self, user: discord.Member, new_level: int, notify: bool = True):
        guild = user.guild
        guild_id = str(guild.id)
        error_msg = None
        target_role_assigned = None

        # 1. Manage Roles
        rank_roles = self.db.get_rank_roles(guild_id)
        if rank_roles:
            # Find the highest rank role user qualifies for
            highest_qualifying_level = 0
            target_role_id = None

            for level_req, r_data in rank_roles.items():
                r_id = r_data["role_id"]
                if new_level >= level_req and level_req > highest_qualifying_level:
                    highest_qualifying_level = level_req
                    target_role_id = r_id
                    target_remove_role_id = r_data.get("remove_role_id")

            if target_role_id:
                target_role = guild.get_role(int(target_role_id))
                if target_role:
                    target_role_assigned = target_role
                    roles_to_remove = []
                    
                    if target_remove_role_id:
                        # Если явно указана роль для удаления
                        rem_role = guild.get_role(int(target_remove_role_id))
                        if rem_role and rem_role in user.roles:
                            roles_to_remove.append(rem_role)
                    else:
                        # Иначе удаляем все предыдущие ранговые роли (старое поведение)
                        for r_data in rank_roles.values():
                            old_r_id = r_data["role_id"]
                            if str(old_r_id) != str(target_role_id):
                                r = guild.get_role(int(old_r_id))
                                if r and r in user.roles:
                                    roles_to_remove.append(r)
                    
                    try:
                        if roles_to_remove:
                            await user.remove_roles(*roles_to_remove, reason="Leveling: removing old rank roles")
                        if target_role not in user.roles:
                            await user.add_roles(target_role, reason="Leveling: adding new rank role")
                    except Exception as e:
                        error_msg = str(e)
                        logging.error(f"Failed to update rank roles for {user}: {e}")
                else:
                    error_msg = f"Роль с ID {target_role_id} не найдена."

        # 2. Notify
        if not notify:
            return target_role_assigned, error_msg

        embed = discord.Embed(
            title="🎉 Повышение уровня!",
            description=f"Поздравляем, {user.mention}! Вы достигли **{new_level} уровня**!",
            color=discord.Color.brand_green()
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        channel_id = self.db.get_setting(guild_id, "levelup_channel")
        if channel_id:
            channel = guild.get_channel(int(channel_id))
            if channel:
                try:
                    await channel.send(embed=embed)
                except Exception as e:
                    logging.error(f"Failed to send level up message: {e}")

        if self.db.get_setting(guild_id, "levelup_dm", "false") == "true":
            try:
                await user.send(embed=embed)
            except Exception as e:
                logging.error(f"Failed to send level up DM: {e}")

        return target_role_assigned, error_msg


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild_id = str(message.guild.id)
        content = message.content.strip()
        min_len = self.get_min_msg_length(guild_id)
        if min_len and len(content) < min_len:
            return

        cooldown = self.get_antifarm_cooldown(guild_id)
        user_key = (message.guild.id, message.author.id)
        if self.anti_farm.check_message(user_key, message.content, cooldown=cooldown):
            await self.add_xp(message.author, self.get_base_message_xp(guild_id), source="messages")

    @commands.Cog.listener()
    async def on_leveling_add_xp(
        self,
        user: discord.Member,
        amount: float,
        source: str = "jobs",
    ):
        """Persist XP rewards dispatched by profession and event cogs."""
        await self.add_xp(user, amount, source=source)

    @tasks.loop(seconds=60)
    async def voice_xp_task(self):
        for guild in self.bot.guilds:
            try:
                await self._update_voice_sessions(guild)
            except Exception:
                logging.exception(
                    "Voice sessions: failed to update guild %s",
                    guild.id,
                )

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
                    guild_id = str(guild.id)
                    base_voice_xp = self.get_base_voice_xp(guild_id)
                    for member in valid_members:
                        await self.add_xp(member, base_voice_xp, source="voice")

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
            for level_req, r_data in rank_roles.items():
                if level >= level_req and level_req > highest_qualifying_level:
                    highest_qualifying_level = level_req
                    r = interaction.guild.get_role(int(r_data["role_id"]))
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
    @app_commands.guild_only()
    async def leaderboard_cmd(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        current_member_ids = [
            str(member.id) for member in interaction.guild.members if not member.bot
        ]
        top_users = self.db.get_top_users(
            guild_id,
            10,
            user_ids=current_member_ids,
        )

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

    @app_commands.command(
        name="voice-leaderboard",
        description="Показать топ-10 самых долгих голосовых сеансов сервера",
    )
    @app_commands.guild_only()
    async def voice_leaderboard_cmd(self, interaction: discord.Interaction):
        guild = interaction.guild
        await interaction.response.defer()
        await self._update_voice_sessions(guild)

        current_member_ids = [str(member.id) for member in guild.members if not member.bot]
        top_users = self.db.get_top_voice_sessions(
            str(guild.id),
            10,
            user_ids=current_member_ids,
        )
        if not top_users:
            await interaction.followup.send(
                "Рейтинг голосовых сеансов пока пуст.",
            )
            return

        rows = []
        for index, user_data in enumerate(top_users):
            member = guild.get_member(int(user_data["user_id"]))
            if member is None:
                continue
            if index == 0:
                position = "🥇"
            elif index == 1:
                position = "🥈"
            elif index == 2:
                position = "🥉"
            else:
                position = f"**{index + 1}.**"
            duration = format_voice_duration(user_data["longest_session_seconds"])
            rows.append(f"{position} {member.mention} — **{duration}**")

        if not rows:
            await interaction.followup.send(
                "Рейтинг голосовых сеансов пока пуст.",
            )
            return

        embed = discord.Embed(
            title="🎙️ Самые долгие голосовые сеансы",
            description="\n".join(rows),
            color=discord.Color.blurple(),
        )
        embed.set_footer(
            text=f"За каждый полный час непрерывного сеанса начисляется ${VOICE_HOURLY_REWARD}."
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="set-rank-role", description="Привязать роль к уровню и выдать подходящим игрокам")
    @app_commands.describe(level="Уровень для получения роли", role="Выдаваемая роль")
    @app_commands.default_permissions(administrator=True)
    async def set_rank_role_cmd(self, interaction: discord.Interaction, level: int, role: discord.Role):
        if level <= 0:
            await interaction.response.send_message("Уровень должен быть больше 0.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        self.db.set_rank_role(str(interaction.guild.id), level, str(role.id))
        
        guild_id = str(interaction.guild.id)
        count = 0
        import asyncio
        for m in interaction.guild.members:
            if m.bot: continue
            data = self.db.get_user(guild_id, str(m.id))
            if data["level"] >= level:
                await self.handle_level_up(m, data["level"], notify=False)
                count += 1
                await asyncio.sleep(0.1) # prevent rate limits
                
        await interaction.followup.send(f"✅ Роль {role.mention} привязана к уровню **{level}**.\nБаза обновлена, роль проверена и выдана {count} подходящим пользователям (чей уровень {level} или выше)!", ephemeral=True)

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
        for lvl, r_data in roles.items():
            role_id = r_data["role_id"]
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
        if not math.isfinite(multiplier) or multiplier < 0:
            await interaction.response.send_message("Множитель должен быть конечным числом не меньше 0.", ephemeral=True)
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
        
        role_assigned, error_msg = await self.handle_level_up(member, current_level, notify=False)
        if error_msg:
            await interaction.response.send_message(f"❌ Ошибка при выдаче роли: `{error_msg}`\n**Совет:** Проверьте, что у бота есть права на выдачу ролей, и что его роль находится **выше** ранговых ролей в иерархии сервера.", ephemeral=True)
        else:
            role_ment = role_assigned.mention if role_assigned else "Нет подходящей роли"
            await interaction.response.send_message(f"✅ Ранговая роль для {member.mention} (уровень {current_level}) была проверена и обновлена. Назначена: {role_ment}", ephemeral=True)

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

