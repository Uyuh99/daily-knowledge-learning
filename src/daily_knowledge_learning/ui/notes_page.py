from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QLineEdit,
    QSplitter, QTextBrowser, QVBoxLayout, QWidget, QStyledItemDelegate, QStyleOptionViewItem, QStyle,
)

from ..models import TopicRecord, TopicStatus
from ..vault_scan import scan_vault
from . import theme
from .widgets import EmptyState, PageHeader, StatusPill, field_label, set_reading_metrics

VERSIONS = ("01-交流前版.md", "02-交流后版.md", "03-AI参考版.md")
DEFAULT_SUBJECTS = ("心理学", "经济学")
STATUSES = ("全部状态", *(status.value for status in (TopicStatus.COMPLETED, TopicStatus.IN_PROGRESS, TopicStatus.TO_LEARN, TopicStatus.DEFERRED)))


class _TopicDelegate(QStyledItemDelegate):
    """Paint selection behind the custom row without painting its text twice."""

    def paint(self, painter, option, index):
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        styled.text = ""
        styled.widget.style().drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter, styled.widget)


class NotesPage(QWidget):
    """Read-only Vault browser with three-version Markdown comparison."""

    def __init__(self, vault_root: Path, subjects: tuple[str, ...] = DEFAULT_SUBJECTS, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vault_root = Path(vault_root)
        self.subjects = tuple(subjects)
        self.records = sorted(scan_vault(self.vault_root), key=lambda row: row.date, reverse=True)
        self._visible: list[TopicRecord] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(theme.SPACE[2])
        root.addWidget(PageHeader("笔记浏览", "按学科与状态筛选，三个版本并排对照"))

        filters = QHBoxLayout()
        filters.setSpacing(theme.SPACE[1])
        self.subject_filter = QComboBox()
        self.subject_filter.addItems(("全部学科", *self.subjects))
        self.status_filter = QComboBox()
        self.status_filter.addItems(STATUSES)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索主题、日期或学科")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(190)
        self.subject_filter.currentIndexChanged.connect(self.refresh)
        self.status_filter.currentIndexChanged.connect(self.refresh)
        self.search.textChanged.connect(self.refresh)
        filters.addWidget(field_label("学科"))
        filters.addWidget(self.subject_filter)
        filters.addSpacing(theme.SPACE[2])
        filters.addWidget(field_label("状态"))
        filters.addWidget(self.status_filter)
        filters.addSpacing(theme.SPACE[2])
        filters.addWidget(field_label("搜索"))
        filters.addWidget(self.search, 1)
        filters.addStretch(1)
        root.addLayout(filters)

        self.result_count = QLabel()
        self.result_count.setObjectName("metaText")
        root.addWidget(self.result_count)

        split = QSplitter(Qt.Orientation.Horizontal)
        topic_panel = QWidget()
        topic_layout = QVBoxLayout(topic_panel)
        topic_layout.setContentsMargins(0, 0, 0, 0)
        topic_layout.setSpacing(0)
        self.topic_list = QListWidget()
        self.topic_list.setItemDelegate(_TopicDelegate(self.topic_list))
        self.topic_list.setMinimumWidth(210)
        self.topic_list.currentRowChanged.connect(self._show_record)
        self.list_empty = EmptyState("没有符合条件的主题", "试试把学科或状态筛选改回「全部」")
        topic_layout.addWidget(self.topic_list, 1)
        topic_layout.addWidget(self.list_empty, 1)
        split.addWidget(topic_panel)
        self.readers: list[QTextBrowser] = []
        self.reader_headers: list[QLabel] = []
        self.reader_columns: list[QFrame] = []
        self.reader_split = QSplitter(Qt.Orientation.Horizontal)
        self.version_picker = QComboBox()
        self.version_picker.addItems(VERSIONS)
        self.version_picker.currentIndexChanged.connect(self._select_reader)
        self.version_picker.hide()
        for name in VERSIONS:
            column = QFrame()
            column.setObjectName("card")
            layout = QVBoxLayout(column)
            layout.setContentsMargins(12, 10, 12, 10)
            layout.setSpacing(theme.SPACE[1])
            header = QLabel(name.removesuffix(".md"))
            header.setObjectName("sectionTitle")
            reader = QTextBrowser()
            reader.setObjectName("reader")
            reader.setOpenExternalLinks(False)
            reader.setReadOnly(True)
            set_reading_metrics(reader)
            self.reader_headers.append(header)
            self.readers.append(reader)
            self.reader_columns.append(column)
            layout.addWidget(header)
            layout.addWidget(reader, 1)
            self.reader_split.addWidget(column)
        split.addWidget(self.reader_split)
        split.setSizes([240, 720])
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        root.addWidget(self.version_picker)
        root.addWidget(split, 1)
        self.splitter = split
        self.refresh()

    def set_subjects(self, subjects: tuple[str, ...]) -> None:
        current = self.subject_filter.currentText()
        self.subjects = tuple(subjects)
        self.subject_filter.blockSignals(True)
        self.subject_filter.clear()
        self.subject_filter.addItems(("全部学科", *self.subjects))
        self.subject_filter.setCurrentText(current if current in self.subjects or current == "全部学科" else "全部学科")
        self.subject_filter.blockSignals(False)
        self.refresh()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_reader_mode()

    def _update_reader_mode(self) -> None:
        # Each comparison column needs room for Chinese headings and prose.
        narrow = self.width() < 1080
        self.version_picker.setVisible(narrow)
        if narrow:
            self._select_reader(self.version_picker.currentIndex())
        else:
            for column in self.reader_columns:
                column.show()

    def _select_reader(self, index: int) -> None:
        for column_index, column in enumerate(self.reader_columns):
            column.setVisible(column_index == index)

    def refresh(self) -> None:
        self.records = sorted(scan_vault(self.vault_root), key=lambda row: row.date, reverse=True)
        subject, status = self.subject_filter.currentText(), self.status_filter.currentText()
        query = self.search.text().strip().casefold()
        self._visible = [
            record for record in self.records
            if (subject == "全部学科" or record.subject == subject)
            and (status == "全部状态" or record.status.value == status)
            and (not query or query in " ".join((record.topic, record.subject, record.date)).casefold())
        ]
        self.result_count.setText(f"显示 {len(self._visible)} / {len(self.records)} 个主题")
        self.topic_list.blockSignals(True)
        self.topic_list.clear()
        for record in self._visible:
            item = QListWidgetItem(f"{record.date}  {record.topic}\n{record.status.value}")
            item.setData(Qt.ItemDataRole.UserRole, record)
            item.setSizeHint(QSize(180, 86))
            self.topic_list.addItem(item)
            row = QWidget()
            layout = QVBoxLayout(row)
            layout.setContentsMargins(10, 8, 10, 8)
            layout.setSpacing(5)
            title = QLabel(record.topic)
            title.setObjectName("noteTopicTitle")
            title.setWordWrap(True)
            layout.addWidget(title)
            metadata = QHBoxLayout()
            date = QLabel(record.date)
            date.setObjectName("metaText")
            metadata.addWidget(date)
            metadata.addStretch()
            metadata.addWidget(StatusPill(record.status.value))
            layout.addLayout(metadata)
            self.topic_list.setItemWidget(item, row)
        self.topic_list.blockSignals(False)
        if not self._visible:
            self.topic_list.setCurrentRow(-1)
            self.topic_list.hide()
            self.list_empty.show()
            if self.search.text().strip():
                self.list_empty.set_text("没有匹配的主题", "换一个关键词，或清空搜索后再试")
            else:
                self.list_empty.set_text("没有符合条件的主题", "试试把学科或状态筛选改回「全部」")
            self._show_record(-1)
        else:
            self.topic_list.show()
            self.list_empty.hide()
            self.topic_list.setCurrentRow(0)

    def _show_record(self, index: int) -> None:
        if index < 0 or index >= len(self._visible):
            for reader in self.readers:
                reader.clear()
            return
        record = self._visible[index]
        names = VERSIONS if record.has_folder else (record.path.name,)
        for column, (name, reader, header) in enumerate(zip(VERSIONS, self.readers, self.reader_headers)):
            exists = column < len(names) and (record.path / names[column] if record.has_folder else record.path).is_file()
            actual = names[column] if column < len(names) else name
            path = record.path / actual if record.has_folder else record.path
            header.setText(f"{name.removesuffix('.md')}  ·  {'存在' if exists else '尚未创建'}")
            reader.setVisible(column < len(names))
            self.reader_columns[column].setVisible(column < len(names))
            if column >= len(names):
                reader.setMarkdown("此版本尚未创建")
            elif not exists:
                reader.setMarkdown("此版本尚未创建")
            else:
                try:
                    text = path.read_text(encoding="utf-8")
                    if text.startswith("---\n") or text.startswith("---\r\n"):
                        lines = text.splitlines(keepends=True)
                        closing = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
                        if closing is not None:
                            text = "".join(lines[closing + 1:]).lstrip("\r\n")
                    reader.setMarkdown(text)
                except (OSError, UnicodeError):
                    reader.setMarkdown("无法读取此笔记")
        self._update_reader_mode()
