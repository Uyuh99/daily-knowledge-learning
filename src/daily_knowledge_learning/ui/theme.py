"""Design tokens and the global Qt stylesheet for the desktop app.

Single source of truth for the visual language: colour, type, spacing, radius,
and the widget rules built from them.  Pages should not carry page-local
stylesheets — read values from :data:`C` / :data:`SPACE` when a layout needs a
number, and use the ``variant`` dynamic property for emphasis changes.

The visual reference is awesome-design-md's Claude DESIGN.md: warm cream
surfaces, editorial serif headings and restrained line illustrations. Warm ink
and a muted terracotta accent create a personal study without green tones.
"""

from __future__ import annotations

from PySide6.QtGui import QColor

# --- colour -----------------------------------------------------------------

PAPER = "#F8F6F0"          # warm paper canvas
SURFACE = "#FFFEFA"        # reading paper, cards and editors
SURFACE_ALT = "#F0EEE5"    # sidebar and quiet surfaces
SURFACE_SUNK = "#E9E1D6"   # warm progress tracks
BORDER = "#E3E0D4"         # soft paper edges
BORDER_STRONG = "#CFC5B8"  # input outlines

INK = "#38332D"            # warm ink
INK_2 = "#645D55"          # body and supporting copy
INK_3 = "#7A7067"          # captions
INK_INVERSE = "#FFFFFF"

ACCENT = "#9D563F"         # readable terracotta on paper
ACCENT_HOVER = "#854431"
ACCENT_PRESS = "#713B2B"
ACCENT_SOFT = "#F0E2D8"
NAVY = "#48382D"           # legacy token used for illustration ink
MINT = "#F2ECE2"           # legacy name; warm parchment, without green
PEACH = "#F4E5D9"
SKY = "#ECE8E1"
TERRACOTTA = "#9D563F"
ILLUSTRATION_MID = "#BAA28A"

OK = "#75604A"
WARN = "#A0721C"
DANGER = "#A8492F"
DEFERRED = "#9A5B2C"

CODE_BG = "#F3EEE5"

# --- status tones (learning topic states) -----------------------------------

STATUS_TONES = {
    "已学": OK,
    "进行中": WARN,
    "待学习": INK_3,
    "已搁置": DEFERRED,
}

# --- metrics ----------------------------------------------------------------

SPACE = (4, 8, 12, 16, 24, 32)

RADIUS_SM = 6
RADIUS_MD = 8
RADIUS_LG = 12

CONTROL_HEIGHT = 38
SIDEBAR_WIDTH = 204

# --- type -------------------------------------------------------------------

FONT_DISPLAY = 28
FONT_TITLE = 16
FONT_SECTION = 14
FONT_BODY = 14
FONT_META = 12
FONT_MICRO = 11


def tint(color: str, ratio: float) -> str:
    """Blend ``color`` toward the paper colour; used for soft badge fills."""

    base = QColor(color)
    paper = QColor(PAPER)
    red = round(base.red() * (1 - ratio) + paper.red() * ratio)
    green = round(base.green() * (1 - ratio) + paper.green() * ratio)
    blue = round(base.blue() * (1 - ratio) + paper.blue() * ratio)
    return QColor(red, green, blue).name()


def stylesheet() -> str:
    """Return the application-wide Qt stylesheet."""

    from .fonts import resolve_editorial_family

    return _TEMPLATE.format(
        DISPLAY_FAMILY=resolve_editorial_family(),
        PAPER=PAPER,
        SURFACE=SURFACE,
        SURFACE_ALT=SURFACE_ALT,
        SURFACE_SUNK=SURFACE_SUNK,
        BORDER=BORDER,
        BORDER_STRONG=BORDER_STRONG,
        INK=INK,
        INK_2=INK_2,
        INK_3=INK_3,
        INK_INVERSE=INK_INVERSE,
        ACCENT=ACCENT,
        ACCENT_HOVER=ACCENT_HOVER,
        ACCENT_PRESS=ACCENT_PRESS,
        ACCENT_SOFT=ACCENT_SOFT,
        OK=OK,
        WARN=WARN,
        DANGER=DANGER,
        DEFERRED=DEFERRED,
        CODE_BG=CODE_BG,
        NAVY=NAVY,
        MINT=MINT,
        PEACH=PEACH,
        SKY=SKY,
        TERRACOTTA=TERRACOTTA,
        R_SM=RADIUS_SM,
        R_MD=RADIUS_MD,
        R_LG=RADIUS_LG,
        H=CONTROL_HEIGHT,
        F_DISPLAY=FONT_DISPLAY,
        F_TITLE=FONT_TITLE,
        F_SECTION=FONT_SECTION,
        F_BODY=FONT_BODY,
        F_META=FONT_META,
        F_MICRO=FONT_MICRO,
    )


