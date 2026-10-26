"""Render the app's SVG mark into a multi-resolution Windows ICO file."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def render_png(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(data)


def main() -> None:
    source = Path(__file__).resolve().parents[1] / "assets" / "daily-learning-icon.svg"
    destination = Path(__file__).resolve().parents[1] / "assets" / "daily-learning.ico"
    renderer = QSvgRenderer(str(source))
    if not renderer.isValid():
        raise RuntimeError(f"Invalid SVG icon: {source}")

    sizes = (16, 24, 32, 48, 64, 128, 256)
    frames = [render_png(renderer, size) for size in sizes]
    header = struct.pack("<HHH", 0, 1, len(frames))
    entries = bytearray()
    offset = 6 + 16 * len(frames)
    for size, frame in zip(sizes, frames, strict=True):
        entries.extend(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(frame), offset))
        offset += len(frame)
    destination.write_bytes(header + entries + b"".join(frames))
    print(destination)


if __name__ == "__main__":
    main()
