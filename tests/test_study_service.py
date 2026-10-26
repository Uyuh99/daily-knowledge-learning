from __future__ import annotations

from pathlib import Path

import pytest

from daily_knowledge_learning.file_writer import update_note
from daily_knowledge_learning.note_manager import create_topic_notes
from daily_knowledge_learning.study_service import (
    AIUnavailableError,
    StudyServiceError,
    generate_ai_reference,
    generate_today_material,
    is_ai_available,
    review_pre_learning,
    start_session,
)


REFERENCE = """## 核心定义
定义内容

## 运行机制
机制内容

## 现实例子
例子内容

## 常见混淆
混淆内容

## 自测问题
问题内容
"""

DAILY_MATERIAL = """## 今日核心问题
如何识别机会成本？

## 核心概念
放弃的最佳可行替代方案的价值。

## 直观解释
选择意味着放弃。

## 运作机制
比较当前方案与最佳替代方案。

## 具体例子
周末工作和休息的选择。

## 适用条件与边界
需要明确可行选项。

## 常见误区
不是把所有未选项相加。

## 自测问题
如何判断最佳替代方案？
"""


class MockProvider:
    def __init__(self, response: str = "合理之处：方向正确。\n问题：请核查证据。") -> None:
        self.available = True
        self.response = response
        self.messages: list[list[dict[str, str]]] = []

    def generate(self, messages: list[dict[str, str]]) -> str:
        self.messages.append(messages)
        return self.response


def _vault_with_route(tmp_path: Path, topic: str = "机会成本") -> Path:
    root = tmp_path / "vault"
    subject = root / "经济学"
    subject.mkdir(parents=True)
    (subject / "经济学学习路线与已学索引.md").write_text(
        "## 模块 A｜经济学基础\n\n"
        "| 顺序 | 知识点 | 与前一节点的关系 |\n"
        "| --- | --- | --- |\n"
        f"| A1 | {topic} | 选择的代价 |\n",
        encoding="utf-8",
    )
    return root


def test_start_session_creates_three_notes_for_new_topic(tmp_path: Path) -> None:
    session = start_session(_vault_with_route(tmp_path), "经济学")

    assert session.topic == "机会成本"
    assert session.module == "经济学基础"
    assert session.prompt.topic == session.topic
    assert session.note_paths.pre_learning.exists()
    assert session.note_paths.post_discussion.exists()
    assert session.note_paths.ai_reference.exists()


def test_daily_material_is_written_as_editable_learning_sheet(tmp_path: Path) -> None:
    session = start_session(_vault_with_route(tmp_path), "经济学")
    provider = MockProvider(DAILY_MATERIAL)

    result = generate_today_material(session, provider)
    saved = session.note_paths.pre_learning.read_text(encoding="utf-8")

    assert result in saved
    assert "仅供学习参考" in saved
    assert "## 我自己的解释" in saved
    assert "## 现实应用" in saved
    assert "## 认知校正" in saved
    assert "## 间隔复习" in saved
    assert "待查证" in saved
    assert "主题：机会成本" in provider.messages[0][1]["content"]


def test_daily_material_rejects_bad_structure_without_writing(tmp_path: Path) -> None:
    session = start_session(_vault_with_route(tmp_path), "经济学")
    before = session.note_paths.pre_learning.read_text(encoding="utf-8")

    with pytest.raises(StudyServiceError, match="结构不完整"):
        generate_today_material(session, MockProvider("不完整"))

    assert session.note_paths.pre_learning.read_text(encoding="utf-8") == before


def test_daily_material_never_overwrites_existing_learner_content(tmp_path: Path) -> None:
    session = start_session(_vault_with_route(tmp_path), "经济学")
    update_note(session.note_paths.pre_learning, "我已经写下自己的想法。")

    with pytest.raises(StudyServiceError, match="保留原文"):
        generate_today_material(session, MockProvider(DAILY_MATERIAL))

    assert "我已经写下自己的想法" in session.note_paths.pre_learning.read_text(encoding="utf-8")


def test_start_session_reuses_existing_in_progress_notes(tmp_path: Path) -> None:
    root = _vault_with_route(tmp_path)
    notes = create_topic_notes(root, "经济学", "机会成本", "我的原始理解")
    before = {path: path.read_text(encoding="utf-8") for path in notes.folder.iterdir()}

    session = start_session(root, "经济学")

    assert session.note_paths.folder == notes.folder
    assert session.note_paths.pre_learning.read_text(encoding="utf-8").endswith("我的原始理解")
    assert {path: path.read_text(encoding="utf-8") for path in notes.folder.iterdir()} == before


def test_start_session_without_available_topic_raises(tmp_path: Path) -> None:
    with pytest.raises(StudyServiceError, match="学习地图"):
        start_session(tmp_path / "empty-vault", "经济学")


