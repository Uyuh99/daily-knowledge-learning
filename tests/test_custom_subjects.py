from pathlib import Path

from daily_knowledge_learning.archive import archive_topic
from daily_knowledge_learning.map_parser import parse_learning_map
from daily_knowledge_learning.note_manager import create_topic_notes, update_post_discussion_note
from daily_knowledge_learning.subjects import create_custom_subject
from daily_knowledge_learning.topic_selector import select_next_topic
from daily_knowledge_learning.vault_scan import scan_vault


def test_custom_subject_creates_editable_route_and_is_scanned(tmp_path: Path) -> None:
    create_custom_subject(tmp_path, "历史", ["时间线", "史料"])
    study_map = parse_learning_map(tmp_path, "历史")
    assert [topic.name for topic in study_map.modules[0].topics] == ["时间线", "史料"]
    notes = create_topic_notes(tmp_path, "历史", "时间线")
    assert notes.folder.is_dir()
    assert any(record.subject == "历史" for record in scan_vault(tmp_path))


def test_custom_subject_progresses_through_selection_and_archive(tmp_path: Path) -> None:
    create_custom_subject(tmp_path, "历史", ["时间线", "史料"])

    first = select_next_topic(tmp_path, "历史")
    assert first.topic == "时间线"
    notes = create_topic_notes(tmp_path, "历史", first.topic)
    update_post_discussion_note(notes.post_discussion, "完成交流。", mark_completed=True)

    result = archive_topic(
        tmp_path,
        "历史",
        notes,
        "总结内容",
        "卡片内容",
        completion_confirmed=True,
    )

    assert result.succeeded, result.failed_steps
    assert select_next_topic(tmp_path, "历史").topic == "史料"
    map_text = (tmp_path / "历史" / "历史学习地图.md").read_text(encoding="utf-8")
    assert "已完成" in map_text
