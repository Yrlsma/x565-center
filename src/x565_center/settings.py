"""Настройки программы: JSON в %APPDATA%\\X565Center."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "X565Center"
SETTINGS_FILE = APP_DIR / "settings.json"

# Стандартные схемы питания Windows.
SCHEME_SAVER = "a1841308-3541-4fab-bc81-f71556f20b4a"
SCHEME_BALANCED = "381b4222-f694-41f0-9685-ff5bb260df2e"
SCHEME_PERFORMANCE = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"

MODES = ("quiet", "balance", "turbo")
MODE_TITLES = {"quiet": "Тихий", "balance": "Баланс", "turbo": "Турбо"}

DEFAULTS = {
    "theme": "dark",
    "modes": {
        "quiet": {"scheme": SCHEME_SAVER, "hz": 60},
        "balance": {"scheme": SCHEME_BALANCED, "hz": 144},
        "turbo": {"scheme": SCHEME_PERFORMANCE, "hz": 144},
    },
}


def write_json(path: Path, data) -> None:
    """Запись через временный файл, чтобы не оставить половину файла при сбое."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class Settings:
    def __init__(self) -> None:
        self.data = copy.deepcopy(DEFAULTS)
        saved = read_json(SETTINGS_FILE)
        if isinstance(saved, dict):
            if saved.get("theme") in ("dark", "light"):
                self.data["theme"] = saved["theme"]
            for mode in MODES:
                cfg = (saved.get("modes") or {}).get(mode)
                if isinstance(cfg, dict):
                    if isinstance(cfg.get("scheme"), str):
                        self.data["modes"][mode]["scheme"] = cfg["scheme"].lower()
                    if isinstance(cfg.get("hz"), int):
                        self.data["modes"][mode]["hz"] = cfg["hz"]

    def save(self) -> None:
        try:
            write_json(SETTINGS_FILE, self.data)
        except OSError:
            pass

    @property
    def theme(self) -> str:
        return self.data["theme"]

    @theme.setter
    def theme(self, value: str) -> None:
        self.data["theme"] = value
        self.save()

    def mode(self, name: str) -> dict:
        return self.data["modes"][name]

    def set_mode(self, name: str, scheme: str, hz: int) -> None:
        self.data["modes"][name] = {"scheme": scheme, "hz": hz}
        self.save()
