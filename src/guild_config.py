"""Слой настроек сервера: объединяет economy.db и leveling.db для веб-панели."""
import json

from src.auto_reactions import auto_reactions_for_dashboard, normalize_auto_reactions

DEFAULT_WELCOME_MESSAGE = "Добро пожаловать на сервер, {mention}! 🎉"
DEFAULT_FAREWELL_MESSAGE = "{user} покинул сервер. До свидания!"

EMOJI_FIELDS = {
    "cashEmoji": "cash_emoji",
    "goldEmoji": "gold_emoji",
    "mapEmoji": "map_emoji",
    "statsEmoji": "stats_emoji",
    "safeEmoji": "safe_emoji",
    "lockEmoji": "lock_emoji",
    "treasureDigEmoji": "treasure_dig_emoji",
    "treasureFoundEmoji": "treasure_found_emoji",
    "treasureExtraEmoji": "treasure_extra_emoji",
    "balanceFinanceEmoji": "balance_ui_finance",
    "balanceRolesEmoji": "balance_ui_roles",
    "balanceEconomyEmoji": "balance_ui_economy",
    "balanceGangEmoji": "balance_ui_gang",
}

ROLE_ICON_FIELDS = {
    "roleIconBountyHunter": "bounty_hunter",
    "roleIconTrader": "trader",
    "roleIconMoonshiner": "moonshiner",
    "roleIconNaturalist": "naturalist",
    "roleIconMiner": "miner",
    "roleIconCollector": "collector",
}

MESSAGE_FIELDS = {
    "rolesDescription": "roles_description",
    "rolesFooter": "roles_footer",
    "workSuccessMessage": "work_success",
    "roleRequiredMessage": "role_required",
    "resetPromptMessage": "reset_prompt",
}

DEFAULT_CUSTOM_MESSAGES = {
    "roles_description": "Выберите профессию и купите доступную роль за золото.",
    "roles_footer": "Доступные роли покупаются зелёными кнопками ниже.",
    "work_success": "{mention}, {scenario} и получили **{reward}**.",
    "role_required": "Команда доступна только роли **{role}**. Купить её можно через `/roles`.",
    "reset_prompt": "Для полного сброса сервера введите: Я знаю что я делаю или I know what I'm doing.",
}


