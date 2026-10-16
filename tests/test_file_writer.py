from pathlib import Path

import pytest

from daily_knowledge_learning.file_writer import (
    NoteConflictError,
    NoteNotFoundError,
    append_to_note,
    create_note,
    update_note,
)


def test_create_update_and_preserve_frontmatter(tmp_path: Path) -> None:
    path = tmp_path / "note.md"
    create_note(path, "---\ntopic: one\n---\n\nold body")
    update_note(path, "new body")
    assert path.read_text(encoding="utf-8") == "---\ntopic: one\n---\n\nnew body"


def test_callable_update_receives_complete_document(tmp_path: Path) -> None:
    path = tmp_path / "note.md"
    create_note(path, "initial")
    update_note(path, lambda text: text + " changed")
    assert path.read_text(encoding="utf-8") == "initial changed"


def test_create_does_not_overwrite_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "note.md"
    path.write_text("valuable", encoding="utf-8")
    with pytest.raises(NoteConflictError):
        create_note(path, "replacement")
    assert path.read_text(encoding="utf-8") == "valuable"


def test_append_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "note.md"
    create_note(path, "initial")
    assert append_to_note(path, "block") is True
    assert append_to_note(path, "block") is False
    assert path.read_text(encoding="utf-8") == "initial\nblock"


def test_missing_file_has_specific_error(tmp_path: Path) -> None:
    with pytest.raises(NoteNotFoundError, match="missing.md"):
        update_note(tmp_path / "missing.md", "body")


def test_update_detects_concurrent_modification(tmp_path: Path) -> None:
    path = tmp_path / "note.md"
    create_note(path, "before")

    def race(_: str) -> str:
        path.write_text("changed by another writer", encoding="utf-8")
        return "our update"

    with pytest.raises(NoteConflictError):
        update_note(path, race)
    assert path.read_text(encoding="utf-8") == "changed by another writer"
