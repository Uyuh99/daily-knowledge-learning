from __future__ import annotations

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .file_writer import update_note


def _yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.width = 4096
    return yaml


def parse_frontmatter(text: str) -> dict[str, Any]:
    """Parse YAML frontmatter, returning an empty mapping when it is absent."""
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return {}
    lines = text.splitlines(keepends=True)
    closing = next((index for index in range(1, len(lines)) if lines[index].strip() == "---"), None)
    if closing is None:
        raise ValueError("unterminated YAML frontmatter")
    try:
        result = _yaml().load("".join(lines[1:closing]))
    except YAMLError as error:
        raise ValueError(f"invalid YAML frontmatter: {error}") from error
    if result is None:
        return {}
    if not isinstance(result, dict):
        raise ValueError("YAML frontmatter must be a mapping")
    return result


def update_frontmatter(
    file_path: Path,
    updates: dict[str, Any],
    preserve_format: bool = True,
) -> None:
    """Update selected YAML keys while retaining other fields and comments."""
    path = Path(file_path)
    if not isinstance(updates, dict):
        raise TypeError("updates must be a mapping")
    original = path.read_text(encoding="utf-8")
    if not original.startswith("---\n") and not original.startswith("---\r\n"):
        raise ValueError(f"{path}: file has no YAML frontmatter")
    lines = original.splitlines(keepends=True)
    closing = next((index for index in range(1, len(lines)) if lines[index].strip() == "---"), None)
    if closing is None:
        raise ValueError(f"{path}: unterminated YAML frontmatter")
    yaml = _yaml()
    try:
        data = yaml.load("".join(lines[1:closing]))
    except YAMLError as error:
        raise ValueError(f"{path}: invalid YAML frontmatter: {error}") from error
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: YAML frontmatter must be a mapping")
    for key, value in updates.items():
        data[key] = value
    import io

    output = io.StringIO()
    yaml.dump(data, output)
    newline = "\r\n" if "\r\n" in original else "\n"
    serialized = output.getvalue().replace("\n", newline)
    if not serialized.endswith(newline):
        serialized += newline
    if not preserve_format:
        serialized = serialized.rstrip("\r\n") + newline
    replacement = f"---{newline}{serialized}---{''.join(lines[closing + 1:])}"
    update_note(path, lambda _: replacement)
