from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from daily_knowledge_learning import archive
from daily_knowledge_learning.archive import (
    ArchiveError,
    append_final_summary,
    append_knowledge_card,
    archive_topic,
    mark_topic_completed,
    update_map_status,
)
from daily_knowledge_learning.note_manager import TopicNotePaths, create_topic_notes
from daily_knowledge_learning.yaml_utils import parse_frontmatter

SUMMARY = "沉没成本是已经发生且无法收回的成本，不应影响后续决策。"
CARD = "- 定义：已付出、无法收回的成本\n- 决策要点：只看边际收益与边际成本"


def _resolved_link(vault: Path, notes: TopicNotePaths) -> str:
    """Vault-relative folder link exactly as ``archive.update_map_status`` writes it."""
    return notes.folder.relative_to(vault).as_posix()

ECON_MAP = """# 经济学学习路线与已学索引

| 日期 | 主题 | 状态 | 完成日期 | 笔记 |
| --- | --- | --- | --- | --- |
| 2026-09-22 | 机会成本 | 已完成 | 2026-09-22 | 经济学/每日记录/2026-09-22-机会成本 |
| 2026-10-01 | 沉没成本 | 进行中 |  |  |
| 2026-10-05 | 边际效用 | 待学习 |  |  |
"""

PSY_MAP = """# 心理学学习地图与进度

| 周 | 主题 | 状态 |
| --- | --- | --- |
| 2 | 工作记忆 | 待学习 |
"""

PSY_LIST_MAP = """# 心理学学习地图与进度

## 第 1 周

- [x] 注意力
- [ ] 工作记忆
- 待学习 记忆
"""


def _vault(tmp_path: Path) -> tuple[Path, TopicNotePaths]:
    created = create_topic_notes(tmp_path, "经济学", "沉没成本", "我的初步理解")
    return tmp_path, created


def _write_map(vault: Path, text: str = ECON_MAP, subject: str = "经济学") -> Path:
    path = vault / subject / archive.MAP_FILES[subject]
    path.parent.mkdir(parents=True, exist_ok=True)
    # Windows text mode would turn "\n" into "\r\n"; keep exact fixtures.
    path.write_bytes(text.encode("utf-8"))
    return path


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_full_archive_updates_all_targets(tmp_path: Path) -> None:
    vault, notes = _vault(tmp_path)
    map_path = _write_map(vault)

    result = archive_topic(
        vault, "经济学", notes, SUMMARY, CARD, completion_confirmed=True
    )

    assert result.succeeded, result.failed_steps
    assert [step.name for step in result.steps] == [
        "更新主题状态",
        "追加 AI 最终总结",
        "更新知识卡片",
        "更新学习地图",
    ]

    post = notes.post_discussion.read_text(encoding="utf-8")
    meta = parse_frontmatter(post)
    assert meta["status"] == "已完成"
    assert meta["completion_date"] == date.today().isoformat()
    assert "## AI 最终总结" in post
    assert post.startswith("---\n")
    assert post.index("## AI 最终总结") > post.index("status: 已完成")

    pre = notes.pre_learning.read_text(encoding="utf-8")
    assert SUMMARY in pre
    assert pre.rstrip().endswith(SUMMARY)
    assert parse_frontmatter(pre)["topic"] == "沉没成本"

    cards = (vault / "经济学" / "知识卡片.md").read_text(encoding="utf-8")
    assert "## 沉没成本" in cards
    assert CARD in cards
    assert f"_归档于 {date.today().isoformat()}_" in cards

    index_text = map_path.read_text(encoding="utf-8")
    assert "2026-10-01 | 沉没成本 | 已完成" in index_text
    assert (
        f"2026-10-01 | 沉没成本 | 已完成 | {date.today().isoformat()} "
        f"| {_resolved_link(vault, notes)} |"
    ) in index_text
    # Untouched rows keep their original state.
    assert "2026-10-05 | 边际效用 | 待学习" in index_text
    assert "2026-09-22 | 机会成本 | 已完成" in index_text
    # The separator row is untouched.
    assert "| --- | --- | --- | --- | --- |" in index_text


