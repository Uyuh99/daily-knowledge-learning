"""PyInstaller entry point for the desktop UI skeleton.

Kept separate from ``daily_knowledge_learning/ui/__main__.py`` so the packaged
executable has a plain top-level script to freeze.
"""

from __future__ import annotations

from daily_knowledge_learning.ui import main

if __name__ == "__main__":
    raise SystemExit(main())