def _parse_channel_ids(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(c).strip() for c in value if str(c).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _channel_ids_to_str(channel_ids):
    if not channel_ids:
        return ""
    return ", ".join(str(c) for c in channel_ids)


def get_guild_settings(economy_store, leveling_db, guild_id):
    gid = str(guild_id)
    econ = economy_store.guild_data(gid)

    try:
        command_channels = json.loads(leveling_db.get_setting(gid, "command_channels", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        command_channels = []

    rank_roles = leveling_db.get_rank_roles(gid)
    rank_roles_list = [
        {"level": str(level), "role": r_data["role_id"], "removeRole": r_data.get("remove_role_id")}
        for level, r_data in sorted(rank_roles.items())
    ]

    thread_channels = econ.get("thread_channel_ids") or []

    settings = {
        "newsChannelId": str(econ.get("news_channel_id") or ""),
        "treasureChannelId": str(econ.get("treasure_channel_id") or ""),
        "agitationChannelId": str(econ.get("agitation_channel_id") or ""),
        "commandChannelIds": _channel_ids_to_str(command_channels),
        "allowAllChannels": leveling_db.get_setting(gid, "allow_all_channels", "false") == "true",
        "threadChannelIds": _channel_ids_to_str(thread_channels),
        "levelupChannelId": str(leveling_db.get_setting(gid, "levelup_channel") or ""),
        "levelupDM": leveling_db.get_setting(gid, "levelup_dm", "false") == "true",
        "antifarmCooldown": int(leveling_db.get_setting(gid, "antifarm_cooldown", "60") or 60),
        "minMsgLength": int(leveling_db.get_setting(gid, "min_msg_length", "0") or 0),
        "xpMessages": int(leveling_db.get_setting(gid, "base_message_xp", "15") or 15),
        "xpVoice": int(leveling_db.get_setting(gid, "base_voice_xp", "10") or 10),
        "xpJobs": float(leveling_db.get_xp_rate(gid, "jobs")),
        "xpEvents": float(leveling_db.get_xp_rate(gid, "events")),
        "xpRateMessages": float(leveling_db.get_xp_rate(gid, "messages")),
        "xpRateVoice": float(leveling_db.get_xp_rate(gid, "voice")),
        "rankRoles": rank_roles_list,
        "welcomeEnabled": bool(econ.get("welcome_enabled")),
        "welcomeChannelId": str(econ.get("welcome_channel_id") or ""),
        "welcomeRoleId": str(econ.get("welcome_role_id") or ""),
        "welcomeMessage": econ.get("welcome_message") or DEFAULT_WELCOME_MESSAGE,
        "farewellEnabled": bool(econ.get("farewell_enabled")),
        "farewellMessage": econ.get("farewell_message") or DEFAULT_FAREWELL_MESSAGE,
        "logsChannelId": str(econ.get("logs_channel_id") or ""),
        "logJoin": econ.get("log_join", True) is not False,
        "logLeave": econ.get("log_leave", True) is not False,
        "logBan": econ.get("log_ban", True) is not False,
        "logDelete": bool(econ.get("log_delete")),
        "logEdit": bool(econ.get("log_edit")),
        "logVoice": bool(econ.get("log_voice")),
        "logCommands": bool(econ.get("log_commands")),
        "autoReactions": auto_reactions_for_dashboard(econ.get("auto_reactions")),
        "goldRate": float(econ.get("gold_rate") or 0),
        "cashEmoji": str(econ.get("cash_emoji") or "💵"),
        "goldEmoji": str(econ.get("gold_emoji") or "🪙"),
        "mapEmoji": str(econ.get("map_emoji") or "🗺️"),
        "statsEmoji": str(econ.get("stats_emoji") or "🤠"),
        "treasureDigEmoji": str(econ.get("treasure_dig_emoji") or "⛏️"),
        "treasureFoundEmoji": str(econ.get("treasure_found_emoji") or "💰"),
        "treasureExtraEmoji": str(econ.get("treasure_extra_emoji") or "✨"),
    }
    role_icons = econ.get("role_key_icons", {})
    if not isinstance(role_icons, dict):
        role_icons = {}
    custom_messages = econ.get("custom_messages", {})
    if not isinstance(custom_messages, dict):
        custom_messages = {}
    for field, db_field in EMOJI_FIELDS.items():
        settings[field] = str(econ.get(db_field) or settings.get(field) or "")
    for field, role_key in ROLE_ICON_FIELDS.items():
        settings[field] = str(role_icons.get(role_key) or "")
    for field, message_key in MESSAGE_FIELDS.items():
        settings[field] = str(
            custom_messages.get(message_key) or DEFAULT_CUSTOM_MESSAGES[message_key]
        )
    return settings


def set_guild_settings(economy_store, leveling_db, guild_id, data):
    gid = str(guild_id)
    econ = economy_store.guild_data(gid)

    if "newsChannelId" in data:
        val = str(data["newsChannelId"]).strip()
        econ["news_channel_id"] = int(val) if val.isdigit() else None

    if "treasureChannelId" in data:
        val = str(data["treasureChannelId"]).strip()
        econ["treasure_channel_id"] = int(val) if val.isdigit() else None

    if "agitationChannelId" in data:
        val = str(data["agitationChannelId"]).strip()
        econ["agitation_channel_id"] = int(val) if val.isdigit() else None

    if "threadChannelIds" in data:
        econ["thread_channel_ids"] = _parse_channel_ids(data["threadChannelIds"])

    if "welcomeEnabled" in data:
        econ["welcome_enabled"] = bool(data["welcomeEnabled"])
    if "welcomeChannelId" in data:
        val = str(data["welcomeChannelId"]).strip()
        econ["welcome_channel_id"] = int(val) if val.isdigit() else None
    if "welcomeRoleId" in data:
        val = str(data["welcomeRoleId"]).strip()
        econ["welcome_role_id"] = int(val) if val.isdigit() else None
    if "welcomeMessage" in data:
        econ["welcome_message"] = str(data["welcomeMessage"] or DEFAULT_WELCOME_MESSAGE)
    if "farewellEnabled" in data:
        econ["farewell_enabled"] = bool(data["farewellEnabled"])
    if "farewellMessage" in data:
        econ["farewell_message"] = str(data["farewellMessage"] or DEFAULT_FAREWELL_MESSAGE)

    if "logsChannelId" in data:
        val = str(data["logsChannelId"]).strip()
        econ["logs_channel_id"] = int(val) if val.isdigit() else None
    for key, field in [
        ("logJoin", "log_join"),
        ("logLeave", "log_leave"),
        ("logBan", "log_ban"),
        ("logDelete", "log_delete"),
        ("logEdit", "log_edit"),
        ("logVoice", "log_voice"),
        ("logCommands", "log_commands"),
    ]:
        if key in data:
            econ[field] = bool(data[key])

    if "autoReactions" in data:
        econ["auto_reactions"] = normalize_auto_reactions(data["autoReactions"])

    if "allowAllChannels" in data:
        leveling_db.set_setting(gid, "allow_all_channels", "true" if data["allowAllChannels"] else "false")

    if "commandChannelIds" in data:
        channels = _parse_channel_ids(data["commandChannelIds"])
        channel_ints = [int(c) for c in channels if c.isdigit()]
        leveling_db.set_setting(gid, "command_channels", json.dumps(channel_ints))

    if "levelupChannelId" in data:
        val = str(data["levelupChannelId"]).strip()
        if val.isdigit():
            leveling_db.set_setting(gid, "levelup_channel", val)
        else:
            leveling_db.set_setting(gid, "levelup_channel", "")

    if "levelupDM" in data:
        leveling_db.set_setting(gid, "levelup_dm", "true" if data["levelupDM"] else "false")

    if "antifarmCooldown" in data:
        leveling_db.set_setting(gid, "antifarm_cooldown", str(max(10, int(data["antifarmCooldown"]))))
    if "minMsgLength" in data:
        leveling_db.set_setting(gid, "min_msg_length", str(max(0, int(data["minMsgLength"]))))

    if "xpMessages" in data:
        leveling_db.set_setting(gid, "base_message_xp", str(max(0, int(data["xpMessages"]))))
    if "xpVoice" in data:
        leveling_db.set_setting(gid, "base_voice_xp", str(max(0, int(data["xpVoice"]))))

    for field, source in [("xpJobs", "jobs"), ("xpEvents", "events"), ("xpRateMessages", "messages"), ("xpRateVoice", "voice")]:
        if field in data:
            leveling_db.set_xp_rate(gid, source, max(0.0, float(data[field])))

    if "goldRate" in data:
        econ["gold_rate"] = max(50.0, float(data["goldRate"]))

    if "rankRoles" in data:
        existing = leveling_db.get_rank_roles(gid)
        for level in list(existing.keys()):
            leveling_db.remove_rank_role(gid, level)
        for entry in data["rankRoles"] or []:
            level = entry.get("level")
            role = str(entry.get("role", "")).strip()
            remove_role = str(entry.get("removeRole", "")).strip()
            if level and role.isdigit():
                leveling_db.set_rank_role(gid, int(level), role, remove_role if remove_role.isdigit() else None)

    for field, db_field in EMOJI_FIELDS.items():
        if field in data:
            val = str(data[field]).strip()
            if val:
                econ[db_field] = val

    role_icons = econ.setdefault("role_key_icons", {})
    for field, role_key in ROLE_ICON_FIELDS.items():
        if field in data:
            val = str(data[field]).strip()
            if val:
                role_icons[role_key] = val

    custom_messages = econ.setdefault("custom_messages", {})
    for field, message_key in MESSAGE_FIELDS.items():
        if field in data:
            val = str(data[field]).strip()
            if val:
                custom_messages[message_key] = val

    economy_store.save_all()
    return get_guild_settings(economy_store, leveling_db, gid)
