"""Запуск: python -m x565_center"""
from __future__ import annotations

import sys

from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from .controller import Controller
from .main_window import MainWindow
from .tray import Tray

SERVER_NAME = "X565Center"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("X565 Center")
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)

    # Второй экземпляр только показывает окно первого.
    probe = QLocalSocket()
    probe.connectToServer(SERVER_NAME)
    if probe.waitForConnected(300):
        probe.disconnectFromServer()
        return 0
    server = QLocalServer()
    QLocalServer.removeServer(SERVER_NAME)
    server.listen(SERVER_NAME)

    ctl = Controller(app)
    tray = None

    def activity_changed() -> None:
        main_active = window.isVisible() and not window.isMinimized()
        ctl.set_active(main_active or (tray is not None and tray.popup.isVisible()))

    def quit_app() -> None:
        window.really_quit = True
        app.quit()

    window = MainWindow(ctl, activity_changed)
    server.newConnection.connect(window.show_front)

    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = Tray(ctl, window.show_front, quit_app, activity_changed)
        tray.show()
    else:
        window.really_quit = True  # без трея закрытие окна завершает программу
        app.setQuitOnLastWindowClosed(True)

    if "--tray" not in sys.argv or tray is None:
        window.show()
    activity_changed()

    code = app.exec()
    ctl.shutdown()
    return code


if __name__ == "__main__":
    sys.exit(main())
