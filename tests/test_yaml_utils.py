from pathlib import Path

import pytest

from daily_knowledge_learning.yaml_utils import parse_frontmatter, update_frontmatter


def test_parse_yaml_types(tmp_path: Path) -> None:
    path = tmp_path / "note.md"
    path.write_text('---\nname: "topic"\ntags: [a, b]\nactive: true\n---\nbody', encoding="utf-8")
    parsed = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert parsed["name"] == "topic"
    assert parsed["tags"] == ["a", "b"]
    assert parsed["active"] is True


def test_update_preserves_other_fields_comments_and_body(tmp_path: Path) -> None:
    path = tmp_path / "note.md"
    original = '---\ntopic: "one" # keep this\ntags:\n  - alpha\nstatus: pending\n---\n\nOriginal body.\n'
    path.write_text(original, encoding="utf-8")
    update_frontmatter(path, {"status": "completed", "completion_date": "2026-10-16"})
    actual = path.read_text(encoding="utf-8")
    assert 'topic: "one" # keep this' in actual
    assert "- alpha" in actual
    assert "status: completed" in actual
    assert "completion_date: '2026-10-16'" in actual
    assert actual.endswith("Original body.\n")


def test_update_requires_frontmatter(tmp_path: Path) -> None:
    path = tmp_path / "note.md"
    path.write_text("plain text", encoding="utf-8")
    with pytest.raises(ValueError, match="no YAML frontmatter"):
        update_frontmatter(path, {"status": "done"})


def test_invalid_yaml_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "note.md"
    path.write_text("---\ninvalid: [\n---\nbody", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid YAML"):
        update_frontmatter(path, {"status": "done"})
