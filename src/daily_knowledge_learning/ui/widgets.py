"""Reusable widget primitives that carry the app's visual language.

Pages compose these instead of restyling raw Qt widgets, so hierarchy stays
consistent across screens.  All styling comes from :mod:`theme`; nothing here
defines its own colours.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QTextDocument, QPainter, QPainterPath, QPen, QColor, QIcon, QPixmap, QPolygonF
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


def navigation_icon(key: str) -> QIcon:
    """Small vector navigation marks; no platform-dependent icon font."""
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(theme.INK_2), 1.6, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if key == "home":
        painter.drawPolyline(QPolygonF([QPointF(3, 10), QPointF(12, 3), QPointF(21, 10)]))
        painter.drawRoundedRect(QRectF(6, 10, 12, 11), 1, 1)
        painter.drawLine(11, 21, 11, 15)
    elif key == "today":
        painter.drawEllipse(QRectF(3, 3, 18, 18))
        painter.drawLine(12, 7, 12, 12)
        painter.drawLine(12, 12, 16, 14)
    elif key == "review":
        painter.drawEllipse(QRectF(3, 3, 18, 18))
        painter.drawPolyline(QPolygonF([QPointF(7, 12), QPointF(10, 15), QPointF(17, 8)]))
    elif key == "stats":
        painter.drawLine(5, 19, 5, 5)
        painter.drawLine(5, 19, 20, 19)
        painter.drawLine(8, 15, 8, 11)
        painter.drawLine(12, 15, 12, 8)
        painter.drawLine(16, 15, 16, 5)
    elif key == "notes":
        painter.drawRoundedRect(QRectF(5, 3, 15, 18), 2, 2)
        painter.drawLine(9, 4, 9, 20)
        painter.drawLine(12, 9, 17, 9)
        painter.drawLine(12, 13, 17, 13)
    elif key == "map":
        painter.drawLine(7, 7, 17, 12)
        painter.drawLine(17, 12, 7, 18)
        for x, y in ((6, 6), (18, 12), (6, 19)):
            painter.setBrush(QColor(theme.SURFACE_ALT))
            painter.drawEllipse(QPointF(x, y), 3, 3)
    else:
        painter.drawEllipse(QRectF(5, 5, 14, 14))
        painter.drawEllipse(QRectF(10, 10, 4, 4))
        for x, y, a, b in ((12, 2, 12, 5), (12, 19, 12, 22), (2, 12, 5, 12), (19, 12, 22, 12)):
            painter.drawLine(x, y, a, b)
    painter.end()
    return QIcon(pixmap)


class BookIllustration(QWidget):
    """A quiet reading desk; original vector artwork, no external assets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(168, 132)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.ACCENT_SOFT))
        painter.drawEllipse(QRectF(15, 9, 124, 112))
        painter.setPen(QPen(QColor(theme.ILLUSTRATION_MID), 1.2))
        painter.drawLine(9, 112, 157, 112)
        painter.setBrush(QColor(theme.SURFACE))
        painter.setPen(QPen(QColor(theme.ACCENT), 1.4))
        for points in (
            [QPointF(15, 52), QPointF(61, 46), QPointF(75, 53), QPointF(75, 108), QPointF(60, 101), QPointF(15, 106)],
            [QPointF(75, 53), QPointF(91, 46), QPointF(135, 51), QPointF(135, 105), QPointF(91, 101), QPointF(75, 108)],
        ):
            painter.drawPolygon(QPolygonF(points))
        painter.setPen(QPen(QColor(theme.ILLUSTRATION_MID), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for y in (64, 73, 82, 91):
            painter.drawLine(25, y, 59, y - 3)
            painter.drawLine(91, y - 3, 124, y)
        painter.setBrush(QColor(theme.TERRACOTTA))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygonF([QPointF(106, 48), QPointF(113, 49), QPointF(113, 69), QPointF(109, 65), QPointF(106, 68)]))
        painter.setPen(QPen(QColor(theme.ACCENT), 1.3))
        painter.drawLine(132, 43, 144, 15)
        painter.setBrush(QColor(theme.ILLUSTRATION_MID))
        for x, y, angle in ((135, 25, -30), (141, 16, 25), (132, 35, -35)):
            painter.save()
            painter.translate(x, y)
            painter.rotate(angle)
            painter.drawEllipse(QRectF(-4, -8, 7, 14))
            painter.restore()
        painter.end()


class SubjectIllustration(QWidget):
    def __init__(self, subject: str, parent=None):
        super().__init__(parent)
        self.subject = subject
        self.setFixedSize(38, 38)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        psychology = self.subject == "psychology"
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.MINT if psychology else theme.PEACH))
        painter.drawRoundedRect(QRectF(0, 0, 38, 38), 10, 10)
        painter.setPen(QPen(QColor(theme.ACCENT if psychology else theme.TERRACOTTA), 1.3,
                            Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if psychology:
            painter.drawEllipse(QRectF(9, 9, 20, 20))
            path = QPainterPath(QPointF(13, 22))
            path.cubicTo(12, 12, 27, 12, 25, 21)
            path.cubicTo(23, 27, 16, 22, 19, 18)
            painter.drawPath(path)
        else:
            painter.drawLine(19, 10, 19, 28)
            painter.drawLine(11, 28, 27, 28)
            painter.drawLine(9, 14, 29, 14)
            for x in (12, 26):
                painter.drawLine(x, 14, x - 4, 23)
                painter.drawLine(x, 14, x + 4, 23)
                painter.drawArc(QRectF(x - 4, 20, 8, 5), 180 * 16, 180 * 16)
        painter.end()

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
