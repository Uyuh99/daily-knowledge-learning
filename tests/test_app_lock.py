from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QLockFile
from PySide6.QtWidgets import QApplication

from daily_knowledge_learning.ui import app as app_module


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication(["app-lock-tests"])


def test_second_process_cannot_acquire_desktop_lock(tmp_path, qt_app, monkeypatch):
    lock_path = tmp_path / "application.lock"
    monkeypatch.setenv("DAILY_KNOWLEDGE_LEARNING_LOCK", str(lock_path))
    app_module._INSTANCE_LOCK = None

    assert app_module._acquire_instance_lock() is True
    second = QLockFile(str(lock_path))
    assert second.tryLock(0) is False

    app_module._INSTANCE_LOCK.unlock()
    app_module._INSTANCE_LOCK = None
    second.unlock()
