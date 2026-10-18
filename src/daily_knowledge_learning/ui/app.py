"""Application bootstrap: font, palette, stylesheet, main window."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from . import theme
from .fonts import build_app_font
from .main_window import MainWindow

APP_NAME = "每日知识点学习"


def build_application(argv: list[str] | None = None) -> QApplication:
    """Create the QApplication with the shared font and stylesheet applied."""

    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setFont(build_app_font())
    app.setStyleSheet(theme.stylesheet())
    return app


def create_window() -> MainWindow:
    return MainWindow()


def run(argv: list[str] | None = None) -> int:
    app = build_application(argv)
    window = create_window()
    window.show()
    return app.exec()
