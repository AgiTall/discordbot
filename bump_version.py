import re
import sys
import os
import json

def get_current_version():
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
            # Remove leading 'v' if present
            v = cfg.get("version", "v0.5.8.1")
            return v.lstrip("v")
    except Exception:
        return "0.5.8.1"

def set_version(new_version):
    current_version = get_current_version()
    print(f"Текущая версия: {current_version}")
    print(f"Новая версия: {new_version}")

    # Список файлов для обновления (добавлен dashboard.html, так как он есть в корне)
    files_to_update = [
        "src/web_routes.py",
        "docs/commands.html",
        "docs/dashboard.html",
        "docs/index.html",
        "docs/levels.html",
        "dashboard.html",
        "config.json"
    ]

    for filepath in files_to_update:
        if not os.path.exists(filepath):
            print(f"Файл {filepath} не найден, пропускаем...")
            continue
            
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Простая замена старой версии на новую по всему файлу
        content = content.replace(f"v{current_version}", f"v{new_version}")
        content = content.replace(current_version, new_version)
            
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
            
        print(f"Обновлен файл: {filepath}")

    print(f"Успех! Версия изменена с {current_version} на {new_version} везде.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python bump_version.py <новая_версия>")
        print("Например: python bump_version.py 0.5.9")
        sys.exit(1)
        
    new_version = sys.argv[1]
    # Remove leading 'v' if user typed it
    new_version = new_version.lstrip("v")
    set_version(new_version)
