"""Режимы «Тихий / Баланс / Турбо» и возврат системы в прежнее состояние.

Перед первым изменением схемы питания или частоты экрана прежние значения
записываются в restore.json. При выходе они возвращаются, файл удаляется.
Если программа упала, файл остаётся и возврат выполняется при следующем запуске.
"""
from __future__ import annotations

from . import display, power
from .settings import APP_DIR, MODES, Settings, read_json, write_json

RESTORE_FILE = APP_DIR / "restore.json"


def remember_state() -> None:
    """Сохранить состояние системы на диск до первого изменения."""
    if RESTORE_FILE.exists():
        return
    try:
        write_json(RESTORE_FILE, {"scheme": power.active_scheme(), "hz": display.current_hz()})
    except OSError:
        pass


def restore_state() -> bool:
    """Вернуть сохранённое состояние. True, если было что возвращать."""
    saved = read_json(RESTORE_FILE)
    if not isinstance(saved, dict):
        RESTORE_FILE.unlink(missing_ok=True)
        return False
    scheme, hz = saved.get("scheme"), saved.get("hz")
    if isinstance(scheme, str) and scheme != power.active_scheme():
        power.set_active(scheme)
    if isinstance(hz, int):
        display.set_hz(hz)
    RESTORE_FILE.unlink(missing_ok=True)
    return True


def apply_mode(settings: Settings, name: str) -> list[str]:
    """Применить режим. Возвращает список того, что применить не удалось."""
    cfg = settings.mode(name)
    problems = []
    remember_state()
    if not power.set_active(cfg["scheme"]):
        problems.append(
            "не удалось переключить схему питания" if power.exists(cfg["scheme"])
            else "схемы питания нет в системе"
        )
    if not display.set_hz(cfg["hz"]):
        problems.append(f"экран не поддерживает {cfg['hz']} Гц")
    return problems


def detect_mode(settings: Settings) -> str | None:
    """Режим, которому сейчас соответствует система, или None."""
    scheme, hz = power.active_scheme(), display.current_hz()
    for name in MODES:
        cfg = settings.mode(name)
        if cfg["scheme"] == scheme and cfg["hz"] == hz:
            return name
    return None
