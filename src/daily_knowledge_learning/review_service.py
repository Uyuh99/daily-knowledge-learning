from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from .file_writer import update_note
from .vault_scan import scan_vault

_INTERVAL = re.compile(r"^\s*-\s*\[(?P<checked>[ xX])\]\s*第\s*(?P<days>1|3|7|14)\s*天[：:].*$")
_INTERVAL_DAYS = (1, 3, 7, 14)


@dataclass(frozen=True, slots=True)
class ReviewTask:
    subject: str
    topic: str
    note_path: Path
    due_date: date
    interval_days: int
    instruction: str


def _pre_learning_path(record) -> Path:
    if record.path.is_dir():
        for name in ("01-交流前版.md", "01-学习前版.md"):
            candidate = record.path / name
            if candidate.is_file():
                return candidate
        return record.path / "01-交流前版.md"
    return record.path


def due_reviews(vault_root: Path, *, today: date | None = None) -> list[ReviewTask]:
    """Return unchecked interval reviews that are due, without modifying notes."""
    today = today or date.today()
    tasks: list[ReviewTask] = []
    for record in scan_vault(Path(vault_root)):
        path = _pre_learning_path(record)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            started = False
            section: list[str] = []
            for line in lines:
                if line.startswith("## "):
                    if started:
                        break
                    started = line.strip() == "## 间隔复习"
                    continue
                if started:
                    section.append(line)
        except (OSError, UnicodeError):
            continue
        try:
            learned_on = date.fromisoformat(record.date)
        except ValueError:
            continue
        for line in section:
            match = _INTERVAL.match(line)
            if not match or match.group("checked").lower() == "x":
                continue
            days = int(match.group("days"))
            due_on = learned_on + timedelta(days=days)
            if due_on <= today:
                tasks.append(ReviewTask(record.subject, record.topic, path, due_on, days, line.strip().split("：", 1)[-1]))
    return sorted(tasks, key=lambda task: (task.due_date, task.subject, task.topic, task.interval_days))


def complete_review(task: ReviewTask) -> None:
    """Atomically check off one review item in its original Markdown note."""
    changed = False

    def mark(document: str) -> str:
        nonlocal changed
        lines = document.splitlines(keepends=True)
        in_section = False
        for index, line in enumerate(lines):
            if line.startswith("## "):
                if in_section:
                    break
                in_section = line.strip() == "## 间隔复习"
                continue
            if not in_section:
                continue
            match = _INTERVAL.match(line.rstrip("\r\n"))
            if match and int(match.group("days")) == task.interval_days and match.group("checked").lower() != "x":
                start, end = match.span("checked")
                lines[index] = line[:start] + "x" + line[end:]
                changed = True
                return "".join(lines)
        return document

    update_note(task.note_path, mark)
    if not changed:
        raise ValueError("这条复习已完成或笔记格式已变化，请刷新复习清单。")
