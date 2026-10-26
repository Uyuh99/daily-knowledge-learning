"""Left navigation rail."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from . import theme
from .widgets import navigation_icon

@dataclass(frozen=True)
class NavEntry:
    key: str
    title: str


NAV_ENTRIES = (
    NavEntry("home", "首页"),
    NavEntry("today", "今日学习"),
    NavEntry("review", "今日复习"),
    NavEntry("stats", "学习统计"),
    NavEntry("notes", "笔记查看"),
    NavEntry("vault_qa", "知识库问答"),
    NavEntry("map", "学习地图"),
    NavEntry("settings", "设置"),
)

# Entries shown in the primary group; the rest sit below a divider.
_PRIMARY_KEYS = ("home", "today", "review", "stats", "notes", "vault_qa", "map")


class Sidebar(QWidget):
    """Brand, grouped navigation and a quiet footer."""

    entry_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(theme.SIDEBAR_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 24, 16, 18)
        layout.setSpacing(theme.SPACE[1])

        mark = QLabel("知")
        mark.setObjectName("brandMark")
        mark.setFixedSize(42, 42)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(mark)
        layout.addSpacing(8)
        brand = QLabel("每日知识点学习")
        brand.setObjectName("sidebarBrand")
        layout.addWidget(brand)
        caption = QLabel("一页思考，一点新知。")
        caption.setObjectName("sidebarCaption")
        caption.setWordWrap(True)
        layout.addWidget(caption)
        section = QLabel("我的书房")
        section.setObjectName("sidebarSection")
        layout.addWidget(section)

        self._list = QListWidget()
        self._list.setObjectName("sidebarList")
        self._list.setFrameShape(QFrame.Shape.NoFrame)
        self._list.setIconSize(QSize(18, 18))
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for entry in NAV_ENTRIES:
            item = QListWidgetItem(entry.title)
            item.setIcon(navigation_icon(entry.key))
            item.setData(Qt.ItemDataRole.UserRole, entry.key)
            item.setToolTip(entry.title)
            item.setSizeHint(QSize(0, 40))
            self._list.addItem(item)
        # Size the rail to its rows so it never stretches a gap between groups.
        self._list.setFixedHeight(self._list.count() * 44 + 8)
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list)
        layout.addStretch(1)

        footer = QLabel(f"心理学 · 经济学\n本地知识库  /  v{__version__}")
        footer.setObjectName("sidebarCaption")
        layout.addWidget(footer)
        self.select("home")
    def current_key(self) -> str:
        item = self._list.currentItem()
        if item is None:
            return "home"
        return str(item.data(Qt.ItemDataRole.UserRole) or "home")

    def select(self, key: str) -> None:
        for row in range(self._list.count()):
            if self._list.item(row).data(Qt.ItemDataRole.UserRole) == key:
                self._list.setCurrentRow(row)
                return

    def _on_row_changed(self, row: int) -> None:
        item = self._list.item(row)
        if item is None:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        if key:
            self.entry_selected.emit(str(key))
