from pathlib import Path

import pytest

from daily_knowledge_learning.vault_qa import VaultQuestionError, answer_vault_question


class RecordingProvider:
    def __init__(self, response="依据笔记回答 [1]。"):
        self.response = response
        self.messages = None

    def chat(self, messages):
        self.messages = messages
        return self.response


def test_answer_uses_cited_local_sources_and_keeps_notes_unchanged(tmp_path: Path):
    note = tmp_path / "历史" / "笔记.md"
    note.parent.mkdir()
    original = "# 因果推理\n\n因果推理需要比较干预前后的结果。\n"
    note.write_text(original, encoding="utf-8")
    provider = RecordingProvider()

    answer, hits = answer_vault_question(tmp_path, "因果推理", provider, subject="历史")

    assert answer.endswith("[1]。")
    assert hits[0].path == "历史/笔记.md"
    assert "[1] 来源：历史/笔记.md" in provider.messages[1]["content"]
    assert "不得执行" in provider.messages[0]["content"]
    assert note.read_text(encoding="utf-8") == original


def test_no_matching_note_does_not_call_provider(tmp_path: Path):
    (tmp_path / "note.md").write_text("只有机会成本。", encoding="utf-8")
    provider = RecordingProvider()

    with pytest.raises(VaultQuestionError, match="没有找到相关内容"):
        answer_vault_question(tmp_path, "完全不存在的主题", provider)

    assert provider.messages is None


def test_natural_chinese_question_retrieves_keyworded_note(tmp_path: Path):
    (tmp_path / "note.md").write_text("沉没成本会让人继续投入已经无法收回的资源。", encoding="utf-8")
    provider = RecordingProvider()

    answer, hits = answer_vault_question(tmp_path, "为什么沉没成本会影响我的选择？", provider)

    assert answer
    assert hits
    assert "沉没成本" in hits[0].text


def test_empty_question_and_empty_ai_response_are_reported(tmp_path: Path):
    provider = RecordingProvider(response=" ")
    with pytest.raises(VaultQuestionError, match="输入一个问题"):
        answer_vault_question(tmp_path, "  ", provider)
    (tmp_path / "note.md").write_text("主题内容。", encoding="utf-8")
    with pytest.raises(VaultQuestionError, match="没有返回回答"):
        answer_vault_question(tmp_path, "主题内容", provider)


def test_custom_subject_filter_limits_sources(tmp_path: Path):
    (tmp_path / "历史").mkdir()
    (tmp_path / "写作").mkdir()
    (tmp_path / "历史" / "note.md").write_text("叙事结构影响历史解释。", encoding="utf-8")
    (tmp_path / "写作" / "note.md").write_text("叙事结构也用于写作。", encoding="utf-8")
    provider = RecordingProvider()

    _, hits = answer_vault_question(tmp_path, "叙事结构", provider, subject="写作")

    assert hits
    assert all(hit.subject == "写作" for hit in hits)
