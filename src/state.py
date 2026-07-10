"""
src/state.py
Единая точка хранения изменяемых глобальных переменных бота.
Все модули импортируют отсюда, чтобы не было циклических зависимостей
и чтобы избавиться от хака _inject_missing_globals().
"""

# Инициализируются в bot.py после создания объектов
bot = None
economy_data = None
economy_lock = None
active_channels = None
