"""Общие элементы интерфейса: плитка, индикатор, график, переключатели."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSlider, QVBoxLayout, QWidget,
)

from . import theme

HOT_TEMP = 70  # °C, с этой температуры показатель подсвечивается как «горячий»
HISTORY_SECONDS = 600


def label(text: str = "", name: str = "") -> QLabel:
    lb = QLabel(text)
    if name:
        lb.setObjectName(name)
    return lb


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def set_prop(widget: QWidget, prop: str, value) -> None:
    if widget.property(prop) != value:
        widget.setProperty(prop, value)
        repolish(widget)


class Bar(QWidget):
    """Тонкий индикатор 6 px."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(6)
        self._fraction = 0.0
        self._hot = False

    def set(self, fraction: float, hot: bool = False) -> None:
        fraction = max(0.0, min(1.0, fraction))
        if fraction != self._fraction or hot != self._hot:
            self._fraction, self._hot = fraction, hot
            self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.colors["track"]))
        p.drawRoundedRect(QRectF(0, 0, self.width(), 6), 3, 3)
        if self._fraction > 0:
            p.setBrush(QColor(theme.colors["hot" if self._hot else "accent"]))
            p.drawRoundedRect(QRectF(0, 0, max(6.0, self.width() * self._fraction), 6), 3, 3)


class Tile(QFrame):
    """Плитка показателя: подпись, крупное число, индикатор, пояснение."""

    def __init__(self, title: str, compact: bool = False) -> None:
        super().__init__()
        self.setObjectName("ttile" if compact else "tile")
        lay = QVBoxLayout(self)
        pad = 14 if compact else 20
        lay.setContentsMargins(pad, pad, pad, pad)
        lay.setSpacing(6 if compact else 14)
        self.title = label(title, "muted")
        self.value = label("—", "tvalue" if compact else "value")
        self.sub = label("", "muted")
        lay.addWidget(self.title)
        lay.addWidget(self.value)
        self.bar = None
        if not compact:
            self.bar = Bar()
            lay.addWidget(self.bar)
        lay.addWidget(self.sub)
        lay.addStretch(1)

    def set(self, value: str, sub: str, fraction: float = 0.0, hot: bool = False) -> None:
        self.value.setText(value)
        self.sub.setText(sub)
        set_prop(self.value, "hot", hot)
        if self.bar:
            self.bar.set(fraction, hot)


class Segmented(QFrame):
    """Группа кнопок с одним выбранным вариантом (или без выбранного)."""

    selected = Signal(str)

    def __init__(self, options: list[tuple], kind: str, tray: bool = False) -> None:
        """options: (ключ, подпись) или (ключ, подпись, значок)."""
        super().__init__()
        self.setObjectName("segment")
        self.setProperty("tray", tray)
        lay = QHBoxLayout(self)
        pad = 5 if tray else 4
        lay.setContentsMargins(pad, pad, pad, pad)
        lay.setSpacing(6 if tray else 4)
        self._buttons: dict[str, QPushButton] = {}
        self._icons: dict[str, str] = {}
        self._current = None
        for key, title, *rest in options:
            btn = QPushButton(title)
            btn.setObjectName("seg")
            btn.setProperty("kind", kind)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self._clicked(k))
            if rest:
                self._icons[key] = rest[0]
                btn.setIconSize(QSize(16, 16))
            lay.addWidget(btn, 1 if tray else 0)
            self._buttons[key] = btn
        if self._icons:
            theme.bus.changed.connect(self._refresh_icons)
            self._refresh_icons()

    def _refresh_icons(self) -> None:
        for key, name in self._icons.items():
            self._buttons[key].setIcon(theme.icon(name, "text2", "text", 16))

    def _clicked(self, key: str) -> None:
        self.set_current(self._current)  # состояние меняет только контроллер
        self.selected.emit(key)

    def set_current(self, key: str | None) -> None:
        self._current = key
        for k, btn in self._buttons.items():
            btn.setChecked(k == key)


class ToggleRow(QPushButton):
    """Переключатель: название слева, состояние текстом «Вкл / Выкл» справа."""

    toggled_by_user = Signal(bool)

    def __init__(self, text: str, tray: bool = False) -> None:
        super().__init__()
        self.setObjectName("toggle")
        self.setProperty("tray", tray)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 14, 0)
        self._text = label(text)
        self._text.setStyleSheet("font-weight: 500;")
        self._state = label("Выкл", "state")
        for lb in (self._text, self._state):
            lb.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lay.addWidget(self._text)
        lay.addStretch(1)
        lay.addWidget(self._state)
        self._on = None
        self.clicked.connect(lambda: self.toggled_by_user.emit(not self._on))
        self.set_state(None)

    def set_state(self, on: bool | None) -> None:
        """None — переключатель недоступен."""
        self._on = on
        self.setEnabled(on is not None)
        self._state.setText("Нет" if on is None else ("Вкл" if on else "Выкл"))
        set_prop(self._state, "on", bool(on))
        self.setAccessibleName(f"{self._text.text()}: {self._state.text()}")


class BrightnessRow(QFrame):
    """Ползунок яркости экрана."""

    changed_by_user = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("slider_row")
        self.setMinimumHeight(48)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(12)
        title = label("Яркость")
        title.setStyleSheet("font-weight: 500;")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setAccessibleName("Яркость экрана")
        self._value = label("—", "state")
        self._value.setMinimumWidth(44)
        self._value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(title)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self._value)
        self.slider.valueChanged.connect(self._on_value)
        self._silent = False

    def _on_value(self, value: int) -> None:
        self._value.setText(f"{value}%")
        if not self._silent:
            self.changed_by_user.emit(value)

    def set_value(self, value: int | None) -> None:
        self.setVisible(value is not None)
        if value is None or self.slider.isSliderDown() or value == self.slider.value():
            return
        self._silent = True
        self.slider.setValue(value)
        self._silent = False


class Chart(QWidget):
    """График температуры процессора и видеокарты за 10 минут."""

    T_MIN, T_MAX = 20.0, 100.0

    def __init__(self, history) -> None:
        super().__init__()
        self._history = history  # deque[(время, cpu, gpu)]
        self.setMinimumHeight(190)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName("График температур процессора и видеокарты")

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QPen(QColor(theme.colors["track"]), 1))
        for i in (1, 2, 3):
            y = round(h * i / 4) + 0.5
            p.drawLine(QPointF(0, y), QPointF(w, y))
        if not self._history:
            return
        now = self._history[-1][0]
        for index, color in ((1, "accent"), (2, "hot")):
            path = QPainterPath()
            started = False
            for point in self._history:
                value = point[index]
                if value is None:
                    started = False
                    continue
                x = w * (1 - (now - point[0]) / HISTORY_SECONDS)
                frac = (min(self.T_MAX, max(self.T_MIN, value)) - self.T_MIN) / (self.T_MAX - self.T_MIN)
                pos = QPointF(x, h - 2 - frac * (h - 4))
                if started:
                    path.lineTo(pos)
                else:
                    path.moveTo(pos)
                    started = True
            pen = QPen(QColor(theme.colors[color]), 2.5)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawPath(path)


class LegendMark(QWidget):
    """Цветная чёрточка в легенде графика."""

    def __init__(self, color: str) -> None:
        super().__init__()
        self._color = color
        self.setFixedSize(14, 3)

    def paintEvent(self, _event) -> None:
        QPainter(self).fillRect(self.rect(), QColor(theme.colors[self._color]))
