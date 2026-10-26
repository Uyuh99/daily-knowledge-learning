"""Read-only learning statistics derived from the Obsidian Vault."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from .models import TopicRecord, TopicStatus
from .review_service import due_reviews
from .vault_scan import scan_vault


@dataclass(frozen=True, slots=True)
class SubjectStats:
    subject: str
    total: int
    completed: int
    in_progress: int
    to_learn: int
    deferred: int

    @property
    def completion_rate(self) -> int:
        return round(self.completed * 100 / self.total) if self.total else 0


@dataclass(frozen=True, slots=True)
class LearningStats:
    total_topics: int
    completed_topics: int
    in_progress_topics: int
    to_learn_topics: int
    deferred_topics: int
    completion_rate: int
    streak_days: int
    active_days: int
    due_reviews: int
    recent_activity: tuple[tuple[date, int], ...]
    subjects: tuple[SubjectStats, ...]


def _parse_record_date(record: TopicRecord) -> date | None:
    try:
        return date.fromisoformat(record.date)
    except ValueError:
        return None


def _streak(days: set[date]) -> int:
    if not days:
        return 0
    cursor = max(days)
    length = 0
    while cursor in days:
        length += 1
        cursor -= timedelta(days=1)
    return length


def _subject_stats(records: list[TopicRecord]) -> tuple[SubjectStats, ...]:
    groups: dict[str, list[TopicRecord]] = {}
    for record in records:
        groups.setdefault(record.subject, []).append(record)
    result: list[SubjectStats] = []
    for subject in sorted(groups):
        items = groups[subject]
        result.append(SubjectStats(
            subject,
            len(items),
            sum(item.status is TopicStatus.COMPLETED for item in items),
            sum(item.status is TopicStatus.IN_PROGRESS for item in items),
            sum(item.status is TopicStatus.TO_LEARN for item in items),
            sum(item.status is TopicStatus.DEFERRED for item in items),
        ))
    return tuple(result)


def calculate_stats(vault_root: Path, *, today: date | None = None) -> LearningStats:
    """Calculate dashboard metrics without changing any Vault files."""
    records = list(scan_vault(Path(vault_root))) if Path(vault_root).is_dir() else []
    completed = [record for record in records if record.status is TopicStatus.COMPLETED]
    completed_dates = {parsed for record in completed if (parsed := _parse_record_date(record)) is not None}
    today = today or date.today()
    recent_start = today - timedelta(days=6)
    activity = Counter(parsed for record in completed if (parsed := _parse_record_date(record)) is not None)
    recent = tuple((day, activity.get(day, 0)) for offset in range(7) for day in (recent_start + timedelta(days=offset),))
    return LearningStats(
        total_topics=len(records),
        completed_topics=len(completed),
        in_progress_topics=sum(record.status is TopicStatus.IN_PROGRESS for record in records),
        to_learn_topics=sum(record.status is TopicStatus.TO_LEARN for record in records),
        deferred_topics=sum(record.status is TopicStatus.DEFERRED for record in records),
        completion_rate=round(len(completed) * 100 / len(records)) if records else 0,
        streak_days=_streak(completed_dates),
        active_days=len(completed_dates),
        due_reviews=len(due_reviews(Path(vault_root), today=today)) if Path(vault_root).is_dir() else 0,
        recent_activity=recent,
        subjects=_subject_stats(records),
    )


__all__ = ["LearningStats", "SubjectStats", "calculate_stats"]
