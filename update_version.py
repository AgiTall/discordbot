import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "VERSION"
CONFIG_PATH = ROOT / "config.json"
VERSION_BADGE_PATTERN = re.compile(
    r'(<span\b[^>]*class="[^"]*\b(?:navbar__badge|footer__version)\b[^"]*"[^>]*>)[^<]*(</span>)'
)


def normalize_version(value: str) -> str:
    version = value.strip()
    if not re.fullmatch(r"v?\d+(?:\.\d+){2,3}", version):
        raise ValueError("Версия должна иметь формат v1.2.3 или v1.2.3.4")
    return version if version.startswith("v") else f"v{version}"


def replace_version_badges(content: str, version: str) -> str:
    """Replace only visible version badges, never arbitrary dotted numbers."""
    return VERSION_BADGE_PATTERN.sub(rf"\g<1>{version}\g<2>", content)


def update_version(root: Path = ROOT):
    version_path = root / "VERSION"
    config_path = root / "config.json"
    if not version_path.exists():
        print(f"❌ Файл {version_path.name} не найден!")
        return False

    try:
        new_version = normalize_version(version_path.read_text(encoding="utf-8"))
    except ValueError as error:
        print(f"❌ {error}")
        return False

    try:
        data = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
        old_version = data.get("version", "неизвестно")
        data["version"] = new_version
        config_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        docs_updated = 0
        for file_path in (root / "docs").glob("*.html"):
            content = file_path.read_text(encoding="utf-8")
            new_content = replace_version_badges(content, new_version)
            if new_content != content:
                file_path.write_text(new_content, encoding="utf-8")
                docs_updated += 1

        print("✅ Версия синхронизирована:")
        print(f"   Было:  {old_version}")
        print(f"   Стало: {new_version}")
        print(f"   Обновлено HTML-файлов: {docs_updated}")
        print("VERSION теперь является единым источником версии для бота и сайта.")
        return True
    except (OSError, json.JSONDecodeError) as error:
        print(f"❌ Не удалось синхронизировать версию: {error}")
        return False

if __name__ == "__main__":
    update_version()
