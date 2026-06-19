"""Discord OAuth и защищённый API настроек сервера."""
import json
import logging
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from functools import wraps

from flask import jsonify, redirect, request, session

import src.guild_config as guild_config

DISCORD_API = "https://discord.com/api"
DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "1513810717495525377")
MANAGE_GUILD = 0x20
ADMINISTRATOR = 0x8

_routes_registered = False


def _http_request(url, method="GET", data=None, headers=None, timeout=15):
    req_headers = dict(headers or {})
    # Discord API требует User-Agent, иначе банит запросы с серверов (403 Forbidden)
    req_headers.setdefault("User-Agent", "DiscordBot (https://pchev.me, 0.6.0)")
    
    body = None
    if data is not None:
        if isinstance(data, dict):
            body = urllib.parse.urlencode(data).encode()
            req_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        else:
            body = data
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _oauth_redirect_uri():
    return os.environ.get(
        "OAUTH_REDIRECT_URI",
        f"http://localhost:{os.environ.get('PORT', '8080')}/auth/discord/callback",
    )


def _can_manage_guild(permissions):
    perms = int(permissions)
    return bool(perms & ADMINISTRATOR) or bool(perms & MANAGE_GUILD)


def _get_leveling_db(get_leveling_db):
    db = get_leveling_db()
    if db is None:
        raise RuntimeError("Leveling module is not loaded")
    return db


def _user_guilds():
    return session.get("guilds") or []


def _user_can_access_guild(guild_id):
    gid = str(guild_id)
    for guild in _user_guilds():
        if str(guild.get("id")) == gid and guild.get("canManage"):
            return True
    return False


def _bot_in_guild(get_bot, guild_id):
    bot = get_bot()
    if bot is None:
        return False
    return any(str(g.id) == str(guild_id) for g in bot.guilds)


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return jsonify({"error": "Unauthorized", "login": "/auth/discord"}), 401
        return f(*args, **kwargs)
    return wrapper


