from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..models import TopicRecord, TopicStatus
from ..vault_scan import scan_vault

VERSIONS = ("01-交流前版.md", "02-交流后版.md", "03-AI参考版.md")
SUBJECTS = ("全部学科", "心理学", "经济学")
STATUSES = ("全部状态", *(status.value for status in (TopicStatus.COMPLETED, TopicStatus.IN_PROGRESS, TopicStatus.TO_LEARN, TopicStatus.DEFERRED)))


class NotesPage(QWidget):
    """Read-only Vault browser with three-version Markdown comparison."""

    def __init__(self, vault_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vault_root = Path(vault_root)
        self.records = sorted(scan_vault(self.vault_root), key=lambda row: row.date, reverse=True)
        self._visible: list[TopicRecord] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        heading = QLabel("笔记浏览")
        heading.setObjectName("pageHeading")
        root.addWidget(heading)
        filters = QHBoxLayout()
        self.subject_filter = QComboBox()
        self.subject_filter.addItems(SUBJECTS)
        self.status_filter = QComboBox()
        self.status_filter.addItems(STATUSES)
        self.subject_filter.currentIndexChanged.connect(self.refresh)
        self.status_filter.currentIndexChanged.connect(self.refresh)
        filters.addWidget(QLabel("学科"))
        filters.addWidget(self.subject_filter)
        filters.addWidget(QLabel("状态"))
        filters.addWidget(self.status_filter)
        filters.addStretch(1)
        root.addLayout(filters)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.topic_list = QListWidget()
        self.topic_list.setMinimumWidth(210)
        self.topic_list.currentRowChanged.connect(self._show_record)
        split.addWidget(self.topic_list)
        self.readers: list[QTextBrowser] = []
        self.reader_split = QSplitter(Qt.Orientation.Horizontal)
        for _ in VERSIONS:
            reader = QTextBrowser()
            reader.setOpenExternalLinks(False)
            reader.setReadOnly(True)
            self.readers.append(reader)
            self.reader_split.addWidget(reader)
        split.addWidget(self.reader_split)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        root.addWidget(split, 1)
        self.refresh()

    def refresh(self) -> None:
        self.records = sorted(scan_vault(self.vault_root), key=lambda row: row.date, reverse=True)
        subject = self.subject_filter.currentText()
        status = self.status_filter.currentText()
        self._visible = [
            record for record in self.records
            if (subject == "全部学科" or record.subject == subject)
            and (status == "全部状态" or record.status.value == status)
        ]
        self.topic_list.blockSignals(True)
        self.topic_list.clear()
        for record in self._visible:
            item = QListWidgetItem(f"{record.date}  {record.topic}\n{record.status.value}")
            item.setData(Qt.ItemDataRole.UserRole, record)
            self.topic_list.addItem(item)
        self.topic_list.blockSignals(False)
        if self._visible:
            self.topic_list.setCurrentRow(0)
        else:
            self._show_record(-1)

    def _show_record(self, index: int) -> None:
        if index < 0 or index >= len(self._visible):
            for reader in self.readers:
                reader.hide()
                reader.clear()
            return
        record = self._visible[index]
        names = VERSIONS if record.has_folder else (record.path.name,)
        for column, reader in enumerate(self.readers):
            if column >= len(names):
                reader.hide()
                continue
            name = names[column]
            path = record.path / name if record.has_folder else record.path
            reader.show()
            reader.setDocumentTitle(name)
            if not path.is_file():
                reader.setMarkdown(f"# {name}\n\n此版本尚未创建")
                continue
            try:
                reader.setMarkdown(f"## {name}\n\n存在\n\n" + path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError):
                reader.setMarkdown(f"# {name}\n\n无法读取此笔记")
