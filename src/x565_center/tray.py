"""Значок в трее и окно 380×620 по макету Tray.dc.html."""
from __future__ import annotations

import math
import time

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QCursor, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QMenu, QPushButton, QSystemTrayIcon, QVBoxLayout,
)

from . import theme
from .pages import MODE_OPTIONS, battery_text
from .widgets import HOT_TEMP, Segmented, Tile, ToggleRow, label


class TrayPopup(QFrame):
    def __init__(self, ctl, open_main, activity_changed) -> None:
        super().__init__(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.ctl = ctl
        self._activity_changed = activity_changed
        self.hidden_at = 0.0
        self.setObjectName("popup")
        self.setFixedSize(380, 620)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(label("X565 Center", "brand"))
        self.subtitle = label("", "muted")
        titles.addWidget(self.subtitle)
        header.addLayout(titles)
        header.addStretch(1)
        self.open_btn = QPushButton()
        self.open_btn.setObjectName("icon_button")
        self.open_btn.setFixedSize(44, 44)
        self.open_btn.setIconSize(QSize(18, 18))
        self.open_btn.setToolTip("Открыть полное окно")
        self.open_btn.setAccessibleName("Открыть полное окно")
        self.open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_btn.clicked.connect(lambda: (self.hide(), open_main()))
        header.addWidget(self.open_btn)
        lay.addLayout(header)

        self.mode_seg = Segmented(MODE_OPTIONS, "mode", tray=True)
        self.mode_seg.setAccessibleName("Режим работы")
        lay.addWidget(self.mode_seg)

        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        self.cpu = Tile("Процессор", compact=True)
        self.gpu = Tile("Видеокарта", compact=True)
        self.fan = Tile("Вентиляторы", compact=True)
        self.mem = Tile("Память", compact=True)
        self._shown: list = []
        lay.addLayout(self.grid)
        self._arrange([self.cpu, self.mem])

        toggles = QVBoxLayout()
        toggles.setSpacing(8)
        self.hz = ToggleRow(f"Экран {ctl.hz_high} Гц", tray=True)
        self.wifi = ToggleRow("Wi‑Fi", tray=True)
        self.bluetooth = ToggleRow("Bluetooth", tray=True)
        for w in (self.hz, self.wifi, self.bluetooth):
            toggles.addWidget(w)
        lay.addLayout(toggles)
        lay.addStretch(1)

        self.mode_seg.selected.connect(ctl.set_mode)
        self.hz.toggled_by_user.connect(ctl.set_high_hz)
        self.wifi.toggled_by_user.connect(lambda on: ctl.set_radio("wifi", on))
        self.bluetooth.toggled_by_user.connect(lambda on: ctl.set_radio("bluetooth", on))
        ctl.mode_changed.connect(self.mode_seg.set_current)
        ctl.hz_changed.connect(self._on_hz)
        ctl.radios_changed.connect(self._on_radios)
        ctl.snapshot.connect(self.on_snapshot)
        theme.bus.changed.connect(self._refresh_icons)

        self.mode_seg.set_current(ctl.mode)
        self._on_hz(ctl.hz)
        self._on_radios(ctl.radios)
        self._refresh_icons()

    def _refresh_icons(self) -> None:
        self.open_btn.setIcon(QIcon(theme.pixmap("expand", theme.colors["text"], 18)))

    def _arrange(self, tiles: list) -> None:
        """Плитки в две колонки; недоступные датчики не показываются."""
        if tiles == self._shown:
            return
        for tile in (self.cpu, self.gpu, self.fan, self.mem):
            self.grid.removeWidget(tile)
            tile.setVisible(tile in tiles)
        for i, tile in enumerate(tiles):
            self.grid.addWidget(tile, i // 2, i % 2)
        self._shown = list(tiles)

    def _on_hz(self, hz) -> None:
        self.hz.set_state(None if hz is None else hz >= self.ctl.hz_high)

    def _on_radios(self, states: dict) -> None:
        self.wifi.set_state(states["wifi"])
        self.bluetooth.set_state(states["bluetooth"])

    def on_snapshot(self, s: dict) -> None:
        if not self.isVisible():
            return
        battery = s["battery"]
        self.subtitle.setText(f"{battery_text(battery)} · {battery['percent']}%" if battery else "От сети")

        tiles = [self.cpu]
        if s["cpu_temp"] is not None:
            self.cpu.set(f"{s['cpu_temp']}°", f"{s['cpu_load']}%", hot=s["cpu_temp"] >= HOT_TEMP)
        else:
            self.cpu.set(f"{s['cpu_load']}%", "загрузка")
        if s["gpu_temp"] is not None:
            tiles.append(self.gpu)
            self.gpu.set(f"{s['gpu_temp']}°", f"{s['gpu_load']}%", hot=s["gpu_temp"] >= HOT_TEMP)
        if s["fan_rpm"] is not None:
            tiles.append(self.fan)
            self.fan.set(str(s["fan_rpm"]), "об/мин")
        tiles.append(self.mem)
        gb = 1024 ** 3
        self.mem.set(f"{s['mem_used'] / gb:.1f}", f"из {math.ceil(s['mem_total'] / gb)} ГБ")
        self._arrange(tiles)

    def show_near_tray(self) -> None:
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(area.right() - self.width() - 12, area.bottom() - self.height() - 12)
        self.show()
        self.activateWindow()
        if self.ctl.last:
            self.on_snapshot(self.ctl.last)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._activity_changed()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self.hidden_at = time.monotonic()
        self._activity_changed()


class Tray(QSystemTrayIcon):
    def __init__(self, ctl, open_main, quit_app, activity_changed) -> None:
        super().__init__()
        self.popup = TrayPopup(ctl, open_main, activity_changed)
        self.setToolTip("X565 Center")
        self.menu = QMenu()
        self.menu.addAction("Открыть окно", open_main)
        self.menu.addSeparator()
        self.menu.addAction("Выход", quit_app)
        self.setContextMenu(self.menu)
        self.activated.connect(self._activated)
        theme.bus.changed.connect(self._refresh_icon)
        self._refresh_icon()

    def _refresh_icon(self) -> None:
        self.setIcon(QIcon(theme.pixmap("logo", theme.PALETTES["dark"]["accent"], 32)))

    def _activated(self, reason) -> None:
        if reason != QSystemTrayIcon.ActivationReason.Trigger:
            return
        # Щелчок по значку при открытом окне сначала закрывает его (потеря фокуса) — не открывать заново.
        if self.popup.isVisible() or time.monotonic() - self.popup.hidden_at < 0.3:
            self.popup.hide()
        else:
            self.popup.show_near_tray()
