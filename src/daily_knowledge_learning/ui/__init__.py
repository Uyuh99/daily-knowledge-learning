"""PySide6 desktop UI skeleton for the Daily Knowledge Learning app.

This package is intentionally decoupled from the in-flux core modules
(``note_manager`` / ``file_writer`` / ``config``).  It only validates the
desktop UI technology path and the Windows packaging story.

Run the skeleton with::

    python -m daily_knowledge_learning.ui
"""

from __future__ import annotations

__all__ = ["main"]


def main() -> int:
    """Entry point used by ``python -m daily_knowledge_learning.ui``."""
    from .app import run

    return run()