def test_review_empty_pre_learning_returns_prompt_without_calling_ai(tmp_path: Path) -> None:
    session = start_session(_vault_with_route(tmp_path), "经济学")
    provider = MockProvider()

    response = review_pre_learning(session, provider)

    assert "尚无正文" in response
    assert provider.messages == []


def test_review_prompt_enforces_feedback_structure_and_safety(tmp_path: Path) -> None:
    root = _vault_with_route(tmp_path)
    notes = create_topic_notes(root, "经济学", "机会成本")
    update_note(notes.pre_learning, "我觉得选择一种方案时，放弃的最好替代方案也有成本。")
    session = start_session(root, "经济学")
    provider = MockProvider()

    response = review_pre_learning(session, provider)
    system_prompt = provider.messages[0][0]["content"]

    assert "合理" in response and "问题" in response
    assert "辅导学习者，不是替他写作业" in system_prompt
    assert "不得代写交流后版主体" in system_prompt
    assert "不得替用户回答自测题" in system_prompt
    assert "不得把模型结论当作对现实的预测" in system_prompt


def test_generate_reference_requires_confirmation_without_calling_ai(tmp_path: Path) -> None:
    root = _vault_with_route(tmp_path)
    notes = create_topic_notes(root, "经济学", "机会成本")
    update_note(notes.post_discussion, "选择的真实成本是放弃的最佳替代方案。")
    session = start_session(root, "经济学")
    provider = MockProvider(REFERENCE)

    with pytest.raises(StudyServiceError, match="确认交流后版"):
        generate_ai_reference(session, provider, user_confirmed=False)

    assert provider.messages == []


def test_generate_reference_writes_notice_and_required_sections(tmp_path: Path) -> None:
    root = _vault_with_route(tmp_path)
    notes = create_topic_notes(root, "经济学", "机会成本")
    update_note(notes.post_discussion, "选择的真实成本是放弃的最佳替代方案。")
    session = start_session(root, "经济学")

    result = generate_ai_reference(session, MockProvider(REFERENCE), user_confirmed=True)
    written = session.note_paths.ai_reference.read_text(encoding="utf-8")

    assert result.startswith("> 本文件由 AI 编写，不代表用户观点。")
    assert written.startswith("---\n")
    assert result in written
    assert all(section in written for section in ("核心定义", "运行机制", "现实例子", "常见混淆", "自测问题"))


def test_generate_reference_refuses_to_overwrite_existing_content(tmp_path: Path) -> None:
    root = _vault_with_route(tmp_path)
    notes = create_topic_notes(root, "经济学", "机会成本")
    update_note(notes.post_discussion, "选择的真实成本是放弃的最佳替代方案。")
    update_note(notes.ai_reference, "已有人工整理内容。")
    session = start_session(root, "经济学")
    provider = MockProvider(REFERENCE)

    with pytest.raises(StudyServiceError, match="拒绝覆盖"):
        generate_ai_reference(session, provider, user_confirmed=True)

    assert provider.messages == []
    assert "已有人工整理内容" in session.note_paths.ai_reference.read_text(encoding="utf-8")


def test_unavailable_provider_raises_catchable_error_and_local_notes_remain_editable(tmp_path: Path) -> None:
    root = _vault_with_route(tmp_path)
    notes = create_topic_notes(root, "经济学", "机会成本", "初始内容")
    session = start_session(root, "经济学")
    provider = MockProvider()
    provider.available = False

    assert is_ai_available(provider) is False
    with pytest.raises(AIUnavailableError):
        review_pre_learning(session, provider)

    update_note(notes.pre_learning, "离线时仍然可以保存。")
    assert "离线时仍然可以保存" in notes.pre_learning.read_text(encoding="utf-8")


def test_review_prompt_includes_relevant_retrieved_note_excerpt(tmp_path: Path) -> None:
    root = _vault_with_route(tmp_path)
    notes = create_topic_notes(root, "经济学", "机会成本")
    update_note(notes.pre_learning, "机会成本是放弃的最佳替代方案价值。")
    prior = root / "经济学" / "每日记录" / "2026-09-01-已学主题"
    prior.mkdir(parents=True)
    (prior / "学习笔记.md").write_text(
        "# 机会成本\n\n旧笔记指出机会成本取决于被放弃方案中的最佳一个。",
        encoding="utf-8",
    )
    session = start_session(root, "经济学")
    provider = MockProvider()

    review_pre_learning(session, provider)

    user_prompt = provider.messages[0][1]["content"]
    assert "旧笔记指出机会成本取决于被放弃方案中的最佳一个" in user_prompt
    assert "来源：经济学/每日记录/2026-09-01-已学主题/学习笔记.md" in user_prompt
