"""Throwaway helper: launch the PACKAGED exe, screenshot its window, kill it.

Proves the PyInstaller artifact is not a blank/unopenable window.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import win32gui  # type: ignore
import win32ui  # type: ignore
from ctypes import windll  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "dist" / "daily-knowledge-learning" / "daily-knowledge-learning.exe"
OUT = ROOT / "test-output"
OUT.mkdir(exist_ok=True)


def find_window(pid: int) -> int | None:
    result: list[int] = []

    def cb(hwnd, _):
        wpid = windll.user32.GetWindowThreadProcessId(hwnd, None)
        if wpid == pid and win32gui.IsWindowVisible(hwnd):
            if win32gui.GetWindowText(hwnd):
                result.append(hwnd)

    win32gui.EnumWindows(cb, None)
    return result[0] if result else None


def capture(hwnd: int, path: Path) -> tuple[int, int]:
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    w, h = right - left, bottom - top
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfc_dc, w, h)
    save_dc.SelectObject(bmp)
    windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)
    bmp.SaveBitmapFile(save_dc, str(path))
    win32gui.DeleteObject(bmp.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)
    return w, h


def main() -> int:
    proc = subprocess.Popen([str(EXE)])
    try:
        hwnd = None
        for _ in range(40):
            time.sleep(0.5)
            if proc.poll() is not None:
                print(f"EXITED early code={proc.returncode}")
                return 1
            hwnd = find_window(proc.pid)
            if hwnd:
                break
        if not hwnd:
            print("no visible window found")
            return 1
        title = win32gui.GetWindowText(hwnd)
        print(f"window title = {title!r}")
        time.sleep(2)
        w, h = capture(hwnd, OUT / "packaged-window.png")
        print(f"saved packaged-window.png {w}x{h}")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
