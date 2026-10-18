from pathlib import Path

import pytest

from daily_knowledge_learning.note_manager import (
    append_ai_reference,
    create_topic_notes,
    update_post_discussion_note,
    update_pre_learning_note,
)
from daily_knowledge_learning.file_writer import NoteConflictError
from daily_knowledge_learning import note_manager


def test_create_notes_with_initial_content(tmp_path: Path) -> None:
    notes = create_topic_notes(tmp_path, "经济学", "机会成本", "My notes")
    assert notes.pre_learning.exists() and notes.post_discussion.exists() and notes.ai_reference.exists()
    assert "My notes" in notes.pre_learning.read_text(encoding="utf-8")


def test_create_empty_notes(tmp_path: Path) -> None:
    notes = create_topic_notes(tmp_path, "心理学", "工作记忆")
    assert notes.pre_learning.read_text(encoding="utf-8").endswith("---\n\n")


def test_existing_topic_is_not_overwritten(tmp_path: Path) -> None:
    notes = create_topic_notes(tmp_path, "经济学", "稀缺性", "valuable")
    with pytest.raises(FileExistsError):
        create_topic_notes(tmp_path, "经济学", "稀缺性", "replacement")
    assert "valuable" in notes.pre_learning.read_text(encoding="utf-8")


def test_create_rollback_preserves_a_raced_in_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_create = note_manager.create_note
    calls = 0

    def fail_after_race(path: Path, content: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            real_create(path, content)
            return
        path.write_text("raced in", encoding="utf-8")
        raise NoteConflictError(path, "file already exists")

    monkeypatch.setattr(note_manager, "create_note", fail_after_race)
    with pytest.raises(NoteConflictError):
        note_manager.create_topic_notes(tmp_path, "经济学", "race")

    folders = list((tmp_path / "经济学").iterdir())
    assert len(folders) == 1
    assert (folders[0] / "02-交流后版.md").read_text(encoding="utf-8") == "raced in"
    assert not (folders[0] / "01-学习前版.md").exists()


def test_invalid_subject_and_topic_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        create_topic_notes(tmp_path, "history", "topic")
    with pytest.raises(ValueError):
        create_topic_notes(tmp_path, "心理学", "../outside")


def test_update_pre_learning_preserves_yaml(tmp_path: Path) -> None:
    notes = create_topic_notes(tmp_path, "心理学", "注意力")
    update_pre_learning_note(notes.pre_learning, "Updated understanding")
    contents = notes.pre_learning.read_text(encoding="utf-8")
    assert "topic: 注意力" in contents
    assert contents.endswith("Updated understanding")


def test_update_post_discussion_without_completion(tmp_path: Path) -> None:
    notes = create_topic_notes(tmp_path, "心理学", "记忆")
    update_post_discussion_note(notes.post_discussion, "Revised explanation")
    contents = notes.post_discussion.read_text(encoding="utf-8")
    assert "status: 进行中" in contents
    assert "Revised explanation" in contents


def test_update_post_discussion_marks_completion(tmp_path: Path) -> None:
    notes = create_topic_notes(tmp_path, "经济学", "激励")
    update_post_discussion_note(notes.post_discussion, "Final notes", mark_completed=True)
    contents = notes.post_discussion.read_text(encoding="utf-8")
    assert "status: 已完成" in contents
    assert "completion_date:" in contents
    assert "Final notes" in contents


def test_ai_reference_append_is_idempotent(tmp_path: Path) -> None:
    notes = create_topic_notes(tmp_path, "经济学", "边际效用")
    assert append_ai_reference(notes.ai_reference, "Reference content") is True
    assert append_ai_reference(notes.ai_reference, "Reference content") is False
    assert notes.ai_reference.read_text(encoding="utf-8").count("Reference content") == 1


def test_ai_reference_rejects_empty_content(tmp_path: Path) -> None:
    notes = create_topic_notes(tmp_path, "经济学", "供需")
    with pytest.raises(ValueError):
        append_ai_reference(notes.ai_reference, "  ")
