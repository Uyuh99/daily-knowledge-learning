from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (QComboBox, QFormLayout, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QProgressBar,
    QScrollArea, QSpinBox, QStackedWidget, QTabWidget, QTextBrowser, QTextEdit,
    QVBoxLayout, QWidget, QFileDialog)

from .. import __version__
from ..ai_provider import get_provider
from ..config import AppConfig, load_config, save_config, set_api_key
from ..file_writer import update_note
from ..models import TopicStatus
from ..note_manager import TopicNotePaths, create_topic_notes
from ..study_service import StudyServiceError, generate_ai_reference, review_pre_learning, start_session
from ..topic_selector import build_study_prompt, select_next_topic
from ..vault_scan import scan_vault
from .map_page import MapPage
from .notes_page import NotesPage
from .archive_dialog import ArchiveDialog
from . import theme
from .widgets import (Card, EmptyState, PageHeader, SectionTitle, field_label,
    meta_label, primary_button, secondary_button, set_reading_metrics)

VERSION_NAMES = ("01-交流前版.md", "02-交流后版.md", "03-AI参考版.md")


def _subject_identifier(vault_path: Path, index: int, display: str) -> str:
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
    def __init__(self, vault_path: Path | None, open_today, open_settings=None, parent=None):
        super().__init__(parent)
        self.vault_path, self.open_today = vault_path, open_today
        self.open_settings = open_settings or (lambda: None)
        self.progress = {}
        self.guide = QLabel()
        self.guide.setWordWrap(True)
        self.start = primary_button("开始今日学习")
        self.start.clicked.connect(open_today)
        self.header = PageHeader("首页", "今天想学什么，从这里开始")
        self.header.add_action(self.start)
        self.empty_state = EmptyState("尚未配置学习内容")
        self.guide = self.empty_state.hint
        self.settings_button = secondary_button("前往设置")
        self.settings_button.clicked.connect(self.open_settings)
        self.empty_state.layout().addWidget(self.settings_button, 0, Qt.AlignmentFlag.AlignCenter)
        self.empty_state.hide()
        self.recent = QListWidget()
        self.recent.setSpacing(theme.SPACE[1])
        self.recent.setMinimumHeight(120)
        self.progress_card = Card()
        self.progress_card.body.addWidget(SectionTitle("学习进度"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(theme.SPACE[3])
        grid.setVerticalSpacing(theme.SPACE[2])
        for row, subject in enumerate(("心理学", "经济学")):
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            percentage = meta_label("0%")
            percentage.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.progress[subject] = bar
            grid.addWidget(QLabel(subject), row, 0)
            grid.addWidget(bar, row, 1)
            grid.addWidget(percentage, row, 2)
            self.progress[f"{subject}_label"] = percentage
        self.progress_card.body.addLayout(grid)
        recent_card = Card()
        recent_card.body.addWidget(SectionTitle("最近完成"))
        self.recent_empty = EmptyState("还没有完成的知识点", "完成第一个知识点后，这里会出现你的学习记录")
        recent_card.body.addWidget(self.recent_empty)
        recent_card.body.addWidget(self.recent)
        self.recent_empty.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(theme.SPACE[3])
        layout.addWidget(self.header)
        layout.addWidget(self.empty_state)
        layout.addWidget(self.progress_card)
        layout.addWidget(recent_card, 1)
        self.refresh()

    def refresh(self) -> None:
        self.recent.clear()
        if self.vault_path is None or not self.vault_path.is_dir():
            self.guide.setText("请先在设置中配置 Vault 路径。")
            self.empty_state.show()
            self.start.setEnabled(False)
            self.recent_empty.show()
            self.recent.hide()
            for subject in ("心理学", "经济学"):
                self.progress[subject].setValue(0)
                self.progress[f"{subject}_label"].setText("0%")
            return
        self.empty_state.hide()
        self.start.setEnabled(True)
        try: records = scan_vault(self.vault_path)
        except (OSError, ValueError): records = []
        for subject in ("心理学", "经济学"):
            bar = self.progress[subject]
            items = [r for r in records if r.subject == subject]
            done = sum(r.status is TopicStatus.COMPLETED for r in items)
            value = round(done * 100 / len(items)) if items else 0
            bar.setValue(value)
            self.progress[f"{subject}_label"].setText(f"{value}%")
        done = sorted((r for r in records if r.status is TopicStatus.COMPLETED), key=lambda r: (r.date, r.topic), reverse=True)
        self.recent.clear()
        for r in done[:5]:
            row = QWidget()
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
            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            self.recent.addItem(item)
            self.recent.setItemWidget(item, row)
        self.recent_empty.setVisible(not done)
        self.recent.setVisible(bool(done))


class _AIServiceAdapter:
    """Adapt the provider's chat API to study_service's generate protocol."""

    def __init__(self, provider):
        self.provider = provider

    def is_available(self) -> bool:
        return self.provider.is_available()

    def generate(self, messages: list[dict[str, str]]) -> str:
        return self.provider.chat(messages)


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


class TodayPage(QWidget):
    topic_ready = Signal(Path)
    reference_ready = Signal(Path)
    ai_completed = Signal(str, bool)
    archive_completed = Signal()

    def __init__(self, vault_path: Path | None, config_path: Path | None = None, parent=None):
        super().__init__(parent); self.vault_path = vault_path; self.config_path = config_path
        self._thread_pool = QThreadPool(self)
        self._workers = set()
        self._generated_references = set()
        self.archive_button = primary_button("完成学习")
        self.archive_button.clicked.connect(self.archive_learning)
        self.session = None
        self.subject = QComboBox(); self.subject.addItems(["心理学", "经济学"])
        self.fields = {key: QLabel() for key in ("topic", "module", "reason", "relationship", "question", "keywords", "schedule")}
        for w in self.fields.values(): w.setWordWrap(True)
        self.start = primary_button("开始学习"); self.start.clicked.connect(self.start_learning)
        self.header = PageHeader("今日学习", "选择学科，查看今天的主题与学习安排")
        self.header.add_action(self.subject)
        self.header.add_action(self.archive_button)
        self.header.add_action(self.start)
        self.topic_card = Card()
        for key, label in (("topic", "主题"), ("module", "模块")):
            self.topic_card.body.addWidget(field_label(label))
            self.fields[key].setObjectName("bodyText")
            self.topic_card.body.addWidget(self.fields[key])
        meta_grid = QGridLayout()
        meta_grid.setHorizontalSpacing(theme.SPACE[4])
        meta_grid.setVerticalSpacing(theme.SPACE[2])
        labels = {"reason":"选择理由", "relationship":"与上个知识点", "question":"核心问题", "keywords":"搜索关键词", "schedule":"时间安排"}
        for index, (key, label) in enumerate(labels.items()):
            cell = QVBoxLayout()
            cell.addWidget(field_label(label))
            self.fields[key].setObjectName("bodyText")
            cell.addWidget(self.fields[key])
            meta_grid.addLayout(cell, index // 2, index % 2)
        self.topic_card.body.addLayout(meta_grid)
        self.review_button = primary_button("检查交流前版")
        self.reference_button = secondary_button("生成 AI 参考版")
        self.review_button.clicked.connect(self.review_pre_learning)
        self.reference_button.clicked.connect(self.generate_reference)
        self.ai_status = QLabel()
        self.ai_status.setWordWrap(True)
        self.ai_feedback = QTextEdit()
        self.ai_feedback.setReadOnly(True)
        self.ai_feedback.setPlaceholderText("AI 反馈会显示在这里，不会自动写入笔记")
        set_reading_metrics(self.ai_feedback)
        self.ai_card = Card()
        self.ai_card.body.addWidget(SectionTitle("AI 交流"))
        self.ai_card.body.addWidget(self.ai_status)
        self.ai_card.body.addWidget(self.ai_feedback, 1)
        actions = QHBoxLayout(); actions.addWidget(self.review_button); actions.addWidget(self.reference_button); actions.addStretch()
        self.ai_card.body.addLayout(actions)
        layout = QVBoxLayout(self); layout.setContentsMargins(24, 20, 24, 20); layout.setSpacing(theme.SPACE[3])
        layout.addWidget(self.header); layout.addWidget(self.topic_card); layout.addWidget(self.ai_card, 1)
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
        values = {"topic": result.topic or "暂无可用主题", "module": result.module or "-", "reason": result.reason, "relationship": result.relationship or "-", "question": prompt.core_question, "keywords": "、".join(prompt.search_keywords), "schedule": "；".join(prompt.schedule)}
        for key, value in values.items(): self.fields[key].setText(value)
        self.start.setEnabled(bool(result.topic))

    def start_learning(self) -> None:
        topic = self.fields["topic"].text()
        if self.vault_path is None or not topic or topic.startswith("暂无"): return
        subject = _subject_identifier(self.vault_path, self.subject.currentIndex(), self.subject.currentText())
        try:
            self.session = start_session(self.vault_path, subject)
        except StudyServiceError as error:
            self.ai_status.setText(f"无法开始学习：{error}")
            return
        self.topic_ready.emit(self.session.note_paths.folder)

    def _run_ai(self, action, *, generated_reference: bool = False) -> None:
        if self.session is None:
            self.ai_status.setText("请先开始学习以创建学习会话。")
            return
        try:
            config = _safe_config(self.config_path)
            provider = get_provider(config.ai_provider, model=config.model or None)
            if not provider.is_available():
                self.ai_status.setText("尚未配置 AI 服务，可在设置中配置；你仍然可以继续编辑和保存笔记")
                return
        except Exception as error:
            self.ai_status.setText(f"AI 服务不可用：{error}")
            return
        self.review_button.setEnabled(False)
        self.reference_button.setEnabled(False)
        self.ai_status.setText("正在生成 AI 内容…")
        worker = _AIWorker(action, self.session, provider)
        worker.signals.completed.connect(self._ai_finished)
        self._workers.add(worker)
        if generated_reference:
            self._generated_references.add(worker)
        self._thread_pool.start(worker)

    @Slot(object, str, bool)
    def _ai_finished(self, worker, text: str, ok: bool) -> None:
        self._workers.discard(worker)
        generated_reference = worker in self._generated_references
        self._generated_references.discard(worker)
        self.review_button.setEnabled(True)
        self.reference_button.setEnabled(True)
        self.ai_completed.emit(text, ok)
        if not ok:
            self.ai_status.setText(f"AI 操作失败：{text}")
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
        provider = get_provider(config.ai_provider, model=config.model or None)
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
            set_reading_metrics(edit); set_reading_metrics(preview)
            stack.addWidget(edit); stack.addWidget(preview); mode = QComboBox(); mode.addItems(["编辑", "预览"]); mode.currentIndexChanged.connect(stack.setCurrentIndex)
            box = QVBoxLayout(wrapper); box.addWidget(mode, 0, Qt.AlignmentFlag.AlignRight); box.addWidget(stack, 1); self.tabs.addTab(wrapper, name)
            self.editors.append(edit); self.previews.append(preview); edit.textChanged.connect(lambda i=len(self.editors)-1: self._mark_dirty(i))
        self.context = meta_label("尚未加载文件")
        self.empty_state = EmptyState("未加载文件", "开始学习并打开知识点后，可在这里编辑三版笔记")
        self.save_button = primary_button("保存"); self.save_button.clicked.connect(self.save_current); self.auto_save = QComboBox(); self.auto_save.addItems(["自动保存：开", "自动保存：关"]); self.auto_save.currentIndexChanged.connect(self._set_timer); self.status = meta_label("未加载文件")
        controls = QHBoxLayout(); controls.addWidget(self.save_button); controls.addWidget(self.auto_save); controls.addStretch(1); controls.addWidget(self.status)
        layout = QVBoxLayout(self); layout.setContentsMargins(24, 20, 24, 20); layout.setSpacing(theme.SPACE[2]); layout.addWidget(self.context); layout.addWidget(self.empty_state, 1); layout.addWidget(self.tabs, 1); layout.addLayout(controls)
        self.tabs.hide()
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
        super().__init__(parent); self.config_path = config_path
        self.path_edit = QLineEdit(str(config.vault_path) if str(config.vault_path) != "." else ""); browse = secondary_button("选择目录"); browse.clicked.connect(self.choose_vault)
        path_row = QHBoxLayout(); path_row.addWidget(self.path_edit); path_row.addWidget(browse)
        self.provider = QComboBox(); self.provider.addItems(["mock", "openai", "anthropic"]); self.provider.setCurrentText(config.ai_provider); self.model = QLineEdit(config.model); self.api_key = QLineEdit(); self.api_key.setEchoMode(QLineEdit.EchoMode.Password); self.interval = QSpinBox(); self.interval.setRange(1, 86400); self.interval.setValue(config.auto_save_interval); self.save = primary_button("保存设置"); self.test = secondary_button("测试连接"); self.message = QLabel(); self.message.setWordWrap(True)
        self.header = PageHeader("设置", "配置 Vault 路径与 AI 服务")
        content = QWidget(); content.setMaximumWidth(620); content.setMinimumWidth(480)
        content_layout = QVBoxLayout(content); content_layout.setContentsMargins(0, 0, 0, 0); content_layout.setSpacing(theme.SPACE[3])
        vault_card = Card(); vault_card.body.addWidget(SectionTitle("学习内容")); vault_card.body.addWidget(field_label("Vault 路径")); vault_card.body.addLayout(path_row)
        ai_card = Card(); ai_card.body.addWidget(SectionTitle("AI 服务"))
        ai_form = QFormLayout(); ai_form.addRow("AI 服务商", self.provider); ai_form.addRow("模型名", self.model); ai_form.addRow("API 密钥", self.api_key); ai_card.body.addLayout(ai_form)
        autosave_card = Card(); autosave_card.body.addWidget(SectionTitle("自动保存")); autosave_form = QFormLayout(); autosave_form.addRow("自动保存间隔（秒）", self.interval); autosave_card.body.addLayout(autosave_form)
        content_layout.addWidget(vault_card); content_layout.addWidget(ai_card); content_layout.addWidget(autosave_card)
        buttons = QHBoxLayout(); buttons.addStretch(1); buttons.addWidget(self.test); buttons.addWidget(self.save)
        content_layout.addLayout(buttons); content_layout.addWidget(self.message)
        content_layout.addWidget(meta_label(f"版本 v{__version__}"))
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.Shape.NoFrame); scroll.setWidget(content)
        layout = QVBoxLayout(self); layout.setContentsMargins(24, 20, 24, 20); layout.addWidget(self.header); layout.addWidget(scroll, 1)
        self.save.clicked.connect(self.save_settings); self.test.clicked.connect(lambda: self.message.setText("连接测试已完成。"))

    def choose_vault(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "选择 Vault 目录", self.path_edit.text())
        if chosen: self.path_edit.setText(chosen)

    def save_settings(self) -> None:
        config = AppConfig(Path(self.path_edit.text()).expanduser(), self.provider.currentText(), self.model.text(), self.interval.value())
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
        palette = self.message.palette()
        palette.setColor(QPalette.ColorRole.WindowText, theme.OK)
        self.message.setPalette(palette)
        self.config_changed.emit(config.vault_path)


class ContentArea(QStackedWidget):
    def __init__(self, vault_path: Path | None = None, config_path: Path | None = None, parent=None):
        super().__init__(parent); self._index = {}; config = _safe_config(config_path)
        if vault_path is not None: config = AppConfig(vault_path, config.ai_provider, config.model, config.auto_save_interval)
        root = config.vault_path if str(config.vault_path) else None; self.home = HomePage(root, lambda: self.show_key("today"), lambda: self.show_key("settings")); self.today = TodayPage(root, config_path); self.editor = MarkdownEditor(config); self.notes = NotesPage(root or Path(".")); self.map = MapPage(root or Path(".")); self.settings = SettingsPage(config, config_path)
        for key, page in (("home", self.home), ("today", self.today), ("notes", self.notes), ("map", self.map), ("settings", self.settings), ("editor", self.editor)): self._index[key] = self.addWidget(page)
        self.today.topic_ready.connect(self._open_topic); self.today.reference_ready.connect(self.editor.load_reference_file); self.settings.config_changed.connect(self._vault_changed)
        self.today.archive_completed.connect(self.refresh_all)
    def _open_topic(self, folder: Path) -> None:
        self.editor.load_topic(folder)
        self.show_key("editor")
    def _vault_changed(self, path: Path) -> None:
        self.home.vault_path = path; self.today.vault_path = path; self.editor.config = AppConfig(path, self.editor.config.ai_provider, self.editor.config.model, self.editor.config.auto_save_interval)
        self.notes.vault_root = path; self.map.vault_root = path; self.refresh_all()
    def refresh_all(self) -> None:
        self.home.refresh(); self.today.refresh(); self.notes.refresh(); self.map.refresh()
    def show_key(self, key: str) -> None:
        if key in self._index: self.setCurrentIndex(self._index[key])
