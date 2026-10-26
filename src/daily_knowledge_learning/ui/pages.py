from __future__ import annotations

import inspect
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QSize, QTimer, Qt, Signal, Slot, QUrl
from PySide6.QtGui import QPalette, QDesktopServices
from PySide6.QtWidgets import (QComboBox, QFormLayout, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QProgressBar, QSpinBox, QStackedWidget, QTabWidget, QTextBrowser, QTextEdit,
    QVBoxLayout, QWidget, QFileDialog, QScrollArea, QFrame, QInputDialog)

from .. import __version__
from ..ai_provider import get_provider
from ..config import AppConfig, load_config, save_config, set_api_key
from ..file_writer import update_note
from ..models import TopicStatus
from ..note_manager import TopicNotePaths, create_topic_notes
from ..review_service import ReviewTask, complete_review, due_reviews
from ..stats_service import LearningStats, calculate_stats
from ..vault_qa import answer_vault_question
from ..study_service import (StudyServiceError, generate_ai_reference,
    generate_today_material, has_learning_material, review_pre_learning, start_session)
from ..topic_selector import build_study_prompt, select_next_topic
from ..vault_scan import scan_vault
from ..subjects import all_subjects, create_custom_subject
from .map_page import MapPage
from .notes_page import NotesPage
from .archive_dialog import ArchiveDialog
from . import theme
from .widgets import (BookIllustration, Card, EmptyState, PageHeader, SectionTitle,
    SubjectIllustration, meta_label, primary_button, secondary_button, set_reading_metrics)

VERSION_NAMES = ("01-交流前版.md", "02-交流后版.md", "03-AI参考版.md")


def _page_body(page: QWidget, max_width: int = 1040) -> QVBoxLayout:
    """Keep long pages usable at the minimum desktop window size."""
    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    scroll = QScrollArea()
    scroll.setObjectName("pageScroll")
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    body = QWidget()
    body.setObjectName("scrollBody")
    shell = QHBoxLayout(body)
    shell.setContentsMargins(0, 0, 0, 0)
    column = QWidget()
    column.setObjectName("pageColumn")
    column.setMaximumWidth(max_width)
    layout = QVBoxLayout(column)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)
    shell.addStretch(0)
    shell.addWidget(column, 1)
    shell.addStretch(0)
    scroll.setWidget(body)
    outer.addWidget(scroll)
    return layout


def _text(text: str, name: str = "bodyText") -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(name not in ("sectionAside", "dateLabel"))
    return label


def _subject_identifier(vault_path: Path, index: int, display: str) -> str:
    project = vault_path / "每日心理学与经济学学习"
    if project.is_dir():
        project_subjects = sorted((path for path in project.iterdir() if path.is_dir()), key=lambda path: path.name)
        for value in (path.name for path in project_subjects):
            if value == display or display in value:
                return value
        if index < len(project_subjects):
            return project_subjects[index].name
    roots = sorted((path for path in vault_path.iterdir() if path.is_dir()), key=lambda path: path.name)
    if len(roots) == 1 and not any((vault_path / name).is_dir() for name in ("心理学", "经济学")):
        roots = sorted((path for path in roots[0].iterdir() if path.is_dir()), key=lambda path: path.name)
    existing = [path.name for path in roots]
    for value in existing:
        if value == display or display in value:
            return value
    return existing[index] if index < len(existing) else display


class MarkdownPreviewPage(QWidget):
    def __init__(self, title: str, markdown: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(title))
        self.viewer = QTextEdit()
        self.viewer.setReadOnly(True)
        self.viewer.setMarkdown(markdown)
        layout.addWidget(self.viewer)


def _safe_config(path: Path | None = None) -> AppConfig:
    try:
        return load_config(path)
    except (OSError, ValueError):
        return AppConfig()


