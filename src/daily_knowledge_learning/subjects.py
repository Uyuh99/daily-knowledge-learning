"""Subject catalog shared by the UI and the Vault workflow."""

from __future__ import annotations

import re
from pathlib import Path

BUILTIN_SUBJECTS = ("心理学", "经济学")
SUBJECT_NAME_LIMIT = 24
_UNSAFE_NAME = re.compile(r"[\\/:*?\"<>|\x00-\x1f]")


def normalize_custom_subjects(values: tuple[str, ...] | list[str] | tuple) -> tuple[str, ...]:
    """Validate and de-duplicate custom names while keeping user order."""
    result: list[str] = []
    for raw in values:
        if not isinstance(raw, str):
            raise TypeError("custom subject names must be strings")
        name = raw.strip()
        if not name or len(name) > SUBJECT_NAME_LIMIT or _UNSAFE_NAME.search(name):
            raise ValueError("custom subject names must be safe folder names")
        if name in BUILTIN_SUBJECTS:
            continue
        if name not in result:
            result.append(name)
    return tuple(result)


def all_subjects(custom: tuple[str, ...] = ()) -> tuple[str, ...]:
    return BUILTIN_SUBJECTS + normalize_custom_subjects(custom)


def map_filename(subject: str) -> str:
    if subject == "经济学":
        return "经济学学习路线与已学索引.md"
    if subject == "心理学":
        return "心理学学习地图与进度.md"
    return f"{subject}学习地图.md"


def subject_root(vault_path: Path, subject: str) -> Path:
    direct = Path(vault_path) / subject
    if direct.is_dir():
        return direct
    nested = Path(vault_path) / "每日心理学与经济学学习" / subject
    return nested


def create_custom_subject(vault_path: Path, subject: str, topics: list[str]) -> Path:
    """Create a small editable learning map for a new subject."""
    name = normalize_custom_subjects((subject,))[0]
    root = Path(vault_path) / name
    root.mkdir(parents=True, exist_ok=False)
    (root / "每日记录").mkdir()
    clean_topics = [item.strip() for item in topics if item.strip()]
    if not clean_topics:
        clean_topics = ["核心概念", "现实例子", "常见误区"]
    rows = "\n".join(f"| {topic} | 待学习 |" for topic in clean_topics)
    map_text = (
        f"# {name}学习地图\n\n"
        "## 学习路线\n\n"
        "| 主题 | 状态 |\n| --- | --- |\n"
        f"{rows}\n"
    )
    try:
        (root / map_filename(name)).write_text(map_text, encoding="utf-8")
    except Exception:
        import shutil
        shutil.rmtree(root, ignore_errors=True)
        raise
    return root


__all__ = [
    "BUILTIN_SUBJECTS",
    "all_subjects",
    "create_custom_subject",
    "map_filename",
    "normalize_custom_subjects",
    "subject_root",
]
