"""Состояние программы и связь интерфейса с системой."""
from __future__ import annotations

import subprocess
from collections import deque

from PySide6.QtCore import QObject, Qt, QThread, Signal

from . import display, modes, theme
from .sensors import SensorWorker, cpu_name
from .settings import MODE_TITLES, Settings
from .widgets import HISTORY_SECONDS

POLL_VISIBLE_MS = 1000
POLL_HIDDEN_MS = 4000
# Штатный Control Center: только запуск его ярлыка из меню «Пуск».
CONTROL_CENTER_APP = r"shell:AppsFolder\ControlCenter3_h329z55cwnj8g!App"


class Controller(QObject):
    snapshot = Signal(dict)
    theme_changed = Signal(str)
    mode_changed = Signal(object)  # str | None
    hz_changed = Signal(object)  # int | None
    radios_changed = Signal(dict)
    health_changed = Signal(object)  # dict | None
    status_changed = Signal(str)

    _to_interval = Signal(int)
    _to_radio = Signal(str, bool)
    _to_brightness = Signal(int)
    _to_stop = Signal()

    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        self.settings = Settings()
        self.cpu_name = cpu_name()
        self.history: deque = deque()
        self.last: dict | None = None
        self.radios = {"wifi": None, "bluetooth": None}
        self.health = None
        self.status = ""
        self._closed = False
        self._interval = POLL_VISIBLE_MS

        # Если прошлый запуск завершился аварийно — вернуть систему в прежнее состояние.
        self.recovered = modes.restore_state()

        rates = display.available_hz()
        self.hz_rates = rates
        self.hz_high = max(rates) if rates else 144
        self.hz_low = 60 if 60 in rates else (min(rates) if rates else 60)
        self.hz = display.current_hz()
        self.mode = modes.detect_mode(self.settings)

        theme.apply(app, self.settings.theme)

        self._thread = QThread()
        self._worker = SensorWorker()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.start)
        self._worker.snapshot.connect(self._on_snapshot)
        self._worker.radios.connect(self._on_radios)
        self._worker.battery_health.connect(self._on_health)
        self._to_interval.connect(self._worker.set_interval)
        self._to_radio.connect(self._worker.set_radio)
        self._to_brightness.connect(self._worker.set_brightness)
        self._to_stop.connect(self._worker.stop, Qt.ConnectionType.BlockingQueuedConnection)
        self._thread.start()
        app.aboutToQuit.connect(self.shutdown)

    # --- датчики ---

    def _on_snapshot(self, snap: dict) -> None:
        self.last = snap
        now = snap["time"]
        self.history.append((now, snap["cpu_temp"], snap["gpu_temp"]))
        while self.history and now - self.history[0][0] > HISTORY_SECONDS:
            self.history.popleft()
        hz = display.current_hz()
        if hz != self.hz:  # частоту поменяли вне программы
            self.hz = hz
            self.hz_changed.emit(hz)
            self._set_mode_value(modes.detect_mode(self.settings))
        self.snapshot.emit(snap)

    def _on_radios(self, states: dict) -> None:
        self.radios = states
        self.radios_changed.emit(states)

    def _on_health(self, health) -> None:
        self.health = health
        self.health_changed.emit(health)

    def set_active(self, active: bool) -> None:
        """Окно на экране — опрос раз в секунду, в трее — раз в 4 секунды."""
        interval = POLL_VISIBLE_MS if active else POLL_HIDDEN_MS
        if interval != self._interval:
            self._interval = interval
            self._to_interval.emit(interval)

    # --- действия пользователя ---

    def set_theme(self, name: str) -> None:
        if name == self.settings.theme:
            return
        self.settings.theme = name
        theme.apply(self.app, name)
        self.theme_changed.emit(name)

    def _set_mode_value(self, name: str | None) -> None:
        self.mode = name
        self.mode_changed.emit(name)

    def _set_status(self, text: str) -> None:
        self.status = text
        self.status_changed.emit(text)

    def set_mode(self, name: str) -> None:
        problems = modes.apply_mode(self.settings, name)
        self.hz = display.current_hz()
        self.hz_changed.emit(self.hz)
        self._set_mode_value(name)
        self._set_status(f"Режим «{MODE_TITLES[name]}»: {'; '.join(problems)}." if problems else "")

    def set_high_hz(self, on: bool) -> None:
        modes.remember_state()
        target = self.hz_high if on else self.hz_low
        ok = display.set_hz(target)
        self.hz = display.current_hz()
        self.hz_changed.emit(self.hz)
        self._set_mode_value(modes.detect_mode(self.settings))
        self._set_status("" if ok else f"Экран не переключился на {target} Гц.")

    def modes_edited(self) -> None:
        self._set_mode_value(modes.detect_mode(self.settings))

    def set_radio(self, name: str, on: bool) -> None:
        self._to_radio.emit(name, on)

    def set_brightness(self, value: int) -> None:
        self._to_brightness.emit(value)

    def open_control_center(self) -> None:
        try:
            subprocess.Popen(["explorer.exe", CONTROL_CENTER_APP])
        except OSError:
            self._set_status("Не удалось открыть штатный Control Center.")

    # --- выход ---

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        modes.restore_state()
        self._to_stop.emit()
        self._thread.quit()
        self._thread.wait(3000)
