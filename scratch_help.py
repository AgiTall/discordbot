def build_help_pages(is_admin):
    pages = {}

    # 1. Overview
    overview = discord.Embed(
        title="Справка бота",
        description=(
            "Добро пожаловать на Дикий Запад! Бот предоставляет систему экономики, "
            "профессий, банд, а также мини-игры и торговлю.\n\n"
            "Используйте выпадающее меню ниже, чтобы выбрать нужную категорию команд."
        ),
        color=discord.Color.gold(),
    )
    overview.add_field(
        name="Быстрый старт",
        value=(
            "`/balance`, `/work`, `/roles`, `/gang-info`, `/bounty`, `/naturalist`"
        ),
        inline=False,
    )
    pages["overview"] = {
        "label": "Обзор",
        "description": "Главная страница справки",
        "emoji": "📖",
        "embed": overview
    }

    # 2. Economy
    economy = discord.Embed(
        title="Справка: Экономика и Действия",
        description="Основные команды для заработка и траты денег.",
        color=discord.Color.gold(),
    )
    economy.add_field(
        name="Деньги и Золото",
        value=(
            "`/balance` — показать ваш баланс, карты, повозку и витрину.\n"
            "`/work` — заработать деньги (кулдаун 2 часа).\n"
            "`/gold-rate` — показать текущий курс золота.\n"
            "`/buy-gold` / `/sell-gold` — обмен валюты.\n"
            "`/deposit` / `/withdraw` — управление вкладом в банке."
        ),
        inline=False,
    )
    economy.add_field(
        name="Магазин и Взаимодействия",
        value=(
            "`/catalog` — открыть каталог товаров Wheeler, Rawson & Co.\n"
            "`/safe-money` / `/safe-take-money` — использование личного сейфа.\n"
            "`/rob` — ограбить другого игрока (риск штрафа, кулдаун 2 часа).\n"
            "`/send` — отправить личное сообщение через бота."
        ),
        inline=False,
    )
    pages["economy"] = {
        "label": "Экономика и Действия",
        "description": "Баланс, работа, магазин, банк и ограбления",
        "emoji": "💰",
        "embed": economy
    }

    # 3. Roles
    roles = discord.Embed(
        title="Справка: Роли и Профессии",
        description="Команды профессий и заработка.",
        color=discord.Color.gold(),
    )
    roles.add_field(
        name="Доступные профессии",
        value=(
            "`/roles` — список профессий с описаниями и кнопками покупки.\n"
            "`/dealer` / `/dealer-delivery` — заполнение и доставка повозки торговца.\n"
            "`/moonshine` — варка и продажа самогона, прокачка аппарата.\n"
            "`/bounty` / `/bounty-leaderboard` — охота за головами и доска почета.\n"
            "`/naturalist` — справочник животных и сбор образцов."
        ),
        inline=False,
    )
    roles.add_field(
        name="Карты сокровищ",
        value=(
            "`/excavation` — потратить карту и попытаться найти клад.\n"
            "Карты выдаются во время ежедневных ивентов."
        ),
        inline=False,
    )
    pages["roles"] = {
        "label": "Роли и Профессии",
        "description": "Торговец, Самогонщик, Охотник, Натуралист",
        "emoji": "🤠",
        "embed": roles
    }

    # 4. Gangs
    gangs = discord.Embed(
        title="Справка: Банды",
        description="Объединяйтесь с другими игроками в банды.",
        color=discord.Color.gold(),
    )
    gangs.add_field(
        name="Управление бандой",
        value=(
            "`/gang-create` — создать банду (цена: 50 золота).\n"
            "`/gang-info` — статистика банды и состав участников.\n"
            "`/gang-invite` / `/gang-join` / `/gang-leave` — приглашение и выход.\n"
            "`/gang-kick` — выгнать участника.\n"
            "`/gang-transfer` — передать лидерство.\n"
            "`/gang-set-roles` — настроить названия ролей в банде."
        ),
        inline=False,
    )
    gangs.add_field(
        name="Общак и Войны",
        value=(
            "`/gang-deposit` / `/gang-withdraw` — пополнение и снятие денег из общака.\n"
            "`/gang-rob` — ограбить общак чужой банды."
        ),
        inline=False,
    )
    pages["gangs"] = {
        "label": "Банды",
        "description": "Создание банд, общак, войны и управление",
        "emoji": "🔫",
        "embed": gangs
    }

    # 5. Games
    games = discord.Embed(
        title="Справка: Игры",
        description="Испытайте удачу в казино.",
        color=discord.Color.gold(),
    )
    games.add_field(
        name="Доступные игры",
        value=(
            "`/dice bet` — кости против бота.\n"
            "`/poker bet` — 5-карточный покер с заменой карт.\n"
            "`/blackjack` — блэкджек с дилером."
        ),
        inline=False,
    )
    pages["games"] = {
        "label": "Игры",
        "description": "Кости, покер, блэкджек",
        "emoji": "🎲",
        "embed": games
    }

    # 6. Admin
    admin = discord.Embed(
        title="Справка: Админ-команды",
        description="Команды управления сервером и экономикой.",
        color=discord.Color.gold(),
    )
    if is_admin:
        admin.add_field(
            name="Основные",
            value="`/check`, `/give-money`, `/remove-money`, `/set-money`, `/give-gold` и т.д.",
            inline=False,
        )
        admin.add_field(
            name="Профессии",
            value="`/fill-dealer`, `/give-moonshine-ingredient`, `/set-moonshine-upgrade`, `/set-moonshine-skill`, `/finish-moonshine`, `/reset-moonshine`",
            inline=False,
        )
        admin.add_field(
            name="Настройки и ивенты",
            value="`/treasure-event`, `/set-agitation-channel`, `/set-discount-shop`, `/set-rate`, `/set-emoji`, `/set-message`, `/set-icon-roles`, `/set-discounts-roles`",
            inline=False,
        )
    else:
        admin.add_field(
            name="Недоступно",
            value="У вас нет прав администратора для просмотра этих команд.",
            inline=False,
        )
    pages["admin"] = {
        "label": "Админ-команды",
        "description": "Настройки и управление ботом",
        "emoji": "⚙️",
        "embed": admin
    }

    # Add banner to all pages if exists
    for key, data in pages.items():
        if os.path.exists(TREASURE_BANNER_FILE):
            data["embed"].set_image(url=f"attachment://{TREASURE_BANNER_FILE}")

    return pages


class HelpCategorySelect(discord.ui.Select):
    def __init__(self, pages):
        self.pages = pages
        options = []
        for key, data in pages.items():
            options.append(
                discord.SelectOption(
                    label=data["label"],
                    description=data["description"],
                    emoji=data["emoji"],
                    value=key
                )
            )
        super().__init__(placeholder="Выберите категорию команд...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_key = self.values[0]
        selected_page = self.pages[selected_key]["embed"]
        await interaction.response.edit_message(embed=selected_page, view=self.view)


class HelpView(discord.ui.View):
    def __init__(self, pages):
        super().__init__(timeout=600)
        self.pages = pages
        self.add_item(HelpCategorySelect(pages))
