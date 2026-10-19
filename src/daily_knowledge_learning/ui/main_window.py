"""Main window shell: sidebar rail plus the stacked content area."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QSplitter, QWidget

from . import theme
from .pages import ContentArea
from .sidebar import Sidebar

WINDOW_TITLE = "每日知识点学习"


class MainWindow(QMainWindow):
    def __init__(
        self,
        vault_path: Path | None = None,
        config_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1120, 720)
        self.setMinimumSize(760, 480)

        central = QWidget(self)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.content = ContentArea(vault_path, config_path)
        self.content.setObjectName("pageSurface")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(0)
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.content)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([theme.SIDEBAR_WIDTH, 900])
        layout.addWidget(splitter)
        self.setCentralWidget(central)

        self.sidebar.entry_selected.connect(self._on_nav_changed)
        self._on_nav_changed(self.sidebar.current_key())

    def _on_nav_changed(self, key: str) -> None:
        self.content.show_key(key)

    def closeEvent(self, event) -> None:
        if self.content.editor.is_dirty() and not self.content.editor.confirm_discard():
            event.ignore()
            return
        event.accept()
