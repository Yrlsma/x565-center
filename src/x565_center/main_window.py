"""Основное окно: боковое меню и разделы."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget,
    QVBoxLayout, QWidget,
)

from . import theme
from .pages import BatteryPage, OverviewPage, PowerPage, ScreenPage, SettingsPage
from .widgets import label

SECTIONS = [
    ("overview", "Обзор", OverviewPage),
    ("power", "Питание", PowerPage),
    ("screen", "Экран", ScreenPage),
    ("battery", "Батарея", BatteryPage),
    ("settings", "Настройки", SettingsPage),
]


class MainWindow(QMainWindow):
    def __init__(self, ctl, activity_changed) -> None:
        super().__init__()
        self.ctl = ctl
        self._activity_changed = activity_changed
        self.really_quit = False
        self.setWindowTitle("X565 Center")

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 28, 16, 28)
        side.setSpacing(6)
        brand = QHBoxLayout()
        brand.setContentsMargins(12, 0, 12, 22)
        brand.setSpacing(10)
        self._logo = QLabel()
        brand.addWidget(self._logo)
        brand.addWidget(label("X565 Center", "brand"))
        brand.addStretch(1)
        side.addLayout(brand)

        self.stack = QStackedWidget()
        self._nav: list[tuple[QPushButton, str]] = []
        group = QButtonGroup(self)
        for index, (icon_name, title, page_cls) in enumerate(SECTIONS):
            btn = QPushButton("  " + title)
            btn.setObjectName("nav")
            btn.setCheckable(True)
            btn.setIconSize(QSize(18, 18))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, i=index: self.stack.setCurrentIndex(i))
            group.addButton(btn)
            side.addWidget(btn)
            self._nav.append((btn, icon_name))
            self.stack.addWidget(page_cls(ctl))
        self._nav[0][0].setChecked(True)
        side.addStretch(1)

        lay.addWidget(sidebar)
        lay.addWidget(self.stack, 1)

        theme.bus.changed.connect(self._refresh_icons)
        self._refresh_icons()

        avail = self.screen().availableGeometry()
        self.setMinimumSize(min(1280, avail.width()), min(820, avail.height() - 40))
        self.resize(self.minimumSize())

    def _refresh_icons(self) -> None:
        self._logo.setPixmap(theme.pixmap("logo", theme.colors["accent"], 26))
        for btn, name in self._nav:
            btn.setIcon(theme.icon(name, "text2", "accent"))
        self.setWindowIcon(QIcon(theme.pixmap("logo", theme.colors["accent"], 32)))

    def show_front(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:
        if self.really_quit:
            event.accept()
        else:  # закрытие окна сворачивает программу в трей
            event.ignore()
            self.hide()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._activity_changed()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._activity_changed()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self._activity_changed()
