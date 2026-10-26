from datetime import date

from daily_knowledge_learning.review_service import complete_review, due_reviews


def test_due_reviews_skip_checked_items_and_mark_original_note(tmp_path):
    note = tmp_path / "每日心理学与经济学学习" / "心理学" / "每日记录" / "2026-10-01-记忆" / "01-交流前版.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "# 记忆\n\n## 间隔复习\n\n"
        "- [x] 第 1 天：不看答案复述\n"
        "- [ ] 第 3 天：举一个新例子\n"
        "- [ ] 第 7 天：解释边界和相近概念\n\n## 其他\n结束\n",
        encoding="utf-8",
    )

    tasks = due_reviews(tmp_path, today=date(2026, 10, 8))

    assert [task.interval_days for task in tasks] == [3, 7]
    assert tasks[0].instruction == "举一个新例子"
    complete_review(tasks[0])
    saved = note.read_text(encoding="utf-8")
    assert "- [x] 第 3 天：举一个新例子" in saved
    assert "## 其他\n结束" in saved
    assert [task.interval_days for task in due_reviews(tmp_path, today=date(2026, 10, 8))] == [7]


def test_due_reviews_ignore_incomplete_schedule_and_future_items(tmp_path):
    note = tmp_path / "心理学" / "每日记录" / "2026-10-07-注意" / "01-学习前版.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "## 间隔复习\n- [ ] 第 1 天：已经到期\n- [ ] 第 3 天：以后再做\n",
        encoding="utf-8",
    )

    assert [task.interval_days for task in due_reviews(tmp_path, today=date(2026, 10, 8))] == [1]
