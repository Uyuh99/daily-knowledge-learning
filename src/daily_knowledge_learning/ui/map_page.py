from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from ..map_parser import parse_learning_map
from ..models import TopicStatus
from ..vault_scan import scan_vault

STATUS_COLORS = {
    TopicStatus.COMPLETED: "#2f855a",
    TopicStatus.IN_PROGRESS: "#b7791f",
    TopicStatus.TO_LEARN: "#687078",
    TopicStatus.DEFERRED: "#c05621",
}


class MapPage(QWidget):
    """Read-only, status-colored view of one subject learning route."""

    def __init__(self, vault_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vault_root = Path(vault_root)
        self.records = scan_vault(self.vault_root)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        heading = QLabel("学习地图")
        heading.setObjectName("pageHeading")
        root.addWidget(heading)
        self.subject_filter = QComboBox()
        self.subject_filter.addItems(("心理学", "经济学"))
        self.subject_filter.currentTextChanged.connect(self.refresh)
        root.addWidget(self.subject_filter)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.content)
        root.addWidget(self.scroll, 1)
        self.refresh()

    def refresh(self) -> None:
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        subject = self.subject_filter.currentText()
        learning_map = parse_learning_map(self.vault_root, subject)
        if not learning_map.modules:
            message = QLabel("学习地图文件缺失或格式无法识别")
            message.setObjectName("mapEmptyState")
            self.content_layout.addWidget(message)
            return
        statuses = {row.topic: row.status for row in self.records if row.subject == subject}
        for module in learning_map.modules:
            title = QLabel(module.name)
            title.setObjectName("mapModuleTitle")
            self.content_layout.addWidget(title)
            for topic in module.topics:
                status = statuses.get(topic.name, TopicStatus.TO_LEARN)
                row = QFrame()
                row.setFrameShape(QFrame.Shape.StyledPanel)
                row.setStyleSheet("QFrame { border: 1px solid #d9dde1; border-left: 4px solid " + STATUS_COLORS.get(status, STATUS_COLORS[TopicStatus.TO_LEARN]) + "; padding: 8px; }")
                layout = QVBoxLayout(row)
                label = QLabel(f"{topic.name}    {status.value}")
                label.setStyleSheet(f"color: {STATUS_COLORS.get(status, STATUS_COLORS[TopicStatus.TO_LEARN])}; font-weight: 600;")
                layout.addWidget(label)
                if topic.prerequisites:
                    layout.addWidget(QLabel("前置：" + "、".join(topic.prerequisites)))
                elif topic.relationship:
                    layout.addWidget(QLabel("关联：" + topic.relationship))
                self.content_layout.addWidget(row)
        self.content_layout.addStretch(1)
