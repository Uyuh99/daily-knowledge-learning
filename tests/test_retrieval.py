"""Tests for the lightweight keyword retrieval module."""

from pathlib import Path

from daily_knowledge_learning.retrieval import (
    NoteChunk,
    format_sources,
    index_notes,
    search,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "vault_minimal"


def _fixture_chunks() -> list[NoteChunk]:
    return index_notes(FIXTURE_ROOT)


def test_index_notes_finds_chinese_note_and_reports_path_and_heading() -> None:
    chunks = _fixture_chunks()

    work_memory = [chunk for chunk in chunks if "工作记忆" in chunk.heading]

    assert work_memory, "应至少索引到工作记忆笔记的标题片段"
    chunk = work_memory[0]
    assert chunk.path == "心理学/每日记录/2026-09-22-工作记忆的容量限制.md"
    assert chunk.heading == "工作记忆的容量限制"
    assert "旧版单文件记录" in chunk.text
    assert chunk.line_number == 8


def test_index_notes_splits_paragraphs_by_heading() -> None:
    chunks = _fixture_chunks()

    headings = {
        chunk.heading
        for chunk in chunks
        if chunk.path.endswith("2026-09-24-锚定效应/02-交流后版.md")
    }

    assert headings == {"锚定效应｜02-交流后版", "锚定效应｜03-AI参考版"}


def test_index_notes_skips_frontmatter() -> None:
    chunks = _fixture_chunks()

    # None of the fixtures expose frontmatter keys as body text.
    assert not any("version:" in chunk.text for chunk in chunks)
    assert not any("status:" in chunk.text for chunk in chunks)
    assert not any(chunk.text.startswith("---") for chunk in chunks)


def test_frontmatter_does_not_match_query_and_reports_body_line() -> None:
    chunks = _fixture_chunks()

    hits = search("status", chunks)

    assert hits == [], "frontmatter 中的 status 不应被当作正文检索"

    work_memory = search("旧版单文件记录", chunks)
    assert work_memory, "正文关键词应能命中"
    assert work_memory[0].line_number == 8


def test_basic_chinese_substring_hit() -> None:
    hits = search("沉没成本", _fixture_chunks())

    assert hits, "中文子串应能命中"
    assert hits[0].heading == "沉没成本｜01-交流前版"
    assert "沉没成本" in hits[0].text
    assert "沉没成本" in hits[0].matched_keywords
    assert hits[0].score == 1


def test_heading_term_also_finds_its_note() -> None:
    # 机会成本只出现在标题里，正文只有「用户原话保留在这里」。
    hits = search("机会成本", _fixture_chunks(), subject="经济学")

    assert hits, "标题中的主题词也应能命中"
    assert any(
        hit.path.endswith("2026-09-22-机会成本/01-交流前版.md") for hit in hits
    )
    assert all("机会成本" in hit.matched_keywords for hit in hits)


def test_multi_keyword_ranking_prefers_more_matches() -> None:
    chunks = _fixture_chunks()

    hits = search("沉没成本 初步理解", chunks)

    assert hits, "多关键词查询应命中"
    assert hits[0].heading == "沉没成本｜01-交流前版"
    assert set(hits[0].matched_keywords) == {"沉没成本", "初步理解"}
    assert hits[0].score == 2
    assert all(hit.score <= hits[0].score for hit in hits)


def test_multi_keyword_ranking_orders_by_hit_count() -> None:
    chunks = _fixture_chunks()

    hits = search("沉没成本 锚定效应 参照", chunks)

    assert hits[0].score == 3
    assert hits[0].heading == "锚定效应｜03-AI参考版"
    # 只有「沉没成本」命中的片段排在两个关键词都命中的片段之后。
    sunk_cost_only = next(
        hit for hit in hits if hit.heading == "沉没成本｜01-交流前版"
    )
    assert sunk_cost_only.score == 1
    assert hits.index(sunk_cost_only) > hits.index(hits[0])


def test_search_accepts_external_ai_keywords() -> None:
    chunks = _fixture_chunks()

    hits = search(
        "",
        chunks,
        extra_keywords=["沉没成本", "初步理解"],
    )

    assert hits
    assert set(hits[0].matched_keywords) == {"沉没成本", "初步理解"}


def test_subject_filter_returns_only_requested_subject() -> None:
    chunks = _fixture_chunks()

    psychology = search("记录", chunks, subject="心理学")
    economics = search("记录", chunks, subject="经济学")

    assert psychology
    assert all(hit.path.startswith("心理学/") for hit in psychology)
    assert economics
    assert all(hit.path.startswith("经济学/") for hit in economics)
    assert search("工作记忆", chunks, subject="经济学") == []


def test_no_hit_returns_empty_list_without_raising() -> None:
    assert search("完全不存在的关键词xyz", _fixture_chunks()) == []
    assert search("机会成本", _fixture_chunks(), limit=0) == []


def test_search_is_case_insensitive_for_english_keywords(tmp_path: Path) -> None:
    note = tmp_path / "笔记.md"
    note.write_text("# AI Retrieval\n\n这里讲 Retrieval 的基本做法。\n", encoding="utf-8")
    chunks = index_notes(tmp_path)

    hits = search("retrieval", chunks)

    assert hits
    assert hits[0].matched_keywords == ("retrieval",)


def test_format_sources_includes_path_and_heading() -> None:
    hits = search("沉没成本", _fixture_chunks())

    text = format_sources(hits)

    assert "沉没成本｜01-交流前版" in text, "格式化结果必须包含标题"
    assert "经济学/每日记录/2026-09-26-沉没成本/01-交流前版.md" in text, (
        "格式化结果必须包含来源路径"
    )
    assert "命中关键词：沉没成本" in text


def test_format_sources_handles_empty_hits() -> None:
    assert "没有检索到" in format_sources([])