def register_web_routes(app, get_bot, economy_store, get_leveling_db):
    global _routes_registered
    if _routes_registered:
        return
    _routes_registered = True

    secret = os.environ.get("FLASK_SECRET_KEY")
    if not secret:
        secret = secrets.token_hex(32)
        logging.warning("FLASK_SECRET_KEY not set — using a random session key (sessions won't survive restarts)")
    app.secret_key = secret

    @app.route("/auth/discord")
    def auth_discord():
        state = secrets.token_urlsafe(16)
        session["oauth_state"] = state
        params = urllib.parse.urlencode({
            "client_id": DISCORD_CLIENT_ID,
            "redirect_uri": _oauth_redirect_uri(),
            "response_type": "code",
            "scope": "identify guilds",
            "state": state,
        })
        return redirect(f"{DISCORD_API}/oauth2/authorize?{params}")

    @app.route("/auth/discord/callback")
    def auth_discord_callback():
        if request.args.get("error"):
            return redirect("/dashboard.html?error=oauth_denied")

        state = request.args.get("state")
        if not state or state != session.get("oauth_state"):
            return redirect("/dashboard.html?error=oauth_state")

        code = request.args.get("code")
        if not code:
            return redirect("/dashboard.html?error=oauth_code")

        client_secret = os.environ.get("DISCORD_CLIENT_SECRET", "")
        if not client_secret:
            return redirect("/dashboard.html?error=oauth_not_configured")

        try:
            token_data = _http_request(
                f"{DISCORD_API}/oauth2/token",
                method="POST",
                data={
                    "client_id": DISCORD_CLIENT_ID,
                    "client_secret": client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": _oauth_redirect_uri(),
                },
            )
        except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
            logging.error(f"OAuth token exchange failed: {e}")
            return redirect("/dashboard.html?error=oauth_token")

        access_token = token_data.get("access_token")
        if not access_token:
            return redirect("/dashboard.html?error=oauth_token")

        auth_header = {"Authorization": f"Bearer {access_token}"}
        try:
            user = _http_request(f"{DISCORD_API}/users/@me", headers=auth_header)
            guilds = _http_request(f"{DISCORD_API}/users/@me/guilds", headers=auth_header)
        except (urllib.error.URLError, json.JSONDecodeError) as e:
            logging.error(f"OAuth user fetch failed: {e}")
            return redirect("/dashboard.html?error=oauth_user")

        bot = get_bot()
        bot_guild_ids = {str(g.id) for g in bot.guilds} if bot else set()

        manageable = []
        for guild in guilds:
            can_manage = _can_manage_guild(guild.get("permissions", 0))
            if not can_manage:
                continue
            gid = str(guild["id"])
            icon = guild.get("icon")
            icon_url = None
            if icon:
                ext = "gif" if icon.startswith("a_") else "png"
                icon_url = f"https://cdn.discordapp.com/icons/{gid}/{icon}.{ext}"
            manageable.append({
                "id": gid,
                "name": guild.get("name", "Сервер"),
                "icon": icon_url,
                "canManage": True,
                "botPresent": gid in bot_guild_ids,
            })

        session["user"] = {
            "id": user.get("id"),
            "username": user.get("username"),
            "global_name": user.get("global_name") or user.get("username"),
            "avatar": user.get("avatar"),
        }
        session["guilds"] = manageable
        session.pop("oauth_state", None)
        return redirect("/dashboard.html")

    @app.route("/auth/logout", methods=["POST"])
    def auth_logout():
        session.clear()
        return jsonify({"status": "ok"})

    @app.route("/api/me")
    def api_me():
        user = session.get("user")
        if not user:
            return jsonify({"authenticated": False}), 401

        bot = get_bot()
        bot_guild_ids = {str(g.id) for g in bot.guilds} if bot else set()
        guilds = []
        for guild in _user_guilds():
            gid = str(guild.get("id"))
            guilds.append({
                **guild,
                "botPresent": gid in bot_guild_ids,
            })

        avatar_url = None
        if user.get("avatar"):
            avatar_url = f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png"

        return jsonify({
            "authenticated": True,
            "user": {**user, "avatar_url": avatar_url},
            "guilds": guilds,
            "clientId": DISCORD_CLIENT_ID,
            "inviteUrl": f"https://discord.com/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&scope=bot%20applications.commands&permissions=8",
        })

    @app.route("/api/guilds/<guild_id>/settings", methods=["GET"])
    @login_required
    def api_get_guild_settings(guild_id):
        if not _user_can_access_guild(guild_id):
            return jsonify({"error": "Forbidden"}), 403
        if not _bot_in_guild(get_bot, guild_id):
            return jsonify({"error": "Bot is not on this server", "botPresent": False}), 404

        db = _get_leveling_db(get_leveling_db)
        settings = guild_config.get_guild_settings(economy_store, db, guild_id)
        return jsonify(settings)

    @app.route("/api/guilds/<guild_id>/settings", methods=["PUT", "POST"])
    @login_required
    def api_set_guild_settings(guild_id):
        if not _user_can_access_guild(guild_id):
            return jsonify({"error": "Forbidden"}), 403
        if not _bot_in_guild(get_bot, guild_id):
            return jsonify({"error": "Bot is not on this server", "botPresent": False}), 404

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "No data"}), 400

        db = _get_leveling_db(get_leveling_db)
        old_settings = guild_config.get_guild_settings(economy_store, db, guild_id)

        try:
            settings = guild_config.set_guild_settings(economy_store, db, guild_id, data)
        except (ValueError, TypeError) as e:
            return jsonify({"error": str(e)}), 400

        bot = get_bot()
        if bot and getattr(bot, "loop", None):
            import asyncio
            guild = bot.get_guild(int(guild_id))
            if guild:
                channel_map = {
                    "newsChannelId": "публикации анонсов и новостей",
                    "treasureChannelId": "ежедневной раздачи карт сокровищ",
                    "levelupChannelId": "уведомлений о повышении уровня",
                    "welcomeChannelId": "приветствий новых участников",
                    "logsChannelId": "записи серверных логов",
                }
                for key, purpose in channel_map.items():
                    if key in data:
                        old_val = str(old_settings.get(key) or "")
                        new_val = str(settings.get(key) or "")
                        if new_val and new_val != old_val and new_val.isdigit():
                            channel = guild.get_channel(int(new_val))
                            if channel:
                                asyncio.run_coroutine_threadsafe(
                                    channel.send(f"✅ Этот канал теперь используется для **{purpose}**."),
                                    bot.loop
                                )

        return jsonify({"status": "ok", "settings": settings})

    @app.route("/api/guilds/<guild_id>/roles", methods=["GET"])
    @login_required
    def api_guild_roles(guild_id):
        if not _user_can_access_guild(guild_id):
            return jsonify({"error": "Forbidden"}), 403
            
        bot = get_bot()
        if not bot:
            return jsonify({"error": "Bot offline"}), 503
            
        guild = bot.get_guild(int(guild_id))
        if not guild:
            return jsonify({"error": "Guild not found"}), 404
            
        roles = []
        for r in guild.roles:
            # Пропускаем роль @everyone (у нее ID совпадает с ID сервера)
            if r.id == guild.id:
                continue
                
            color_hex = str(r.color)
            if color_hex == "#000000":
                color_hex = "#99aab5" # Дефолтный цвет Discord
                
            roles.append({
                "id": str(r.id),
                "name": r.name,
                "color": color_hex,
                "position": r.position
            })
            
        # Сортируем от самых высоких ролей к самым низким
        roles.sort(key=lambda x: x["position"], reverse=True)
        return jsonify(roles)

    @app.route("/api/guilds/<guild_id>/emojis", methods=["GET"])
    @login_required
    def api_guild_emojis(guild_id):
        if not _user_can_access_guild(guild_id):
            return jsonify({"error": "Forbidden"}), 403
            
        bot = get_bot()
        if not bot:
            return jsonify({"error": "Bot offline"}), 503
            
        guild = bot.get_guild(int(guild_id))
        if not guild:
            return jsonify({"error": "Guild not found"}), 404
            
        emojis = []
        for e in guild.emojis:
            emojis.append({
                "id": str(e.id),
                "name": e.name,
                "url": str(e.url),
                "animated": e.animated,
                "format": f"<a:{e.name}:{e.id}>" if e.animated else f"<:{e.name}:{e.id}>"
            })
            
        return jsonify(emojis)

    @app.route("/api/guilds/<guild_id>/channels", methods=["GET"])
    @login_required
    def api_guild_channels(guild_id):
        if not _user_can_access_guild(guild_id):
            return jsonify({"error": "Forbidden"}), 403
            
        bot = get_bot()
        if not bot:
            return jsonify({"error": "Bot offline"}), 503
            
        guild = bot.get_guild(int(guild_id))
        if not guild:
            return jsonify({"error": "Guild not found"}), 404
            
        channels = []
        for c in guild.text_channels:
            channels.append({
                "id": str(c.id),
                "name": c.name,
                "position": c.position
            })
            
        channels.sort(key=lambda x: x["position"])
        return jsonify(channels)

    @app.route("/api/guilds/<guild_id>/stats", methods=["GET"])
    @login_required
    def api_guild_stats(guild_id):
        if not _user_can_access_guild(guild_id):
            return jsonify({"error": "Forbidden"}), 403
            
        bot = get_bot()
        if not bot:
            return jsonify({"error": "Bot offline"}), 503
            
        guild_data = economy_store.guild_data(guild_id)
        users = guild_data.get("users", {})
        gangs = guild_data.get("gangs", {})
        gold_rate = guild_data.get("gold_rate", 543.45)
        
        # 1. Leaderboard
        user_list = []
        total_cash = 0.0
        total_gold = 0.0
        
        for u_id, u_data in users.items():
            c = float(u_data.get("cash", 0.0))
            g = float(u_data.get("gold", 0.0))
            total_cash += c
            total_gold += g
            wealth = c + (g * gold_rate)
            
            # Try to resolve username if possible, otherwise use ID
            name = f"User {u_id}"
            user_obj = bot.get_user(int(u_id))
            if user_obj:
                name = user_obj.display_name
            elif "name" in u_data:
                name = u_data["name"]
                
            user_list.append({
                "id": u_id,
                "name": name,
                "cash": c,
                "gold": g,
                "wealth": wealth,
                "level": u_data.get("level", 1)
            })
            
        user_list.sort(key=lambda x: x["wealth"], reverse=True)
        top_10 = user_list[:10]
        
        # 2. Gangs
        gang_list = []
        for g_name, g_data in gangs.items():
            gc = float(g_data.get("cash", 0.0))
            gg = float(g_data.get("gold", 0.0))
            g_wealth = gc + (gg * gold_rate)
            total_cash += gc
            total_gold += gg
            
            gang_list.append({
                "name": g_name,
                "id": g_data.get("id", 0),
                "members_count": len(g_data.get("members", [])),
                "cash": gc,
                "gold": gg,
                "wealth": g_wealth,
                "influence": g_data.get("influence", 0)
            })
            
        gang_list.sort(key=lambda x: x["wealth"], reverse=True)
        
        return jsonify({
            "leaderboard": top_10,
            "gangs": gang_list,
            "globals": {
                "total_users": len(users),
                "total_gangs": len(gangs),
                "total_cash": total_cash,
                "total_gold": total_gold,
                "gold_rate": gold_rate
            }
        })

    @app.route("/api/config", methods=["GET"])
    def legacy_get_config():
        return jsonify({
            "error": "Deprecated. Log in via Discord and use /api/guilds/<guild_id>/settings",
            "login": "/auth/discord",
        }), 410

    @app.route("/api/config", methods=["POST"])
    def legacy_post_config():
        return jsonify({
            "error": "Deprecated. Log in via Discord and use /api/guilds/<guild_id>/settings",
            "login": "/auth/discord",
        }), 410
