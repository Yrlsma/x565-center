"""Схемы питания Windows через powercfg."""
from __future__ import annotations

import re
import subprocess

from .settings import SCHEME_BALANCED, SCHEME_PERFORMANCE, SCHEME_SAVER

_GUID = r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"
_LINE = re.compile(rf"({_GUID})\s*(?:\((.*)\))?")
NO_WINDOW = 0x08000000
_SUB_SLEEP = "238c9fa8-0aad-41ed-83f4-97be242c8f20"  # небольшая группа настроек, чтобы запрос был коротким

STANDARD_SCHEMES = {
    SCHEME_SAVER: "Экономия энергии",
    SCHEME_BALANCED: "Сбалансированная",
    SCHEME_PERFORMANCE: "Высокая производительность",
}


def _run(*args: str) -> tuple[int, str]:
    try:
        res = subprocess.run(
            ["powercfg", *args], capture_output=True, timeout=10, creationflags=NO_WINDOW
        )
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""
    # Кодировка вывода зависит от консоли: UTF-8 или OEM (cp866).
    try:
        return res.returncode, res.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return res.returncode, res.stdout.decode("oem", errors="replace")


def exists(guid: str) -> bool:
    code, _ = _run("/query", guid, _SUB_SLEEP)
    return code == 0


def list_schemes() -> list[tuple[str, str]]:
    """[(guid, название)] для схем, которые есть в системе.

    На ноутбуках с ждущим режимом S0 `powercfg /list` показывает только «Сбалансированную»,
    хотя стандартные схемы есть и включаются — они проверяются отдельно.
    """
    _, out = _run("/list")
    schemes = []
    for line in out.splitlines():
        m = _LINE.search(line)
        if m:
            schemes.append((m.group(1).lower(), (m.group(2) or m.group(1)).strip()))
    listed = {guid for guid, _ in schemes}
    for guid, name in STANDARD_SCHEMES.items():
        if guid not in listed and exists(guid):
            schemes.append((guid, name))
    order = list(STANDARD_SCHEMES)
    schemes.sort(key=lambda s: order.index(s[0]) if s[0] in order else len(order))
    return schemes


def active_scheme() -> str | None:
    _, out = _run("/getactivescheme")
    m = _LINE.search(out)
    return m.group(1).lower() if m else None


def set_active(guid: str) -> bool:
    code, _ = _run("/setactive", guid)
    return code == 0 and active_scheme() == guid.lower()
