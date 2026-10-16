from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .map_parser import MapTopic, StudyMap, parse_learning_map
from .models import TopicRecord, TopicStatus
from .vault_scan import scan_subject


@dataclass(frozen=True, slots=True)
class DeferredTopic:
    topic: str
    module: str
    reason: str


@dataclass(frozen=True, slots=True)
class SelectionResult:
    subject: str
    topic: str | None
    module: str | None
    reason: str
    relationship: str
    previous_topic: str | None
    deferred: tuple[DeferredTopic, ...] = ()


@dataclass(frozen=True, slots=True)
class StudyPrompt:
    topic: str
    relationship: str
    core_question: str
    search_keywords: tuple[str, ...]
    schedule: tuple[str, ...]


def _subject_root(vault_path: Path, subject: str) -> Path:
    direct = vault_path / subject
    if direct.is_dir():
        return direct
    return vault_path / "每日心理学与经济学学习" / subject


def _record_by_topic(records: list[TopicRecord]) -> dict[str, TopicRecord]:
    # When multiple daily records share a topic, the newest one is authoritative.
    return {record.topic: record for record in sorted(records, key=lambda item: item.date)}


def _latest_completed(records: list[TopicRecord]) -> TopicRecord | None:
    completed = [record for record in records if record.status is TopicStatus.COMPLETED]
    return max(completed, key=lambda item: (item.date, item.topic), default=None)


def _flatten(study_map: StudyMap) -> list[tuple[str, MapTopic]]:
    return [(module.name, topic) for module in study_map.modules for topic in module.topics]


def select_next_topic(vault_path: Path, subject: str) -> SelectionResult:
    records = scan_subject(_subject_root(Path(vault_path), subject), subject)
    by_topic = _record_by_topic(records)
    latest = _latest_completed(records)
    study_map = parse_learning_map(Path(vault_path), subject)

    in_progress = [record for record in records if record.status is TopicStatus.IN_PROGRESS]
    if in_progress:
        active = max(in_progress, key=lambda item: (item.date, item.topic))
        module = next((name for name, topic in _flatten(study_map) if topic.name == active.topic), None)
        return SelectionResult(subject, active.topic, module, "该主题的交流后版尚未确认，继续完成当前学习。", "继续当前主题", latest.topic if latest else None)

    flattened = _flatten(study_map)
    if not flattened:
        return SelectionResult(subject, None, None, "未找到可解析的学习地图或路线主题。", "", latest.topic if latest else None)

    completed = {record.topic for record in records if record.status is TopicStatus.COMPLETED}
    deferred: list[DeferredTopic] = []
    selected: SelectionResult | None = None
    for module_name, topic in flattened:
        record = by_topic.get(topic.name)
        if record and record.status is TopicStatus.COMPLETED:
            continue
        missing = [name for name in topic.prerequisites if name not in completed]
        if missing:
            if record is not None:
                deferred.append(DeferredTopic(topic.name, module_name, f"前置知识尚未完成：{'、'.join(missing)}；已创建记录保留并暂缓。"))
            continue
        if selected is not None:
            continue
        previous = latest.topic if latest else None
        relationship = topic.relationship or (f"路线中的下一主题，承接「{previous}」。" if previous else "该模块的起点主题。")
        reason = "按学习地图顺序选择了前置知识已完成、尚未学习的主题。"
        if record is not None:
            reason += "现有笔记状态未标记为已完成，因此仍按 Vault 状态继续此主题。"
        selected = SelectionResult(subject, topic.name, module_name, reason, relationship, previous)

    if selected is not None:
        return SelectionResult(
            selected.subject,
            selected.topic,
            selected.module,
            selected.reason,
            selected.relationship,
            selected.previous_topic,
            tuple(deferred),
        )

    return SelectionResult(subject, None, None, "当前路线中没有可开始的主题。", "", latest.topic if latest else None, tuple(deferred))


def build_study_prompt(result: SelectionResult) -> StudyPrompt:
    topic = result.topic or "待确定主题"
    prior = f"与已完成的「{result.previous_topic}」的关系：{result.relationship}" if result.previous_topic else result.relationship
    keywords = (topic, f"{topic} 核心机制", f"{topic} 证据与适用边界")
    return StudyPrompt(
        topic=topic,
        relationship=prior,
        core_question=f"「{topic}」试图解释什么现象？它的关键机制和适用边界是什么？",
        search_keywords=keywords,
        schedule=("5 分钟：写下已有理解与疑问", "15 分钟：查阅可靠来源，梳理定义和机制", "10 分钟：用自己的例子说明，并记录仍不确定之处"),
    )