def test_unconfirmed_archive_is_refused_and_writes_nothing(tmp_path: Path) -> None:
    vault, notes = _vault(tmp_path)
    _write_map(vault)
    before = _snapshot(vault)

    with pytest.raises(ArchiveError) as caught:
        archive_topic(vault, "经济学", notes, SUMMARY, CARD, completion_confirmed=False)
    assert caught.value.step == "归档主题"
    assert "确认" in caught.value.reason

    assert _snapshot(vault) == before


@pytest.mark.parametrize(
    ("call", "step"),
    [
        (lambda p: mark_topic_completed(p, completion_confirmed=False), "更新主题状态"),
        (
            lambda p: append_final_summary(p, SUMMARY, completion_confirmed=False),
            "追加 AI 最终总结",
        ),
    ],
)
def test_unconfirmed_step_functions_are_refused(tmp_path: Path, call: Any, step: str) -> None:
    _, notes = _vault(tmp_path)
    before = _snapshot(notes.folder)
    with pytest.raises(ArchiveError) as caught:
        call(notes)
    assert caught.value.step == step
    assert _snapshot(notes.folder) == before


def test_unconfirmed_card_and_map_are_refused(tmp_path: Path) -> None:
    vault, notes = _vault(tmp_path)
    _write_map(vault)
    before = _snapshot(vault)

    with pytest.raises(ArchiveError):
        append_knowledge_card(
            vault, "经济学", "沉没成本", CARD, completion_confirmed=False
        )
    assert _snapshot(vault) == before

    # The map step itself has no confirmation flag; archive_topic gates it.
    assert _snapshot(vault) == before
    with pytest.raises(ArchiveError):
        archive_topic(vault, "经济学", notes, SUMMARY, CARD, completion_confirmed=False)
    assert "进行中" in (vault / "经济学" / archive.MAP_FILES["经济学"]).read_text(
        encoding="utf-8"
    )


def test_repeat_archive_is_idempotent(tmp_path: Path) -> None:
    vault, notes = _vault(tmp_path)
    map_path = _write_map(vault)

    first = archive_topic(vault, "经济学", notes, SUMMARY, CARD, completion_confirmed=True)
    assert first.succeeded, first.failed_steps
    after_first = _snapshot(vault)

    second = archive_topic(vault, "经济学", notes, SUMMARY, CARD, completion_confirmed=True)

    assert second.succeeded, second.failed_steps
    assert _snapshot(vault) == after_first
    links = [step for step in second.steps if step.name != "更新主题状态"]
    assert all(step.changed is False for step in links), links
    assert date.today().isoformat() in map_path.read_text(encoding="utf-8")
    assert map_path.read_text(encoding="utf-8").count("| 沉没成本 |") == 1
    # Rewriting the frontmatter changes its formatting but not its values.
    post = notes.post_discussion.read_text(encoding="utf-8")
    assert post.count("completion_date:") == 1
    assert parse_frontmatter(post)["completion_date"] == date.today().isoformat()


def test_repeat_archive_on_later_day_does_not_duplicate_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault, notes = _vault(tmp_path)
    _write_map(vault)
    archive.archive_topic(vault, "经济学", notes, SUMMARY, CARD, completion_confirmed=True)
    before = _snapshot(vault)

    class LaterDate:
        @staticmethod
        def today() -> date:
            return date(2030, 1, 1)

    monkeypatch.setattr(archive, "date", LaterDate)
    result = archive.archive_topic(
        vault, "经济学", notes, SUMMARY, CARD, completion_confirmed=True
    )

    assert result.succeeded, result.failed_steps
    assert _snapshot(vault) == before