class HomePage(QWidget):
    subject_requested = Signal(int)

    def __init__(self, vault_path: Path | None, open_today, open_settings=None,
                 subjects: tuple[str, ...] = ("心理学", "经济学"), on_subject_added=None, parent=None):
        super().__init__(parent)
        self.vault_path, self.open_today = vault_path, open_today
        self.open_settings = open_settings or (lambda: None)
        self.subjects = tuple(subjects)
        self.on_subject_added = on_subject_added or (lambda name: None)
        self.progress = {}
        self.metrics = {}
        self.next_topics = {}
        layout = _page_body(self)
        header = PageHeader("每日一知", "读一点，想深一点。让知识慢慢成为自己的见解。")
        today = datetime.now()
        weekday = "一二三四五六日"[today.weekday()]
        header.add_action(_text(f"{today.month:02d} 月 {today.day:02d} 日  ·  周{weekday}", "dateLabel"))
        layout.addWidget(header)
        hero = QFrame()
        hero.setObjectName("studyHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 22, 20, 22)
        copy = QVBoxLayout()
        copy.setSpacing(10)
        self.hero_eyebrow = _text("今日书签  /  从一个问题开始", "heroEyebrow")
        self.hero_title = _text("留一点时间，给新的理解。", "heroTitle")
        self.hero_body = _text("先写下自己的想法，再与新的观点相遇。", "heroBody")
        copy.addWidget(self.hero_eyebrow)
        copy.addWidget(self.hero_title)
        copy.addWidget(self.hero_body)
        self.start = primary_button("翻开今日学习  →")
        self.start.clicked.connect(lambda checked=False: self._open_subject(0))
        copy.addWidget(self.start, 0, Qt.AlignmentFlag.AlignLeft)
        hero_layout.addLayout(copy, 1)
        self.illustration = BookIllustration()
        hero_layout.addWidget(self.illustration)
        layout.addWidget(hero)
        self.empty_state = EmptyState("连接你的知识库", "请先在设置中配置 Vault 路径。")
        self.guide = self.empty_state.hint
        self.settings_button = secondary_button("前往设置")
        self.settings_button.clicked.connect(self.open_settings)
        self.empty_state.layout().addWidget(self.settings_button, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_state)
        subject_header = QHBoxLayout()
        subject_header.addWidget(SectionTitle("案头的学问"))
        subject_header.addStretch()
        subject_header.addWidget(_text("从理解自己，到理解世界", "sectionAside"))
        self.add_subject_button = secondary_button("＋ 添加学问")
        self.add_subject_button.clicked.connect(self._add_subject)
        subject_header.addWidget(self.add_subject_button)
        layout.addLayout(subject_header)
        self.subject_cards = QGridLayout()
        self.subject_cards.setHorizontalSpacing(12)
        self.subject_cards.setVerticalSpacing(12)
        self._rebuild_subject_cards()
        layout.addLayout(self.subject_cards)
        recent_header = QHBoxLayout()
        recent_header.addWidget(SectionTitle("最近的收获"))
        recent_header.addStretch()
        self.summary = _text("每一次理解，都值得留下。", "sectionAside")
        recent_header.addWidget(self.summary)
        layout.addLayout(recent_header)
        self.recent = QListWidget()
        self.recent.setObjectName("recentList")
        self.recent.setMinimumHeight(80)
        self.recent.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.recent_empty = EmptyState("还没有完成的知识点", "完成第一个知识点后，这里会出现你的学习记录")
        layout.addWidget(self.recent_empty)
        layout.addWidget(self.recent)
        layout.addStretch(1)
        self.refresh()

    def set_subjects(self, subjects: tuple[str, ...]) -> None:
        self.subjects = tuple(subjects)
        self._rebuild_subject_cards()
        self.refresh()

    def _rebuild_subject_cards(self) -> None:
        while self.subject_cards.count():
            item = self.subject_cards.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
            elif item.layout() is not None:
                item.layout().deleteLater()
        self.progress.clear(); self.metrics.clear(); self.next_topics.clear()
        self.subject_cards.setColumnStretch(0, 1)
        self.subject_cards.setColumnStretch(1, 1)
        for index, subject in enumerate(self.subjects):
            key = "psychology" if subject == "心理学" else "economics" if subject == "经济学" else "custom"
            card = Card(margins=(18, 16, 18, 16), spacing=10)
            card.setObjectName("subjectCard")
            card.setProperty("subject", key)
            title_row = QHBoxLayout()
            title_copy = QVBoxLayout(); title_copy.setSpacing(2)
            title_copy.addWidget(_text(subject, "subjectTitle"))
            subtitle = "理解心智与行为" if key == "psychology" else "看见选择与取舍" if key == "economics" else "建立自己的学习路线"
            title_copy.addWidget(_text(subtitle, "subjectSubtitle"))
            title_row.addLayout(title_copy, 1); title_row.addWidget(SubjectIllustration(key)); card.body.addLayout(title_row)
            counts = QHBoxLayout(); count = _text("0 / 0", "metricValue")
            self.metrics[subject] = count; counts.addWidget(count); counts.addWidget(_text("已学 / 已记录", "metricLabel"), 1, Qt.AlignmentFlag.AlignBottom); counts.setSpacing(10); card.body.addLayout(counts)
            bar = QProgressBar(); bar.setRange(0, 100); bar.setTextVisible(False); bar.setProperty("subject", key)
            self.progress[subject] = bar; card.body.addWidget(bar)
            next_topic = QPushButton("选择学习主题  →"); next_topic.setProperty("variant", "subject"); next_topic.setProperty("subject", key); next_topic.setCursor(Qt.CursorShape.PointingHandCursor)
            next_topic.clicked.connect(lambda checked=False, index=index: self._open_subject(index)); self.next_topics[subject] = next_topic; card.body.addWidget(next_topic)
            self.subject_cards.addWidget(card, index // 2, index % 2)
        add_index = len(self.subjects)
        self.subject_cards.addWidget(self._new_subject_card(), add_index // 2, add_index % 2)

    def _new_subject_card(self) -> QWidget:
        card = Card(margins=(18, 16, 18, 16), spacing=10)
        card.setObjectName("subjectCard")
        card.setProperty("subject", "custom")
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        title = _text("添加一门学问", "subjectTitle")
        title.setStyleSheet(f"color: {theme.ACCENT};")
        card.body.addWidget(title)
        card.body.addWidget(_text("把感兴趣的方向放进自己的学习书房。", "subjectSubtitle"))
        button = secondary_button("创建学习入口  ＋")
        button.clicked.connect(self._add_subject)
        card.body.addStretch(1)
        card.body.addWidget(button)
        return card

    def _add_subject(self) -> None:
        if self.vault_path is None or not self.vault_path.is_dir():
            QMessageBox.information(self, "先连接知识库", "请先在设置中配置 Vault 路径，再添加自定义学问。")
            return
        name, ok = QInputDialog.getText(self, "添加一门学问", "学问名称（例如：历史、哲学、写作）：")
        if not ok or not name.strip():
            return
        if name.strip() in self.subjects:
            QMessageBox.information(self, "学问已存在", "这门学问已经在你的书房里了。")
            return
        raw_topics, ok = QInputDialog.getText(
            self, "设置学习路线", "起步主题（用逗号分隔，可留空使用默认主题）：",
            text="核心概念，现实例子，常见误区",
        )
        if not ok:
            return
        try:
            create_custom_subject(self.vault_path, name, raw_topics.replace("，", ",").split(","))
            self.on_subject_added(name.strip())
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "添加失败", str(error))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.illustration.setVisible(self.width() >= 670)

    def _open_subject(self, index: int) -> None:
        subject = self.subjects[index] if 0 <= index < len(self.subjects) else None
        if subject is not None and subject in self.next_topics and not self.next_topics[subject].isEnabled():
            self.empty_state.show()
            self.guide.setText("当前 Vault 没有找到可开始的学习主题，请在设置中选择包含‘每日心理学与经济学学习’的目录。")
            return
        self.subject_requested.emit(index)
        self.open_today()

    def refresh(self) -> None:
        self.recent.clear()
        if self.vault_path is None or not self.vault_path.is_dir():
            self.hero_eyebrow.setText("今日书签  /  从一个问题开始")
            self.hero_title.setText("留一点时间，给新的理解。")
            self.hero_body.setText("先写下自己的想法，再与新的观点相遇。")
            self.empty_state.show()
            self.start.setEnabled(False)
            self.recent_empty.show()
            self.recent.hide()
            for subject, bar in self.progress.items():
                bar.setValue(0)
                self.metrics[subject].setText("0 / 0")
                self.next_topics[subject].setEnabled(False)
            return
        self.empty_state.hide()
        has_topics = False
        try: records = scan_vault(self.vault_path)
        except (OSError, ValueError): records = []
        for index, subject in enumerate(self.subjects):
            bar = self.progress[subject]
            items = [r for r in records if r.subject == subject]
            done = sum(r.status is TopicStatus.COMPLETED for r in items)
            bar.setValue(round(done * 100 / len(items)) if items else 0)
            self.metrics[subject].setText(f"{done} / {len(items)}")
            try:
                identifier = _subject_identifier(self.vault_path, index, subject)
                selected = select_next_topic(self.vault_path, identifier)
                topic = selected.topic
            except (OSError, ValueError):
                topic = None
            short_topic = topic[:16] + "…" if topic and len(topic) > 16 else topic
            self.next_topics[subject].setText(f"今日 · {short_topic}  →" if topic else "查看学习安排  →")
            self.next_topics[subject].setToolTip(topic or "查看该学科的学习安排")
            self.next_topics[subject].setEnabled(bool(topic))
            has_topics = has_topics or bool(topic)
            if index == 0:
                self.hero_eyebrow.setText("今日书签  /  心理学")
                self.hero_title.setText(topic or "留一点时间，给新的理解。")
                self.hero_body.setText("从自己的经验出发，理解这个观点如何影响日常生活。")
                continuing = any(r.topic == topic and r.status is TopicStatus.IN_PROGRESS for r in items)
                self.start.setText("继续这一页  →" if continuing else "翻开今日学习  →")
        self.start.setEnabled(has_topics)
        if not has_topics:
            self.empty_state.show()
            self.guide.setText("当前 Vault 没有找到可开始的学习主题，请在设置中选择包含‘每日心理学与经济学学习’的目录。")
        done = sorted((r for r in records if r.status is TopicStatus.COMPLETED), key=lambda r: (r.date, r.topic), reverse=True)
        self.recent.clear()
        for r in done[:5]:
            row = QWidget(self.recent.viewport())
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(theme.SPACE[2], theme.SPACE[1], theme.SPACE[2], theme.SPACE[1])
            row_layout.setSpacing(theme.SPACE[0])
            topic = QLabel(r.topic)
            topic.setWordWrap(True)
            metadata = QHBoxLayout()
            metadata.addWidget(meta_label(r.date))
            metadata.addStretch(1)
            metadata.addWidget(meta_label(r.subject))
            row_layout.addWidget(topic)
            row_layout.addLayout(metadata)
            row.ensurePolished()
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, max(64, row.sizeHint().height())))
            self.recent.addItem(item)
            self.recent.setItemWidget(item, row)
        self.recent_empty.setVisible(not done)
        self.recent.setVisible(bool(done))
        self.recent.setFixedHeight(min(5, max(1, len(done))) * 68 + 12)
        self.summary.setText(f"已留下 {len(done)} 次学习记录" if done else "每一次理解，都值得留下。")


