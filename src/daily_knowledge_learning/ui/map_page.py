from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from ..map_parser import parse_learning_map
from ..models import TopicStatus
from ..vault_scan import scan_vault
from .widgets import EmptyState, PageHeader, StatusPill, field_label, meta_label


class MapPage(QWidget):
    """Read-only, status-colored view of one subject learning route."""

    def __init__(self, vault_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vault_root = Path(vault_root)
        self.records = scan_vault(self.vault_root)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        root.addWidget(PageHeader("学习地图", "按学科查看学习路线与每个知识点的状态"))
        controls = QHBoxLayout()
        controls.addWidget(field_label("学科"))
        self.subject_filter = QComboBox()
        self.subject_filter.addItems(("心理学", "经济学"))
        self.subject_filter.currentTextChanged.connect(self.refresh)
        controls.addWidget(self.subject_filter)
        controls.addStretch(1)
        for status in (TopicStatus.COMPLETED, TopicStatus.IN_PROGRESS, TopicStatus.TO_LEARN, TopicStatus.DEFERRED):
            controls.addWidget(StatusPill(status.value))
        root.addLayout(controls)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(4, 4, 14, 8)
        self.content_layout.setSpacing(8)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.content)
        root.addWidget(self.scroll, 1)
        self.refresh()

    def refresh(self) -> None:
        self.records = scan_vault(self.vault_root)
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        subject = self.subject_filter.currentText()
        learning_map = parse_learning_map(self.vault_root, subject)
        if not learning_map.modules:
            self.content_layout.addWidget(EmptyState("学习地图文件缺失或格式无法识别", f"请确认 {subject}/学习路线与已学索引.md 存在且格式正确"))
            return
        statuses = {row.topic: row.status for row in self.records if row.subject == subject}
        for module in learning_map.modules:
            title = QLabel(module.name)
            title.setObjectName("mapModuleTitle")
            self.content_layout.addWidget(title)
            for topic in module.topics:
                status = statuses.get(topic.name, TopicStatus.TO_LEARN)
                row = QFrame()
                row.setObjectName("mapRow")
                layout = QVBoxLayout(row)
                layout.setContentsMargins(12, 9, 12, 9)
                layout.setSpacing(4)
                top = QHBoxLayout()
                label = QLabel(topic.name)
                label.setObjectName("bodyText")
                label.setWordWrap(True)
                top.addWidget(label, 1)
                top.addWidget(StatusPill(status.value))
                layout.addLayout(top)
                if topic.prerequisites:
                    layout.addWidget(meta_label("前置：" + "、".join(topic.prerequisites)))
                elif topic.relationship:
                    layout.addWidget(meta_label("关联：" + topic.relationship))
                self.content_layout.addWidget(row)
        self.content_layout.addStretch(1)
