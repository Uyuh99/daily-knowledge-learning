from __future__ import annotations

import errno
import hashlib
import os
import tempfile
from collections.abc import Callable
from pathlib import Path


class NoteFileError(OSError):
    """Base error with the affected note path and the original reason."""

    def __init__(self, path: Path, message: str) -> None:
        self.path = path
        super().__init__(f"{path}: {message}")


class NoteNotFoundError(FileNotFoundError, NoteFileError):
    pass


class NotePermissionError(PermissionError, NoteFileError):
    pass


class NoteDiskFullError(NoteFileError):
    pass


class NoteEncodingError(UnicodeError):
    def __init__(self, path: Path, cause: UnicodeError) -> None:
        self.path = path
        super().__init__(f"{path}: invalid UTF-8 content ({cause})")


class NoteConflictError(NoteFileError):
    """Raised when a note changed after it was read for an update."""


def _raise_file_error(path: Path, error: OSError) -> None:
    message = error.strerror or str(error)
    if isinstance(error, FileNotFoundError):
        raise NoteNotFoundError(path, message) from error
    if isinstance(error, PermissionError):
        raise NotePermissionError(path, message) from error
    if error.errno == errno.ENOSPC or getattr(error, "winerror", None) == 112:
        raise NoteDiskFullError(path, message) from error
    raise NoteFileError(path, message) from error


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeError as error:
        raise NoteEncodingError(path, error) from error
    except OSError as error:
        _raise_file_error(path, error)


def _write_temp(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = None
    temp_path: Path | None = None
    try:
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            suffix=f"{path.suffix}.tmp",
            prefix=f".{path.name}.",
            dir=path.parent,
            delete=False,
        )
        temp_path = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        if _read(temp_path) != content:
            raise NoteFileError(path, "temporary write verification failed")
        return temp_path
    except UnicodeError as error:
        if handle is not None and not handle.closed:
            handle.close()
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise NoteEncodingError(path, error) from error
    except OSError as error:
        if handle is not None and not handle.closed:
            handle.close()
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        _raise_file_error(path, error)
    raise AssertionError("unreachable")


def _commit(path: Path, content: str, expected: str | None) -> None:
    temp_path = _write_temp(path, content)
    try:
        if expected is None:
            try:
                os.link(temp_path, path)
            except FileExistsError as error:
                raise NoteConflictError(path, "file already exists; refusing to overwrite") from error
        else:
            current = _read(path)
            if hashlib.sha256(current.encode("utf-8")).digest() != expected:
                raise NoteConflictError(path, "note changed during update; retry after reviewing it")
            os.replace(temp_path, path)
    except OSError as error:
        if isinstance(error, NoteFileError):
            raise
        _raise_file_error(path, error)
    finally:
        temp_path.unlink(missing_ok=True)


def create_note(file_path: Path, content: str) -> None:
    """Create a UTF-8 note atomically without replacing an existing file."""
    path = Path(file_path)
    if not isinstance(content, str):
        raise TypeError("content must be a string")
    _commit(path, content, expected=None)


def update_note(
    file_path: Path,
    content: str | Callable[[str], str],
) -> None:
    """Replace a note body while preserving frontmatter, or transform its text.

    A string replaces the Markdown body and preserves an existing YAML block.
    A callable receives the complete original document and must return text.
    """
    path = Path(file_path)
    original = _read(path)
    if callable(content):
        updated = content(original)
    elif isinstance(content, str):
        if original.startswith("---\n") or original.startswith("---\r\n"):
            lines = original.splitlines(keepends=True)
            closing = next(
                (index for index in range(1, len(lines)) if lines[index].strip() == "---"),
                None,
            )
            if closing is None:
                raise NoteFileError(path, "unterminated YAML frontmatter")
            prefix = "".join(lines[: closing + 1])
            separator = "" if prefix.endswith(("\n", "\r")) else "\n"
            updated = f"{prefix}{separator}\n{content}"
        else:
            updated = content
    else:
        raise TypeError("content must be a string or Callable[[str], str]")
    if not isinstance(updated, str):
        raise TypeError("note update must return a string")
    digest = hashlib.sha256(original.encode("utf-8")).digest()
    _commit(path, updated, expected=digest)


def append_to_note(file_path: Path, content: str) -> bool:
    """Append content once; return False when the exact block is already present."""
    if not isinstance(content, str) or not content:
        raise ValueError("content must be a non-empty string")
    path = Path(file_path)
    original = _read(path)
    if content in original:
        return False
    separator = "" if not original or original.endswith("\n") else "\n"
    digest = hashlib.sha256(original.encode("utf-8")).digest()
    _commit(path, f"{original}{separator}{content}", expected=digest)
    return True
