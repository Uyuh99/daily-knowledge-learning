from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Protocol, TypeAlias

from .file_writer import NoteFileError, update_note
from .note_manager import TopicNotePaths, create_topic_notes
from .retrieval import format_sources, index_notes, search
from .topic_selector import StudyPrompt, build_study_prompt, select_next_topic
from .vault_scan import scan_subject


class StudyServiceError(RuntimeError):
    """A study workflow could not proceed safely."""


class AIUnavailableError(StudyServiceError):
    """The configured AI provider is unavailable."""


ChatMessage: TypeAlias = dict[str, str]


class AIProvider(Protocol):
    @property
    def available(self) -> bool: ...

    def generate(self, messages: list[ChatMessage]) -> str: ...


@dataclass(frozen=True, slots=True)
class StudySession:
    subject: str
    topic: str
    module: str | None
    note_paths: TopicNotePaths
    prompt: StudyPrompt


_AI_REFERENCE_NOTICE = "> 本文件由 AI 编写，不代表用户观点。"
_REFERENCE_SECTIONS = (
    "核心定义",
    "运行机制",
    "现实例子",
    "常见混淆",
    "自测问题",
)
_EMPTY_PRE_LEARNING_MESSAGE = "交流前版尚无正文，请先写下你目前的理解和疑问，再请求 AI 反馈。"


def is_ai_available(provider: AIProvider) -> bool:
    availability = getattr(provider, "available", None)
    if availability is None:
        availability = getattr(provider, "is_available", False)
    if callable(availability):
        availability = availability()
    return bool(availability)


def _require_ai(provider: AIProvider) -> None:
    try:
        available = is_ai_available(provider)
    except Exception as error:
        raise AIUnavailableError("AI 服务当前不可用，请稍后重试。") from error
    if not available:
        raise AIUnavailableError("AI 服务当前不可用，请稍后重试。")


def _subject_root(vault_path: Path, subject: str) -> Path:
    direct = vault_path / subject
    if direct.is_dir():
        return direct
    return vault_path / "每日心理学与经济学学习" / subject


def _paths_for_existing(folder: Path) -> TopicNotePaths:
    pre_learning = folder / "01-交流前版.md"
    if not pre_learning.exists():
        pre_learning = folder / "01-学习前版.md"
    return TopicNotePaths(
        folder=folder,
        pre_learning=pre_learning,
        post_discussion=folder / "02-交流后版.md",
        ai_reference=folder / "03-AI参考版.md",
    )


_TOPIC_FOLDER = re.compile(r"^\d{4}-\d{2}-\d{2}-(?P<topic>.+)$")


def _existing_topic_folder(subject_root: Path, topic: str) -> Path | None:
    """Find folders created by either the core note manager or Vault workflow."""
    candidates = [subject_root / "每日记录", subject_root]
    matches: list[Path] = []
    for parent in candidates:
        if not parent.is_dir():
            continue
        for entry in parent.iterdir():
            if entry.is_dir() and (match := _TOPIC_FOLDER.match(entry.name)) and match.group("topic") == topic:
                matches.append(entry)
    return max(matches, key=lambda item: item.name, default=None)


def start_session(vault_path: Path, subject: str) -> StudySession:
    selection = select_next_topic(Path(vault_path), subject)
    if selection.topic is None:
        raise StudyServiceError(selection.reason or "当前没有可学习的主题。")

    try:
        records = scan_subject(_subject_root(Path(vault_path), subject), subject)
    except (OSError, ValueError) as error:
        raise StudyServiceError(f"无法读取 {subject} 的学习记录。") from error

    existing_folder = _existing_topic_folder(_subject_root(Path(vault_path), subject), selection.topic)
    if existing_folder is not None:
        note_paths = _paths_for_existing(existing_folder)
    else:
        subject_root = _subject_root(Path(vault_path), subject)
        try:
            note_paths = create_topic_notes(
                subject_root.parent,
                subject,
                selection.topic,
            )
        except (OSError, ValueError) as error:
            raise StudyServiceError(f"无法为主题「{selection.topic}」创建笔记。") from error

    return StudySession(
        subject=subject,
        topic=selection.topic,
        module=selection.module,
        note_paths=note_paths,
        prompt=build_study_prompt(selection),
    )


