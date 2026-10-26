from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .file_writer import append_to_note, create_note, update_note
from .yaml_utils import update_frontmatter
from .subjects import normalize_custom_subjects


@dataclass(frozen=True, slots=True)
class TopicNotePaths:
    folder: Path
    pre_learning: Path
    post_discussion: Path
    ai_reference: Path


def create_topic_notes(
    vault_path: Path,
    subject: str,
    topic_name: str,
    initial_content: str = "",
) -> TopicNotePaths:
    normalize_custom_subjects((subject,)) if subject not in {"经济学", "心理学"} else None
    if not topic_name or topic_name in {".", ".."} or any(c in topic_name for c in "/\\\0"):
        raise ValueError("topic_name must be a non-empty folder name")
    today = date.today().isoformat()
    folder = Path(vault_path) / subject / f"{today}-{topic_name}"
    if folder.exists():
        raise FileExistsError(f"{folder}: topic already exists; refusing to overwrite")
    folder.mkdir(parents=True, exist_ok=False)
    paths = TopicNotePaths(
        folder=folder,
        pre_learning=folder / "01-学习前版.md",
        post_discussion=folder / "02-交流后版.md",
        ai_reference=folder / "03-AI参考版.md",
    )
    header = (
        "---\n"
        f"topic: {topic_name}\n"
        f"subject: {subject}\n"
        f"date: {today}\n"
        "status: 进行中\n"
        "---\n\n"
    )
    created: list[Path] = []
    try:
        create_note(paths.pre_learning, f"{header}{initial_content}")
        created.append(paths.pre_learning)
        create_note(paths.post_discussion, header)
        created.append(paths.post_discussion)
        create_note(paths.ai_reference, header)
        created.append(paths.ai_reference)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        try:
            folder.rmdir()
        except OSError:
            pass
        raise
    return paths


def update_pre_learning_note(note_path: Path, content: str) -> None:
    update_note(note_path, content)


def update_post_discussion_note(
    note_path: Path,
    content: str,
    mark_completed: bool = False,
) -> None:
    update_note(note_path, content)
    if mark_completed:
        update_frontmatter(
            note_path,
            {"status": "已完成", "completion_date": date.today().isoformat()},
        )


def append_ai_reference(note_path: Path, ai_content: str) -> bool:
    if not ai_content.strip():
        raise ValueError("ai_content must not be empty")
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    block = f"---\n\n## AI 参考 - {timestamp}\n\n{ai_content.strip()}"
    return append_to_note(note_path, block)
