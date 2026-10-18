from datetime import date
from pathlib import Path

import pytest

from daily_knowledge_learning.archive import (
    ArchiveError,
    append_final_summary,
    append_knowledge_card,
    archive_topic,
    mark_topic_completed,
    update_map_status,
)
from daily_knowledge_learning.note_manager import TopicNotePaths, create_topic_notes


SUBJECT = "???"
TOPIC = "????"


def _notes(vault: Path) -> TopicNotePaths:
    return create_topic_notes(vault, SUBJECT, TOPIC, "Initial thoughts")


def _map(vault: Path) -> Path:
    path = vault / SUBJECT / "????????????.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"| {TOPIC} | ??? | ??? |\n", encoding="utf-8")
    return path


def test_archive_topic_completes_all_steps_in_temporary_vault(tmp_path: Path) -> None:
    notes = _notes(tmp_path)
    map_path = _map(tmp_path)

    result = archive_topic(
        tmp_path, SUBJECT, notes, "A final synthesis.", "Opportunity cost is the next best alternative.",
        completion_confirmed=True,
    )

    assert result.successful
    assert set(result.steps) == {"topic_status", "final_summary", "knowledge_card", "learning_map"}
    assert "status: ???" in notes.post_discussion.read_text(encoding="utf-8")
    assert "completion_date:" in notes.post_discussion.read_text(encoding="utf-8")
    assert "## AI ????" in notes.pre_learning.read_text(encoding="utf-8")
    assert "## AI ????" in notes.post_discussion.read_text(encoding="utf-8")
    assert "## ????" in (tmp_path / SUBJECT / "????.md").read_text(encoding="utf-8")
    assert "???" in map_path.read_text(encoding="utf-8")
    assert "????" in map_path.read_text(encoding="utf-8")


def test_unconfirmed_completion_is_rejected(tmp_path: Path) -> None:
    notes = _notes(tmp_path)
    with pytest.raises(ArchiveError, match="explicitly confirmed"):
        mark_topic_completed(notes, completion_confirmed=False)
    with pytest.raises(ArchiveError, match="explicitly confirmed"):
        append_final_summary(notes, "summary", completion_confirmed=False)
    with pytest.raises(ArchiveError, match="explicitly confirmed"):
        append_knowledge_card(tmp_path, SUBJECT, TOPIC, "card", completion_confirmed=False)

    result = archive_topic(tmp_path, SUBJECT, notes, "summary", "card", completion_confirmed=False)
    assert result.errors["confirmation"]
    assert "AI ????" not in notes.pre_learning.read_text(encoding="utf-8")


def test_archive_is_idempotent_even_when_repeated_on_a_later_day(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import daily_knowledge_learning.archive as archive

    notes = _notes(tmp_path)
    _map(tmp_path)
    archive.archive_topic(tmp_path, SUBJECT, notes, "Summary once.", "Card once.", completion_confirmed=True)
    first_card = (tmp_path / SUBJECT / "????.md").read_text(encoding="utf-8")
    monkeypatch.setattr(archive, "date", type("LaterDate", (), {"today": staticmethod(lambda: __import__("datetime").date(2030, 1, 1)), "fromisoformat": staticmethod(__import__("datetime").date.fromisoformat)}))
    archive.archive_topic(tmp_path, SUBJECT, notes, "Summary once.", "Card once.", completion_confirmed=True)

    assert notes.pre_learning.read_text(encoding="utf-8").count("Summary once.") == 1
    assert notes.post_discussion.read_text(encoding="utf-8").count("Summary once.") == 1
    assert (tmp_path / SUBJECT / "????.md").read_text(encoding="utf-8") == first_card


def test_card_file_is_created_when_missing(tmp_path: Path) -> None:
    append_knowledge_card(tmp_path, SUBJECT, TOPIC, "Short card.", completion_confirmed=True)
    card = tmp_path / SUBJECT / "????.md"
    assert card.exists()
    assert "Short card." in card.read_text(encoding="utf-8")


def test_missing_learning_map_does_not_fail_archive(tmp_path: Path) -> None:
    notes = _notes(tmp_path)
    result = archive_topic(tmp_path, SUBJECT, notes, "Summary", "Card", completion_confirmed=True)
    assert result.successful
    assert result.steps["learning_map"].startswith("skipped")


def test_three_column_map_preserves_status_and_appends_date_and_link(tmp_path: Path) -> None:
    notes = _notes(tmp_path)
    path = _map(tmp_path)
    path.write_text(
        "| \u5468 | \u4e3b\u9898 | \u72b6\u6001 |\n"
        "| --- | --- | --- |\n"
        f"| 2 | {TOPIC} | \u5f85\u5b66\u4e60 |\n",
        encoding="utf-8",
    )

    update_map_status(tmp_path, SUBJECT, TOPIC, notes)
    row = path.read_text(encoding="utf-8").splitlines()[-1]
    cells = [cell.strip() for cell in row.strip("|").split("|")]

    assert cells[2] == "\u5df2\u5b8c\u6210"
    assert cells[3] == date.today().isoformat()
    assert TOPIC in cells[4]
    assert len(cells) == 5


def test_append_final_summary_updates_both_note_versions(tmp_path: Path) -> None:
    notes = _notes(tmp_path)
    append_final_summary(notes, "Shared summary.", completion_confirmed=True)
    assert "Shared summary." in notes.pre_learning.read_text(encoding="utf-8")
    assert "Shared summary." in notes.post_discussion.read_text(encoding="utf-8")
