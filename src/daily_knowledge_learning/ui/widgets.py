"""Reusable widget primitives that carry the app's visual language.

Pages compose these instead of restyling raw Qt widgets, so hierarchy stays
consistent across screens.  All styling comes from :mod:`theme`; nothing here
defines its own colours.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme

# --- page structure ---------------------------------------------------------


class PageHeader(QWidget):
    """Page title, optional subtitle, and a right-aligned action row."""

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(theme.SPACE[3])

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(theme.SPACE[0] + 2)
        self.title = QLabel(title)
        self.title.setObjectName("pageHeading")
        text.addWidget(self.title)
        self.subtitle = QLabel(subtitle)
        self.subtitle.setObjectName("pageSubtitle")
        self.subtitle.setWordWrap(True)
        self.subtitle.setVisible(bool(subtitle))
        text.addWidget(self.subtitle)
        layout.addLayout(text, 1)

        self.actions = QHBoxLayout()
        self.actions.setContentsMargins(0, 0, 0, 0)
        self.actions.setSpacing(theme.SPACE[1])
        layout.addLayout(self.actions)

    def add_action(self, button: QWidget) -> None:
        self.actions.addWidget(button)

    def set_subtitle(self, text: str) -> None:
        self.subtitle.setText(text)
        self.subtitle.setVisible(bool(text))


class SectionTitle(QLabel):
    """Small heading that opens a block of content inside a page."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("sectionTitle")


class Hairline(QFrame):
    """One-pixel divider."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("hairline")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedHeight(1)


class Card(QFrame):
    """Bordered white surface that groups related content."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        margins: tuple[int, int, int, int] = (18, 16, 18, 16),
        spacing: int = theme.SPACE[2],
        flat: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("cardFlat" if flat else "card")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(*margins)
        self.body.setSpacing(spacing)


class EmptyState(QFrame):
    """Dashed panel explaining why a region has no content and what to do."""

    def __init__(
        self,
        title: str,
        hint: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("emptyState")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(theme.SPACE[1])
        layout.addStretch(1)
        self.title = QLabel(title)
        self.title.setObjectName("emptyTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setWordWrap(True)
        layout.addWidget(self.title)
        self.hint = QLabel(hint)
        self.hint.setObjectName("emptyHint")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setWordWrap(True)
        self.hint.setVisible(bool(hint))
        layout.addWidget(self.hint)
        layout.addStretch(1)

    def set_text(self, title: str, hint: str = "") -> None:
        self.title.setText(title)
        self.hint.setText(hint)
        self.hint.setVisible(bool(hint))


class StatusPill(QLabel):
    """Compact coloured label for a topic status."""

    def __init__(self, status: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusPill")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.set_status(status)

    def set_status(self, status: str) -> None:
        tone = theme.STATUS_TONES.get(status, theme.INK_3)
        self.setText(status)
        self.setStyleSheet(
            f"background-color: {theme.tint(tone, 0.86)};"
            f" color: {tone};"
            f" border-radius: {theme.RADIUS_SM}px;"
            f" padding: 1px 8px;"
            f" font-size: {theme.FONT_MICRO}px;"
            " font-weight: 600;"
        )


# --- helpers ----------------------------------------------------------------


def primary_button(text: str, parent: QWidget | None = None) -> QPushButton:
    button = QPushButton(text, parent)
    button.setProperty("variant", "primary")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def secondary_button(text: str, parent: QWidget | None = None) -> QPushButton:
    button = QPushButton(text, parent)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def ghost_button(text: str, parent: QWidget | None = None) -> QPushButton:
    button = QPushButton(text, parent)
    button.setProperty("variant", "ghost")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def field_label(text: str, parent: QWidget | None = None) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName("fieldLabel")
    return label


def meta_label(text: str = "", parent: QWidget | None = None) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName("metaText")
    return label


def apply_document_style(document: QTextDocument) -> None:
    """Give a QTextDocument the shared reading typography."""

    document.setDefaultStyleSheet(theme.document_stylesheet())
    document.setDocumentMargin(2)


def set_reading_metrics(widget) -> None:
    """Tune a QTextEdit/QTextBrowser for long-form Chinese reading."""

    widget.setLineWrapMode(widget.LineWrapMode.WidgetWidth)
    if hasattr(widget, "document"):
        document = widget.document()
        document.setDocumentMargin(14)
        document.setDefaultStyleSheet(theme.document_stylesheet())
