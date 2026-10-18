"""Confirmation dialog for archiving a completed study topic."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextEdit,
    QVBoxLayout,
)

from .. import archive
from ..ai_provider import AIProvider
from ..models import TopicStatus
from ..study_service import StudySession
from ..yaml_utils import parse_frontmatter


class ArchiveDialog(QDialog):
    """Let a learner review and confirm the side effects of archiving a topic.

    The dialog performs no Vault writes until the confirmation button is pressed.
    ``archive_completed`` is emitted after a successful archive so the owning
    page can refresh its own data without this dialog knowing about that page.
    """

    archive_completed = Signal()

    def __init__(
        self,
        parent,
        *,
        vault_path: Path,
        subject: str,
        session: StudySession,
        provider: AIProvider,
    ) -> None:
        super().__init__(parent)
        self.vault_path = Path(vault_path)
        self.subject = subject
        self.session = session
        self.provider = provider
        self._archived = False
        self._already_archived = self._is_already_archived()

        self.setWindowTitle("确认归档")
        self.resize(620, 520)
        self.topic_label = QLabel(f"即将归档主题「{session.topic}」")
        self.topic_label.setWordWrap(True)
        self.checklist = QLabel(
            "将会：\n"
            "✓ 把主题标记为「已完成」并记录完成日期\n"
            "✓ 在 01-交流前版.md 和 02-交流后版.md 末尾追加同一段 AI 最终总结\n"
            "✓ 把知识卡片追加到 知识卡片.md\n"
            "✓ 更新学习地图中的状态和笔记链接"
        )
        self.checklist.setWordWrap(True)
        self.summary_hint = QLabel("即将生成的最终总结（可编辑）：")
        self.summary_hint.setWordWrap(True)
        self.summary = QTextEdit()
        self.summary.setPlaceholderText("AI 不可用时，请在此输入最终总结后再确认归档。")
        self.summary.setAcceptRichText(False)
        self.result = QLabel()
        self.result.setWordWrap(True)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确认归档")
        self.buttons.rejected.connect(self.reject)
        self.buttons.accepted.connect(self._confirm_archive)

        layout = QVBoxLayout(self)
        for widget in (
            self.topic_label,
            self.checklist,
            self.summary_hint,
            self.summary,
            self.result,
            self.buttons,
        ):
            layout.addWidget(widget)

        if self._already_archived:
            self.result.setText("该主题已标记为完成，可查看现有总结。")
            self.summary.setPlainText(self._existing_summary())
            self.summary.setReadOnly(True)
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        else:
            self._load_summary_draft()

    @property
    def archived(self) -> bool:
        """Whether this dialog completed an archive operation successfully."""

        return self._archived

    def _is_already_archived(self) -> bool:
        try:
            metadata = parse_frontmatter(
                self.session.note_paths.post_discussion.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, ValueError):
            return False
        return metadata.get("status") == archive.DONE or metadata.get("status") == TopicStatus.COMPLETED

    def _existing_summary(self) -> str:
        try:
            text = self.session.note_paths.post_discussion.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return ""
        marker = archive.SUMMARY_HEADING
        if marker not in text:
            return ""
        return text.split(marker, 1)[1].lstrip(" \r\n").strip()

    def _load_summary_draft(self) -> None:
        """Ask the configured provider for a short draft, without writing it."""

        try:
            available = self.provider.is_available()
        except Exception:
            available = False
        if not available:
            self.summary_hint.setText(
                "即将生成的最终总结（可编辑）：AI 当前不可用，请手写总结后确认归档。"
            )
            return
        try:
            content = self.session.note_paths.post_discussion.read_text(encoding="utf-8")
            messages = [
                {
                    "role": "system",
                    "content": "请用中文写一段精炼的学习最终总结，概括主题定义、关键理解和一个应用提醒，不超过三段。",
                },
                {
                    "role": "user",
                    "content": f"主题：{self.session.topic}\n交流后笔记：\n{content}",
                },
            ]
            draft = self.provider.chat(messages, timeout=30.0)
            if isinstance(draft, str) and draft.strip():
                self.summary.setPlainText(draft.strip())
                return
        except Exception:
            pass
        self.summary_hint.setText(
            "即将生成的最终总结（可编辑）：AI 生成失败，请手写总结后确认归档。"
        )

    def _card_content(self, summary: str) -> str:
        """Condense the editable summary into a useful knowledge-card body."""

        text = " ".join(line.strip() for line in summary.splitlines() if line.strip())
        sentences = re.split(r"(?<=[。！？!?；;])\s*", text)
        selected = [sentence for sentence in sentences if sentence][:3]
        return " ".join(selected)[:800] or text[:800]

    def _confirm_archive(self) -> None:
        summary = self.summary.toPlainText().strip()
        if not summary:
            self.result.setText("最终总结不能为空，请补充内容后再确认归档。")
            return
        result = archive.archive_topic(
            self.vault_path,
            self.subject,
            self.session.note_paths,
            summary,
            self._card_content(summary),
            completion_confirmed=True,
        )
        failures = result.failed_steps
        warnings = result.warnings
        if failures:
            lines = ["归档未完全成功："]
            lines.extend(f"• {step.name}：{step.message}" for step in failures)
            if warnings:
                lines.append("警告：")
                lines.extend(f"• {step.name}：{step.message}" for step in warnings)
            self.result.setText("\n".join(lines))
            return

        self._archived = True
        lines = ["已归档", "实际改动："]
        lines.extend(
            f"• {path.relative_to(self.vault_path) if path.is_relative_to(self.vault_path) else path}"
            for path in (
                self.session.note_paths.pre_learning,
                self.session.note_paths.post_discussion,
                self.vault_path / self.subject / archive.KNOWLEDGE_CARD_FILE,
            )
        )
        if warnings:
            lines.append("警告：")
            lines.extend(f"• {step.name}：{step.message}" for step in warnings)
        self.result.setText("\n".join(lines))
        self.summary.setReadOnly(True)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.archive_completed.emit()

