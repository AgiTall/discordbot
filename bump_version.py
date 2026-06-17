import re
import sys
import os

FILES_TO_UPDATE = [
    "bot.py",
    "src/web_routes.py",
    "docs/commands.html",
    "docs/dashboard.html",
    "docs/index.html",
    "docs/levels.html"
]

def bump_version(bump_type="patch"):
    # Читаем текущую версию из bot.py (или config.json если есть)
    bot_code = ""
    try:
        with open("bot.py", "r", encoding="utf-8") as f:
            bot_code = f.read()
    except Exception:
        pass

    match = re.search(r'BOT_VERSION = "v(\d+)\.(\d+)\.(\d+)"', bot_code)
    if not match:
        print("Ошибка: Не удалось найти BOT_VERSION в bot.py")
        return
        
    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    current_version = f"{major}.{minor}.{patch}"
    print(f"Текущая версия: {current_version}")

    # Вычисляем новую версию
    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        print("Неизвестный тип обновления. Используйте: major, minor или patch.")
        return

    new_version = f"{major}.{minor}.{patch}"
    print(f"Новая версия: {new_version}")
    
    # Регулярные выражения для каждого файла
    patterns = {
        "bot.py": (rf'BOT_VERSION = "v{current_version}"', f'BOT_VERSION = "v{new_version}"'),
        "src/web_routes.py": (rf'0\.5\.\d+', new_version),  # Обновляем версию в User-Agent
        "docs/commands.html": (rf'v{current_version}', f'v{new_version}'),
        "docs/dashboard.html": (rf'v{current_version}', f'v{new_version}'),
        "docs/index.html": (rf'v{current_version}', f'v{new_version}'),
        "docs/levels.html": (rf'v{current_version}', f'v{new_version}')
    }

    # Заменяем версию во всех файлах
    for filepath in FILES_TO_UPDATE:
        if not os.path.exists(filepath):
            print(f"Файл {filepath} не найден, пропускаем...")
            continue
            
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        if filepath == "src/web_routes.py":
            # В web_routes.py мы ищем именно строку User-Agent
            content = re.sub(rf'pchev\.me, {current_version}', f'pchev.me, {new_version}', content)
        else:
            old_str, new_str = patterns[filepath]
            content = content.replace(old_str, new_str)
            
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
            
        print(f"Обновлен файл: {filepath}")

    print(f"Успех! Все файлы обновлены до версии {new_version}")

    # Обновляем config.json version
    try:
        import json
        cfg_path = "config.json"
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        else:
            cfg = {}
        cfg["version"] = f"v{new_version}"
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print("Обновлено config.json")
    except Exception as e:
        print(f"Не удалось обновить config.json: {e}")

if __name__ == "__main__":
    b_type = sys.argv[1].lower() if len(sys.argv) > 1 else "patch"
    bump_version(b_type)
