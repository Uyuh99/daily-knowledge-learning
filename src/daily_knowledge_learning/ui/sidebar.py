"""Left-hand navigation sidebar for the main window."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class NavEntry:
    """One navigation destination shown in the sidebar."""

    key: str
    title: str


# The four entries required by the UI skeleton task.
NAV_ENTRIES: tuple[NavEntry, ...] = (
    NavEntry(key="home", title="首页"),
    NavEntry(key="today", title="今日学习"),
    NavEntry(key="map", title="学习地图"),
    NavEntry(key="settings", title="设置"),
)


class Sidebar(QWidget):
    """Vertical navigation list; emits ``entry_selected`` on user click."""

    entry_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(180)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(8)

        brand = QLabel("每日知识点学习")
        brand.setObjectName("sidebarBrand")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(brand)

        self._list = QListWidget()
        self._list.setObjectName("sidebarList")
        self._list.setFrameShape(QListWidget.Shape.NoFrame)
        self._list.setIconSize(QSize(0, 0))
        for entry in NAV_ENTRIES:
            item = QListWidgetItem(entry.title)
            item.setData(Qt.ItemDataRole.UserRole, entry.key)
            self._list.addItem(item)
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list, 1)

        version = QLabel("技术验证骨架 v0.1")
        version.setObjectName("sidebarFooter")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        self._list.setCurrentRow(0)

    # -- helpers ---------------------------------------------------------
    def current_key(self) -> str:
        item = self._list.currentItem()
        if item is None:
            return NAV_ENTRIES[0].key
        return str(item.data(Qt.ItemDataRole.UserRole))

    def select(self, key: str) -> None:
        """Programmatically select a navigation entry by key."""
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == key:
                self._list.setCurrentRow(row)
                return

    def _on_row_changed(self, row: int) -> None:
        item = self._list.item(row)
        if item is None:
            return
        self.entry_selected.emit(str(item.data(Qt.ItemDataRole.UserRole)))