def test_knowledge_card_is_created_when_missing(tmp_path: Path) -> None:
    vault, notes = _vault(tmp_path)
    card_path = vault / "心理学" / "知识卡片.md"
    assert not card_path.exists()

    assert append_knowledge_card(
        vault, "心理学", "工作记忆", CARD, completion_confirmed=True
    )
    assert card_path.exists()
    text = card_path.read_text(encoding="utf-8")
    assert text.startswith("---\nsubject: 心理学\n")
    assert "## 工作记忆" in text

    assert not append_knowledge_card(
        vault, "心理学", "工作记忆", CARD, completion_confirmed=True
    )
    assert card_path.read_text(encoding="utf-8") == text


def test_missing_map_file_does_not_break_archive(tmp_path: Path) -> None:
    vault, notes = _vault(tmp_path)

    result = archive_topic(vault, "经济学", notes, SUMMARY, CARD, completion_confirmed=True)

    # A missing map is a warning: the archive still succeeds overall.
    assert result.succeeded, result.failed_steps
    assert [step.name for step in result.warnings] == ["更新学习地图"]
    assert "未找到学习地图文件" in result.warnings[0].message
    # The other steps still landed.
    assert parse_frontmatter(notes.post_discussion.read_text(encoding="utf-8"))["status"] == "已完成"
    assert (vault / "经济学" / "知识卡片.md").exists()


def test_missing_topic_row_is_a_warning_step(tmp_path: Path) -> None:
    vault, notes = _vault(tmp_path)
    _write_map(vault, ECON_MAP.replace("沉没成本", "其他主题"))

    result = archive_topic(vault, "经济学", notes, SUMMARY, CARD, completion_confirmed=True)

    assert result.succeeded, result.failed_steps
    assert [step.name for step in result.warnings] == ["更新学习地图"]
    assert "沉没成本" in result.warnings[0].message


def test_three_column_map_keeps_status_column_count(tmp_path: Path) -> None:
    vault = tmp_path
    map_path = _write_map(vault, PSY_MAP, subject="心理学")
    notes = create_topic_notes(vault, "心理学", "工作记忆")

    result = archive_topic(
        vault, "心理学", notes, SUMMARY, CARD, completion_confirmed=True
    )

    assert result.succeeded, result.failed_steps
    row = next(
        line
        for line in map_path.read_text(encoding="utf-8").splitlines()
        if "工作记忆" in line
    )
    assert row.count("|") == 6
    assert "| 已完成 |" in row
    assert date.today().isoformat() in row
    assert f"[[{_resolved_link(vault, notes)}]]" in row
    assert row.index("| 已完成 |") < row.index(date.today().isoformat())


def test_list_map_marks_checkbox_completed(tmp_path: Path) -> None:
    vault = tmp_path
    map_path = _write_map(vault, PSY_LIST_MAP, subject="心理学")
    notes = create_topic_notes(vault, "心理学", "工作记忆")

    result = archive_topic(
        vault, "心理学", notes, SUMMARY, CARD, completion_confirmed=True
    )

    assert result.succeeded, result.failed_steps
    text = map_path.read_text(encoding="utf-8")
    assert "- [x] 注意力" in text  # untouched
    assert (
        f"- [x] 工作记忆 已完成 {date.today().isoformat()} "
        f"[[{_resolved_link(vault, notes)}]]"
    ) in text
    assert "- 待学习 记忆" in text


def test_summary_is_appended_to_both_versions(tmp_path: Path) -> None:
    _, notes = _vault(tmp_path)

    append_final_summary(notes, SUMMARY, completion_confirmed=True)
    append_final_summary(notes, SUMMARY, completion_confirmed=True)

    for path in (notes.pre_learning, notes.post_discussion):
        text = path.read_text(encoding="utf-8")
        assert text.count("## AI 最终总结") == 1
        assert text.count(SUMMARY) == 1
        assert "---\n\n## AI 最终总结\n\n" + SUMMARY in text


def test_empty_summary_and_card_are_rejected(tmp_path: Path) -> None:
    vault, notes = _vault(tmp_path)
    with pytest.raises(ArchiveError):
        append_final_summary(notes, "   ", completion_confirmed=True)
    with pytest.raises(ArchiveError):
        append_knowledge_card(
            vault, "经济学", "沉没成本", "", completion_confirmed=True
        )
