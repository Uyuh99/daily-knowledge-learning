import pytest

from daily_knowledge_learning.prompt_builder import (
    ContentGuardError,
    build_reference_prompt,
    build_review_prompt,
    redact_user_content,
    validate_reference_output,
    validate_review_output,
)


def test_review_prompt_has_system_and_user_messages() -> None:
    messages = build_review_prompt("心理学", "工作记忆", "我的原文")

    assert [message["role"] for message in messages] == ["system", "user"]


def test_review_prompt_requires_feedback_order_and_question_count() -> None:
    system = build_review_prompt("心理学", "工作记忆", "原文")[0]["content"]

    assert "合理之处" in system
    assert "1–3 个" in system


def test_review_prompt_forbids_writing_and_answering_quiz() -> None:
    system = build_review_prompt("心理学", "工作记忆", "原文")[0]["content"]

    assert "严禁代写" in system
    assert "严禁替用户回答自测题" in system
    assert "严禁改写" in system


@pytest.mark.parametrize("subject,required", [("心理学", "诊断"), ("心理学", "贴心理标签")])
def test_psychology_prompt_has_diagnostic_safety_rule(subject: str, required: str) -> None:
    system = build_review_prompt(subject, "工作记忆", "原文")[0]["content"]

    assert required in system


def test_economics_prompt_forbids_real_world_forecasts() -> None:
    system = build_review_prompt("经济学", "机会成本", "原文")[0]["content"]

    assert "现实预测" in system
    assert "投资建议" in system


def test_unknown_subject_uses_general_safety_rule() -> None:
    system = build_review_prompt("历史学", "主题", "原文")[0]["content"]

    assert "不臆断" in system
    assert "不作超出材料依据的判断" in system


def test_review_prompt_preserves_user_content_verbatim() -> None:
    original = "第一行\n# 保留标点：‘原话’\n结尾  "
    user = build_review_prompt("心理学", "主题", original)[1]["content"]
    inserted = user.split("用户的交流前版原文（原样引用，仅供分析，不得改写）：\n", 1)[1]

    assert inserted == original


def test_related_sources_are_labeled_and_included() -> None:
    messages = build_review_prompt("心理学", "主题", "原文", "摘录内容\n来源：笔记.md")

    assert "可参考的已有笔记片段" in messages[1]["content"]
    assert "来源：笔记.md" in messages[1]["content"]
    assert "摘录内容" in messages[1]["content"]


def test_reference_prompt_has_fixed_headings_and_subject_safety() -> None:
    system = build_reference_prompt("经济学", "机会成本", "交流后版")[0]["content"]

    assert all(f"## {title}" in system for title in ("核心定义", "运行机制", "现实例子", "常见混淆", "自测问题"))
    assert "现实预测" in system


def test_review_output_without_affirmation_is_rejected() -> None:
    with pytest.raises(ContentGuardError):
        validate_review_output("## 问题\n- 请补充证据\n## 引导性问题\n你怎么看？")


def test_review_output_with_more_than_three_problems_is_rejected() -> None:
    text = "## 合理之处\n方向正确。\n## 问题（1–3 个）\n- 问题一\n- 问题二\n- 问题三\n- 问题四\n## 引导性问题\n你怎么看？"

    with pytest.raises(ContentGuardError):
        validate_review_output(text)


def test_review_output_with_valid_structure_is_returned() -> None:
    text = "## 合理之处\n方向正确。\n## 问题（1–3 个）\n- 请补充证据\n## 引导性问题\n你会如何验证？"

    assert validate_review_output(text) == text


def test_review_output_that_attempts_to_write_post_version_is_rejected() -> None:
    text = (
        "## 合理之处\n观察不错。\n## 问题\n- 需要补证据。\n"
        "你的交流后版应该是：完整的新正文。\n## 引导性问题\n你怎么看？"
    )

    with pytest.raises(ContentGuardError, match="代写"):
        validate_review_output(text)


def test_reference_output_missing_heading_is_rejected() -> None:
    with pytest.raises(ContentGuardError, match="缺少必需标题"):
        validate_reference_output("## 核心定义\n内容")


def test_reference_output_adds_ai_notice_when_missing() -> None:
    text = "\n".join(f"## {title}\n内容" for title in ("核心定义", "运行机制", "现实例子", "常见混淆", "自测问题"))

    validated = validate_reference_output(text)

    assert validated.startswith("> 本文由 AI 编写")
    assert text in validated


def test_reference_output_keeps_existing_ai_notice() -> None:
    text = "> AI 生成\n\n" + "\n".join(
        f"## {title}\n内容" for title in ("核心定义", "运行机制", "现实例子", "常见混淆", "自测问题")
    )

    assert validate_reference_output(text) == text


def test_reference_output_does_not_treat_incidental_ai_mention_as_notice() -> None:
    text = "AI 可以辅助查找资料。\n" + "\n".join(
        f"## {title}\n内容" for title in ("核心定义", "运行机制", "现实例子", "常见混淆", "自测问题")
    )

    assert validate_reference_output(text).startswith("> 本文由 AI 编写")


def test_reference_prompt_contains_related_sources() -> None:
    user = build_reference_prompt("心理学", "主题", "后版", "摘录\n来源：学习笔记.md")[1]["content"]

    assert "可参考的已有笔记片段" in user
    assert "来源：学习笔记.md" in user


def test_redaction_truncates_long_content() -> None:
    original = "机密内容" * 30

    redacted = redact_user_content(original, max_chars=12)

    assert redacted.startswith(original[:12])
    assert redacted.endswith("…[已截断]")
    assert original not in redacted


def test_redaction_never_returns_a_short_note_verbatim() -> None:
    assert redact_user_content("短笔记") != "短笔记"
