from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from daily_knowledge_learning.config import AppConfig
from daily_knowledge_learning.ui.pages import ContentArea, MarkdownEditor


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication(["ui-tests"])


def test_invalid_vault_guides_user(app, tmp_path):
    area = ContentArea(tmp_path / "missing", tmp_path / "config.json")
    assert "请先在设置中配置 Vault 路径" in area.home.guide.text()
    assert not area.home.start.isEnabled()


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
