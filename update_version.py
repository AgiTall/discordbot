import json
import os
import re
import glob

VERSION_FILE = "VERSION"
CONFIG_PATH = "config.json"


def update_version():
    # ── Читаем версию из файла VERSION ───────────────────────
    if not os.path.exists(VERSION_FILE):
        print(f"❌ Файл {VERSION_FILE} не найден!")
        return

    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        NEW_VERSION = f.read().strip()

    if not NEW_VERSION:
        print("❌ Файл VERSION пустой!")
        return

    # Убеждаемся, что версия начинается с 'v'
    if not NEW_VERSION.startswith("v"):
        NEW_VERSION = "v" + NEW_VERSION

    if not os.path.exists(CONFIG_PATH):
        print(f"❌ Ошибка: Файл {CONFIG_PATH} не найден!")
        return

    try:
        # Загружаем текущий конфиг
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        old_version = data.get("version", "неизвестно")
        
        # Если версия не изменилась, предупреждаем
        if old_version == NEW_VERSION:
            print(f"ℹ️ Версия в файле уже равна {NEW_VERSION}. Изменения не требуются.")
            return

        # Обновляем версию
        data["version"] = NEW_VERSION

        # Сохраняем конфиг обратно с красивым форматированием
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Поддерживаем и semver (1.2.3), и расширенную версию (1.2.3.4).
        pattern_v = re.compile(r"v\d+(?:\.\d+){2,3}")
        pattern_num = re.compile(r"(?<!v)\b\d+(?:\.\d+){2,3}\b")
        
        # Ищем все файлы, где нужно обновить версию
        files_to_update = glob.glob("docs/*.html") + glob.glob("docs/js/*.js") + ["src/web_routes.py"]
        docs_updated = 0
        
        for file_path in files_to_update:
            if not os.path.exists(file_path):
                continue
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Ищем любую старую версию и заменяем на новую
                new_content = pattern_v.sub(NEW_VERSION, content)
                new_content = pattern_num.sub(NEW_VERSION.lstrip('v'), new_content)
                
                if new_content != content:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    docs_updated += 1
            except Exception as e:
                print(f"⚠️ Не удалось обновить {file_path}: {e}")

        print(f"✅ Успех! Версия бота обновлена:")
        print(f"   Было:  {old_version}")
        print(f"   Стало: {NEW_VERSION}")
        print(f"   Обновлено файлов: {docs_updated}")
        print("Бот автоматически загрузит новую версию при следующем запуске.")

    except Exception as e:
        print(f"❌ Произошла ошибка при обновлении файла: {e}")

if __name__ == "__main__":
    update_version()
