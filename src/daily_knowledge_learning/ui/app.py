"""Application bootstrap: font, palette, stylesheet, main window."""

from __future__ import annotations

import sys
import os
from pathlib import Path

from PySide6.QtCore import QLockFile
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import theme
from .fonts import build_app_font
from .main_window import MainWindow

APP_NAME = "每日知识点学习"
_INSTANCE_LOCK: QLockFile | None = None


def _instance_lock_path() -> Path:
    """Return a per-user lock path for the desktop application.

    Keeping this outside the install directory makes the guard work for both
    the installed and portable builds, while the environment override keeps
    the behaviour deterministic in tests.
    """

    override = os.environ.get("DAILY_KNOWLEDGE_LEARNING_LOCK")
    if override:
        return Path(override).expanduser()
    root = Path.home() / ".config" / "daily-knowledge-learning"
    return root / "application.lock"


def _acquire_instance_lock() -> bool:
    """Acquire the process lock, returning false when another copy is live."""

    global _INSTANCE_LOCK
    lock_path = _instance_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(lock_path))
    # A lock left behind by a terminated process is safe to reclaim after Qt's
    # stale-lock check.  We never show a second window when the lock is held.
    lock.setStaleLockTime(10_000)
    if not lock.tryLock(0):
        return False
    _INSTANCE_LOCK = lock
    return True


def _icon_path() -> Path:
    bundle = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[4]))
    return bundle / "assets" / "daily-learning.ico"


def build_application(argv: list[str] | None = None) -> QApplication:
    """Create the QApplication with the shared font and stylesheet applied."""

    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setWindowIcon(QIcon(str(_icon_path())))
    font = build_app_font()
    app.setFont(font)
    # Qt's stylesheet font-size rules can otherwise reset inherited families.
    app.setStyleSheet(theme.stylesheet() + f'\nQWidget {{ font-family: "{font.family()}"; }}')
    return app


def create_window() -> MainWindow:
    return MainWindow()


def run(argv: list[str] | None = None) -> int:
    if not _acquire_instance_lock():
        return 0
    app = build_application(argv)
    window = create_window()
    window.show()
    return app.exec()
