"""Единое интерактивное меню профессии «Коллекционер»."""

import math
import os
import random
import discord
from discord import app_commands
from discord.ext import commands

from src.collector_logic import *
from src.role_utils import has_game_role

COLLECTOR_IMAGE_FILE = "assets/images/collector.png"
COLLECTOR_IMAGE_NAME = "collector.png"
COLLECTOR_EMOJI = "<:collector:1513992804672602356>"
SHOVEL_EMOJI = "<:shovel:1518547808012079114>"
DETECTOR_EMOJI = "<:weapon_kit_metal_detector:1527574659636400138>"
MAP_EMOJI = "<:folder_maps:1527626199025844274>"


async def get_emoji_map(bot):
    cached = getattr(bot, "_collector_emojis", None)
    if cached is None:
        try:
            cached = {emoji.name: str(emoji) for emoji in await bot.fetch_application_emojis()}
        except Exception:
            cached = {}
        bot._collector_emojis = cached
    return cached


def collector_image():
    if not os.path.exists(COLLECTOR_IMAGE_FILE):
        return None
    return discord.File(COLLECTOR_IMAGE_FILE, filename=COLLECTOR_IMAGE_NAME)


def with_background(embed):
    if os.path.exists(COLLECTOR_IMAGE_FILE):
        embed.set_image(url=f"attachment://{COLLECTOR_IMAGE_NAME}")
    return embed


def main_embed(account, note=None):
    data = normalize_collector_data(account.get("collector"))
    unique = sum(progress(data, key)[0] for key in COLLECTIONS)
    total = sum(len(items) for items in COLLECTION_ITEMS.values())
    shovel = f"{SHOVEL_EMOJI} куплена" if data["tools"]["shovel"] else f"{SHOVEL_EMOJI} не куплена"
    detector = f"{DETECTOR_EMOJI} куплен" if data["tools"]["detector"] else f"{DETECTOR_EMOJI} не куплен"
    text = (
        f"**Уровень:** {data['level']} · опыт {data['xp']}/{data['level'] * 100}\n"
        f"**Находки:** {total_items(data)} · уникальных {unique}/{total}\n"
        f"**Продано наборов:** {data['sets_sold']}\n\n"
        f"**Инструменты**\n└─ {shovel}\n└─ {detector}\n\n"
        "Купите карту нужной коллекции, выберите одну из трёх точек поиска, "
        "а найденные предметы продавайте поштучно или полным набором."
    )
    if note:
        text = f"{note}\n\n{text}"
    return with_background(discord.Embed(title=f"{COLLECTOR_EMOJI} Коллекционер", description=text, color=discord.Color.gold()))


def list_embed(data):
    lines = []
    for key, rule in COLLECTIONS.items():
        owned, total = progress(data, key)
        requirements = f"с {rule['level']} ур."
        lines.append(f"**{rule['name']}** — {owned}/{total}\n└─ {requirements} · комплект ${rule['payout']}")
    return with_background(discord.Embed(title="Коллекционные наборы", description="\n".join(lines), color=discord.Color.gold()))


def collection_options(action):
    options = []
    for key, rule in COLLECTIONS.items():
        description = f"С {rule['level']} уровня · {len(COLLECTION_ITEMS[key])} предметов"
        if action == "sell":
            description = f"Комплект: ${rule['payout']}"
        options.append(discord.SelectOption(label=rule["name"], value=key, description=description))
    return options


class CollectorView(discord.ui.View):
    def __init__(self, bot, owner_id, timeout=600):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.owner_id = owner_id

    async def interaction_check(self, interaction):
        self.bot.set_economy_guild_id(interaction.guild_id)
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Это меню коллекционера открыто не для вас.", ephemeral=True)
            return False
        return True

    async def show_main(self, interaction, note=None):
        async with self.bot.economy_lock:
            account = self.bot.get_account(interaction.user.id)
            account["collector"] = normalize_collector_data(account.get("collector"))
            self.bot.save_economy()
            embed = main_embed(account, note)
        await interaction.response.edit_message(embed=embed, view=CollectorMainView(self.bot, self.owner_id))