def _markdown_body(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        closing = next(
            (index for index in range(1, len(lines)) if lines[index].strip() == "---"),
            None,
        )
        if closing is not None:
            lines = lines[closing + 1 :]
    return "\n".join(line for line in lines if not line.lstrip().startswith("#")).strip()


def _read_note(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise StudyServiceError(f"无法读取笔记：{path.name}") from error


def _generate(provider: AIProvider, messages: list[ChatMessage]) -> str:
    _require_ai(provider)
    try:
        response = provider.generate(messages)
    except Exception as error:
        raise AIUnavailableError("AI 服务请求失败，请稍后重试。") from error
    if not isinstance(response, str) or not response.strip():
        raise StudyServiceError("AI 未返回可用内容，请重试。")
    return response.strip()


def _subject_guidance(subject: str) -> str:
    if subject == "心理学":
        return "心理学主题不得用于诊断用户或现实人物。"
    if subject == "经济学":
        return "经济学主题不得把模型结论当作对现实的预测。"
    return ""


def review_pre_learning(session: StudySession, provider: AIProvider) -> str:
    pre_learning = _read_note(session.note_paths.pre_learning)
    body = _markdown_body(pre_learning)
    if not body:
        return _EMPTY_PRE_LEARNING_MESSAGE

    chunks = index_notes(session.note_paths.folder.parent.parent)
    hits = search(
        session.topic,
        chunks,
        subject=session.subject,
        extra_keywords=session.prompt.search_keywords,
        limit=5,
    )
    sources = format_sources(hits)
    system = (
        "你是在辅导学习者，不是替他写作业。请用中文简洁反馈。"
        f"{_subject_guidance(session.subject)}"
        "先指出理解中合理之处，再指出最重要的 1–3 个问题，最后提出引导学习者自行核查和修正的问题。"
        "不得代写交流后版主体，不得替用户回答自测题，不得改写交流前版原话。"
    )
    user = (
        f"主题：{session.topic}\n模块：{session.module or '未分类'}\n"
        f"学习引导：{session.prompt.core_question}\n\n"
        f"学习者交流前版原文（只供分析，不要改写）：\n{body}\n\n"
        f"相关已有笔记片段：\n{sources}"
    )
    return _generate(
        provider,
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
    )


def _reference_body(text: str) -> str:
    cleaned = text.strip()
    if not all(section in cleaned for section in _REFERENCE_SECTIONS):
        raise StudyServiceError("AI 参考版内容缺少必需结构，未写入笔记。")
    return f"{_AI_REFERENCE_NOTICE}\n\n{cleaned}"


def generate_ai_reference(
    session: StudySession,
    provider: AIProvider,
    *,
    user_confirmed: bool,
) -> str:
    if not user_confirmed:
        raise StudyServiceError("请先确认交流后版，再生成 AI 参考版。")

    post_discussion = _read_note(session.note_paths.post_discussion)
    body = _markdown_body(post_discussion)
    if not body:
        raise StudyServiceError("交流后版尚无正文，无法生成 AI 参考版。")

    existing_reference = _read_note(session.note_paths.ai_reference)
    if _markdown_body(existing_reference):
        raise StudyServiceError("AI 参考版已有内容，拒绝覆盖。")

    system = (
        "你是在辅导学习者，不是替他写作业。请用中文为当前主题生成参考材料。"
        f"{_subject_guidance(session.subject)}"
        "严格使用以下五个 Markdown 二级标题：核心定义、运行机制、现实例子、常见混淆、自测问题。"
        "自测问题只列问题，不提供答案。"
    )
    user = (
        f"主题：{session.topic}\n模块：{session.module or '未分类'}\n"
        f"学习者交流后版：\n{body}\n\n"
        f"学习引导：{session.prompt.core_question}"
    )
    content = _reference_body(
        _generate(provider, [{"role": "system", "content": system}, {"role": "user", "content": user}])
    )
    try:
        update_note(session.note_paths.ai_reference, content)
    except NoteFileError as error:
        raise StudyServiceError("AI 参考版写入失败，笔记内容未被覆盖。") from error
    return content
