from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class TopicStatus(StrEnum):
    COMPLETED = "已学"
    IN_PROGRESS = "进行中"
    TO_LEARN = "待学习"
    DEFERRED = "暂缓"
    TO_ARCHIVE = "待归档"


@dataclass(frozen=True, slots=True)
class TopicRecord:
    subject: str
    topic: str
    date: str
    path: Path
    status: TopicStatus
    has_folder: bool
    versions: tuple[str, ...] = ()

