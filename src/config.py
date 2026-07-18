"""Configuration manager: loads/saves bot settings and session data.

Usage:
    from src.config import config
    token = config.get("token")
    config.set("some_setting", value)
    config.save()

This keeps a simple JSON file `config.json` at project root and writes
atomically. It also provides a `sync()` helper to ensure in-memory
state is refreshed from disk (useful if other processes may edit it).
"""
from pathlib import Path
import json
import threading
import tempfile
import os

_LOCK = threading.RLock()
VERSION_PATH = Path(__file__).resolve().parents[1] / "VERSION"

DEFAULT = {
    "version": "v0.0.0",
    "token": "",
    "connection": {
        "intents": {},
    },
    "settings": {},
}


class ConfigManager:
    def __init__(self, path="config.json"):
        self.path = Path(path)
        self._data = {}
        self._load()

    def _load(self):
        with _LOCK:
            if not self.path.exists():
                self._data = dict(DEFAULT)
                return
            try:
                with self.path.open("r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                # malformed file -> fallback to defaults but keep existing file
                self._data = dict(DEFAULT)

    def sync(self):
        """Reload from disk (non-destructive)."""
        self._load()

    def get(self, key, default=None):
        with _LOCK:
            if key == "version":
                try:
                    version = VERSION_PATH.read_text(encoding="utf-8").strip()
                except OSError:
                    version = ""
                if version:
                    return version if version.startswith("v") else f"v{version}"
            return self._data.get(key, default)

    def set(self, key, value):
        with _LOCK:
            self._data[key] = value

    def update(self, mapping: dict):
        with _LOCK:
            self._data.update(mapping)

    def save(self):
        """Write JSON atomically to avoid partial files on crash."""
        with _LOCK:
            tmp_fd, tmp_path = tempfile.mkstemp(prefix="config-", suffix=".json", dir=str(self.path.parent))
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as tf:
                    json.dump(self._data, tf, ensure_ascii=False, indent=2)
                os.replace(tmp_path, str(self.path))
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass


# Single module-level instance usable across the project
config = ConfigManager()