def document_stylesheet() -> str:
    """Stylesheet for QTextDocument content (markdown previews, note readers).

    Kept separate from :func:`stylesheet` because Qt rich text understands a
    different CSS subset than the widget stylesheet does.
    """

    return (
        f"body {{ color: {INK}; font-size: {FONT_BODY + 1}px; }}"
        f" h1 {{ font-size: {FONT_DISPLAY}px; font-weight: 600; color: {INK};"
        " margin-top: 4px; margin-bottom: 12px; }}"
        f" h2 {{ font-size: {FONT_TITLE + 2}px; font-weight: 600; color: {INK};"
        " margin-top: 18px; margin-bottom: 8px; }}"
        f" h3 {{ font-size: {FONT_SECTION + 1}px; font-weight: 600; color: {INK};"
        " margin-top: 14px; margin-bottom: 6px; }}"
        f" p {{ margin-top: 0px; margin-bottom: 9px; }}"
        f" li {{ margin-bottom: 4px; }}"
        f" a {{ color: {ACCENT}; text-decoration: none; }}"
        f" code {{ background-color: {CODE_BG}; color: {INK}; }}"
        f" blockquote {{ color: {INK_2}; }}"
        f" hr {{ color: {BORDER}; }}"
        f" table {{ border-color: {BORDER}; }}"
    )


