from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .file_writer import append_to_note, create_note, update_note
from .note_manager import TopicNotePaths
from .yaml_utils import update_frontmatter

logger = logging.getLogger(__name__)


class ArchiveError(Exception):
    """An archive step failed or was attempted without user confirmation."""

    def __init__(self, step: str, reason: str) -> None:
        self.step = step
        self.reason = reason
        super().__init__(f"{step}: {reason}")


@dataclass(slots=True)
class ArchiveResult:
    """Per-step outcomes for an archive attempt."""

    steps: dict[str, str] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def successful(self) -> bool:
        return not self.errors


def _require_confirmation(step: str, completion_confirmed: bool) -> None:
    if not completion_confirmed:
        raise ArchiveError(step, "completion must be explicitly confirmed by the user")


def mark_topic_completed(
    note_paths: TopicNotePaths,
    completion_date: str | None = None,
    *,
    completion_confirmed: bool,
) -> None:
    _require_confirmation("mark_topic_completed", completion_confirmed)
    try:
        date.fromisoformat(completion_date) if completion_date else None
    except ValueError as error:
        raise ArchiveError("mark_topic_completed", "completion_date must be YYYY-MM-DD") from error
    update_frontmatter(
        note_paths.post_discussion,
        {"status": "???", "completion_date": completion_date or date.today().isoformat()},
    )


def append_final_summary(
    note_paths: TopicNotePaths,
    summary: str,
    *,
    completion_confirmed: bool,
) -> None:
    _require_confirmation("append_final_summary", completion_confirmed)
    if not summary.strip():
        raise ArchiveError("append_final_summary", "summary must not be empty")
    block = f"---\n\n## AI ????\n\n{summary.strip()}"
    for path in (note_paths.pre_learning, note_paths.post_discussion):
        append_to_note(path, block)


def append_knowledge_card(
    vault_path: Path,
    subject: str,
    topic_name: str,
    card_content: str,
    *,
    completion_confirmed: bool,
) -> None:
    _require_confirmation("append_knowledge_card", completion_confirmed)
    if not topic_name.strip() or not card_content.strip():
        raise ArchiveError("append_knowledge_card", "topic_name and card_content must not be empty")
    path = Path(vault_path) / subject / "????.md"
    block = (
        f"---\n\n## {topic_name.strip()}\n\n{card_content.strip()}\n\n"
        f"_??? {date.today().isoformat()}_"
    )
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if f"## {topic_name.strip()}" not in existing:
            append_to_note(path, block)
    else:
        try:
            create_note(path, block.lstrip("\n"))
        except FileExistsError:
            # Another writer created it after the existence check.
            existing = path.read_text(encoding="utf-8")
            if f"## {topic_name.strip()}" not in existing:
                append_to_note(path, block)


_MAP_FILES = {
    "???": "????????????.md",
    "???": "??????????.md",
}
_STATUS = re.compile(r"???|???")


def update_map_status(
    vault_path: Path,
    subject: str,
    topic_name: str,
    note_paths: TopicNotePaths,
) -> None:
    filename = _MAP_FILES.get(subject)
    if filename is None:
        logger.warning("No learning map configured for subject %r", subject)
        return
    path = Path(vault_path) / subject / filename
    if not path.exists():
        logger.warning("Learning map is missing: %s", path)
        return
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    changed = False
    completion_date = date.today().isoformat()
    note_link = Path(note_paths.post_discussion).relative_to(Path(vault_path)).as_posix()
    for index, line in enumerate(lines):
        if topic_name not in line:
            continue
        updated = _STATUS.sub("???", line)
        if updated == line:
            continue
        ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        body = updated.rstrip("\r\n")
        if "|" in body:
            cells = body.split("|")
            status_index = next(
                (index for index, cell in enumerate(cells) if "???" in cell),
                None,
            )
            if status_index is None:
                continue
            leading = cells[status_index][: len(cells[status_index]) - len(cells[status_index].lstrip())]
            trailing = cells[status_index][len(cells[status_index].rstrip()):]
            cells[status_index] = f"{leading}???{trailing}"
            insertion_index = len(cells) - 1 if cells[-1].strip() == "" else len(cells)
            cells[insertion_index:insertion_index] = [
                f" {completion_date} ",
                f" [{topic_name}]({note_link}) ",
            ]
            body = "|".join(cells)
        else:
            body += f"?{completion_date} ? [{topic_name}]({note_link})?"
        lines[index] = body + ending
        changed = True
        break
    if not changed:
        logger.warning("Topic %r was not found as an active row in %s", topic_name, path)
        return
    update_note(path, "".join(lines))


def archive_topic(
    vault_path: Path,
    subject: str,
    note_paths: TopicNotePaths,
    ai_summary: str,
    card_content: str,
    *,
    completion_confirmed: bool,
) -> ArchiveResult:
    result = ArchiveResult()
    if not completion_confirmed:
        result.errors["confirmation"] = "completion must be explicitly confirmed by the user"
        return result
    topic_name = note_paths.folder.name.split("-", 3)[-1]
    actions = (
        ("topic_status", lambda: mark_topic_completed(note_paths, completion_confirmed=True)),
        ("final_summary", lambda: append_final_summary(note_paths, ai_summary, completion_confirmed=True)),
        ("knowledge_card", lambda: append_knowledge_card(
            vault_path, subject, topic_name, card_content, completion_confirmed=True
        )),
        ("learning_map", lambda: update_map_status(vault_path, subject, topic_name, note_paths)),
    )
    for step, action in actions:
        try:
            if step == "learning_map" and not (Path(vault_path) / subject / _MAP_FILES.get(subject, "")).is_file():
                result.steps[step] = "skipped: learning map is missing"
                continue
            action()
            result.steps[step] = "success"
        except Exception as error:
            result.errors[step] = str(error)
            logger.exception("Archive step %s failed", step)
    return result
