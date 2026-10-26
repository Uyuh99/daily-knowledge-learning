from datetime import date

from daily_knowledge_learning.stats_service import calculate_stats


def _completed(root, day: str, topic: str, *, with_review: bool = False) -> None:
    folder = root / "心理学" / "每日记录" / f"{day}-{topic}"
    folder.mkdir(parents=True)
    if with_review:
        (folder / "01-交流前版.md").write_text(
            "## 间隔复习\n\n- [ ] 第 1 天：不看答案复述\n", encoding="utf-8"
        )
    (folder / "02-交流后版.md").write_text(
        "---\nstatus: 已完成\n---\n\n完成。\n", encoding="utf-8"
    )


def test_calculate_stats_reads_records_and_due_reviews(tmp_path):
    root = tmp_path / "vault"
    _completed(root, "2026-10-22", "主题一", with_review=True)
    _completed(root, "2026-10-23", "主题二")
    in_progress = root / "心理学" / "每日记录" / "2026-10-24-主题三"
    in_progress.mkdir(parents=True)
    (in_progress / "01-交流前版.md").write_text("还在学习。", encoding="utf-8")

    stats = calculate_stats(root, today=date(2026, 10, 24))

    assert stats.total_topics == 3
    assert stats.completed_topics == 2
    assert stats.in_progress_topics == 1
    assert stats.completion_rate == 67
    assert stats.streak_days == 2
    assert stats.active_days == 2
    assert stats.due_reviews == 1
    assert stats.recent_activity[-2:] == ((date(2026, 10, 23), 1), (date(2026, 10, 24), 0))
    assert stats.subjects[0].subject == "心理学"
    assert stats.subjects[0].completion_rate == 67
