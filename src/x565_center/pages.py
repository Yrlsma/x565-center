"""Разделы основного окна: Обзор, Питание, Экран, Батарея, Настройки."""
from __future__ import annotations

import ctypes

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QPushButton, QVBoxLayout, QWidget,
)

from . import display, power
from .settings import APP_DIR, MODE_TITLES, MODES
from .widgets import (
    HOT_TEMP, BrightnessRow, Chart, LegendMark, Segmented, Tile, ToggleRow, label,
)

THEME_OPTIONS = [("dark", "Тёмная", "moon"), ("light", "Светлая", "sun")]
MODE_OPTIONS = [(m, MODE_TITLES[m]) for m in MODES]
STANDARD_SCHEMES = power.STANDARD_SCHEMES


def battery_text(battery: dict) -> str:
    if battery["charging"]:
        return "Заряжается"
    return "От сети" if battery["plugged"] else "От батареи"


def card(title: str = "") -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(20, 20, 20, 20)
    lay.setSpacing(10)
    if title:
        lay.addWidget(label(title, "h2"))
    return frame, lay


class Page(QWidget):
    def __init__(self, ctl, title: str) -> None:
        super().__init__()
        self.ctl = ctl
        self.setObjectName("page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(32, 28, 32, 36)
        self.root.setSpacing(22)
        self.header = QHBoxLayout()
        self.header.setSpacing(12)
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addWidget(label(title, "h1"))
        self.subtitle = label("", "muted")
        titles.addWidget(self.subtitle)
        self.header.addLayout(titles)
        self.header.addStretch(1)
        self.root.addLayout(self.header)


class OverviewPage(Page):
    def __init__(self, ctl) -> None:
        super().__init__(ctl, "Обзор")
        self.theme_seg = Segmented(THEME_OPTIONS, "theme")
        self.theme_seg.setAccessibleName("Тема оформления")
        self.mode_seg = Segmented(MODE_OPTIONS, "mode")
        self.mode_seg.setAccessibleName("Режим работы")
        self.header.addWidget(self.theme_seg)
        self.header.addWidget(self.mode_seg)

        tiles = QHBoxLayout()
        tiles.setSpacing(16)
        self.cpu = Tile("Процессор")
        self.gpu = Tile("Видеокарта")
        self.fan = Tile("Вентиляторы")
        self.battery = Tile("Батарея")
        for tile in (self.cpu, self.gpu, self.fan, self.battery):
            tiles.addWidget(tile, 1)
        for tile in (self.gpu, self.fan, self.battery):
            tile.hide()  # появятся, когда датчик ответит
        self.root.addLayout(tiles)

        bottom = QHBoxLayout()
        bottom.setSpacing(16)
        chart_card, chart_lay = card()
        chart_lay.setSpacing(14)
        head = QHBoxLayout()
        head.addWidget(label("Температура за 10 минут", "h2"))
        head.addStretch(1)
        for color, name in (("accent", "CPU"), ("hot", "GPU")):
            head.addSpacing(8)
            head.addWidget(LegendMark(color))
            head.addWidget(label(name, "muted"))
        chart_lay.addLayout(head)
        self.chart = Chart(ctl.history)
        chart_lay.addWidget(self.chart, 1)
        bottom.addWidget(chart_card, 2)

        quick_card, quick = card("Быстрые действия")
        self.hz = ToggleRow(f"Экран {ctl.hz_high} Гц")
        self.wifi = ToggleRow("Wi‑Fi")
        self.bluetooth = ToggleRow("Bluetooth")
        self.brightness = BrightnessRow()
        for w in (self.hz, self.wifi, self.bluetooth, self.brightness):
            quick.addWidget(w)
        quick.addStretch(1)
        bottom.addWidget(quick_card, 1)
        self.root.addLayout(bottom, 1)

        self.status = label("", "warn")
        self.status.setWordWrap(True)
        self.status.hide()
        self.root.addWidget(self.status)

        self.theme_seg.selected.connect(ctl.set_theme)
        self.mode_seg.selected.connect(ctl.set_mode)
        self.hz.toggled_by_user.connect(ctl.set_high_hz)
        self.wifi.toggled_by_user.connect(lambda on: ctl.set_radio("wifi", on))
        self.bluetooth.toggled_by_user.connect(lambda on: ctl.set_radio("bluetooth", on))
        self.brightness.changed_by_user.connect(ctl.set_brightness)

        ctl.theme_changed.connect(self.theme_seg.set_current)
        ctl.mode_changed.connect(self.mode_seg.set_current)
        ctl.hz_changed.connect(self._on_hz)
        ctl.radios_changed.connect(self._on_radios)
        ctl.health_changed.connect(lambda _h: ctl.last and self.on_snapshot(ctl.last))
        ctl.status_changed.connect(self._on_status)
        ctl.snapshot.connect(self.on_snapshot)

        self.theme_seg.set_current(ctl.settings.theme)
        self.mode_seg.set_current(ctl.mode)
        self._on_hz(ctl.hz)
        self._on_radios(ctl.radios)
        self._on_status(ctl.status)

    def _on_hz(self, hz) -> None:
        self.hz.set_state(None if hz is None else hz >= self.ctl.hz_high)

    def _on_radios(self, states: dict) -> None:
        self.wifi.set_state(states["wifi"])
        self.bluetooth.set_state(states["bluetooth"])

    def _on_status(self, text: str) -> None:
        self.status.setText(text)
        self.status.setVisible(bool(text))

    def on_snapshot(self, s: dict) -> None:
        if not self.isVisible():
            return
        battery = s["battery"]
        parts = [self.ctl.cpu_name]
        if s["gpu_name"]:
            parts.append(s["gpu_name"])
        if battery:
            parts.append("от сети" if battery["plugged"] else "от батареи")
        self.subtitle.setText(" · ".join(parts))

        load = s["cpu_load"]
        if s["cpu_temp"] is not None:
            self.cpu.set(f"{s['cpu_temp']}°", f"Загрузка {load}%", load / 100, s["cpu_temp"] >= HOT_TEMP)
        else:
            self.cpu.set(f"{load}%", "Загрузка · температура недоступна", load / 100)

        self.gpu.setVisible(s["gpu_temp"] is not None)
        if s["gpu_temp"] is not None:
            self.gpu.set(
                f"{s['gpu_temp']}°", f"Загрузка {s['gpu_load']}%",
                s["gpu_load"] / 100, s["gpu_temp"] >= HOT_TEMP,
            )

        self.fan.setVisible(s["fan_rpm"] is not None)
        if s["fan_rpm"] is not None:
            self.fan.set(str(s["fan_rpm"]), "об/мин · только чтение", s["fan_rpm"] / 6000)

        self.battery.setVisible(battery is not None)
        if battery:
            sub = battery_text(battery)
            if self.ctl.health:
                sub += f" · износ {self.ctl.health['wear']}%"
            self.battery.set(f"{battery['percent']}%", sub, battery["percent"] / 100)

        self.brightness.set_value(s["brightness"])
        self.chart.update()


class PowerPage(Page):
    def __init__(self, ctl) -> None:
        super().__init__(ctl, "Питание")
        self.subtitle.setText("Состав режимов. Штатные режимы Office / Gaming / Turbo программа не трогает.")
        self._filling = False
        self._rows: dict[str, tuple[QComboBox, QComboBox]] = {}

        modes_card, lay = card("Режимы")
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)
        grid.addWidget(label("Схема питания Windows", "muted"), 0, 1)
        grid.addWidget(label("Частота экрана", "muted"), 0, 2)
        for row, mode in enumerate(MODES, start=1):
            name = label(MODE_TITLES[mode])
            name.setStyleSheet("font-weight: 600;")
            name.setMinimumWidth(90)
            scheme, hz = QComboBox(), QComboBox()
            scheme.setAccessibleName(f"Схема питания для режима {MODE_TITLES[mode]}")
            hz.setAccessibleName(f"Частота экрана для режима {MODE_TITLES[mode]}")
            hz.setMinimumWidth(120)
            scheme.activated.connect(lambda _i, m=mode: self._edited(m))
            hz.activated.connect(lambda _i, m=mode: self._edited(m))
            grid.addWidget(name, row, 0)
            grid.addWidget(scheme, row, 1)
            grid.addWidget(hz, row, 2)
            self._rows[mode] = (scheme, hz)
        grid.setColumnStretch(3, 1)
        lay.addLayout(grid)
        self.note = label("", "warn")
        self.note.setWordWrap(True)
        lay.addWidget(self.note)
        lay.addWidget(label("Изменения применяются при следующем выборе режима.", "muted"))
        self.root.addWidget(modes_card)

        cc_card, cc = card("Штатный Control Center")
        text = label(
            "Вентиляторы, лимиты мощности и подсветка клавиатуры настраиваются только в штатной программе.",
            "muted",
        )
        text.setWordWrap(True)
        cc.addWidget(text)
        button = QPushButton("Открыть Control Center")
        button.setObjectName("button")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(ctl.open_control_center)
        cc.addWidget(button, 0, Qt.AlignmentFlag.AlignLeft)
        self.root.addWidget(cc_card)
        self.root.addStretch(1)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._fill()

    def _fill(self) -> None:
        schemes = power.list_schemes()
        existing = {guid for guid, _ in schemes}
        rates = self.ctl.hz_rates
        missing = []
        for mode, (scheme_box, hz_box) in self._rows.items():
            cfg = self.ctl.settings.mode(mode)
            scheme_box.clear()
            for guid, name in schemes:
                scheme_box.addItem(name, guid)
            if cfg["scheme"] not in existing:
                name = STANDARD_SCHEMES.get(cfg["scheme"], cfg["scheme"])
                scheme_box.addItem(f"{name} — нет в системе", cfg["scheme"])
                missing.append(f"«{MODE_TITLES[mode]}»")
            scheme_box.setCurrentIndex(scheme_box.findData(cfg["scheme"]))
            hz_box.clear()
            for rate in sorted(set(rates) | {cfg["hz"]}):
                hz_box.addItem(f"{rate} Гц", rate)
            hz_box.setCurrentIndex(hz_box.findData(cfg["hz"]))
        self.note.setText(
            f"Схемы питания для режимов {', '.join(missing)} в Windows нет: "
            "эти режимы пока меняют только частоту экрана." if missing else ""
        )
        self.note.setVisible(bool(missing))

    def _edited(self, mode: str) -> None:
        scheme_box, hz_box = self._rows[mode]
        self.ctl.settings.set_mode(mode, scheme_box.currentData(), hz_box.currentData())
        self.ctl.modes_edited()
        self._fill()


