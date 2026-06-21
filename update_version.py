import json
import os

# ==========================================
# ВПИШИТЕ НОВУЮ ВЕРСИЮ СЮДА:
NEW_VERSION = "v0.6.2.0"
# ==========================================

CONFIG_PATH = "config.json"

def update_version():
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

        import re
        import glob
        
        # Обновляем версию во всех HTML файлах в папке docs
        docs_updated = 0
        html_files = glob.glob("docs/*.html")
        
        for html_file in html_files:
            try:
                with open(html_file, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Ищем старую версию в HTML и заменяем на новую
                new_content = content.replace(old_version, NEW_VERSION)
                if new_content != content:
                    with open(html_file, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    docs_updated += 1
            except Exception as e:
                print(f"⚠️ Не удалось обновить {html_file}: {e}")

        print(f"✅ Успех! Версия бота обновлена:")
        print(f"   Было:  {old_version}")
        print(f"   Стало: {NEW_VERSION}")
        print("Бот автоматически загрузит новую версию при следующем запуске.")

    except Exception as e:
        print(f"❌ Произошла ошибка при обновлении файла: {e}")

if __name__ == "__main__":
    update_version()