class ReviewPage(QWidget):
    reviews_changed = Signal()

    def __init__(self, vault_path: Path | None, parent=None):
        super().__init__(parent)
        self.vault_path = vault_path
        self.rows = QVBoxLayout()
        self.rows.setSpacing(10)
        layout = _page_body(self)
        layout.addWidget(PageHeader("今日复习", "按学习单中的间隔计划，集中完成今天到期的回忆练习。"))
        self.count = _text("正在整理复习计划…", "sectionAside")
        layout.addWidget(self.count)
        self.empty = EmptyState("今天没有待复习内容", "新完成的学习单会按第 1、3、7、14 天安排回顾。")
        layout.addWidget(self.empty)
        rows_host = QWidget()
        rows_host.setLayout(self.rows)
        layout.addWidget(rows_host)
        layout.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        while self.rows.count():
            item = self.rows.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        tasks = due_reviews(self.vault_path) if self.vault_path and self.vault_path.is_dir() else []
        self.count.setText(f"{len(tasks)} 项待复习" if tasks else "复习清单已完成")
        self.empty.setVisible(not tasks)
        for task in tasks:
            card = Card(margins=(18, 14, 18, 14), spacing=8)
            top = QHBoxLayout()
            title = _text(task.topic, "subjectTitle")
            top.addWidget(title, 1)
            top.addWidget(meta_label(task.subject))
            card.body.addLayout(top)
            when = "逾期" if task.due_date < datetime.now().date() else "今天"
            card.body.addWidget(_text(f"第 {task.interval_days} 天 · {when}到期 · {task.due_date.isoformat()}", "metaText"))
            card.body.addWidget(_text(task.instruction, "bodyText"))
            finish = secondary_button("完成复习")
            finish.clicked.connect(lambda checked=False, item=task: self._complete(item))
            card.body.addWidget(finish, 0, Qt.AlignmentFlag.AlignRight)
            self.rows.addWidget(card)

    def _complete(self, task: ReviewTask) -> None:
        try:
            complete_review(task)
        except (OSError, ValueError) as error:
            self.count.setText(f"无法更新笔记：{error}")
            return
        self.refresh()
        self.reviews_changed.emit()


