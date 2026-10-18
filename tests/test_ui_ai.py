from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from daily_knowledge_learning.config import AppConfig, save_config
from daily_knowledge_learning.file_writer import update_note
from daily_knowledge_learning.study_service import start_session
from daily_knowledge_learning.study_service import _AI_REFERENCE_NOTICE
from daily_knowledge_learning.ui.pages import TodayPage
from daily_knowledge_learning.ui.sidebar import NAV_ENTRIES
from daily_knowledge_learning.ui.main_window import MainWindow

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "vault_minimal"
REFERENCE = """## 核心定义
定义
## 运行机制
机制
## 现实例子
例子
## 常见混淆
混淆
## 自测问题
问题
"""


class Provider:
    def __init__(self, *, available=True, response="反馈：请补充证据"):
        self.available = available
        self.response = response
        self.calls = 0

    def is_available(self):
        return self.available

    def chat(self, messages):
        self.calls += 1
        return self.response


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication(["ui-ai-tests"])


@pytest.fixture
def vault(tmp_path):
    root = tmp_path / "vault"
    shutil.copytree(FIXTURE_ROOT, root)
    return root


def _session(vault):
    session = start_session(vault, "经济学")
    update_note(session.note_paths.pre_learning, "我认为机会成本是放弃的最佳替代选项。")
    update_note(session.note_paths.post_discussion, "机会成本是做出选择时放弃的最佳替代选项。")
    return session


def test_navigation_contains_notes_and_real_map(app, vault):
    window = MainWindow(vault)
    assert [entry.title for entry in NAV_ENTRIES] == ["首页", "今日学习", "笔记查看", "学习地图", "设置"]
    for entry in NAV_ENTRIES:
        window.sidebar.select(entry.key)
        assert window.sidebar.current_key() == entry.key
    window.sidebar.select("notes")
    assert window.content.notes.topic_list.count() > 0
    window.sidebar.select("map")
    assert window.content.map.content_layout.count() > 0
    window.close()


def test_ai_review_runs_in_worker_and_does_not_write_notes(app, vault, tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    save_config(AppConfig(vault, "mock", "", 30), config_path)
    page = TodayPage(vault, config_path)
    page.session = _session(vault)
    provider = Provider()
    monkeypatch.setattr("daily_knowledge_learning.ui.pages.get_provider", lambda *args, **kwargs: provider)
    before = {path: path.read_bytes() for path in page.session.note_paths.folder.glob("*.md")}
    loop = QEventLoop()
    page.ai_completed.connect(lambda *_: loop.quit())
    QTimer.singleShot(5000, loop.quit)
    page.review_pre_learning()
    loop.exec()
    assert not page._thread_pool.activeThreadCount(), (page.ai_status.text(), len(page._workers))
    app.processEvents()
    page._thread_pool.waitForDone(5000)
    app.processEvents()
    assert page.ai_feedback.toPlainText() == "反馈：请补充证据"
    assert {path: path.read_bytes() for path in page.session.note_paths.folder.glob("*.md")} == before
    page.close()


def test_unavailable_ai_shows_editable_fallback(app, vault, tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    save_config(AppConfig(vault, "mock", "", 30), config_path)
    page = TodayPage(vault, config_path)
    page.session = _session(vault)
    monkeypatch.setattr("daily_knowledge_learning.ui.pages.get_provider", lambda *args, **kwargs: Provider(available=False))
    page.review_pre_learning()
    assert "尚未配置 AI 服务" in page.ai_status.text()
    page.close()


def test_reference_generation_cancel_does_not_call_provider_or_write(app, vault, tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    save_config(AppConfig(vault, "mock", "", 30), config_path)
    page = TodayPage(vault, config_path)
    page.session = _session(vault)
    provider = Provider(response=REFERENCE)
    monkeypatch.setattr("daily_knowledge_learning.ui.pages.get_provider", lambda *args, **kwargs: provider)
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.No)
    before = page.session.note_paths.ai_reference.read_bytes()
    page.generate_reference()
    assert provider.calls == 0
    assert page.session.note_paths.ai_reference.read_bytes() == before
    page.close()


def test_confirmed_reference_is_written_with_ai_notice(app, vault, tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    save_config(AppConfig(vault, "mock", "", 30), config_path)
    page = TodayPage(vault, config_path)
    page.session = _session(vault)
    provider = Provider(response=REFERENCE)
    monkeypatch.setattr("daily_knowledge_learning.ui.pages.get_provider", lambda *args, **kwargs: provider)
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    loop = QEventLoop()
    page.ai_completed.connect(lambda *_: loop.quit())
    QTimer.singleShot(5000, loop.quit)
    page.generate_reference()
    loop.exec()
    page._thread_pool.waitForDone(5000)
    assert not page._thread_pool.activeThreadCount(), (page.ai_status.text(), len(page._workers))
    content = page.session.note_paths.ai_reference.read_text(encoding="utf-8")
    assert _AI_REFERENCE_NOTICE in content
    assert all(section in content for section in ("核心定义", "运行机制", "现实例子", "常见混淆", "自测问题"))
    page.close()
