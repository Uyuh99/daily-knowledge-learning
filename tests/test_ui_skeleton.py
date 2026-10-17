"""Smoke test for the PySide6 UI skeleton.

Runs offscreen so it can execute in CI / headless environments.  It proves the
window builds, the sidebar has the required entries, and switching entries
actually swaps the content page.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from daily_knowledge_learning.ui.app import (  # noqa: E402
    build_application,
    create_window,
)
from daily_knowledge_learning.ui.main_window import WINDOW_TITLE  # noqa: E402
from daily_knowledge_learning.ui.sidebar import NAV_ENTRIES  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return build_application(["daily-knowledge-learning-ui-test"])


def test_window_title_is_chinese(app: QApplication) -> None:
    window = create_window()
    assert window.windowTitle() == WINDOW_TITLE
    window.close()


def test_sidebar_has_four_required_entries(app: QApplication) -> None:
    window = create_window()
    titles = [entry.title for entry in NAV_ENTRIES]
    assert titles == ["首页", "今日学习", "学习地图", "设置"]
    assert window.sidebar.current_key() == "home"
    window.close()


def test_navigation_switches_content_page(app: QApplication) -> None:
    window = create_window()
    seen: set[int] = set()
    for entry in NAV_ENTRIES:
        window.sidebar.select(entry.key)
        assert window.sidebar.current_key() == entry.key
        seen.add(window.content.currentIndex())
    # Each of the four entries maps to a distinct page.
    assert len(seen) == len(NAV_ENTRIES)
    window.close()


def test_markdown_rendering_produces_rich_text(app: QApplication) -> None:
    from daily_knowledge_learning.ui.pages import MarkdownPreviewPage

    page = MarkdownPreviewPage("标题", "**粗体** 与 `代码`")
    plain = page.viewer.toPlainText()
    assert "粗体" in plain
    assert page.viewer.toHtml().lower().count("font-weight") >= 1
