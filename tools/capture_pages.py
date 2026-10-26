"""Capture every main page of the real window as a PNG for design review.

Part of the UI design-system work (YZFD-31): gives a repeatable before/after
visual baseline.  Run it offscreen so it works unattended::

    uv run python tools/capture_pages.py --vault tests/fixtures/vault_minimal

Output lands under ``test-output/ui-capture/`` and is not committed.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from daily_knowledge_learning.ui.app import build_application  # noqa: E402
from daily_knowledge_learning.ui.main_window import MainWindow  # noqa: E402
from daily_knowledge_learning.ui.sidebar import NAV_ENTRIES  # noqa: E402

PAGES = tuple(entry.key for entry in NAV_ENTRIES) + ("editor",)
SIZES = ((1024, 680), (1280, 800), (760, 480))


def _first_topic_folder(vault: Path | None) -> Path | None:
    if vault is None:
        return None
    for candidate in sorted(Path(vault).rglob("01-*.md")):
        return candidate.parent
    return None


def capture(vault: Path | None, out_dir: Path, sizes) -> list[Path]:
    app = build_application(["ui-capture"])
    window = MainWindow(vault)
    window.show()
    app.processEvents()

    folder = _first_topic_folder(vault)
    if folder is not None:
        window.content.editor.load_topic(folder)

    written: list[Path] = []
    for width, height in sizes:
        window.resize(width, height)
        app.processEvents()
        size_dir = out_dir / f"{width}x{height}"
        size_dir.mkdir(parents=True, exist_ok=True)
        for key in PAGES:
            if key == "editor":
                window.content.show_key("editor")
            else:
                window.sidebar.select(key)
            app.processEvents()
            target = size_dir / f"ui-{key}.png"
            window.grab().save(str(target))
            written.append(target)
    window.close()
    app.processEvents()
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture UI pages to PNG.")
    parser.add_argument("--vault", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=Path("test-output/ui-capture"))
    parser.add_argument("--size", action="append", metavar="WxH")
    args = parser.parse_args(argv)
    sizes = SIZES
    if args.size:
        sizes = tuple(
            tuple(int(part) for part in value.lower().split("x")) for value in args.size
        )
    if QApplication.instance() is not None:
        raise SystemExit("run this as a fresh process; no QApplication may exist yet")
    for path in capture(args.vault, args.out, sizes):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
