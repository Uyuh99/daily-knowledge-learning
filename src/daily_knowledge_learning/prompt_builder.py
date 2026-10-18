from __future__ import annotations

import re


SAFETY_RULES: dict[str, str] = {
    "心理学": "不得诊断或给用户、现实人物贴心理标签，也不得根据知识点判断现实人物。",
    "经济学": "不得将经济学模型直接当作现实预测，也不得提供投资建议。",
}
_GENERIC_SAFETY_RULE = "只讨论知识本身；不臆断用户或他人的情况，不作超出材料依据的判断。"
_REFERENCE_HEADINGS = ("核心定义", "运行机制", "现实例子", "常见混淆", "自测问题")
_AI_NOTICE = "> 本文由 AI 编写，仅供学习参考，不代表用户观点。"


class ContentGuardError(ValueError):
    """Generated content does not meet the learning-safety contract."""


def _safety_rule(subject: str) -> str:
    return SAFETY_RULES.get(subject, _GENERIC_SAFETY_RULE)


def _source_block(related_sources: str) -> str:
    if not related_sources:
        return ""
    return f"\n\n可参考的已有笔记片段（以下内容含来源标注）：\n{related_sources}"


def build_review_prompt(
    subject: str,
    topic: str,
    pre_learning_content: str,
    related_sources: str = "",
) -> list[dict[str, str]]:
    system = (
        "你是一名学习辅导者，不是代写者。请用清晰、具体的中文反馈。\n"
        "输出必须依次包含「合理之处」、「问题（1–3 个）」和「引导性问题」三个部分；"
        "先指出用户理解中合理之处，再指出最重要的 1–3 个问题，最后提出引导用户自行思考的问题。\n"
        "严禁代写交流后版正文，严禁替用户回答自测题，严禁改写或润色交流前版原话。\n"
        f"学科安全约束：{_safety_rule(subject)}"
    )
    user = (
        f"学科：{subject}\n主题：{topic}\n"
        "用户的交流前版原文（原样引用，仅供分析，不得改写）：\n"
        f"{pre_learning_content}"
        f"{_source_block(related_sources)}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_reference_prompt(
    subject: str,
    topic: str,
    post_discussion_content: str,
    related_sources: str = "",
) -> list[dict[str, str]]:
    headings = "\n".join(f"## {heading}" for heading in _REFERENCE_HEADINGS)
    system = (
        "你是一名学习辅导者。请根据交流后版生成简洁、准确的中文学习参考资料。\n"
        f"输出必须严格使用以下五个二级标题，顺序和文字均不得改变：\n{headings}\n"
        "自测问题只列问题，不提供答案。不得把模型结论写成现实预测或投资建议。\n"
        f"学科安全约束：{_safety_rule(subject)}"
    )
    user = (
        f"学科：{subject}\n主题：{topic}\n"
        "用户的交流后版内容：\n"
        f"{post_discussion_content}"
        f"{_source_block(related_sources)}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def validate_review_output(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ContentGuardError("反馈内容为空。")

    reasonable = re.search(r"合理之处|合理的地方|合理部分", text)
    problem = re.search(r"问题(?:（[^）]*）|\s*[:：])?", text)
    if reasonable is None or problem is None or reasonable.start() > problem.start():
        raise ContentGuardError("反馈必须先指出合理之处，再列出问题。")

    guidance = re.search(r"引导性问题|引导问题", text[problem.end() :])
    problem_text = text[problem.end() : problem.end() + guidance.start()] if guidance else text[problem.end() :]
    problem_text = problem_text.strip("：: \t\r\n")
    if not problem_text:
        raise ContentGuardError("问题部分不能为空。")

    list_items = re.findall(r"(?m)^\s*(?:[-*•]|\d+[.、)])\s+\S.+$", problem_text)
    if list_items:
        count = len(list_items)
    else:
        count = len([line for line in problem_text.splitlines() if line.strip()])
    if not 1 <= count <= 3:
        raise ContentGuardError("问题数量必须为 1–3 个。")

    if re.search(r"(?:你的交流后版(?:应该是|可以写成|如下)\s*[:：]|以下是(?:你|您的)交流后版|改写后的交流后版\s*[:：])", text):
        raise ContentGuardError("反馈包含代写交流后版正文的内容。")
    return text


def validate_reference_output(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ContentGuardError("参考内容为空。")
    missing = [heading for heading in _REFERENCE_HEADINGS if f"## {heading}" not in text]
    if missing:
        raise ContentGuardError("参考内容缺少必需标题：" + "、".join(missing))
    ai_declaration = re.search(
        r"(?:AI.{0,8}(?:编写|生成|撰写)|人工智能.{0,8}(?:编写|生成|撰写))",
        text,
        flags=re.IGNORECASE,
    )
    if ai_declaration is None:
        return f"{_AI_NOTICE}\n\n{text.strip()}"
    return text


def redact_user_content(text: str, max_chars: int = 80) -> str:
    """Return a log-safe excerpt that never reproduces the complete note."""
    if max_chars < 0:
        raise ValueError("max_chars must be non-negative")
    if not text:
        return "[用户内容已省略]"
    if len(text) <= max_chars:
        return "[用户内容已省略]"
    return f"{text[:max_chars]}…[已截断]"
