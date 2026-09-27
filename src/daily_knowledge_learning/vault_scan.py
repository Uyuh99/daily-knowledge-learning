from __future__ import annotations

import re
from pathlib import Path

from .models import TopicRecord, TopicStatus

_DATE_TOPIC = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<topic>.+?)(?:\.md)?$")
_COMPLETED_VALUES = {"已完成", "已确认", "completed", "confirmed"}
_DEFERRED_VALUES = {"暂缓", "deferred"}


def _frontmatter(path: Path) -> dict[str, str]:
    """Read the simple scalar YAML fields used by the existing notes."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    fields: dict[str, str] = {}
    for line in text.splitlines()[1:]:
        if line.strip() == "---":
            break
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip().strip("'\"")
    return fields


def _status_for_folder(folder: Path, versions: tuple[str, ...]) -> TopicStatus:
    after = folder / "02-交流后版.md"
    if not after.exists():
        return TopicStatus.IN_PROGRESS if versions else TopicStatus.TO_LEARN

    metadata = _frontmatter(after)
    status = metadata.get("status", "")
    if status in _COMPLETED_VALUES:
        return TopicStatus.COMPLETED
    if status in _DEFERRED_VALUES:
        return TopicStatus.DEFERRED
    return TopicStatus.IN_PROGRESS


def scan_subject(subject_root: Path, subject: str) -> list[TopicRecord]:
    """Scan one subject without changing any Vault file.

    A folder-based topic is authoritative for the new workflow. A legacy
    single Markdown note is retained and reported as ``待学习`` until the
    user completes and confirms the three-version workflow.
    """
    records_root = subject_root / "每日记录"
    if not records_root.is_dir():
        return []

    records: list[TopicRecord] = []
    for entry in sorted(records_root.iterdir(), key=lambda item: item.name):
        match = _DATE_TOPIC.match(entry.name)
        if not match:
            continue
        date = match.group("date")
        topic = match.group("topic")
        if entry.is_dir():
            versions = tuple(
                name
                for name in ("01-交流前版.md", "02-交流后版.md", "03-AI参考版.md")
                if (entry / name).exists()
            )
            status = _status_for_folder(entry, versions)
            records.append(
                TopicRecord(subject, topic, date, entry, status, True, versions)
            )
        elif entry.is_file() and entry.suffix.lower() == ".md":
            records.append(
                TopicRecord(
                    subject,
                    topic,
                    date,
                    entry,
                    TopicStatus.TO_LEARN,
                    False,
                )
            )
    return records


def scan_vault(vault_root: Path) -> list[TopicRecord]:
    """Scan the supported subjects in an Obsidian learning project."""
    records: list[TopicRecord] = []
    project_root = vault_root / "每日心理学与经济学学习"
    if not project_root.is_dir():
        # This also makes small fixture Vaults useful in tests and exercises.
        project_root = vault_root
    for subject in ("心理学", "经济学"):
        records.extend(scan_subject(project_root / subject, subject))
    return records
