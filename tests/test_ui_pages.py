from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from daily_knowledge_learning.config import AppConfig
from daily_knowledge_learning.ui.pages import ContentArea, MarkdownEditor, SettingsPage
from daily_knowledge_learning.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication(["ui-tests"])


def test_invalid_vault_guides_user(app, tmp_path):
    area = ContentArea(tmp_path / "missing", tmp_path / "config.json")
    assert "请先在设置中配置 Vault 路径" in area.home.guide.text()
    assert not area.home.start.isEnabled()


def test_vault_without_learning_map_explains_why_start_is_unavailable(app, tmp_path):
    vault = tmp_path / "unrelated-vault"
    vault.mkdir()
    window = MainWindow(vault, tmp_path / "config.json")
    assert not window.content.home.start.isEnabled()
    assert "没有找到可开始的学习主题" in window.content.home.guide.text()
    window.content.show_key("today")
    assert "没有找到可开始的学习主题" in window.content.today.ai_status.text()
    window.close()


def test_parent_obsidian_vault_resolves_nested_learning_project(app, tmp_path):
    import shutil
    vault = tmp_path / "obsidian"
    project = vault / "每日心理学与经济学学习"
    shutil.copytree(Path(__file__).parent / "fixtures" / "vault_minimal" / "经济学", project / "经济学")
    shutil.copytree(Path(__file__).parent / "fixtures" / "vault_minimal" / "心理学", project / "心理学")
    (project / "心理学" / "心理学学习地图与进度.md").write_text(
        "# 心理学学习地图与进度\n\n## 学习路线\n\n- 工作记忆的容量限制\n", encoding="utf-8"
    )
    (project / "经济学" / "经济学学习路线与已学索引.md").write_text(
        "# 经济学学习路线与已学索引\n\n## 学习路线\n\n- 机会成本\n", encoding="utf-8"
    )
    window = MainWindow(vault, tmp_path / "config.json")
    assert window.content.home.start.isEnabled()
    assert window.content.home.hero_title.text()
    window.close()


def test_settings_provider_selection_supplies_gateway_defaults(app):
    settings = SettingsPage(AppConfig())
    settings.provider.setCurrentIndex(settings.provider.findData("deepseek"))
    assert settings.api_base_url.text() == "https://api.deepseek.com"
    settings.provider.setCurrentIndex(settings.provider.findData("custom"))
    assert settings.api_base_url.text() == ""
    assert "gateway.example.com" in settings.api_base_url.placeholderText()
    settings.provider.setCurrentIndex(settings.provider.findData("anthropic"))
    assert settings.api_base_url.text() == "https://api.anthropic.com"


def test_first_launch_can_open_settings_from_home(app, tmp_path):
    window = MainWindow(config_path=tmp_path / "missing-config.json")
    window.show()
    app.processEvents()
    assert window.content.home.empty_state.isVisible()
    assert not window.content.home.start.isEnabled()
    window.content.home.settings_button.click()
    assert window.content.currentWidget() is window.content.settings
    assert window.sidebar.current_key() == "settings"
    window.close()


def test_starting_study_keeps_editor_open_and_navigation_in_sync(app, tmp_path, monkeypatch):
    import shutil
    from daily_knowledge_learning.config import save_config
    from PySide6.QtCore import QEventLoop, QTimer

    vault = tmp_path / "vault"
    shutil.copytree(Path(__file__).parent / "fixtures" / "vault_minimal", vault)
    from daily_knowledge_learning.study_service import start_session
    session = start_session(vault, "心理学")
    session.note_paths.pre_learning.write_text("", encoding="utf-8")
    config_path = tmp_path / "config.json"
    save_config(AppConfig(vault, "mock", "", 30), config_path)
    window = MainWindow(vault, config_path)
    provider = type("Provider", (), {
        "is_available": lambda self: True,
        "chat": lambda self, messages: (
            "## 今日核心问题\n问题\n## 核心概念\n概念\n## 直观解释\n解释\n"
            "## 运作机制\n机制\n## 具体例子\n例子\n## 适用条件与边界\n边界\n"
            "## 常见误区\n误区\n## 自测问题\n问题"
        ),
    })()
    from daily_knowledge_learning.ui import pages
    monkeypatch.setattr(pages, "get_provider", lambda *args, **kwargs: provider)
    window.content.home.start.click()
    assert window.content.currentWidget() is window.content.today
    assert window.sidebar.current_key() == "today"
    assert window.content.today.start.isEnabled()
    window.content.today.subject.setCurrentText("心理学")
    loop = QEventLoop()
    window.content.today.ai_completed.connect(lambda *_: loop.quit())
    QTimer.singleShot(5000, loop.quit)
    window.content.today.start.click()
    loop.exec()
    window.content.today._thread_pool.waitForDone(5000)
    app.processEvents()
    assert window.content.currentWidget() is window.content.editor
    assert window.sidebar.current_key() == "today"
    assert window.content.editor.folder is not None
    assert not window.content.editor.tabs.isHidden()
    window.close()


