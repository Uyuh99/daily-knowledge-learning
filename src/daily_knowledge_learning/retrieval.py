"""Lightweight keyword retrieval over Obsidian Markdown notes.

The first version deliberately stays small: read Markdown files, split them
into heading-scoped chunks, and match user keywords by substring. No vector
database, embedding, or external search service is involved, so every answer
can be traced back to a file path and heading.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

# Subjects used by the learning Vault. ``search`` also accepts any other
# subject already present in the indexed chunks.
KNOWN_SUBJECTS = ("心理学", "经济学")

_HEADING = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.*)$")
_FRONTMATTER_DELIMITER = "---"


@dataclass(frozen=True, slots=True)
class NoteChunk:
    """One heading-scoped paragraph of a Markdown note."""

    path: str
    heading: str
    text: str
    line_number: int


@dataclass(frozen=True, slots=True)
class SearchHit:
    """A chunk that matched at least one query keyword."""

    path: str
    heading: str
    text: str
    line_number: int
    matched_keywords: tuple[str, ...]
    score: int
    subject: str | None = None


def _normalize(value: str) -> str:
    return value.casefold()


def _split_keywords(query: str) -> list[str]:
    """Split a free-form query into keywords.

    Chinese notes have no word boundaries, so the query is split on
    whitespace and common separators only. Chinese keywords stay intact and
    are matched later as substrings.
    """
    parts = [part.strip() for part in re.split(r"[\s,，、;；|/]+", query)]
    return _merge_keywords(parts)


def _merge_keywords(parts: Iterable[str]) -> list[str]:
    """De-duplicate keywords case-insensitively, keeping the first spelling."""
    seen: dict[str, str] = {}
    for part in parts:
        part = part.strip()
        if not part:
            continue
        seen.setdefault(_normalize(part), part)
    return list(seen.values())


def _split_frontmatter(text: str) -> tuple[int, list[str]]:
    """Return ``(first_body_line, lines)`` with YAML frontmatter removed.

    ``first_body_line`` is 1-based and points at the first line after the
    closing ``---`` marker, so reported line numbers stay true to the file.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIMITER:
        return 1, lines
    for index in range(1, len(lines)):
        if lines[index].strip() == _FRONTMATTER_DELIMITER:
            return index + 2, lines
    # An unterminated frontmatter block is treated as having no body.
    return len(lines) + 1, lines


def _subject_for(path: Path, root: Path) -> str | None:
    """Best-effort subject from the note's folder, for subject filtering."""
    try:
        relative = path.relative_to(root)
    except ValueError:
        return None
    parts = relative.parts
    labelled = [part for part in parts if part in KNOWN_SUBJECTS]
    if labelled:
        return labelled[0]
    # A single-subject fixture root such as ``vault/心理学/...`` has the
    # subject as the first folder.
    return parts[0] if len(parts) > 1 else None


def _chunks_for_file(path: Path, root: Path) -> list[NoteChunk]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    first_body_line, lines = _split_frontmatter(text)
    relative = path.relative_to(root).as_posix()

    chunks: list[NoteChunk] = []
    heading = path.stem
    buffer: list[str] = []
    start_line = first_body_line

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if body:
            chunks.append(
                NoteChunk(
                    path=relative,
                    heading=heading,
                    text=body,
                    line_number=start_line,
                )
            )

    for offset, line in enumerate(lines, start=1):
        # Line numbers are 1-based and must match the original file.
        if offset < first_body_line:
            continue
        match = _HEADING.match(line)
        if match:
            flush()
            buffer = []
            heading = match.group("title").strip() or path.stem
            start_line = offset
            continue
        if not buffer:
            start_line = offset
        buffer.append(line)

    flush()
    return chunks


def index_notes(root: Path) -> list[NoteChunk]:
    """Recursively index every ``.md`` file below ``root``.

    Frontmatter is skipped and empty paragraphs are dropped. Results are
    ordered by path then line number so repeated runs are stable.
    """
    root = Path(root)
    if not root.is_dir():
        return []

    chunks: list[NoteChunk] = []
    for path in sorted(root.rglob("*.md"), key=lambda item: item.as_posix()):
        chunks.extend(_chunks_for_file(path, root))
    return chunks


def _chunk_subject(chunk: NoteChunk) -> str | None:
    parts = Path(chunk.path).parts
    for part in parts:
        if part in KNOWN_SUBJECTS:
            return part
    return parts[0] if len(parts) > 1 else None


def search(
    query: str,
    chunks: list[NoteChunk],
    *,
    subject: str | None = None,
    limit: int = 5,
    extra_keywords: Sequence[str] | None = None,
) -> list[SearchHit]:
    """Return the chunks that match ``query``, best matches first.

    Matching is substring-based and case-insensitive, which is what works
    for Chinese notes that have no whitespace word boundaries. Ranking puts
    the number of distinct matched keywords first and prefers shorter
    paragraphs on ties.

    A term counts as matched when it appears in the paragraph body or in its
    heading, so searching a topic name still finds the note it belongs to.
    """
    keywords = _split_keywords(query)
    if extra_keywords:
        extra = [str(item).strip() for item in extra_keywords if str(item).strip()]
        keywords = _merge_keywords([*keywords, *extra])
    if not keywords or limit <= 0:
        return []

    normalized_keywords = [(keyword, _normalize(keyword)) for keyword in keywords]

    hits: list[SearchHit] = []
    for chunk in chunks:
        chunk_subject = _chunk_subject(chunk)
        if subject is not None and chunk_subject != subject:
            continue
        haystack = _normalize(f"{chunk.heading}\n{chunk.text}")
        matched = tuple(
            keyword
            for keyword, normalized in normalized_keywords
            if normalized in haystack
        )
        if not matched:
            continue
        hits.append(
            SearchHit(
                path=chunk.path,
                heading=chunk.heading,
                text=chunk.text,
                line_number=chunk.line_number,
                matched_keywords=matched,
                score=len(matched),
                subject=chunk_subject,
            )
        )

    hits.sort(
        key=lambda hit: (
            -hit.score,
            len(hit.text),
            hit.path,
            hit.line_number,
        )
    )
    return hits[:limit]


def format_sources(hits: list[SearchHit]) -> str:
    """Render hits as prompt-ready text that keeps path and heading."""
    if not hits:
        return "（没有检索到相关笔记片段）"

    blocks: list[str] = []
    for index, hit in enumerate(hits, start=1):
        keywords = "、".join(hit.matched_keywords)
        blocks.append(
            "\n".join(
                (
                    f"[{index}] 来源：{hit.path}（第 {hit.line_number} 行）",
                    f"标题：{hit.heading}",
                    f"命中关键词：{keywords}",
                    hit.text,
                )
            )
        )
    return "\n\n".join(blocks)
