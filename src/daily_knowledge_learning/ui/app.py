"""Application bootstrap and a small stylesheet for the UI skeleton."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .fonts import build_app_font
from .main_window import MainWindow

APP_NAME = "每日知识点学习"

STYLESHEET = """
QWidget#sidebar {
    background-color: #f2f3f5;
    border-right: 1px solid #dcdfe6;
}
QLabel#sidebarBrand {
    font-size: 15px;
    font-weight: 600;
    color: #1f2329;
    padding: 6px 0;
}
QLabel#sidebarFooter {
    color: #8a9099;
    font-size: 11px;
}
QListWidget#sidebarList {
    background: transparent;
    outline: 0;
}
QListWidget#sidebarList::item {
    height: 38px;
    border-radius: 6px;
    padding-left: 10px;
    color: #1f2329;
}
QListWidget#sidebarList::item:selected {
    background-color: #d8e3fb;
    color: #1a56db;
}
QListWidget#sidebarList::item:hover:!selected {
    background-color: #e6e9ee;
}
QWidget#contentArea {
    background-color: #ffffff;
}
QLabel#pageHeading {
    font-size: 20px;
    font-weight: 600;
    color: #1f2329;
}
QLabel#pageBody {
    color: #4e5969;
    font-size: 13px;
}
QTextEdit#markdownViewer {
    border: 1px solid #dcdfe6;
    border-radius: 6px;
    padding: 8px;
    background-color: #ffffff;
    color: #1f2329;
}
"""


def build_application(argv: list[str] | None = None) -> QApplication:
    """Create (or return) the QApplication with fonts and styling applied."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setFont(build_app_font())
    app.setStyleSheet(STYLESHEET)
    return app


def create_window() -> MainWindow:
    """Build the main window without entering the event loop (used by tests)."""
    return MainWindow()


def run(argv: list[str] | None = None) -> int:
    """Launch the desktop window and block until it closes."""
    app = build_application(argv)
    window = create_window()
    window.show()
    return app.exec()
