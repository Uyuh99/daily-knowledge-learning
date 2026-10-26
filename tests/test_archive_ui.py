from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialogButtonBox

from daily_knowledge_learning import archive
from daily_knowledge_learning.ai_provider import MockProvider
from daily_knowledge_learning.file_writer import update_note
from daily_knowledge_learning.note_manager import create_topic_notes
from daily_knowledge_learning.ui.archive_dialog import ArchiveDialog
from daily_knowledge_learning.yaml_utils import parse_frontmatter


SUBJECT = archive.SUBJECTS[0]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication(["archive-ui-tests"])


def _session(vault: Path):
    notes = create_topic_notes(vault, SUBJECT, "沉没成本")
    update_note(notes.post_discussion, "我现在会比较未来的增量收益与成本，而不是追回过去投入。")
    return SimpleNamespace(topic="沉没成本", note_paths=notes)


def _map(vault: Path, topic: str = "沉没成本") -> None:
    path = vault / SUBJECT / archive.MAP_FILES[SUBJECT]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"| 主题 | 状态 |\n| --- | --- |\n| {topic} | 待学习 |\n", encoding="utf-8")


def _dialog(app, vault: Path, provider=None) -> ArchiveDialog:
    session = _session(vault)
    _map(vault)
    return ArchiveDialog(None, vault_path=vault, subject=SUBJECT, session=session, provider=provider or MockProvider(["最终总结。关键定义。应用提醒。"]))


def test_dialog_constructs_with_topic_and_summary_draft(app, tmp_path):
    dialog = _dialog(app, tmp_path)
    assert "沉没成本" in dialog.topic_label.text()
    assert "最终总结" in dialog.summary.toPlainText()


def test_cancel_does_not_write(app, tmp_path):
    dialog = _dialog(app, tmp_path)
    before = {p.relative_to(tmp_path).as_posix(): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    dialog.reject()
    after = {p.relative_to(tmp_path).as_posix(): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after
    assert not dialog.archived


def test_confirm_archives_and_updates_status_and_card(app, tmp_path):
    dialog = _dialog(app, tmp_path)
    dialog._confirm_archive()
    assert dialog.archived
    assert parse_frontmatter(dialog.session.note_paths.post_discussion.read_text(encoding="utf-8"))["status"] == archive.DONE
    card = tmp_path / SUBJECT / archive.KNOWLEDGE_CARD_FILE
    assert "## 沉没成本" in card.read_text(encoding="utf-8")


def test_archive_requires_saved_personal_post_discussion(app, tmp_path):
    dialog = _dialog(app, tmp_path)
    update_note(dialog.session.note_paths.post_discussion, "")

    dialog._confirm_archive()

    assert not dialog.archived
    assert "先在「交流后版」写下并保存" in dialog.result.text()
    assert parse_frontmatter(dialog.session.note_paths.post_discussion.read_text(encoding="utf-8"))["status"] == "进行中"
    assert not (tmp_path / SUBJECT / archive.KNOWLEDGE_CARD_FILE).exists()


def test_partial_failure_warning_is_shown(app, tmp_path, monkeypatch):
    dialog = _dialog(app, tmp_path)
    expected = archive.ArchiveResult(
        "沉没成本",
        "2026-10-18",
        (archive.StepResult("更新学习地图", True, message="学习地图未找到该主题行"),),
    )
    monkeypatch.setattr(archive, "archive_topic", lambda *args, **kwargs: expected)
    dialog._confirm_archive()
    assert dialog.archived
    assert "警告" in dialog.result.text()
    assert "学习地图未找到该主题行" in dialog.result.text()


def test_existing_archive_is_read_only_and_not_repeated(app, tmp_path):
    first = _dialog(app, tmp_path)
    first._confirm_archive()
    second = ArchiveDialog(None, vault_path=tmp_path, subject=SUBJECT, session=first.session, provider=MockProvider())
    assert "已标记为完成" in second.result.text()
    assert not second.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    assert second.summary.isReadOnly()