class CollectorMainView(CollectorView):
    @discord.ui.button(label="Искать", emoji="🔎", style=discord.ButtonStyle.primary, row=0)
    async def find_button(self, interaction, button):
        async with self.bot.economy_lock:
            account=self.bot.get_account(interaction.user.id); data=normalize_collector_data(account.get("collector")); account["collector"]=data; self.bot.save_economy()
        maps="\n".join(f"└─ {rule['name']}: **{data['maps'].get(key,0)}**" for key,rule in COLLECTIONS.items())
        embed = with_background(discord.Embed(title="Поиск коллекций", description=f"{MAP_EMOJI} Выберите карту коллекции. Одна карта расходуется на три точки поиска.\n\n**Ваши карты**\n{maps}", color=discord.Color.gold()))
        await interaction.response.edit_message(embed=embed, view=CollectorSelectView(self.bot, self.owner_id, "search"))

    @discord.ui.button(label="Продать", emoji="💰", style=discord.ButtonStyle.success, row=0)
    async def sell_button(self, interaction, button):
        embed = with_background(discord.Embed(title="Продажа коллекций", description="Выберите коллекцию: дальше можно продать все её предметы поштучно либо один полный набор.", color=discord.Color.gold()))
        await interaction.response.edit_message(embed=embed, view=CollectorSelectView(self.bot, self.owner_id, "sell"))

    @discord.ui.button(label="Магазин", emoji="🛒", style=discord.ButtonStyle.secondary, row=0)
    async def shop_button(self, interaction, button):
        async with self.bot.economy_lock:
            account = self.bot.get_account(interaction.user.id)
            data = normalize_collector_data(account.get("collector")); account["collector"] = data
            self.bot.save_economy()
        text = f"{SHOVEL_EMOJI} **Лопата** — $35\n{DETECTOR_EMOJI} **Металлоискатель** — $250\n\n{MAP_EMOJI} **Карты коллекций**\n└─ Каждая карта открывает раскопки с тремя точками."
        await interaction.response.edit_message(embed=with_background(discord.Embed(title="Магазин коллекционера", description=text, color=discord.Color.gold())), view=CollectorShopView(self.bot, self.owner_id, data))


