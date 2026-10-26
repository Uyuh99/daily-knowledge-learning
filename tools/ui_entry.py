"""PyInstaller entry point for the desktop UI skeleton.

Kept separate from ``daily_knowledge_learning/ui/__main__.py`` so the packaged
executable has a plain top-level script to freeze.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Keep the DLL search-directory handles alive for the frozen process lifetime.
_dll_directories = []
if getattr(sys, "frozen", False) and sys.platform == "win32":
    bundle = Path(sys._MEIPASS)
    for directory in (bundle, bundle / "PySide6", bundle / "shiboken6"):
        if directory.is_dir():
            _dll_directories.append(os.add_dll_directory(str(directory)))
    os.environ["PATH"] = str(bundle / "PySide6") + os.pathsep + os.environ.get("PATH", "")
    from shiboken6 import Shiboken  # noqa: F401

from daily_knowledge_learning.ui import main

if __name__ == "__main__":
    raise SystemExit(main())
