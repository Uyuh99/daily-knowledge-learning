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


_MAP_FILES = {
    "经济学": "经济学学习路线与已学索引.md",
    "心理学": "心理学学习地图与进度.md",
}
_ECON_MODULE = re.compile(r"^#{2,3}\s+模块\s+([A-Z0-9]+)\s*[｜|]\s*(.+?)\s*$")
_PSYCH_MODULE = re.compile(r"^#{2,3}\s+(?:当前\s*)?(?:模块(?:\s+\S+)?\s*[：:｜|]\s*)?(.+?)\s*$")


def _subject_root(vault_path: Path, subject: str) -> Path:
    direct = vault_path / subject
    if direct.is_dir():
        return direct
    nested = vault_path / "每日心理学与经济学学习" / subject
    return nested


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _clean_cell(cell: str) -> str:
    return re.sub(r"\s+", " ", cell.strip()).strip("*` ")


def _parse_tables(text: str, subject: str) -> tuple[LearningModule, ...]:
    modules: list[LearningModule] = []
    current_name: str | None = None
    current_topics: list[MapTopic] = []
    table_header: list[str] | None = None
    previous_topic: str | None = None

    def finish_module() -> None:
        nonlocal current_name, current_topics
        if current_name and current_topics:
            modules.append(LearningModule(current_name, tuple(current_topics)))
        current_name, current_topics = None, []

    for line in text.splitlines():
        heading = _ECON_MODULE.match(line) if subject == "经济学" else _PSYCH_MODULE.match(line)
        if heading:
            finish_module()
            current_name = heading.group(2).strip() if subject == "经济学" else heading.group(1).strip().lstrip(":： ")
            if subject == "心理学":
                current_name = re.sub(r"^模块\s*[：:]?\s*", "", current_name)
            table_header = None
            previous_topic = None
            continue

        if not line.lstrip().startswith("|"):
            table_header = None
            continue
        cells = _cells(line)
        normalized = [_clean_cell(cell) for cell in cells]
        if any(cell in {"顺序", "知识点"} for cell in normalized) and "知识点" in normalized:
            table_header = normalized
            continue
        if table_header is None or not current_name or not cells or all(set(c) <= {"-", ":", " "} for c in cells):
            continue
        if len(cells) < len(table_header):
            continue
        row = dict(zip(table_header, cells, strict=False))
        topic_name = _clean_cell(row.get("知识点", ""))
        if not topic_name or topic_name in {"主题", "知识点"}:
            continue
        relation = _clean_cell(row.get("核心关联", row.get("与前一节点的关系", "")))
        # The route tables encode dependencies by ordered progression: each
        # node follows the previous node in its module/branch.
        prereqs = (previous_topic,) if previous_topic else ()
        current_topics.append(MapTopic(topic_name, prereqs, relation))
        previous_topic = topic_name

    finish_module()
    if subject == "经济学":
        # The economics route is cumulative: each later item follows the full
        # sequence before it, including across module boundaries.
        completed_route: list[str] = []
        route_modules: list[LearningModule] = []
        for module in modules:
            route_topics: list[MapTopic] = []
            for topic in module.topics:
                route_topics.append(MapTopic(topic.name, tuple(completed_route), topic.relationship))
                completed_route.append(topic.name)
            route_modules.append(LearningModule(module.name, tuple(route_topics)))
        modules = route_modules
    return tuple(modules)


def parse_learning_map(vault_path: Path, subject: str) -> StudyMap:
    """Parse a subject route map. Missing or changed formats produce an empty map."""
    filename = _MAP_FILES.get(subject)
    if filename is None:
        return StudyMap()
    try:
        text = (_subject_root(Path(vault_path), subject) / filename).read_text(encoding="utf-8")
        modules = _parse_tables(text, subject)
    except (OSError, UnicodeError, ValueError, TypeError, IndexError):
        return StudyMap()
    return StudyMap(modules) if modules else StudyMap()