class CollectionSelect(discord.ui.Select):
    def __init__(self, bot, action):
        self.bot = bot; self.action = action
        placeholders = {"search": "Какую карту использовать?", "sell": "Что продавать?"}
        super().__init__(placeholder=placeholders[action], options=collection_options(action))

    async def callback(self, interaction):
        key = self.values[0]
        async with self.bot.economy_lock:
            account = self.bot.get_account(interaction.user.id)
            data = normalize_collector_data(account.get("collector")); account["collector"] = data
            if self.action == "search":
                result = begin_search(data, key)
                self.bot.save_economy()
                if result.get("error") == "level": note = f"Для этой карты нужен **{result['required']} уровень**."
                elif result.get("error") == "tools": note = "Не хватает: **" + ", ".join("лопаты" if x == "shovel" else "металлоискателя" for x in result["missing"]) + "**."
                elif result.get("error") == "map": note = f"Нет карты **{COLLECTIONS[key]['name']}**. Купите её в магазине."
                else:
                    remaining=data["maps"].get(key,0)
                    embed=with_background(discord.Embed(title=f"{MAP_EMOJI} {COLLECTIONS[key]['name']}", description=f"На карте отмечены три возможные точки. У вас две попытки.\nКарт этого вида осталось: **{remaining}**.", color=discord.Color.gold()))
                    view=CollectorHuntView(self.bot, interaction.user.id, key)
                    await interaction.response.edit_message(embed=embed,view=view); return
                embed=main_embed(account,note); view=CollectorMainView(self.bot,interaction.user.id)
            else:
                self.bot.save_economy(); owned,total=progress(data,key); count=sum(data["inventory"].get(x,0) for x in COLLECTION_ITEMS[key])
                unit=max(1,COLLECTIONS[key]["payout"]//total//2)
                embed=with_background(discord.Embed(title=f"Продать: {COLLECTIONS[key]['name']}", description=f"Уникальных: **{owned}/{total}** · всего предметов: **{count}**\n\nПоштучная цена: **${unit}**\nПолный набор: **${COLLECTIONS[key]['payout']}**", color=discord.Color.gold()))
                view=CollectorSellView(self.bot,interaction.user.id,key)
        await interaction.response.edit_message(embed=embed, view=view)


class CollectorSelectView(CollectorView):
    def __init__(self, bot, owner_id, action):
        super().__init__(bot, owner_id); self.add_item(CollectionSelect(bot, action))
    @discord.ui.button(label="Назад", emoji="↩️", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction, button): await self.show_main(interaction)


class CollectorPages(CollectorView):
    def __init__(self, bot, owner_id, key, rows):
        super().__init__(bot, owner_id); self.key=key; self.rows=rows; self.page=0
    def embed(self):
        pages=max(1, math.ceil(len(self.rows)/12)); part=self.rows[self.page*12:(self.page+1)*12]
        embed=discord.Embed(title=COLLECTIONS[self.key]["name"], description="\n".join(part), color=discord.Color.gold())
        embed.set_footer(text=f"Страница {self.page+1}/{pages}"); return with_background(embed)
    @discord.ui.button(label="Назад", emoji="◀️", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction, button): self.page=max(0,self.page-1); await interaction.response.edit_message(embed=self.embed(),view=self)
    @discord.ui.button(label="Дальше", emoji="▶️", style=discord.ButtonStyle.secondary)
    async def nxt(self, interaction, button): self.page=min(max(0,math.ceil(len(self.rows)/12)-1),self.page+1); await interaction.response.edit_message(embed=self.embed(),view=self)
    @discord.ui.button(label="В меню", emoji="↩️", style=discord.ButtonStyle.primary)
    async def menu(self, interaction, button): await self.show_main(interaction)


class CollectorSellView(CollectorView):
    def __init__(self, bot, owner_id, key):
        super().__init__(bot,owner_id); self.key=key
    async def finish(self,interaction,kind):
        async with self.bot.economy_lock:
            account=self.bot.get_account(interaction.user.id); data=normalize_collector_data(account.get("collector")); account["collector"]=data
            if kind=="set":
                reward=sell_set(data,self.key); count=len(COLLECTION_ITEMS[self.key]) if reward else 0
                note=f"Полный набор продан за **${reward}**." if reward else "Полный набор ещё не собран."
            else:
                count,reward=sell_individual_items(data,self.key)
                note=f"Поштучно продано предметов: **{count}**, получено **${reward}**."
            account["cash"]+=reward; self.bot.save_economy(); embed=main_embed(account,note)
        await interaction.response.edit_message(embed=embed,view=CollectorMainView(self.bot,self.owner_id))
    @discord.ui.button(label="Продать поштучно",emoji="🪙",style=discord.ButtonStyle.success)
    async def singles(self,interaction,button): await self.finish(interaction,"singles")
    @discord.ui.button(label="Продать полный набор",emoji="💰",style=discord.ButtonStyle.success)
    async def full_set(self,interaction,button): await self.finish(interaction,"set")
    @discord.ui.button(label="Назад",emoji="↩️",style=discord.ButtonStyle.secondary)
    async def back(self,interaction,button): await self.show_main(interaction)


class CollectorHuntView(CollectorView):
    def __init__(self,bot,owner_id,key):
        super().__init__(bot,owner_id,timeout=120); self.key=key; self.target=random.randrange(3); self.attempts=0; self.done=False
        for index in range(3): self.add_item(CollectorDigButton(index))
    async def dig(self,interaction,button):
        if self.done or button.disabled: return await interaction.response.send_message("Эта точка уже проверена.",ephemeral=True)
        self.attempts+=1; button.disabled=True
        if button.index==self.target:
            self.done=True
            async with self.bot.economy_lock:
                account=self.bot.get_account(interaction.user.id); data=normalize_collector_data(account.get("collector")); account["collector"]=data
                result=grant_find(data,self.key); self.bot.save_economy(); emojis=await get_emoji_map(self.bot); item=result["item"]
                note=f"{emojis.get(emoji_name(item),'🔎')} Найдено: **{item_display_name(item)}** · в сумке {result['quantity']} · +{result['xp']} XP."
                if result["levels"]: note+=f"\nНовый уровень: **{data['level']}**!"
                embed=main_embed(account,note)
            for child in self.children: child.disabled=True
            return await interaction.response.edit_message(embed=embed,view=CollectorMainView(self.bot,self.owner_id))
        button.style=discord.ButtonStyle.danger
        if self.attempts>=2:
            self.done=True
            for child in self.children: child.disabled=True
            self.children[self.target].style=discord.ButtonStyle.success
            embed=with_background(discord.Embed(title="Находка ускользнула",description="Две точки оказались пустыми. Карта израсходована, а место находки отмечено зелёным.",color=discord.Color.dark_red()))
            return await interaction.response.edit_message(embed=embed,view=self)
        embed=with_background(discord.Embed(title="Пустая точка",description="Здесь ничего нет. Осталась ещё одна попытка.",color=discord.Color.gold()))
        await interaction.response.edit_message(embed=embed,view=self)


class CollectorDigButton(discord.ui.Button):
    def __init__(self,index):
        super().__init__(label=f"Точка {index+1}",emoji="⛏️",style=discord.ButtonStyle.secondary); self.index=index
    async def callback(self,interaction): await self.view.dig(interaction,self)


class MapShopSelect(discord.ui.Select):
    def __init__(self,bot):
        self.bot=bot
        options=[discord.SelectOption(label=rule["name"],value=key,description=f"Карта ${rule['map_price']} · с {rule['level']} уровня",emoji=discord.PartialEmoji.from_str(MAP_EMOJI)) for key,rule in COLLECTIONS.items()]
        super().__init__(placeholder="Купить карту коллекции",options=options)
    async def callback(self,interaction):
        key=self.values[0]; price=COLLECTIONS[key]["map_price"]
        async with self.bot.economy_lock:
            account=self.bot.get_account(interaction.user.id); data=normalize_collector_data(account.get("collector")); account["collector"]=data
            if data["level"]<COLLECTIONS[key]["level"]: note=f"Карта откроется с **{COLLECTIONS[key]['level']} уровня**."
            elif account["cash"]<price: note=f"Не хватает денег: карта стоит **${price}**."
            else: account["cash"]-=price; data["maps"][key]+=1; note=f"{MAP_EMOJI} Куплена карта **{COLLECTIONS[key]['name']}**. Теперь их: **{data['maps'][key]}**."
            self.bot.save_economy(); embed=main_embed(account,note)
        await interaction.response.edit_message(embed=embed,view=CollectorMainView(self.bot,interaction.user.id))


class CollectorShopView(CollectorView):
    def __init__(self, bot, owner_id, data):
        super().__init__(bot, owner_id)
        self.buy_shovel.disabled = data["tools"]["shovel"]
        self.buy_detector.disabled = data["tools"]["detector"]
        self.add_item(MapShopSelect(bot))
    async def buy(self, interaction, tool, price):
        async with self.bot.economy_lock:
            account=self.bot.get_account(interaction.user.id); data=normalize_collector_data(account.get("collector")); account["collector"]=data
            if data["tools"][tool]: note="Этот инструмент уже куплен."
            elif account["cash"] < price: note=f"Не хватает денег: нужно **${price:.0f}**."
            else: account["cash"]-=price; data["tools"][tool]=True; note="Инструмент куплен."
            self.bot.save_economy(); embed=main_embed(account,note)
        await interaction.response.edit_message(embed=embed,view=CollectorMainView(self.bot,self.owner_id))
    @discord.ui.button(label="Купить лопату · $35", emoji=SHOVEL_EMOJI, style=discord.ButtonStyle.success)
    async def buy_shovel(self, interaction, button): await self.buy(interaction,"shovel",SHOVEL_PRICE)
    @discord.ui.button(label="Купить металлоискатель · $250", emoji=DETECTOR_EMOJI, style=discord.ButtonStyle.success)
    async def buy_detector(self, interaction, button): await self.buy(interaction,"detector",DETECTOR_PRICE)
    @discord.ui.button(label="Назад", emoji="↩️", style=discord.ButtonStyle.secondary)
    async def back(self, interaction, button): await self.show_main(interaction)


class CollectorCog(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @app_commands.command(name="collector", description="Коллекционер: поиск, наборы и инструменты")
    async def collector(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
        token = self.bot.set_economy_guild_id(interaction.guild_id)
        try:
            async with self.bot.economy_lock:
                account=self.bot.get_account(interaction.user.id)
                if not has_game_role(interaction.user, COLLECTOR_ROLE_KEY, account):
                    self.bot.save_economy(); return await interaction.response.send_message("Нужна роль **Коллекционер** из `/roles`.", ephemeral=True)
                account["collector"]=normalize_collector_data(account.get("collector")); self.bot.save_economy(); embed=main_embed(account)
        finally:
            self.bot.reset_economy_guild_id(token)
        image=collector_image(); kwargs={"embed":embed,"view":CollectorMainView(self.bot,interaction.user.id),"ephemeral":True}
        if image: kwargs["file"]=image
        await interaction.response.send_message(**kwargs)


async def setup(bot):
    await bot.add_cog(CollectorCog(bot))
