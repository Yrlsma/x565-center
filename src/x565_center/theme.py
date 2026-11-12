"""Темы оформления: цвета из docs/DESIGN.md, таблица стилей, значки."""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QObject, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer

PALETTES = {
    "dark": {
        "bg": "#0F1216", "side": "#0B0D10", "card": "#171B21", "sel": "#1B2027",
        "border": "#2B323C", "track": "#262C35", "text": "#E8EAED", "text2": "#A7B0BB",
        "accent": "#2FD3C0", "on_accent": "#06231F", "hot": "#FFB25C",
    },
    "light": {
        "bg": "#F3F5F7", "side": "#FFFFFF", "card": "#FFFFFF", "sel": "#EEF1F4",
        "border": "#D9DEE4", "track": "#E3E7EC", "text": "#14171A", "text2": "#56606B",
        "accent": "#0B7D72", "on_accent": "#FFFFFF", "hot": "#A8480A",
    },
}

# Inter и JetBrains Mono используются, если установлены; иначе системные шрифты Windows 11.
FONT_TEXT = '"Inter", "Segoe UI Variable Text", "Segoe UI"'
FONT_MONO = '"JetBrains Mono", "Cascadia Mono", "Consolas"'

colors: dict[str, str] = dict(PALETTES["dark"])

ICONS = {
    "logo": '<circle cx="12" cy="12" r="9"/><path d="M12 12l5-3"/><circle cx="12" cy="12" r="1.5"/>',
    "overview": '<rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/>'
                '<rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/>',
    "power": '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
    "screen": '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
    "battery": '<rect x="2" y="7" width="17" height="10" rx="2"/><path d="M22 11v2"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/>',
    "moon": '<path d="M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10z"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19"/>',
    "expand": '<path d="M14 4h6v6M20 4l-8 8M10 20H4v-6M4 20l8-8"/>',
}


class _Bus(QObject):
    changed = Signal()


bus = _Bus()


def pixmap(name: str, color: str, size: int) -> QPixmap:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        f"{ICONS[name]}</svg>"
    )
    scale = 2  # запас для масштаба экрана до 200%
    pm = QPixmap(size * scale, size * scale)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    pm.setDevicePixelRatio(scale)
    return pm


def icon(name: str, off: str, on: str | None = None, size: int = 18) -> QIcon:
    """Значок: цвет off в обычном состоянии, on — у нажатой (выбранной) кнопки."""
    ic = QIcon()
    ic.addPixmap(pixmap(name, colors[off], size), QIcon.Mode.Normal, QIcon.State.Off)
    ic.addPixmap(pixmap(name, colors[on or off], size), QIcon.Mode.Normal, QIcon.State.On)
    return ic


def stylesheet() -> str:
    c = colors
    return f"""
* {{ outline: none; }}
QWidget {{ color: {c['text']}; font-family: {FONT_TEXT}; font-size: 14px; }}
#root, #page, #popup {{ background: {c['bg']}; }}
#popup {{ border: 1px solid {c['border']}; }}
#sidebar {{ background: {c['side']}; }}
QLabel {{ background: transparent; }}
QLabel#brand {{ font-size: 16px; font-weight: 700; }}
QLabel#h1 {{ font-size: 26px; font-weight: 700; }}
QLabel#h2 {{ font-size: 15px; font-weight: 600; }}
QLabel#muted {{ font-size: 13px; color: {c['text2']}; }}
QLabel#warn {{ font-size: 13px; color: {c['hot']}; }}
QLabel#value {{ font-family: {FONT_MONO}; font-size: 40px; font-weight: 700; }}
QLabel#tvalue {{ font-family: {FONT_MONO}; font-size: 28px; font-weight: 700; }}
QLabel#value[hot="true"], QLabel#tvalue[hot="true"] {{ color: {c['hot']}; }}
QLabel#state {{ font-size: 13px; font-weight: 700; color: {c['text2']}; }}
QLabel#state[on="true"] {{ color: {c['accent']}; }}

QPushButton#nav {{ min-height: 44px; padding: 0 12px; border: 0; border-radius: 10px;
    background: transparent; color: {c['text2']}; font-weight: 500; text-align: left; }}
QPushButton#nav:hover {{ color: {c['text']}; }}
QPushButton#nav:checked {{ background: {c['sel']}; color: {c['text']}; font-weight: 600; }}

#segment {{ background: {c['card']}; border-radius: 12px; }}
#card #segment {{ background: {c['sel']}; }}
#segment[tray="true"] {{ background: {c['side']}; border-radius: 14px; }}
QPushButton#seg {{ min-height: 44px; padding: 0 16px; border: 0; border-radius: 9px;
    background: transparent; color: {c['text2']}; font-weight: 600; }}
QPushButton#seg:hover {{ color: {c['text']}; }}
QPushButton#seg[kind="theme"]:checked {{ background: {c['border']}; color: {c['text']}; }}
QPushButton#seg[kind="mode"]:checked {{ background: {c['accent']}; color: {c['on_accent']}; font-weight: 700; }}
#segment[tray="true"] QPushButton#seg {{ min-height: 48px; border-radius: 10px; }}

#tile, #card {{ background: {c['card']}; border-radius: 16px; }}
#ttile {{ background: {c['card']}; border-radius: 14px; }}

QPushButton#toggle {{ min-height: 48px; border: 1px solid {c['border']}; border-radius: 12px;
    background: {c['sel']}; }}
QPushButton#toggle:hover {{ border-color: {c['text2']}; }}
QPushButton#toggle[tray="true"] {{ min-height: 46px; border: 0; background: {c['card']}; }}
#slider_row {{ border: 1px solid {c['border']}; border-radius: 12px; background: {c['sel']}; }}

QPushButton#button {{ min-height: 44px; padding: 0 18px; border: 1px solid {c['border']};
    border-radius: 10px; background: {c['sel']}; font-weight: 600; }}
QPushButton#button:hover {{ border-color: {c['text2']}; }}
QPushButton#icon_button {{ border: 0; border-radius: 10px; background: {c['card']}; }}

QComboBox {{ min-height: 40px; min-width: 240px; padding: 0 12px; border: 1px solid {c['border']};
    border-radius: 9px; background: {c['sel']}; }}
QComboBox::drop-down {{ border: 0; width: 28px; }}
QComboBox QAbstractItemView {{ background: {c['card']}; color: {c['text']}; border: 1px solid {c['border']};
    selection-background-color: {c['sel']}; selection-color: {c['text']}; }}

QSlider::groove:horizontal {{ height: 6px; border-radius: 3px; background: {c['track']}; }}
QSlider::sub-page:horizontal {{ height: 6px; border-radius: 3px; background: {c['accent']}; }}
QSlider::handle:horizontal {{ width: 18px; height: 18px; margin: -6px 0; border-radius: 9px; background: {c['accent']}; }}

QMenu {{ background: {c['card']}; border: 1px solid {c['border']}; padding: 6px; }}
QMenu::item {{ padding: 8px 20px; border-radius: 6px; }}
QMenu::item:selected {{ background: {c['sel']}; }}
"""


def apply(app, name: str) -> None:
    colors.clear()
    colors.update(PALETTES[name])
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(colors["bg"]))
    pal.setColor(QPalette.ColorRole.Base, QColor(colors["card"]))
    pal.setColor(QPalette.ColorRole.Button, QColor(colors["sel"]))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        pal.setColor(role, QColor(colors["text"]))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(colors["accent"]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(colors["on_accent"]))
    app.setPalette(pal)
    app.setStyleSheet(stylesheet())
    bus.changed.emit()
