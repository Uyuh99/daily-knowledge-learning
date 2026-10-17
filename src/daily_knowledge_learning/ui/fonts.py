"""Font helpers so Chinese text never renders as tofu (豆腐块) on Windows.

The UI asks for a font stack of fonts that ship with Chinese Windows
(Microsoft YaHei / SimHei / SimSun) and falls back to whatever the system
reports, instead of relying on Qt's default family (which can miss CJK).
"""

from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase

# Ordered preference: modern UI font first, then older Windows CJK fonts.
CJK_FONT_CANDIDATES = (
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "微软雅黑",
    "SimHei",
    "黑体",
    "SimSun",
    "宋体",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
)


def resolve_cjk_family() -> str | None:
    """Return the first installed family from the preference list, if any."""
    installed = set(QFontDatabase.families())
    for family in CJK_FONT_CANDIDATES:
        if family in installed:
            return family
    return None


def build_app_font() -> QFont:
    """Build a font suitable for Simplified Chinese UI text."""
    family = resolve_cjk_family()
    font = QFont()
    if family is not None:
        font.setFamily(family)
    font.setPointSize(10)
    return font