def test_home_subject_links_match_the_learning_subject(app, tmp_path):
    import shutil

    vault = tmp_path / "vault"
    shutil.copytree(Path(__file__).parent / "fixtures" / "vault_minimal", vault)
    window = MainWindow(vault, tmp_path / "config.json")
    home = window.content.home
    home.next_topics["经济学"].click()
    assert window.content.today.subject.currentText() == "经济学"
    assert window.content.currentWidget() is window.content.today
    window.content.show_key("home")
    home.start.click()
    assert window.content.today.subject.currentText() == "心理学"
    assert home.hero_title.text() == window.content.today.fields["topic"].text()
    window.close()


def test_home_refreshes_vault_progress_when_reopened(app, tmp_path):
    import shutil

    vault = tmp_path / "vault"
    shutil.copytree(Path(__file__).parent / "fixtures" / "vault_minimal", vault)
    window = MainWindow(vault, tmp_path / "config.json")
    home = window.content.home
    before = home.metrics["心理学"].text()

    completed = vault / "心理学" / "每日记录" / "2026-10-20-新主题"
    completed.mkdir()
    (completed / "02-交流后版.md").write_text(
        "---\nstatus: 已完成\n---\n\n已完成。\n", encoding="utf-8"
    )
    window.content.show_key("notes")
    window.content.show_key("home")

    assert home.metrics["心理学"].text() != before
    assert home.metrics["心理学"].text().startswith("1 /")
    window.close()


def test_vault_qa_runs_in_background_and_renders_citations(app, tmp_path, monkeypatch):
    from daily_knowledge_learning.ui import pages

    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "心理学" / "记录.md"
    note.parent.mkdir()
    note.write_text("# 工作记忆\n\n工作记忆容量有限。", encoding="utf-8")
    config = AppConfig(vault, "openai", "gpt-test", 30)
    window = MainWindow(vault, tmp_path / "config.json")
    page = window.content.vault_qa
    page.config = config
    provider = type("Provider", (), {
        "is_available": lambda self: True,
        "chat": lambda self, messages: "笔记指出工作记忆容量有限 [1]。",
    })()
    monkeypatch.setattr(pages, "get_provider", lambda *args, **kwargs: provider)
    page.question.setPlainText("工作记忆")
    page.ask_question()
    page._thread_pool.waitForDone(5000)
    app.processEvents()
    assert "[1]" in page.answer.toPlainText()
    assert page.sources.count() == 1
    from PySide6.QtCore import Qt
    assert page.sources.item(0).data(Qt.ItemDataRole.UserRole) == "心理学/记录.md"
    window.close()


def test_editor_loads_and_saves_note_without_replacing_frontmatter(app, tmp_path):
    folder = tmp_path / "2026-10-18-topic"
    folder.mkdir()
    note = folder / "01-交流前版.md"
    note.write_text("---\ntopic: topic\nstatus: 进行中\n---\n\n初始正文", encoding="utf-8")
    editor = MarkdownEditor(AppConfig(auto_save_interval=30))
    editor.load_topic(folder)
    assert "初始正文" in editor.editors[0].toPlainText()
    editor.editors[0].setPlainText("更新正文")
    assert editor.save_current()
    saved = note.read_text(encoding="utf-8")
    assert "topic: topic" in saved and "status: 进行中" in saved and "更新正文" in saved
    assert "已保存于" in editor.status.text()