class ScreenPage(Page):
    def __init__(self, ctl) -> None:
        super().__init__(ctl, "Экран")
        box, lay = card("Встроенный экран")
        self.info = label("", "muted")
        lay.addWidget(self.info)
        self.hz = ToggleRow(f"Экран {ctl.hz_high} Гц")
        self.brightness = BrightnessRow()
        lay.addWidget(self.hz)
        lay.addWidget(self.brightness)
        box.setMaximumWidth(560)
        self.root.addWidget(box)
        self.root.addStretch(1)
        self.hz.toggled_by_user.connect(ctl.set_high_hz)
        self.brightness.changed_by_user.connect(ctl.set_brightness)
        ctl.hz_changed.connect(self._on_hz)
        ctl.snapshot.connect(lambda s: self.isVisible() and self.brightness.set_value(s["brightness"]))
        self._on_hz(ctl.hz)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.ctl.last:
            self.brightness.set_value(self.ctl.last["brightness"])

    def _on_hz(self, hz) -> None:
        self.hz.set_state(None if hz is None else hz >= self.ctl.hz_high)
        mode = display.current_mode()
        self.info.setText(f"{mode[0]}×{mode[1]} · {mode[2]} Гц" if mode else "Экран не найден")


class BatteryPage(Page):
    def __init__(self, ctl) -> None:
        super().__init__(ctl, "Батарея")
        row = QHBoxLayout()
        row.setSpacing(16)
        self.charge = Tile("Заряд")
        self.wear = Tile("Износ")
        row.addWidget(self.charge, 1)
        row.addWidget(self.wear, 1)
        row.addStretch(2)
        self.root.addLayout(row)
        self.root.addStretch(1)
        ctl.snapshot.connect(lambda _s: self.isVisible() and self._update())
        ctl.health_changed.connect(lambda _h: self._update())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._update()

    def _update(self) -> None:
        battery = self.ctl.last["battery"] if self.ctl.last else None
        if battery:
            self.charge.set(f"{battery['percent']}%", battery_text(battery), battery["percent"] / 100)
            self.subtitle.setText("")
        else:
            self.charge.set("—", "Нет данных")
            self.subtitle.setText("Батарея не найдена.")
        health = self.ctl.health
        self.wear.setVisible(health is not None)
        if health:
            self.wear.set(
                f"{health['wear']}%",
                f"Ёмкость {health['full'] / 1000:.1f} из {health['design'] / 1000:.1f} Вт·ч",
                health["wear"] / 100, health["wear"] >= 40,
            )


class SettingsPage(Page):
    def __init__(self, ctl) -> None:
        super().__init__(ctl, "Настройки")
        look, lay = card("Оформление")
        self.theme_seg = Segmented(THEME_OPTIONS, "theme")
        lay.addWidget(self.theme_seg, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(label("Окно из трея всегда в той же теме.", "muted"))
        self.root.addWidget(look)

        sensors, lay = card("Датчики")
        admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        text = label(
            "Температура процессора берётся из термозон Windows, видеокарты — из драйвера NVIDIA. " + (
                "Программа запущена с правами администратора." if admin else
                "Обороты вентиляторов без прав администратора и библиотеки LibreHardwareMonitor недоступны."
            ),
            "muted",
        )
        text.setWordWrap(True)
        lay.addWidget(text)
        lay.addWidget(label(f"Настройки хранятся в {APP_DIR}", "muted"))
        self.root.addWidget(sensors)
        self.root.addStretch(1)

        self.theme_seg.selected.connect(ctl.set_theme)
        ctl.theme_changed.connect(self.theme_seg.set_current)
        self.theme_seg.set_current(ctl.settings.theme)
