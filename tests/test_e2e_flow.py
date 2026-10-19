from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialogButtonBox

from daily_knowledge_learning import archive
from daily_knowledge_learning.ai_provider import MockProvider
from daily_knowledge_learning.file_writer import update_note
from daily_knowledge_learning.models import TopicStatus
from daily_knowledge_learning.study_service import start_session
from daily_knowledge_learning.ui.archive_dialog import ArchiveDialog
from daily_knowledge_learning.ui.main_window import MainWindow
from daily_knowledge_learning.yaml_utils import parse_frontmatter


FIXTURE = Path(__file__).parent / "fixtures" / "vault_minimal"
SUMMARY = "最终总结。关键定义。应用提醒。"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication(["e2e-flow-tests"])


@pytest.fixture
def vault(tmp_path):
    root = tmp_path / "vault"
    shutil.copytree(FIXTURE, root)
    return root


def test_archive_flow_refreshes_existing_pages_and_is_idempotent(app, vault, monkeypatch):
    window = MainWindow(vault)
    today = window.content.today
    today.subject.setCurrentIndex(1)
    today.start_learning()
    session = today.session
    assert session is not None

    update_note(session.note_paths.pre_learning, "交流前版本。")
    update_note(session.note_paths.post_discussion, "交流后版本。")
    update_note(session.note_paths.ai_reference, "AI 参考版本。")

    editor = window.content.editor
    editor.load_topic(session.note_paths.folder)
    editor.editors[0].setPlainText("未保存的编辑器内容")
    editor._dirty.add(0)
    notes_widget, map_widget = window.content.notes, window.content.map
    observed = []
    today.archive_completed.connect(lambda: observed.append(True))

    class ConfirmArchive:
        def __init__(self, parent, **kwargs):
            kwargs["provider"] = MockProvider([SUMMARY])
            self.dialog = ArchiveDialog(parent, **kwargs)
            self.archive_completed = self.dialog.archive_completed

        def exec(self):
            self.dialog.summary.setPlainText(SUMMARY)
            self.dialog._confirm_archive()

    monkeypatch.setattr("daily_knowledge_learning.ui.pages.ArchiveDialog", ConfirmArchive)
    today.archive_button.click()

    assert observed == [True]
    assert today.archive_button.text() == "查看归档结果"
    assert not today.archive_button.isEnabled()
    assert parse_frontmatter(session.note_paths.post_discussion.read_text(encoding="utf-8"))["status"] == archive.DONE
    assert SUMMARY in session.note_paths.pre_learning.read_text(encoding="utf-8")
    assert SUMMARY in session.note_paths.post_discussion.read_text(encoding="utf-8")
    assert "## " + session.topic in (vault / session.subject / archive.KNOWLEDGE_CARD_FILE).read_text(encoding="utf-8")
    assert window.content.notes is notes_widget
    assert window.content.map is map_widget
    assert editor.is_dirty()
    assert editor.editors[0].toPlainText() == "未保存的编辑器内容"

    before = (vault / session.subject / archive.KNOWLEDGE_CARD_FILE).read_text(encoding="utf-8")
    duplicate = ArchiveDialog(None, vault_path=vault, subject=session.subject, session=session, provider=MockProvider())
    assert not duplicate.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    duplicate._confirm_archive()
    after = (vault / session.subject / archive.KNOWLEDGE_CARD_FILE).read_text(encoding="utf-8")
    assert after == before

    refreshed = window.content.map
    assert refreshed is map_widget
    editor._dirty.clear()
    window.close()
