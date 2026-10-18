from __future__ import annotations
from dataclasses import dataclass
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QSizePolicy, QVBoxLayout, QWidget

@dataclass(frozen=True)
class NavEntry:
    key: str
    title: str

NAV_ENTRIES = (NavEntry("home", "首页"), NavEntry("today", "今日学习"), NavEntry("map", "学习地图"), NavEntry("settings", "设置"))

class Sidebar(QWidget):
    entry_selected = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent); self.setObjectName("sidebar"); self.setFixedWidth(180); self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self); layout.setContentsMargins(8, 12, 8, 12); layout.setSpacing(8); brand = QLabel("每日知识点学习"); brand.setObjectName("sidebarBrand"); brand.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(brand)
        self._list = QListWidget(); self._list.setObjectName("sidebarList"); self._list.setFrameShape(QListWidget.Shape.NoFrame); self._list.setIconSize(QSize(0, 0))
        for entry in NAV_ENTRIES:
            item = QListWidgetItem(entry.title); item.setData(Qt.ItemDataRole.UserRole, entry.key); self._list.addItem(item)
        self._list.currentRowChanged.connect(self._on_row_changed); layout.addWidget(self._list, 1); footer = QLabel("v0.1"); footer.setObjectName("sidebarFooter"); footer.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(footer); self._list.setCurrentRow(0)
    def current_key(self) -> str:
        item = self._list.currentItem(); return str(item.data(Qt.ItemDataRole.UserRole)) if item else "home"
    def select(self, key: str) -> None:
        for row in range(self._list.count()):
            if self._list.item(row).data(Qt.ItemDataRole.UserRole) == key: self._list.setCurrentRow(row); return
    def _on_row_changed(self, row: int) -> None:
        item = self._list.item(row)
        if item: self.entry_selected.emit(str(item.data(Qt.ItemDataRole.UserRole)))