_TEMPLATE = """
/* ============================ base ============================ */

QWidget {{
    color: {INK};
    font-size: {F_BODY}px;
}}

QMainWindow, QDialog {{ background-color: {PAPER}; }}

QWidget#pageSurface {{ background-color: {PAPER}; }}

QToolTip {{
    background-color: {INK};
    color: {INK_INVERSE};
    border: none;
    padding: 5px 9px;
    font-size: {F_META}px;
}}

/* ============================ sidebar ========================= */

QWidget#sidebar {{
    background-color: {SURFACE_ALT};
    border-right: 1px solid {BORDER};
}}

QLabel#sidebarBrand {{
    color: {INK};
    font-size: {F_TITLE}px;
    font-weight: 600;
}}

QLabel#sidebarCaption {{
    color: {INK_3};
    font-size: {F_MICRO}px;
}}

QLabel#sidebarSection {{
    color: {INK_3};
    font-size: {F_MICRO}px;
    font-weight: 600;
}}

QFrame#sidebarRule {{ background-color: {BORDER}; border: none; }}

QListWidget#sidebarList {{
    background: transparent;
    border: none;
    outline: 0;
}}

QListWidget#sidebarList::item {{
    height: 38px;
    border-radius: {R_MD}px;
    padding-left: 12px;
    margin: 1px 0px;
    color: {INK_2};
    font-size: {F_BODY}px;
}}

QListWidget#sidebarList::item:hover {{
    background-color: {SURFACE};
    color: {INK};
}}

QListWidget#sidebarList::item:selected {{
    background-color: {ACCENT_SOFT};
    color: {ACCENT_PRESS};
    font-weight: 600;
}}

QListWidget#sidebarList::item:selected:hover {{
    background-color: {ACCENT_SOFT};
    color: {ACCENT_PRESS};
}}

/* ============================ page chrome ===================== */

QLabel#pageHeading {{
    color: {INK};
    font-size: {F_DISPLAY}px;
    font-family: "{DISPLAY_FAMILY}";
    font-weight: 400;
}}

QLabel#pageSubtitle {{
    color: {INK_3};
    font-size: {F_META}px;
}}

QLabel#sectionTitle {{
    color: {INK};
    font-size: {F_SECTION}px;
    font-weight: 600;
}}

QLabel#fieldLabel {{
    color: {INK_3};
    font-size: {F_META}px;
}}

QLabel#metaText {{
    color: {INK_3};
    font-size: {F_META}px;
}}

QLabel#bodyText {{ color: {INK_2}; }}

QFrame#card {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: {R_LG}px;
}}

QFrame#cardFlat {{
    background-color: {SURFACE};
    border: none;
    border-radius: {R_MD}px;
}}

QFrame#hairline {{
    background-color: {BORDER};
    border: none;
    max-height: 1px;
    min-height: 1px;
}}

/* empty / error states */

QFrame#emptyState {{
    background-color: {SURFACE};
    border: 1px dashed {BORDER_STRONG};
    border-radius: {R_LG}px;
}}

QLabel#emptyTitle {{
    color: {INK};
    font-size: {F_SECTION}px;
    font-weight: 600;
}}

QLabel#emptyHint {{
    color: {INK_3};
    font-size: {F_META}px;
}}

/* status pill */

QLabel#statusPill {{
    border-radius: {R_SM}px;
    padding: 1px 8px;
    font-size: {F_MICRO}px;
    font-weight: 600;
}}

/* ============================ buttons ========================= */

QPushButton {{
    background-color: {SURFACE};
    color: {INK};
    border: 1px solid {BORDER_STRONG};
    border-radius: {R_MD}px;
    padding: 5px 14px;
    min-height: 24px;
}}

QPushButton:hover {{
    background-color: {SURFACE_ALT};
    border-color: {INK_3};
}}

QPushButton:pressed {{
    background-color: {SURFACE_SUNK};
}}

QPushButton:focus {{
    border-color: {ACCENT};
}}

QPushButton:disabled {{
    background-color: {SURFACE_ALT};
    color: {INK_3};
    border-color: {BORDER};
}}

QPushButton[variant="primary"] {{
    background-color: {ACCENT};
    color: {INK_INVERSE};
    border: 1px solid {ACCENT};
    font-weight: 600;
    padding: 6px 18px;
}}

QPushButton[variant="primary"]:hover {{
    background-color: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}

QPushButton[variant="primary"]:pressed {{
    background-color: {ACCENT_PRESS};
    border-color: {ACCENT_PRESS};
}}

QPushButton[variant="primary"]:focus {{
    border-color: {ACCENT_PRESS};
}}

QPushButton[variant="primary"]:disabled {{
    background-color: {SURFACE_SUNK};
    color: {INK_3};
    border-color: {SURFACE_SUNK};
}}

QPushButton[variant="ghost"] {{
    background: transparent;
    border: 1px solid transparent;
    color: {INK_2};
    padding: 5px 10px;
}}

QPushButton[variant="ghost"]:hover {{
    background-color: {SURFACE_ALT};
    color: {INK};
}}

QPushButton[variant="danger"] {{
    background-color: {SURFACE};
    color: {DANGER};
    border: 1px solid {DANGER};
}}

QPushButton[variant="danger"]:hover {{
    background-color: #F7E9E4;
}}

/* ============================ inputs ========================== */

QLineEdit, QSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{
    background-color: {SURFACE};
    color: {INK};
    border: 1px solid {BORDER_STRONG};
    border-radius: {R_SM}px;
    padding: 5px 9px;
    selection-background-color: {ACCENT_SOFT};
    selection-color: {ACCENT_PRESS};
}}

QLineEdit, QSpinBox, QComboBox {{ min-height: 24px; }}

QLineEdit:hover, QSpinBox:hover, QComboBox:hover, QTextEdit:hover {{
    border-color: {INK_3};
}}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus,
QTextEdit:focus, QPlainTextEdit:focus {{
    border: 2px solid {ACCENT};
    padding: 4px 8px;
}}

QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
    background-color: {SURFACE_ALT};
    color: {INK_3};
    border-color: {BORDER};
}}

QLineEdit[readOnly="true"] {{
    background-color: {SURFACE_ALT};
}}

QComboBox::drop-down {{
    border: none;
    width: 22px;
}}

QComboBox QAbstractItemView {{
    background-color: {SURFACE};
    border: 1px solid {BORDER_STRONG};
    border-radius: {R_SM}px;
    padding: 4px;
    outline: 0;
    selection-background-color: {ACCENT_SOFT};
    selection-color: {ACCENT_PRESS};
}}

QSpinBox::up-button, QSpinBox::down-button {{ width: 16px; }}

/* ============================ text areas ====================== */

QTextEdit, QTextBrowser, QPlainTextEdit {{
    background-color: {SURFACE};
    padding: 10px 12px;
}}

QTextBrowser#reader {{
    background-color: {SURFACE};
}}

QTextBrowser#readerEmpty {{
    background-color: {SURFACE_ALT};
    color: {INK_3};
}}

/* ============================ tabs ============================ */

QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: {R_LG}px;
    background-color: {SURFACE};
    top: -1px;
}}

QTabBar::tab {{
    background: transparent;
    color: {INK_3};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 7px 14px;
    margin-right: 2px;
    font-size: {F_META}px;
}}

QTabBar::tab:hover {{ color: {INK}; }}

QTabBar::tab:selected {{
    color: {ACCENT_PRESS};
    border-bottom: 2px solid {ACCENT};
    font-weight: 600;
}}

/* ============================ lists =========================== */

QListWidget {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: {R_LG}px;
    padding: 4px;
    outline: 0;
}}

QListWidget::item {{
    border-radius: {R_SM}px;
    padding: 8px 10px;
    margin: 1px 2px;
    color: {INK};
}}

QListWidget::item:hover {{ background-color: {SURFACE_ALT}; }}

QListWidget::item:selected {{
    background-color: {ACCENT_SOFT};
    color: {ACCENT_PRESS};
}}

QListWidget::item:selected:hover {{
    background-color: {ACCENT_SOFT};
    color: {ACCENT_PRESS};
}}

/* ============================ scroll bars ===================== */

QScrollBar:vertical {{
    background: transparent;
    width: 11px;
    margin: 2px 2px 2px 0px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER_STRONG};
    border-radius: 4px;
    min-height: 28px;
}}

QScrollBar::handle:vertical:hover {{ background: {INK_3}; }}

QScrollBar:horizontal {{
    background: transparent;
    height: 11px;
    margin: 0px 2px 2px 2px;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER_STRONG};
    border-radius: 4px;
    min-width: 28px;
}}

QScrollBar::handle:horizontal:hover {{ background: {INK_3}; }}

QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0px;
    height: 0px;
    border: none;
    background: transparent;
}}

QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ============================ progress ======================== */

QProgressBar {{
    background-color: {SURFACE_SUNK};
    border: none;
    border-radius: 3px;
    height: 6px;
    max-height: 6px;
    color: {INK_2};
    font-size: {F_MICRO}px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 3px;
}}

QProgressBar[tone="warm"]::chunk {{ background-color: {WARN}; }}

/* ============================ splitter ======================== */

QSplitter::handle {{ background: transparent; }}
QSplitter::handle:horizontal {{ width: 14px; }}
QSplitter::handle:vertical {{ height: 14px; }}

/* ============================ group box ======================= */

QGroupBox {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: {R_LG}px;
    margin-top: 12px;
    padding: 18px 16px 14px 16px;
    font-size: {F_SECTION}px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0px 6px;
    background-color: {PAPER};
    color: {INK};
}}

/* ============================ dialogs ========================= */

QDialog QLabel#dialogTitle {{
    font-size: {F_TITLE}px;
    font-weight: 600;
}}

QDialogButtonBox QPushButton {{ min-width: 84px; }}

QMenu {{
    background-color: {SURFACE};
    border: 1px solid {BORDER_STRONG};
    border-radius: {R_MD}px;
    padding: 6px;
}}

QMenu::item {{
    padding: 6px 18px 6px 14px;
    border-radius: {R_SM}px;
}}

QMenu::item:selected {{
    background-color: {ACCENT_SOFT};
    color: {ACCENT_PRESS};
}}

QMessageBox {{ background-color: {PAPER}; }}

QMessageBox QLabel {{ color: {INK}; }}

/* ============================ cards in map ==================== */

QFrame#mapRow {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: {R_MD}px;
}}

QLabel#mapModuleTitle {{
    color: {INK_2};
    font-size: {F_SECTION}px;
    font-weight: 600;
    padding: 12px 0px 4px;
}}

/* Personal study: Claude's editorial rhythm, adapted to Chinese reading. */
QScrollArea#pageScroll, QWidget#scrollBody {{ background: {PAPER}; border: none; }}
QWidget#pageColumn {{ background: transparent; }}
QLabel {{ background: transparent; }}
QFrame#studyHero {{ background: {MINT}; border: 1px solid {BORDER}; border-radius: 12px; }}
QLabel#heroEyebrow {{ color: {ACCENT}; font-size: 11px; font-weight: 500; }}
QLabel#heroTitle {{ color: {INK}; font-family: "{DISPLAY_FAMILY}"; font-size: 30px; font-weight: 400; }}
QLabel#heroBody {{ color: {INK_2}; font-size: 13px; }}
QFrame#subjectCard {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
QLabel#subjectTitle {{ color: {INK}; font-family: "{DISPLAY_FAMILY}"; font-size: 22px; font-weight: 400; }}
QLabel#subjectSubtitle {{ color: {INK_3}; font-size: 12px; }}
QLabel#metricValue {{ color: {INK}; font-size: 23px; font-weight: 500; }}
QLabel#metricLabel {{ color: {INK_2}; font-size: 12px; }}
QLabel#topicTitle {{ color: {INK}; font-family: "{DISPLAY_FAMILY}"; font-size: 26px; font-weight: 400; }}
QLabel#noteTopicTitle {{ color: {INK}; font-size: {F_BODY}px; font-weight: 500; }}
QLabel#stepLabel {{ color: {ACCENT}; font-size: 12px; font-weight: 500; }}
QLabel#notice {{ color: {INK_2}; background: {SURFACE_ALT}; padding: 10px 12px; border-radius: 8px; }}
QLabel#brandMark {{ background: {ACCENT}; color: {SURFACE}; border-radius: 7px; font-family: "{DISPLAY_FAMILY}"; font-size: 25px; font-weight: 400; }}
QLabel#sidebarSection {{ padding-top: 18px; padding-bottom: 6px; }}
QListWidget#sidebarList::item:selected {{ background: {ACCENT_SOFT}; color: {ACCENT_PRESS}; }}
QTextBrowser#reader {{ border: none; padding: 0px; }}
QListWidget#recentList::item {{ padding: 0px; margin: 2px; }}
QLabel#statusLabel {{ color: {ACCENT_PRESS}; }}
QLabel#dateLabel {{ color: {INK_3}; font-size: 11px; padding: 6px 0px; }}
QLabel#sectionAside {{ color: {INK_3}; font-size: 12px; }}
QFrame#questionCard {{ background: {SURFACE_ALT}; border: none; border-left: 3px solid {ACCENT}; border-radius: 4px; }}
QLabel#readingQuestion {{ color: {INK}; font-size: 16px; }}
QLabel#readingBody {{ color: {INK_2}; font-size: 14px; }}
QLabel#subjectNext {{ color: {ACCENT}; font-size: 12px; }}
QLabel#subjectNext[subject="economics"] {{ color: {TERRACOTTA}; }}
QFrame#practiceSteps {{ border: none; background: {SURFACE_ALT}; border-radius: 8px; }}
QLabel#practiceStep {{ color: {INK_2}; font-size: 12px; padding: 4px 0px; }}
QPushButton[variant="subject"] {{ background: transparent; color: {ACCENT}; border: none; text-align: left; padding: 4px 0px; font-size: 12px; }}
QPushButton[variant="subject"]:hover {{ color: {ACCENT_PRESS}; text-decoration: underline; }}
QPushButton[variant="subject"][subject="economics"] {{ color: {TERRACOTTA}; }}
QProgressBar[subject="economics"]::chunk {{ background: {TERRACOTTA}; }}
QFrame#statsMetricCard {{ background: {SURFACE}; border: 1px solid {BORDER}; border-top: 2px solid {ACCENT}; border-radius: 8px; }}
QLabel#statsMetricValue {{ color: {INK}; font-family: "{DISPLAY_FAMILY}"; font-size: 28px; font-weight: 500; }}
QFrame#statsPanel {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; }}
"""
