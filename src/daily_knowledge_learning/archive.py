"""Archive a finished topic into the knowledge cards and the learning map.

Every write here is a side effect on the user's Obsidian Vault, so all entry
points take an explicit ``completion_confirmed`` flag. Callers must only pass
``True`` after the user has confirmed the topic is finished.

Two Vault layouts are supported without a Markdown parser:

* Table layout — a learning-map row such as
  ``| 日期 | 主题 | 状态 | 完成日期 | 笔记 |``. The row's status cell becomes
  ``已完成``, its first empty cell after the status receives the completion
  date, and its last cell receives the note link.
* List layout — a bullet topic line such as
  ``- [ ] 沉没成本`` or ``- 进行中 沉没成本``. The status token is replaced by
  ``- [x] 主题 已完成 YYYY-MM-DD [[笔记]]``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .file_writer import append_to_note, create_note, update_note
from .note_manager import TopicNotePaths
from .yaml_utils import parse_frontmatter, update_frontmatter

SUBJECTS: tuple[str, str] = ("经济学", "心理学")

MAP_FILES: dict[str, str] = {
    "经济学": "经济学学习路线与已学索引.md",
    "心理学": "心理学学习地图与进度.md",
}

KNOWLEDGE_CARD_FILE = "知识卡片.md"

SUMMARY_HEADING = "## AI 最终总结"
DONE = "已完成"

_OPEN_STATUSES = ("待学习", "进行中", "待归档", "未开始", "未学习")
_LIST_OPEN = ("[ ]", "进行中", "待学习", "待归档")

# Characters that would break a Markdown table cell or a bracketed link.
_UNSAFE_LINK_CHARS = re.compile(r"[\[\]|]")


class ArchiveError(Exception):
    """归档失败，含步骤名和原因。"""

    def __init__(self, step: str, reason: str) -> None:
        self.step = step
        self.reason = reason
        super().__init__(f"归档步骤『{step}』失败：{reason}")


@dataclass(frozen=True, slots=True)
class StepResult:
    """Outcome of one archive step."""

    name: str
    ok: bool
    changed: bool = False
    message: str = ""


@dataclass(frozen=True, slots=True)
class ArchiveResult:
    """Per-step outcome of :func:`archive_topic`."""

    topic_name: str
    completion_date: str
    steps: tuple[StepResult, ...]

    @property
    def succeeded(self) -> bool:
        return all(step.ok for step in self.steps)

    @property
    def failed_steps(self) -> tuple[StepResult, ...]:
        return tuple(step for step in self.steps if not step.ok)

    @property
    def warnings(self) -> tuple[StepResult, ...]:
        return tuple(step for step in self.steps if step.ok and step.message)


def _today() -> str:
    return date.today().isoformat()


def _check_subject(subject: str) -> None:
    if subject not in SUBJECTS:
        raise ValueError("subject must be '经济学' or '心理学'")


def _require_confirmation(step: str, completion_confirmed: bool) -> None:
    if not completion_confirmed:
        raise ArchiveError(step, "用户尚未确认完成，拒绝写入归档结果")


def topic_name_from_folder(folder: Path) -> str:
    """Derive the topic name from the dated folder name ``YYYY-MM-DD-主题``."""
    match = re.match(r"^\d{4}-\d{2}-\d{2}-(.+)$", Path(folder).name)
    return match.group(1) if match else Path(folder).name


def mark_topic_completed(
    note_paths: TopicNotePaths,
    completion_date: str | None = None,
    *,
    completion_confirmed: bool,
) -> bool:
    """Set ``status``/``completion_date`` on the post-discussion note."""
    _require_confirmation("更新主题状态", completion_confirmed)
    if completion_date is None:
        completion_date = _today()
    # Skip unchanged values: rewriting them would churn the file on every run.
    try:
        current = parse_frontmatter(
            Path(note_paths.post_discussion).read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        current = {}
    if current.get("status") == DONE and current.get("completion_date"):
        return False
    updated = {**current, "status": DONE, "completion_date": completion_date}
    try:
        update_frontmatter(
            note_paths.post_discussion,
            updated,
        )
    except Exception as error:  # noqa: BLE001 - re-raised with step context
        raise ArchiveError("更新主题状态", str(error)) from error
    return True


def _summary_block(summary: str) -> str:
    return f"---\n\n{SUMMARY_HEADING}\n\n{summary.strip()}"


def append_final_summary(
    note_paths: TopicNotePaths,
    summary: str,
    *,
    completion_confirmed: bool,
) -> bool:
    """Append the same final summary to both the pre- and post-discussion notes.

    The append is idempotent: an identical block already present is skipped.
    Returns ``True`` when the notes now contain the summary.
    """
    _require_confirmation("追加 AI 最终总结", completion_confirmed)
    if not isinstance(summary, str) or not summary.strip():
        raise ArchiveError("追加 AI 最终总结", "总结内容不能为空")
    block = _summary_block(summary)
    try:
        first = append_to_note(note_paths.pre_learning, block)
        second = append_to_note(note_paths.post_discussion, block)
    except Exception as error:  # noqa: BLE001
        raise ArchiveError("追加 AI 最终总结", str(error)) from error
    return first or second


def append_knowledge_card(
    vault_path: Path,
    subject: str,
    topic_name: str,
    card_content: str,
    *,
    completion_confirmed: bool,
) -> bool:
    """Append a condensed card to ``{subject}/知识卡片.md``, creating it if absent.

    Returns ``True`` when the block was appended and ``False`` when the exact
    block was already present.
    """
    _require_confirmation("更新知识卡片", completion_confirmed)
    _check_subject(subject)
    if not isinstance(card_content, str) or not card_content.strip():
        raise ArchiveError("更新知识卡片", "知识卡片内容不能为空")
    card_path = Path(vault_path) / subject / KNOWLEDGE_CARD_FILE
    block = f"---\n\n## {topic_name}\n\n{card_content.strip()}\n\n_归档于 {_today()}_\n"
    heading = re.compile(rf"^##\s+{re.escape(topic_name.strip())}\s*$", re.MULTILINE)
    try:
        if not card_path.exists():
            header = (
                f"---\nsubject: {subject}\ntype: 知识卡片\n---\n\n"
                f"# {subject}知识卡片\n"
            )
            try:
                create_note(card_path, f"{header}\n{block}")
                return True
            except FileExistsError:
                # Another writer created the file between the check and here.
                pass
        existing = card_path.read_text(encoding="utf-8")
        if heading.search(existing):
            return False
        return append_to_note(card_path, block)
    except Exception as error:  # noqa: BLE001
        raise ArchiveError("更新知识卡片", str(error)) from error


def _note_link(vault_path: Path, note_path: Path) -> str:
    """Vault-relative link, resolved without encoding tricks for folders."""
    try:
        relative = note_path.relative_to(Path(vault_path))
    except ValueError:
        relative = note_path
    return _UNSAFE_LINK_CHARS.sub("-", relative.as_posix())


def _topic_lines(lines: list[str], topic_name: str) -> list[int]:
    """Indexes of lines that mention the topic as a whole cell or link text."""
    pattern = re.compile(
        rf"(?:\|\s*{re.escape(topic_name)}\s*\|)"
        rf"|(?:\[\[\s*[^\]\n]*{re.escape(topic_name)}\s*\]\])"
    )
    return [index for index, line in enumerate(lines) if pattern.search(line)] or [
        index for index, line in enumerate(lines) if topic_name in line
    ]


def _rewrite_table_row(line: str, completion_date: str, link: str) -> str | None:
    """Mark a map table row completed; ``None`` when it has no status cell."""
    newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
    body = line[: len(line) - len(newline)] if newline else line
    trailing_pipe = body.rstrip().endswith("|")
    cells = body.split("|")
    if len(cells) < 4 or "---" in cells[1]:
        return None
    first = 1
    # A row without a trailing pipe has no closing "" after its last cell.
    last = len(cells) - 2 - (0 if trailing_pipe else 1)
    column_count = last - first + 1
    content = [cell.strip() for cell in cells[1:] if cell.strip()]
    rows = [cell.strip() for cell in cells[first : last + 1]]
    if column_count >= 3:
        # Three or more columns: status, then a date, then the note link.
        # status_cell is the absolute index of the status cell.
        status_cell = None
        for cell_index in map(lambda offset: first + offset, range(len(rows))):
            if cells[cell_index].strip() in _OPEN_STATUSES:
                status_cell = cell_index
                break
        if status_cell is None:
            # No open status left: only a genuinely completed row is idempotent.
            if DONE not in content or link not in content:
                return None
            return f"{body}{newline}"
        topic_cell = cells[status_cell]
        cells[status_cell] = f" {DONE} "
        cells_after_status = last - status_cell
        if cells_after_status < 2:
            # A compact three-column map has no date/link columns yet. Add
            # both cells after the status while preserving a closing pipe.
            insertion = last + 1
            cells[insertion:insertion] = [
                f" {completion_date} ",
                f" [[{link}]] ",
            ]
        else:
            # Wider maps already reserve columns for completion date and link.
            # Use the first empty cell after status for the date and the last
            # column for the link, leaving unrelated columns untouched.
            date_index = next(
                (
                    candidate
                    for candidate in range(status_cell + 1, last)
                    if not cells[candidate].strip()
                ),
                status_cell + 1,
            )
            if date_index > status_cell + 1:
                # The status came from a spare column: keep the topic name.
                cells[date_index - 1] = topic_cell
            cells[date_index] = f" {completion_date} "
            cells[last] = f" {link} "
    else:
        # Two columns: the last one holds state; write date and link there.
        last_cell = cells[last]
        if last_cell.strip() not in _OPEN_STATUSES and (
            DONE in last_cell or link in last_cell
        ):
            current = last_cell.strip()
            if DONE in current and link in current:
                return f"{body}{newline}"
            return f"{body} {DONE} {completion_date} [[{link}]] |{newline}"
        if last_cell.strip() not in _OPEN_STATUSES:
            return None
        cells[last] = f" {DONE} · {completion_date} · [[{link}]] "
    return "|".join(cells) + newline


def _rewrite_list_item(line: str, topic_name: str, completion_date: str, link: str) -> str | None:
    """Mark a bullet topic line completed; ``None`` when it is not a topic line."""
    newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
    body = line[: len(line) - len(newline)] if newline else line
    match = re.match(r"^(?P<indent>\s*)[-*]\s+(?P<rest>.+)$", body)
    if not match or topic_name not in match.group("rest"):
        return None
    rest = match.group("rest")
    detail = f"{DONE} {completion_date} [[{link}]]"
    if DONE in rest and link in rest:
        return f"{body}{newline}"
    indent = match.group("indent")
    checkbox = re.match(r"^\[(?P<mark>[ xX])\]\s*(?P<label>.*)$", rest)
    if checkbox is not None:
        label = checkbox.group("label").strip()
        return f"{indent}- [x] {label} {detail}{newline}"
    for token in ("进行中", "待学习", "待归档", "未开始", "未学习"):
        if token in rest:
            label = rest.replace(token, "", 1).strip()
            return f"{indent}- {label} {detail}{newline}"
    return None


def _map_topic_lines(lines: list[str], topic_name: str) -> list[int]:
    return [
        index
        for index in _topic_lines(lines, topic_name)
        if lines[index].strip().startswith("|")
        or re.match(r"^\s*[-*]\s+", lines[index]) is not None
    ]


def update_map_status(
    vault_path: Path,
    subject: str,
    topic_name: str,
    note_paths: TopicNotePaths,
) -> bool:
    """Update the subject's learning map row to 已完成 with date and note link.

    Returns ``True`` when the map changed and ``False`` when it was already
    current. A missing map file raises :class:`ArchiveError`; a missing topic
    line is also reported as an :class:`ArchiveError` and recorded as a warning
    by :func:`archive_topic` without stopping the rest of the archive.
    """
    _check_subject(subject)
    map_path = Path(vault_path) / subject / MAP_FILES[subject]
    if not map_path.exists():
        raise ArchiveError("更新学习地图", f"未找到学习地图文件 {map_path.name}")
    try:
        original = map_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ArchiveError("更新学习地图", str(error)) from error

    lines = original.splitlines(keepends=True)
    link = _note_link(vault_path, note_paths.folder)
    rewritten: str | None = None
    for index in _map_topic_lines(lines, topic_name):
        line = lines[index]
        candidate = None
        if line.strip().startswith("|"):
            candidate = _rewrite_table_row(line, _today(), link)
        else:
            candidate = _rewrite_list_item(line, topic_name, _today(), link)
        if candidate is not None:
            lines[index] = candidate
            rewritten = "".join(lines)
            break
    if rewritten is None:
        raise ArchiveError("更新学习地图", f"学习地图中没有可更新的主题行『{topic_name}』")
    updated = rewritten
    if updated == original:
        return False
    try:
        update_note(map_path, lambda _: updated)
    except Exception as error:  # noqa: BLE001
        raise ArchiveError("更新学习地图", str(error)) from error
    return True


def archive_topic(
    vault_path: Path,
    subject: str,
    note_paths: TopicNotePaths,
    ai_summary: str,
    card_content: str,
    *,
    completion_confirmed: bool,
) -> ArchiveResult:
    """Run every archive step in order; a failing step is recorded, not raised."""
    if not completion_confirmed:
        raise ArchiveError("归档主题", "用户尚未确认完成，拒绝写入归档结果")
    _check_subject(subject)
    topic_name = topic_name_from_folder(note_paths.folder)
    completion_date = _today()
    steps: list[StepResult] = []

    def run(name: str, action, *, optional: bool = False) -> None:  # noqa: ANN001
        try:
            changed = bool(action())
        except ArchiveError as error:
            note = f"（已忽略）{error.reason}" if optional else error.reason
            steps.append(StepResult(name, ok=optional, message=note))
        except Exception as error:  # noqa: BLE001
            note = f"（已忽略）{error}" if optional else str(error)
            steps.append(StepResult(name, ok=optional, message=note))
        else:
            steps.append(StepResult(name, ok=True, changed=changed))

    run(
        "更新主题状态",
        lambda: mark_topic_completed(
            note_paths, completion_date, completion_confirmed=True
        ),
    )
    run(
        "追加 AI 最终总结",
        lambda: append_final_summary(
            note_paths, ai_summary, completion_confirmed=True
        ),
    )
    run(
        "更新知识卡片",
        lambda: append_knowledge_card(
            vault_path,
            subject,
            topic_name,
            card_content,
            completion_confirmed=True,
        ),
    )
    run(
        "更新学习地图",
        lambda: update_map_status(vault_path, subject, topic_name, note_paths),
        optional=True,
    )
    return ArchiveResult(topic_name, completion_date, tuple(steps))