class StatsPage(QWidget):
    """A read-only dashboard derived from the current Vault contents."""

    def __init__(self, vault_path: Path | None, parent=None):
        super().__init__(parent)
        self.vault_path = vault_path
        layout = _page_body(self)
        header = PageHeader("学习统计", "看见已经走过的路，也知道下一步从哪里开始。")
        self.refresh_button = secondary_button("刷新数据")
        self.refresh_button.clicked.connect(self.refresh)
        header.add_action(self.refresh_button)
        layout.addWidget(header)

        self.empty = EmptyState("还没有可统计的学习记录", "连接 Vault 并完成一个知识点后，这里会开始记录你的学习轨迹。")
        layout.addWidget(self.empty)

        self.metric_grid = QGridLayout()
        self.metric_grid.setHorizontalSpacing(12)
        self.metric_grid.setVerticalSpacing(12)
        self.metric_values: dict[str, QLabel] = {}
        metric_specs = (
            ("total", "主题总数", "从 Vault 扫描到的知识点"),
            ("completed", "已完成", "已经确认的学习单"),
            ("rate", "完成率", "已完成 / 主题总数"),
            ("streak", "连续学习", "按完成日期计算"),
            ("reviews", "待复习", "今天已经到期的回顾"),
            ("active", "活跃天数", "有完成记录的日期"),
        )
        for index, (key, title, hint) in enumerate(metric_specs):
            card = Card(margins=(16, 14, 16, 14), spacing=5)
            card.setObjectName("statsMetricCard")
            card.body.addWidget(_text(title, "metricLabel"))
            value = _text("—", "statsMetricValue")
            self.metric_values[key] = value
            card.body.addWidget(value)
            card.body.addWidget(_text(hint, "metaText"))
            self.metric_grid.addWidget(card, index // 3, index % 3)
        layout.addLayout(self.metric_grid)

        activity = Card(margins=(18, 16, 18, 16), spacing=10)
        activity.setObjectName("statsPanel")
        activity.body.addWidget(SectionTitle("近 7 天活动"))
        self.activity_rows = QVBoxLayout()
        self.activity_rows.setSpacing(7)
        activity.body.addLayout(self.activity_rows)
        layout.addWidget(activity)

        subject_panel = Card(margins=(18, 16, 18, 16), spacing=10)
        subject_panel.setObjectName("statsPanel")
        subject_panel.body.addWidget(SectionTitle("各学问进度"))
        self.subject_rows = QVBoxLayout()
        self.subject_rows.setSpacing(12)
        subject_panel.body.addLayout(self.subject_rows)
        layout.addWidget(subject_panel)
        layout.addStretch(1)
        self.refresh()

    def _clear_layout(self, target: QVBoxLayout) -> None:
        while target.count():
            item = target.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

    def _set_metric(self, key: str, value: str) -> None:
        self.metric_values[key].setText(value)

    def refresh(self) -> None:
        stats = calculate_stats(self.vault_path) if self.vault_path and self.vault_path.is_dir() else LearningStats(
            0, 0, 0, 0, 0, 0, 0, 0, 0, (), ()
        )
        has_data = stats.total_topics > 0
        self.empty.setVisible(not has_data)
        self.metric_grid.setEnabled(has_data)
        self._set_metric("total", str(stats.total_topics))
        self._set_metric("completed", str(stats.completed_topics))
        self._set_metric("rate", f"{stats.completion_rate}%")
        self._set_metric("streak", f"{stats.streak_days} 天")
        self._set_metric("reviews", str(stats.due_reviews))
        self._set_metric("active", str(stats.active_days))

        self._clear_layout(self.activity_rows)
        max_activity = max((count for _, count in stats.recent_activity), default=0)
        for day, count in stats.recent_activity:
            row = QHBoxLayout()
            row.setSpacing(10)
            label = _text(day.strftime("%m/%d"), "metaText")
            label.setFixedWidth(42)
            row.addWidget(label)
            bar = QProgressBar()
            bar.setRange(0, max(1, max_activity))
            bar.setValue(count)
            bar.setTextVisible(False)
            bar.setToolTip(f"{day.isoformat()}：完成 {count} 个主题")
            row.addWidget(bar, 1)
            row.addWidget(_text(str(count), "metricLabel"))
            self.activity_rows.addLayout(row)

        self._clear_layout(self.subject_rows)
        if not stats.subjects:
            self.subject_rows.addWidget(_text("连接 Vault 后会显示各学问的完成进度。", "metaText"))
        for subject in stats.subjects:
            row = QVBoxLayout()
            top = QHBoxLayout()
            top.addWidget(_text(subject.subject, "subjectTitle"), 1)
            top.addWidget(_text(f"{subject.completed} / {subject.total} · {subject.completion_rate}%", "metricLabel"))
            row.addLayout(top)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(subject.completion_rate)
            bar.setTextVisible(False)
            row.addWidget(bar)
            status = _text(
                f"进行中 {subject.in_progress} · 待学习 {subject.to_learn} · 暂缓 {subject.deferred}",
                "metaText",
            )
            row.addWidget(status)
            self.subject_rows.addLayout(row)


class _AIServiceAdapter:
    """Adapt the provider's chat API to study_service's generate protocol."""

    # A complete daily lesson is substantially longer than a connection
    # probe. DeepSeek can take 30–60 seconds to return it, so the UI worker
    # must not use the provider's short 30-second default timeout.
    GENERATION_TIMEOUT_SECONDS = 90.0

    def __init__(self, provider):
        self.provider = provider

    def is_available(self) -> bool:
        return self.provider.is_available()

    def generate(self, messages: list[dict[str, str]]) -> str:
        chat = self.provider.chat
        # Keep compatibility with lightweight test/custom providers that
        # implement the original ``chat(messages)`` shape.
        try:
            parameters = inspect.signature(chat).parameters.values()
            accepts_timeout = any(
                parameter.name == "timeout"
                or parameter.kind is inspect.Parameter.VAR_KEYWORD
                for parameter in parameters
            )
        except (TypeError, ValueError):
            accepts_timeout = False
        if accepts_timeout:
            return chat(messages, timeout=self.GENERATION_TIMEOUT_SECONDS)
        return chat(messages)


class _WorkerSignals(QObject):
    completed = Signal(object, str, bool)


class _AIWorker(QRunnable):
    def __init__(self, action, session, provider):
        super().__init__()
        self.signals = _WorkerSignals()
        self.action = action
        self.session = session
        self.provider = _AIServiceAdapter(provider)

    def run(self):
        try:
            self.signals.completed.emit(self, self.action(self.session, self.provider), True)
        except Exception as error:
            self.signals.completed.emit(self, str(error), False)


class _ConnectionSignals(QObject):
    completed = Signal(object, str, bool)


class _ConnectionWorker(QRunnable):
    def __init__(self, provider):
        super().__init__()
        self.signals = _ConnectionSignals()
        self.provider = provider

    def run(self):
        try:
            self.provider.chat([{"role": "user", "content": "只回复：连接成功"}], timeout=15.0)
            self.signals.completed.emit(self, "连接成功，供应商已返回响应。", True)
        except Exception as error:
            self.signals.completed.emit(self, str(error), False)


class _VaultQASignals(QObject):
    completed = Signal(object, object, bool)


class _VaultQAWorker(QRunnable):
    def __init__(self, vault_path: Path, question: str, subject: str | None, provider):
        super().__init__()
        self.signals = _VaultQASignals()
        self.vault_path, self.question, self.subject, self.provider = vault_path, question, subject, provider

    def run(self):
        try:
            self.signals.completed.emit(
                self, answer_vault_question(self.vault_path, self.question, self.provider, subject=self.subject), True
            )
        except Exception as error:
            self.signals.completed.emit(self, str(error), False)


class VaultQAPage(QWidget):
    """Ask questions grounded in the local Markdown Vault."""

    def __init__(self, vault_path: Path | None, config: AppConfig, parent=None):
        super().__init__(parent)
        self.vault_path, self.config = vault_path, config
        self._thread_pool = QThreadPool(self)
        self._workers = set()
        layout = _page_body(self)
        layout.addWidget(PageHeader("知识库问答", "基于自己的笔记寻找答案，每条结论都能回到原文。"))
        card = Card(margins=(20, 18, 20, 18), spacing=12)
        card.body.addWidget(SectionTitle("向你的笔记提问"))
        controls = QHBoxLayout()
        self.subject = QComboBox()
        self.subject.addItem("全部学科", None)
        controls.addWidget(QLabel("范围")); controls.addWidget(self.subject)
        controls.addStretch(1)
        card.body.addLayout(controls)
        self.question = QTextEdit()
        self.question.setObjectName("vaultQuestion")
        self.question.setPlaceholderText("例如：沉没成本会怎样影响我的日常选择？")
        self.question.setFixedHeight(94)
        card.body.addWidget(self.question)
        actions = QHBoxLayout()
        self.ask = primary_button("检索并回答  →")
        self.ask.clicked.connect(self.ask_question)
        self.status = _text("回答仅依据本地 Markdown 笔记；发送问题和相关片段到所选 AI 服务。", "metaText")
        self.status.setWordWrap(True)
        actions.addWidget(self.ask); actions.addWidget(self.status, 1)
        card.body.addLayout(actions)
        layout.addWidget(card)
        layout.addWidget(SectionTitle("回答"))
        self.answer = QTextBrowser()
        self.answer.setObjectName("vaultAnswer")
        self.answer.setOpenExternalLinks(False)
        self.answer.setPlaceholderText("检索到的答案会显示在这里。")
        self.answer.setMinimumHeight(180)
        layout.addWidget(self.answer)
        layout.addWidget(SectionTitle("引用来源  ·  双击打开原笔记"))
        self.sources = QListWidget()
        self.sources.setObjectName("vaultSources")
        self.sources.itemDoubleClicked.connect(self._open_source)
        self.sources.setMinimumHeight(100)
        layout.addWidget(self.sources)
        layout.addStretch(1)
        self.set_subjects(all_subjects(config.custom_subjects))

    def set_subjects(self, subjects: tuple[str, ...]) -> None:
        selected = self.subject.currentData() if hasattr(self, "subject") else None
        self.subject.clear()
        self.subject.addItem("全部学科", None)
        for name in subjects:
            self.subject.addItem(name, name)
        index = self.subject.findData(selected)
        self.subject.setCurrentIndex(index if index >= 0 else 0)

    def refresh(self) -> None:
        available = self.vault_path is not None and self.vault_path.is_dir()
        self.ask.setEnabled(available)
        if not available:
            self.status.setText("请先在设置中配置有效的 Vault 路径。")

    def ask_question(self) -> None:
        question = self.question.toPlainText().strip()
        if not question:
            self.status.setText("请先输入一个问题。")
            return
        if self.vault_path is None or not self.vault_path.is_dir():
            self.status.setText("请先在设置中配置有效的 Vault 路径。")
            return
        if self.config.ai_provider == "mock":
            self.status.setText("请先在设置中选择并配置 OpenAI、Claude 或其他 AI 服务。")
            return
        try:
            provider = get_provider(
                self.config.ai_provider, model=self.config.model or None,
                base_url=self.config.api_base_url or None, api_protocol=self.config.api_protocol,
            )
            if not provider.is_available():
                self.status.setText("请先在设置中配置 API 密钥。")
                return
        except (TypeError, ValueError) as error:
            self.status.setText(f"AI 配置无效：{error}")
            return
        worker = _VaultQAWorker(self.vault_path, question, self.subject.currentData(), provider)
        worker.signals.completed.connect(self._answer_finished)
        self._workers.add(worker)
        self.ask.setEnabled(False)
        self.ask.setText("正在检索与整理…")
        self.status.setText("正在本地检索笔记，并请求 AI 根据来源作答…")
        self._thread_pool.start(worker)

    @Slot(object, object, bool)
    def _answer_finished(self, worker, result, ok: bool) -> None:
        self._workers.discard(worker)
        self.ask.setEnabled(True)
        self.ask.setText("检索并回答  →")
        if not ok:
            self.status.setText(f"回答失败：{result}")
            return
        response, hits = result
        self.answer.setMarkdown(response)
        self.sources.clear()
        for index, hit in enumerate(hits, start=1):
            item = QListWidgetItem(f"[{index}] {hit.heading}  ·  {hit.path}  ·  第 {hit.line_number} 行")
            item.setData(Qt.ItemDataRole.UserRole, hit.path)
            self.sources.addItem(item)
        self.status.setText(f"已参考 {len(hits)} 段本地笔记。")

    def _open_source(self, item: QListWidgetItem) -> None:
        if self.vault_path is None:
            return
        target = (self.vault_path / str(item.data(Qt.ItemDataRole.UserRole))).resolve()
        try:
            target.relative_to(self.vault_path.resolve())
        except ValueError:
            return
        if target.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))


