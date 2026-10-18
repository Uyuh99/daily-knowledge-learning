from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class MapTopic:
    name: str
    prerequisites: tuple[str, ...] = ()
    relationship: str = ""


@dataclass(frozen=True, slots=True)
class LearningModule:
    name: str
    topics: tuple[MapTopic, ...]


@dataclass(frozen=True, slots=True)
class StudyMap:
    modules: tuple[LearningModule, ...] = ()


MAP_FILES = {
    "经济学": "经济学学习路线与已学索引.md",
    "心理学": "心理学学习地图与进度.md",
}
_ECON_MODULE = re.compile(r"^#{2,3}\s+模块\s+[A-Z0-9]+\s*[｜|]\s*(.+?)\s*$")
_PSYCH_MODULE = re.compile(r"^#{2,3}\s+(?:当前\s*)?(?:模块(?:\s+\S+)?\s*[：:｜|]\s*)?(.+?)\s*$")


def _subject_root(vault_path: Path, subject: str) -> Path:
    direct = vault_path / subject
    return direct if direct.is_dir() else vault_path / "每日心理学与经济学学习" / subject


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).strip("*` ")


def _parse(text: str, subject: str) -> StudyMap:
    modules: list[LearningModule] = []
    name: str | None = None
    topics: list[MapTopic] = []
    headers: list[str] | None = None
    previous: str | None = None

    def finish() -> None:
        nonlocal name, topics
        if name and topics:
            modules.append(LearningModule(name, tuple(topics)))
        name, topics = None, []

    for line in text.splitlines():
        match = _ECON_MODULE.match(line) if subject == "经济学" else _PSYCH_MODULE.match(line)
        if match:
            finish()
            name = _clean(match.group(1))
            if subject == "心理学":
                name = re.sub(r"^模块\s*[：:]?\s*", "", name)
            headers, previous = None, None
            continue
        if not line.lstrip().startswith("|"):
            headers = None
            continue
        cells = [_clean(cell) for cell in line.strip().strip("|").split("|")]
        if "知识点" in cells:
            headers = cells
            continue
        if not headers or not name or len(cells) < len(headers):
            continue
        if all(set(cell) <= {"-", ":", " "} for cell in cells):
            continue
        row = dict(zip(headers, cells, strict=False))
        topic = row.get("知识点", "")
        if not topic:
            continue
        relation = row.get("核心关联", row.get("与前一节点的关系", ""))
        topics.append(MapTopic(topic, (previous,) if previous else (), relation))
        previous = topic
    finish()
    return StudyMap(tuple(modules))


def parse_learning_map(vault_path: Path, subject: str) -> StudyMap:
    """Read a subject's Markdown route map; missing or malformed files yield an empty map."""
    filename = MAP_FILES.get(subject)
    if filename is None:
        return StudyMap()
    try:
        text = (_subject_root(Path(vault_path), subject) / filename).read_text(encoding="utf-8")
        result = _parse(text, subject)
    except (OSError, UnicodeError, ValueError, TypeError):
        return StudyMap()
    return result if result.modules else StudyMap()
