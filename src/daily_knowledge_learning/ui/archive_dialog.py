"""Confirmation dialog for archiving a completed study topic."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QTextEdit, QVBoxLayout

from .. import archive
from ..ai_provider import AIProvider
from ..models import TopicStatus
from ..study_service import StudySession, markdown_body
from ..yaml_utils import parse_frontmatter
from . import theme
from .widgets import Hairline, PageHeader, field_label, primary_button, secondary_button, set_reading_metrics


class ArchiveDialog(QDialog):
    """Review archive side effects and confirm the final summary."""

    archive_completed = Signal()

    def __init__(self, parent, *, vault_path: Path, subject: str, session: StudySession, provider: AIProvider) -> None:
        super().__init__(parent)
        self.vault_path, self.subject, self.session, self.provider = Path(vault_path), subject, session, provider
        self._archived = False
        self._already_archived = self._is_already_archived()
        self.setWindowTitle("确认归档")
        self.resize(640, 540)
        self.topic_label = QLabel(f"即将归档主题「{session.topic}」")
        self.topic_label.setObjectName("dialogTitle")
        self.topic_label.setWordWrap(True)

        self.checklist = QFrame()
        checklist_layout = QVBoxLayout(self.checklist)
        checklist_layout.setContentsMargins(0, 0, 0, 0)
        checklist_layout.setSpacing(theme.SPACE[1])
        checklist_layout.addWidget(field_label("将会"))
        for index, text in enumerate((
            "仅在交流后版已有你的学习总结时，把主题标记为「已完成」并记录完成日期",
            "在 01-交流前版.md 和 02-交流后版.md 末尾追加同一段 AI 最终总结",
            "把知识卡片追加到 知识卡片.md",
            "更新学习地图中的状态和笔记链接",
        )):
            if index:
                checklist_layout.addWidget(Hairline())
            line = QLabel(text)
            line.setWordWrap(True)
            checklist_layout.addWidget(line)

        self.summary_hint = QLabel("即将生成的最终总结（可编辑）：")
        self.summary_hint.setObjectName("metaText")
        self.summary_hint.setWordWrap(True)
        self.summary = QTextEdit()
        self.summary.setPlaceholderText("AI 不可用时，请在此输入最终总结后再确认归档。")
        self.summary.setAcceptRichText(False)
        set_reading_metrics(self.summary)
        self.result = QLabel()
        self.result.setObjectName("metaText")
        self.result.setWordWrap(True)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setProperty("variant", "")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确认归档")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setProperty("variant", "primary")
        self.buttons.rejected.connect(self.reject)
        self.buttons.accepted.connect(self._confirm_archive)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(theme.SPACE[2])
        layout.addWidget(PageHeader("归档确认", "请检查将要写入笔记库的内容"))
        layout.addWidget(self.topic_label)
        layout.addWidget(self.checklist)
        layout.addWidget(self.summary_hint)
        layout.addWidget(self.summary, 1)
        layout.addWidget(self.result)
        layout.addWidget(self.buttons)

        if self._already_archived:
            self.result.setText("该主题已标记为完成，可查看现有总结。")
            self.summary.setPlainText(self._existing_summary())
            self.summary.setReadOnly(True)
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        else:
            self._load_summary_draft()

    @property
    def archived(self) -> bool:
        return self._archived

    def _is_already_archived(self) -> bool:
        try:
            metadata = parse_frontmatter(self.session.note_paths.post_discussion.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            return False
        return metadata.get("status") in (archive.DONE, TopicStatus.COMPLETED)

    def _existing_summary(self) -> str:
        try:
            text = self.session.note_paths.post_discussion.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return ""
        return text.split(archive.SUMMARY_HEADING, 1)[1].lstrip(" \r\n").strip() if archive.SUMMARY_HEADING in text else ""

    def _load_summary_draft(self) -> None:
        try:
            available = self.provider.is_available()
        except Exception:
            available = False
        if not available:
            self.summary_hint.setText("即将生成的最终总结（可编辑）：AI 当前不可用，请手写总结后确认归档。")
            return
        try:
            content = self.session.note_paths.post_discussion.read_text(encoding="utf-8")
            messages = [
                {"role": "system", "content": "请用中文写一段精炼的学习最终总结，概括主题定义、关键理解和一个应用提醒，不超过三段。"},
                {"role": "user", "content": f"主题：{self.session.topic}\n交流后笔记：\n{content}"},
            ]
            draft = self.provider.chat(messages, timeout=30.0)
            if isinstance(draft, str) and draft.strip():
                self.summary.setPlainText(draft.strip())
                return
        except Exception:
            pass
        self.summary_hint.setText("即将生成的最终总结（可编辑）：AI 生成失败，请手写总结后确认归档。")

    def _card_content(self, summary: str) -> str:
        text = " ".join(line.strip() for line in summary.splitlines() if line.strip())
        sentences = re.split(r"(?<=[。！？!?])\s*", text)
        selected = [sentence for sentence in sentences if sentence][:3]
        return " ".join(selected)[:800] or text[:800]

    def _confirm_archive(self) -> None:
        try:
            post_body = markdown_body(self.session.note_paths.post_discussion.read_text(encoding="utf-8"))
        except (OSError, UnicodeError):
            post_body = ""
        if not post_body:
            self.result.setText("请先在「交流后版」写下并保存你自己的理解，再进行归档。")
            self.result.setStyleSheet(f"color: {theme.DANGER};")
            return
        summary = self.summary.toPlainText().strip()
        if not summary:
            self.result.setText("最终总结不能为空，请补充内容后再确认归档。")
            self.result.setStyleSheet(f"color: {theme.DANGER};")
            return
        result = archive.archive_topic(self.vault_path, self.subject, self.session.note_paths, summary, self._card_content(summary), completion_confirmed=True)
        failures, warnings = result.failed_steps, result.warnings
        if failures:
            lines = ["归档未完全成功："]
            lines.extend(f"- {step.name}：{step.message}" for step in failures)
            if warnings:
                lines.append("警告：")
                lines.extend(f"- {step.name}：{step.message}" for step in warnings)
            self.result.setText("\n".join(lines))
            self.result.setStyleSheet(f"color: {theme.DANGER};")
            return
        self._archived = True
        lines = ["已归档", "实际改动："]
        lines.extend(f"- {path.relative_to(self.vault_path) if path.is_relative_to(self.vault_path) else path}" for path in (
            self.session.note_paths.pre_learning, self.session.note_paths.post_discussion,
            self.vault_path / self.subject / archive.KNOWLEDGE_CARD_FILE,
        ))
        if warnings:
            lines.append("警告：")
            lines.extend(f"- {step.name}：{step.message}" for step in warnings)
        self.result.setText("\n".join(lines))
        self.result.setStyleSheet(f"color: {theme.OK};")
        self.summary.setReadOnly(True)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.archive_completed.emit()
