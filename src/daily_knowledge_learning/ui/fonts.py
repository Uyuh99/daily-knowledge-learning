"""Font helpers so Chinese text never renders as tofu boxes on Windows.

The UI asks for a font stack of families that ship with Chinese Windows
(Microsoft YaHei UI / Microsoft YaHei / SimHei / SimSun) and falls back to
whatever the system reports, instead of relying on Qt's default family (which
can miss CJK).
"""

from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase

# Ordered preference: modern UI fonts first, then older Windows CJK fonts.
CJK_FONT_CANDIDATES = (
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "微软雅黑",
    "Noto Sans SC",
    "Noto Sans CJK SC",
    "SimHei",
    "黑体",
    "SimSun",
    "宋体",
    "Source Han Sans SC",
)

BASE_POINT_SIZE = 10.5


def resolve_cjk_family() -> str | None:
    """Return the first installed family from the preference list, if any."""

    installed = set(QFontDatabase.families())
    for family in CJK_FONT_CANDIDATES:
        if family in installed:
            return family
    return None


def build_app_font() -> QFont:
    """Build the base font used by every widget in the app."""

    family = resolve_cjk_family()
    font = QFont()
    if family is not None:
        font.setFamily(family)
    font.setPointSizeF(BASE_POINT_SIZE)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font


def resolve_editorial_family() -> str:
    """Pair Chinese serif headings with the legible sans-serif UI body."""
    installed = set(QFontDatabase.families())
    for family in ("Noto Serif SC Medium", "STZhongsong", "SimSun", "宋体"):
        if family in installed:
            return family
    return resolve_cjk_family() or "serif"


def build_display_font(point_size: float = 15.0, weight: QFont.Weight = QFont.Weight.DemiBold) -> QFont:
    """Build a larger font for headings that sit outside the stylesheet."""

    font = build_app_font()
    font.setPointSizeF(point_size)
    font.setWeight(weight)
    return font


__all__ = [
    "CJK_FONT_CANDIDATES",
    "build_app_font",
    "build_display_font",
    "resolve_cjk_family",
    "resolve_editorial_family",
]
