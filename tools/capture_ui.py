"""Throwaway helper: launch the real window, screenshot it, then exit.

Not part of the deliverable — used only to prove the window actually opens and
to capture a screenshot for the issue report.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from daily_knowledge_learning.ui.app import build_application, create_window
from daily_knowledge_learning.ui.sidebar import NAV_ENTRIES

OUT_DIR = Path(__file__).resolve().parents[1] / "test-output"
OUT_DIR.mkdir(exist_ok=True)


def main() -> int:
    app = build_application(["ui-evidence"])
    window = create_window()
    window.show()

    shots = ["home", "today", "map", "settings"]

    def grab(index: int = 0) -> None:
        if index >= len(shots):
            app.quit()
            return
        key = shots[index]
        if key == "home":
            window.sidebar.select("_markdown_preview")
        else:
            window.sidebar.select(key)
        app.processEvents()
        QTimer.singleShot(250, lambda: _save(window, key, index))

    def _save(win, key: str, index: int) -> None:
        pixmap = win.grab()
        target = OUT_DIR / f"ui-{index + 1}-{key}.png"
        pixmap.save(str(target))
        print(f"saved {target} {pixmap.width()}x{pixmap.height()}")
        grab(index + 1)

    QTimer.singleShot(800, lambda: grab(0))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