class TodayPage(QWidget):
    topic_ready = Signal(Path)
    reference_ready = Signal(Path)
    ai_completed = Signal(str, bool)
    archive_completed = Signal()

    def __init__(self, vault_path: Path | None, config_path: Path | None = None,
                 subjects: tuple[str, ...] = ("心理学", "经济学"), parent=None):
        super().__init__(parent); self.vault_path = vault_path; self.config_path = config_path
        self.subjects = tuple(subjects)
        self._thread_pool = QThreadPool(self)
        self._workers = set()
        self._generated_references = set()
        self._generated_materials = set()
        self.archive_button = primary_button("完成并归档")
        self.archive_button.clicked.connect(self.archive_learning)
        self.session = None
        self.subject = QComboBox(); self.subject.addItems(self.subjects)
        self.fields = {key: QLabel() for key in ("topic", "module", "reason", "relationship", "question", "keywords", "schedule")}
        for w in self.fields.values(): w.setWordWrap(True)
        self.start = primary_button("生成今日学习单  →"); self.start.clicked.connect(self.start_learning)
        form = QFormLayout()
        form.setSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        labels = {"reason":"为什么学它", "relationship":"知识的衔接", "keywords":"检索线索"}
        for key, label in labels.items():
            self.fields[key].setObjectName("readingBody")
            form.addRow(_text(label, "fieldLabel"), self.fields[key])
        self.fields["topic"].setObjectName("topicTitle")
        self.fields["module"].setObjectName("metaText")
        self.fields["question"].setObjectName("readingQuestion")
        self.fields["schedule"].setObjectName("practiceStep")
        self.review_button = QPushButton("检查交流前版")
        self.reference_button = QPushButton("生成 AI 参考版")
        self.review_button.clicked.connect(self.review_pre_learning)
        self.reference_button.clicked.connect(self.generate_reference)
        self.ai_status = QLabel()
        self.ai_status.setObjectName("statusLabel")
        self.ai_status.setWordWrap(True)
        self.ai_feedback = QTextEdit()
        self.ai_feedback.setReadOnly(True)
        self.ai_feedback.setMinimumHeight(150)
        set_reading_metrics(self.ai_feedback)
        self.ai_feedback.setPlaceholderText("AI 反馈会显示在这里，不会自动写入笔记")
        layout = _page_body(self, 860)
        header = PageHeader("今日学习", "带着问题阅读，在交流中修正，把收获写进自己的语言。")
        header.add_action(self.subject)
        layout.addWidget(header)
        steps = QFrame()
        steps.setObjectName("practiceSteps")
        steps_row = QHBoxLayout(steps)
        steps_row.setContentsMargins(16, 9, 16, 9)
        for index, title in enumerate(("01  独立思考", "02  交流求证", "03  整理归档")):
            steps_row.addWidget(_text(title, "stepLabel"), 1)
        layout.addWidget(steps)
        topic = Card(margins=(24, 22, 24, 22), spacing=12)
        topic.body.addWidget(_text("今日阅读  /  先从你的理解出发", "stepLabel"))
        topic.body.addWidget(self.fields["topic"])
        topic.body.addWidget(self.fields["module"])
        question = QFrame()
        question.setObjectName("questionCard")
        question_layout = QVBoxLayout(question)
        question_layout.setContentsMargins(16, 12, 16, 12)
        question_layout.setSpacing(6)
        question_layout.addWidget(_text("带着这个问题读", "stepLabel"))
        question_layout.addWidget(self.fields["question"])
        topic.body.addWidget(question)
        topic.body.addLayout(form)
        topic.body.addWidget(_text("给这次学习留一点时间", "fieldLabel"))
        topic.body.addWidget(self.fields["schedule"])
        topic.body.addWidget(self.start, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(topic)
        discussion = Card()
        discussion.body.addWidget(_text("02  /  交流与反思", "stepLabel"))
        discussion.body.addWidget(_text("让想法经得起追问", "sectionTitle"))
        discussion.body.addWidget(_text("先保存独立思考，再让 AI 帮你补充证据与不同视角。", "metaText"))
        discussion.body.addWidget(self.ai_status)
        discussion.body.addWidget(self.ai_feedback, 1)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self.review_button)
        actions.addWidget(self.reference_button)
        actions.addStretch()
        discussion.body.addLayout(actions)
        layout.addWidget(discussion, 1)
        finish = QHBoxLayout()
        finish.addWidget(_text("03  /  整理收获，保存到知识库", "metaText"), 1)
        finish.addWidget(self.archive_button)
        layout.addLayout(finish)
        self.subject.currentTextChanged.connect(self.refresh); self.refresh()

    def refresh(self) -> None:
        if self.vault_path is None or not self.vault_path.is_dir():
            self.fields["topic"].setText("请先在设置中配置 Vault 路径。"); self.start.setEnabled(False); return
        try:
            records = scan_vault(self.vault_path)
            internal_subject = _subject_identifier(self.vault_path, self.subject.currentIndex(), self.subject.currentText())
            result = select_next_topic(self.vault_path, internal_subject); prompt = build_study_prompt(result)
        except Exception as error:
            self.fields["topic"].setText(f"无法读取今日选题：{error}"); self.start.setEnabled(False); return
        if not result.topic:
            self.fields["topic"].setText("暂无可用主题")
            self.ai_status.setText(
                "没有找到可开始的学习主题。请到设置中选择包含‘每日心理学与经济学学习’及学习地图的 Vault 目录。"
            )
            self.start.setEnabled(False)
            return
        values = {"topic": result.topic or "暂无可用主题", "module": result.module or self.subject.currentText(), "reason": result.reason, "relationship": result.relationship or "从这个主题开始，逐步建立联系。", "question": prompt.core_question, "keywords": " · ".join(prompt.search_keywords), "schedule": "\n".join(prompt.schedule)}
        for key, value in values.items(): self.fields[key].setText(value)
        self.start.setEnabled(bool(result.topic))

    def start_learning(self) -> None:
        topic = self.fields["topic"].text()
        if self.vault_path is None or not topic or topic.startswith("暂无"): return
        subject = _subject_identifier(self.vault_path, self.subject.currentIndex(), self.subject.currentText())
        try:
            config = _safe_config(self.config_path)
            provider = get_provider(config.ai_provider, model=config.model or None,
                                    base_url=config.api_base_url or None,
                                    api_protocol=config.api_protocol)
            if not provider.is_available():
                self.ai_status.setText("尚未配置可用的 AI 服务。请先到设置填写供应商、模型和 API 密钥。")
                return
            self.session = start_session(self.vault_path, subject)
        except StudyServiceError as error:
            self.ai_status.setText(f"无法开始学习：{error}")
            return
        except Exception as error:
            self.ai_status.setText(f"AI 服务不可用：{error}")
            return
        try:
            has_material = has_learning_material(self.session)
        except StudyServiceError as error:
            self.ai_status.setText(f"无法读取学习单：{error}")
            return
        if has_material:
            self.ai_status.setText("已找到这门主题的学习记录，正在继续。")
            self.topic_ready.emit(self.session.note_paths.folder)
            return
        self.start.setEnabled(False)
        self._run_ai(generate_today_material, generated_material=True, provider=provider)

    def _run_ai(self, action, *, generated_reference: bool = False,
                generated_material: bool = False, provider=None) -> None:
        if self.session is None:
            self.ai_status.setText("请先开始学习以创建学习会话。")
            return
        try:
            if provider is None:
                config = _safe_config(self.config_path)
                provider = get_provider(config.ai_provider, model=config.model or None,
                                        base_url=config.api_base_url or None,
                                        api_protocol=config.api_protocol)
            if not provider.is_available():
                self.ai_status.setText("尚未配置 AI 服务，可在设置中配置；你仍然可以继续编辑和保存笔记")
                return
        except Exception as error:
            self.ai_status.setText(f"AI 服务不可用：{error}")
            if generated_material:
                self.start.setEnabled(True)
            return
        self.review_button.setEnabled(False)
        self.reference_button.setEnabled(False)
        self.ai_status.setText("正在生成 AI 内容…")
        worker = _AIWorker(action, self.session, provider)
        worker.signals.completed.connect(self._ai_finished)
        self._workers.add(worker)
        if generated_reference:
            self._generated_references.add(worker)
        if generated_material:
            self._generated_materials.add(worker)
        self._thread_pool.start(worker)

    @Slot(object, str, bool)
    def _ai_finished(self, worker, text: str, ok: bool) -> None:
        self._workers.discard(worker)
        generated_reference = worker in self._generated_references
        generated_material = worker in self._generated_materials
        self._generated_references.discard(worker)
        self._generated_materials.discard(worker)
        self.review_button.setEnabled(True)
        self.reference_button.setEnabled(True)
        self.start.setEnabled(True)
        self.ai_completed.emit(text, ok)
        if not ok:
            self.ai_status.setText(f"AI 操作失败：{text}")
            if generated_material:
                self.start.setText("重试生成学习单  →")
            return
        if generated_material:
            self.start.setText("继续这一页  →")
            self.ai_status.setText("今日学习单已生成并保存。先阅读材料，再补充你的理解；保存后可继续交流与归档。")
            self.topic_ready.emit(self.session.note_paths.folder)
            return
        if generated_reference:
            self.ai_status.setText("AI 参考版已生成并写入笔记。")
            self.reference_ready.emit(self.session.note_paths.ai_reference)
        else:
            self.ai_status.setText("AI 已完成反馈，笔记未被修改。")
            self.ai_feedback.setPlainText(text)

    def review_pre_learning(self) -> None:
        self._run_ai(review_pre_learning)

    def generate_reference(self) -> None:
        if self.session is None:
            self.ai_status.setText("请先开始学习以创建学习会话。")
            return
        answer = QMessageBox.question(
            self,
            "生成 AI 参考版",
            "这会调用 AI 生成参考版并写入 03-AI参考版.md",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._run_ai(
            lambda session, provider: generate_ai_reference(session, provider, user_confirmed=True),
            generated_reference=True,
        )

    def archive_learning(self) -> None:
        if self.vault_path is None or self.session is None:
            self.ai_status.setText("请先开始学习并创建学习会话。")
            return
        config = _safe_config(self.config_path)
        provider = get_provider(config.ai_provider, model=config.model or None,
                                base_url=config.api_base_url or None,
                                api_protocol=config.api_protocol)
        dialog = ArchiveDialog(self, vault_path=self.vault_path, subject=self.session.subject,
                               session=self.session, provider=provider)
        dialog.archive_completed.connect(self._archive_finished)
        dialog.exec()

    @Slot()
    def _archive_finished(self) -> None:
        self.archive_button.setText("查看归档结果")
        self.archive_button.setEnabled(False)
        self.archive_completed.emit()


class MarkdownEditor(QWidget):
    dirty_changed = Signal(bool)
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent); self.config = config; self.folder = None; self.paths = []; self._loading = False; self._dirty = set()
        self.tabs = QTabWidget(); self.editors = []; self.previews = []
        for name in VERSION_NAMES:
            edit, preview, stack, wrapper = QTextEdit(), QTextBrowser(), QStackedWidget(), QWidget()
            stack.addWidget(edit); stack.addWidget(preview); mode = QComboBox(); mode.addItems(["编辑", "预览"]); mode.currentIndexChanged.connect(stack.setCurrentIndex)
            edit.setPlaceholderText("写下你对这个知识点的理解…")
            set_reading_metrics(edit)
            set_reading_metrics(preview)
            box = QVBoxLayout(wrapper); box.addWidget(mode, 0, Qt.AlignmentFlag.AlignRight); box.addWidget(stack, 1); self.tabs.addTab(wrapper, name.removesuffix(".md"))
            self.editors.append(edit); self.previews.append(preview); edit.textChanged.connect(lambda i=len(self.editors)-1: self._mark_dirty(i))
        self.save_button = primary_button("保存笔记"); self.save_button.clicked.connect(self.save_current); self.auto_save = QComboBox(); self.auto_save.addItems(["自动保存：开", "自动保存：关"]); self.auto_save.currentIndexChanged.connect(self._set_timer); self.status = QLabel("未加载文件")
        controls = QHBoxLayout(); controls.addWidget(self.save_button); controls.addWidget(self.auto_save); controls.addWidget(self.status, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(PageHeader("记录你的理解", "保留最初的观点，也看见思考的变化。"))
        self.context = meta_label("尚未加载文件")
        self.empty_state = EmptyState("未加载文件", "开始学习并打开知识点后，可在这里编辑三版笔记")
        layout.addWidget(self.context)
        layout.addWidget(self.empty_state, 1)
        layout.addWidget(self.tabs, 1)
        self.tabs.hide()
        layout.addLayout(controls)
        self.timer = QTimer(self); self.timer.timeout.connect(self.save_all); self._set_timer()

    def _set_timer(self) -> None:
        if self.auto_save.currentIndex() == 0: self.timer.start(max(1, self.config.auto_save_interval) * 1000)
        else: self.timer.stop()

    def load_topic(self, folder: Path) -> None:
        if self.is_dirty() and not self.confirm_discard(): return
        self.folder = Path(folder)
        self.context.setText(self.folder.name)
        self.empty_state.hide()
        self.tabs.show()
        files = sorted(self.folder.glob("*.md"))
        by_prefix = {path.name[:2]: path for path in files}
        self.paths = [by_prefix.get(f"0{i}", self.folder / VERSION_NAMES[i - 1]) for i in range(1, 4)]
        self._loading = True
        try:
            for i, path in enumerate(self.paths):
                try: text = path.read_text(encoding="utf-8")
                except (OSError, UnicodeError): text = ""
                self.editors[i].setPlainText(text); self.previews[i].setMarkdown(text)
            self._dirty.clear(); self.status.setText("已加载")
        finally: self._loading = False

    def load_reference_file(self, path: Path) -> None:
        if self.folder != Path(path).parent or 2 in self._dirty:
            return
        self.paths[2] = Path(path)
        try: text = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeError): return
        self._loading = True
        try:
            self.editors[2].setPlainText(text); self.previews[2].setMarkdown(text)
        finally: self._loading = False

    def _mark_dirty(self, index: int) -> None:
        if self._loading: return
        self._dirty.add(index); self.previews[index].setMarkdown(self.editors[index].toPlainText()); self.status.setText("未保存"); self.dirty_changed.emit(True)

    def is_dirty(self) -> bool: return bool(self._dirty)
    def confirm_discard(self) -> bool:
        return QMessageBox.question(self, "未保存改动", "有未保存的改动，确定放弃吗？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def save_current(self) -> bool:
        index = self.tabs.currentIndex()
        if index not in self._dirty or index >= len(self.paths): return True
        path = self.paths[index]; self.status.setText("保存中")
        try: update_note(path, self.editors[index].toPlainText())
        except Exception as error: self.status.setText(f"保存失败：{path}；{error}"); return False
        self._dirty.discard(index); self.status.setText(f"已保存于 {datetime.now().strftime('%H:%M:%S')}"); self.dirty_changed.emit(self.is_dirty()); return True

    def save_all(self) -> bool:
        return all(self._save_index(i) for i in tuple(self._dirty))
    def _save_index(self, index: int) -> bool:
        self.tabs.setCurrentIndex(index); return self.save_current()


class SettingsPage(QWidget):
    config_changed = Signal(Path)
    def __init__(self, config: AppConfig, config_path: Path | None = None, parent=None):
        super().__init__(parent); self.config_path = config_path; self.config = config
        self.path_edit = QLineEdit(str(config.vault_path) if str(config.vault_path) != "." else ""); browse = secondary_button("选择目录"); browse.clicked.connect(self.choose_vault)
        path_row = QHBoxLayout(); path_row.addWidget(self.path_edit); path_row.addWidget(browse)
        self.provider = QComboBox()
        for label, value in (("模拟服务（离线）", "mock"), ("OpenAI", "openai"),
                             ("DeepSeek", "deepseek"), ("硅基流动", "siliconflow"),
                             ("OpenRouter", "openrouter"), ("自定义中转网关", "custom"),
                             ("Claude（Anthropic 官方接口）", "anthropic")):
            self.provider.addItem(label, value)
        self.provider.setCurrentIndex(max(0, self.provider.findData(config.ai_provider)))
        self.protocol = QComboBox()
        self.protocol.addItem("OpenAI 兼容（Chat Completions）", "openai")
        self.protocol.addItem("Anthropic 兼容（Messages API）", "anthropic")
        self.protocol.setCurrentIndex(max(0, self.protocol.findData(config.api_protocol)))
        self.model = QLineEdit(config.model)
        self.api_base_url = QLineEdit(config.api_base_url)
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.interval = QSpinBox(); self.interval.setRange(1, 86400); self.interval.setValue(config.auto_save_interval)
        self.save = primary_button("保存设置"); self.test = QPushButton("测试连接"); self.message = QLabel()
        self._connection_pool = QThreadPool(self)
        self._connection_workers = set()
        self.provider.currentIndexChanged.connect(self._provider_changed)
        self.protocol.currentIndexChanged.connect(self._provider_changed)
        form = QFormLayout(); form.addRow("Vault 路径", path_row); form.addRow("AI 服务商", self.provider)
        form.addRow("中转协议", self.protocol)
        form.addRow("网关 / API 地址", self.api_base_url); form.addRow("模型名", self.model)
        form.addRow("API 密钥", self.api_key); form.addRow("自动保存间隔（秒）", self.interval)
        self.path_edit.setPlaceholderText("选择你的 Obsidian 笔记库目录")
        self.model.setPlaceholderText("输入服务商支持的模型名称")
        self.api_base_url.setPlaceholderText("选择供应商后自动填入默认网关，也可以填写兼容接口地址")
        self.api_key.setPlaceholderText("输入新密钥以更新，留空保留现有密钥")
        self.interval.setSuffix(" 秒")
        self.message.setWordWrap(True)
        self.message.setObjectName("statusLabel")
        form.setSpacing(16)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        buttons = QHBoxLayout()
        buttons.addWidget(self.save)
        buttons.addWidget(self.test)
        buttons.addStretch()
        layout = _page_body(self)
        layout.addWidget(PageHeader("偏好设置", "连接你的知识库，选择适合自己的学习工具。"))
        card = Card(margins=(24, 24, 24, 24), spacing=16)
        card.body.addWidget(SectionTitle("知识库与 AI 服务"))
        card.body.addWidget(_text("笔记保存在你选择的本地目录中。", "metaText"))
        card.body.addLayout(form)
        card.body.addLayout(buttons)
        card.body.addWidget(self.message)
        layout.addWidget(card)
        layout.addWidget(_text(f"版本 {__version__}", "metaText"))
        layout.addStretch()
        self.save.clicked.connect(self.save_settings)
        self.test.clicked.connect(self.test_connection)
        self._provider_changed()

    def _provider_changed(self) -> None:
        from ..config import OPENAI_COMPATIBLE_PROVIDERS

        provider = self.provider.currentData()
        protocol = self.protocol.currentData()
        defaults = {**OPENAI_COMPATIBLE_PROVIDERS, "anthropic": "https://api.anthropic.com"}
        previous = self.api_base_url.text().strip()
        if provider == "mock":
            self.api_base_url.setEnabled(False)
            self.api_key.setEnabled(False)
            self.api_base_url.clear()
        else:
            self.api_base_url.setEnabled(True)
            self.api_key.setEnabled(True)
            if not previous or previous in defaults.values():
                self.api_base_url.setText(defaults.get(provider, ""))
        self.protocol.setVisible(provider == "custom")
        self.api_base_url.setPlaceholderText(
            ("OpenAI 兼容地址，例如 https://gateway.example.com/v1"
             if protocol == "openai" else "Anthropic 兼容地址，例如 https://gateway.example.com")
            if provider == "custom" else "供应商 API 基础地址"
        )

    @Slot(object, str, bool)
    def _connection_finished(self, worker, message: str, ok: bool) -> None:
        self._connection_workers.discard(worker)
        self.test.setEnabled(True)
        self.test.setText("测试连接")
        self.message.setText(message if ok else f"连接失败：{message}")
        palette = self.message.palette()
        palette.setColor(QPalette.ColorRole.WindowText, theme.OK if ok else theme.DANGER)
        self.message.setPalette(palette)

    def test_connection(self) -> None:
        provider_name = self.provider.currentData()
        if provider_name == "mock":
            self.message.setText("模拟服务无需网络连接。")
            return
        try:
            provider = get_provider(
                provider_name,
                model=self.model.text().strip() or None,
                base_url=self.api_base_url.text().strip() or None,
                api_key=self.api_key.text() or None,
                api_protocol=self.protocol.currentData(),
            )
        except (TypeError, ValueError) as error:
            self.message.setText(f"配置无效：{error}")
            return
        if not provider.is_available():
            self.message.setText("请先输入 API 密钥。")
            return
        worker = _ConnectionWorker(provider)
        worker.signals.completed.connect(self._connection_finished)
        self._connection_workers.add(worker)
        self.test.setEnabled(False)
        self.test.setText("正在连接…")
        self.message.setText("正在验证网关、模型和 API 密钥…")
        self._connection_pool.start(worker)

    def choose_vault(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "选择 Vault 目录", self.path_edit.text())
        if chosen: self.path_edit.setText(chosen)

    def save_settings(self) -> None:
        config = AppConfig(
            Path(self.path_edit.text()).expanduser(), self.provider.currentData(), self.model.text(),
            self.interval.value(), self.config.custom_subjects, self.api_base_url.text().strip(),
            self.protocol.currentData(),
        )
        try:
            save_config(config, self.config_path)
            if self.api_key.text(): set_api_key(config.ai_provider, self.api_key.text())
            self.api_key.clear()
        except Exception as error:
            self.message.setText(f"保存失败：{error}")
            palette = self.message.palette()
            palette.setColor(QPalette.ColorRole.WindowText, theme.DANGER)
            self.message.setPalette(palette)
            return
        self.message.setText("设置已保存。")
        self.config = config
        palette = self.message.palette()
        palette.setColor(QPalette.ColorRole.WindowText, theme.OK)
        self.message.setPalette(palette)
        self.config_changed.emit(config.vault_path)


class ContentArea(QStackedWidget):
    def __init__(self, vault_path: Path | None = None, config_path: Path | None = None, parent=None):
        super().__init__(parent); self._index = {}; config = _safe_config(config_path)
        if vault_path is not None:
            config = AppConfig(vault_path, config.ai_provider, config.model, config.auto_save_interval,
                               config.custom_subjects, config.api_base_url, config.api_protocol)
        self.config = config
        subjects = all_subjects(config.custom_subjects)
        root = config.vault_path if config.vault_path != Path("") else None
        self.home = HomePage(root, lambda: self.show_key("today"), lambda: self.show_key("settings"), subjects, self._add_custom_subject)
        self.review = ReviewPage(root)
        self.stats = StatsPage(root)
        self.today = TodayPage(root, config_path, subjects)
        self.vault_qa = VaultQAPage(root, config)
        self.editor = MarkdownEditor(config)
        self.notes = NotesPage(root or Path("."), subjects)
        self.map = MapPage(root or Path("."), subjects); self.settings = SettingsPage(config, config_path)
        for key, page in (("home", self.home), ("today", self.today), ("review", self.review), ("stats", self.stats), ("notes", self.notes), ("vault_qa", self.vault_qa), ("map", self.map), ("settings", self.settings), ("editor", self.editor)): self._index[key] = self.addWidget(page)
        self.currentChanged.connect(self._refresh_active_page)
        self.today.topic_ready.connect(self._open_topic); self.today.reference_ready.connect(self.editor.load_reference_file); self.settings.config_changed.connect(self._vault_changed)
        self.review.reviews_changed.connect(self.home.refresh)
        self.home.subject_requested.connect(self.today.subject.setCurrentIndex)
        self.today.archive_completed.connect(self.refresh_all)

    def _add_custom_subject(self, name: str) -> None:
        custom = tuple((*self.config.custom_subjects, name))
        self.config = AppConfig(self.config.vault_path, self.config.ai_provider, self.config.model,
                                self.config.auto_save_interval, custom, self.config.api_base_url,
                                self.config.api_protocol)
        try:
            save_config(self.config, self.settings.config_path)
        except Exception as error:
            QMessageBox.warning(self.home, "设置未保存", f"学问已创建，但配置保存失败：{error}")
        self.home.set_subjects(all_subjects(custom))
        self.today.subjects = all_subjects(custom)
        self.today.subject.blockSignals(True)
        current = self.today.subject.currentText()
        self.today.subject.clear(); self.today.subject.addItems(self.today.subjects)
        self.today.subject.setCurrentText(current)
        self.today.subject.blockSignals(False)
        self.notes.set_subjects(self.today.subjects)
        self.map.set_subjects(all_subjects(custom))
        self.vault_qa.set_subjects(all_subjects(custom))
        self.settings.config = self.config
    def _open_topic(self, folder: Path) -> None:
        self.editor.load_topic(folder)
        self.show_key("editor")
    def _vault_changed(self, path: Path) -> None:
        saved = self.settings.config
        self.config = AppConfig(path, saved.ai_provider, saved.model,
                                saved.auto_save_interval, saved.custom_subjects,
                                saved.api_base_url, saved.api_protocol)
        self.home.vault_path = path; self.today.vault_path = path; self.stats.vault_path = path; self.editor.config = self.config
        self.vault_qa.vault_path = path; self.vault_qa.config = self.config
        self.settings.config = self.config
        self.notes.vault_root = path; self.map.vault_root = path; self.review.vault_path = path; self.refresh_all()
    def refresh_all(self) -> None:
        self.home.refresh(); self.today.refresh(); self.review.refresh(); self.stats.refresh(); self.notes.refresh(); self.map.refresh(); self.vault_qa.refresh()
    def show_key(self, key: str) -> None:
        if key in self._index: self.setCurrentIndex(self._index[key])

    def _refresh_active_page(self, index: int) -> None:
        page = self.widget(index)
        refresh = getattr(page, "refresh", None)
        if callable(refresh):
            refresh()
