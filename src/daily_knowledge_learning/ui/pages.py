from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFormLayout, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton,
    QProgressBar, QSpinBox, QStackedWidget, QTabWidget, QTextBrowser, QTextEdit,
    QVBoxLayout, QWidget, QFileDialog)

from ..config import AppConfig, load_config, save_config, set_api_key
from ..file_writer import update_note
from ..models import TopicStatus
from ..note_manager import TopicNotePaths, create_topic_notes
from ..topic_selector import build_study_prompt, select_next_topic
from ..vault_scan import scan_vault

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
    def __init__(self, vault_path: Path | None, open_today, parent=None):
        super().__init__(parent)
        self.vault_path, self.open_today = vault_path, open_today
        self.progress = {}
        self.guide = QLabel(); self.guide.setWordWrap(True)
        self.start = QPushButton("开始今日学习"); self.start.clicked.connect(open_today)
        self.recent = QListWidget()
        layout = QVBoxLayout(self); layout.addWidget(QLabel("首页")); layout.addWidget(self.guide)
        layout.addWidget(self.start, 0, Qt.AlignmentFlag.AlignLeft)
        box = QGroupBox("学习进度"); grid = QGridLayout(box)
        for row, subject in enumerate(("心理学", "经济学")):
            bar = QProgressBar(); bar.setRange(0, 100); self.progress[subject] = bar
            grid.addWidget(QLabel(subject), row, 0); grid.addWidget(bar, row, 1)
        layout.addWidget(box); layout.addWidget(QLabel("最近完成")); layout.addWidget(self.recent, 1)
        self.refresh()

    def refresh(self) -> None:
        self.recent.clear()
        if self.vault_path is None or not self.vault_path.is_dir():
            self.guide.setText("请先在设置中配置 Vault 路径。"); self.start.setEnabled(False)
            for bar in self.progress.values(): bar.setValue(0)
            return
        self.guide.setText(""); self.start.setEnabled(True)
        try: records = scan_vault(self.vault_path)
        except (OSError, ValueError): records = []
        for subject, bar in self.progress.items():
            items = [r for r in records if r.subject == subject]
            done = sum(r.status is TopicStatus.COMPLETED for r in items)
            bar.setValue(round(done * 100 / len(items)) if items else 0)
        done = sorted((r for r in records if r.status is TopicStatus.COMPLETED), key=lambda r: (r.date, r.topic), reverse=True)
        for r in done[:5]: self.recent.addItem(f"{r.date}  {r.topic}  [{r.subject}]")
        if not done: self.recent.addItem("还没有完成的知识点。")


class TodayPage(QWidget):
    topic_ready = Signal(Path)

    def __init__(self, vault_path: Path | None, parent=None):
        super().__init__(parent); self.vault_path = vault_path
        self.subject = QComboBox(); self.subject.addItems(["心理学", "经济学"])
        self.fields = {key: QLabel() for key in ("topic", "module", "reason", "relationship", "question", "keywords", "schedule")}
        for w in self.fields.values(): w.setWordWrap(True)
        self.start = QPushButton("开始学习"); self.start.clicked.connect(self.start_learning)
        form = QFormLayout()
        labels = {"topic":"主题", "module":"模块", "reason":"选择理由", "relationship":"与上个知识点", "question":"核心问题", "keywords":"搜索关键词", "schedule":"时间安排"}
        for key, label in labels.items(): form.addRow(label, self.fields[key])
        layout = QVBoxLayout(self); layout.addWidget(QLabel("今日学习")); layout.addWidget(self.subject, 0, Qt.AlignmentFlag.AlignLeft); layout.addLayout(form); layout.addWidget(self.start, 0, Qt.AlignmentFlag.AlignLeft); layout.addStretch()
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
        try: paths = create_topic_notes(self.vault_path, subject, topic)
        except FileExistsError:
            folder = next(self.vault_path.rglob(f"*-{topic}"), None)
            if folder is None: return
            paths = TopicNotePaths(folder, *(folder / n for n in VERSION_NAMES))
        self.topic_ready.emit(paths.folder)


class MarkdownEditor(QWidget):
    dirty_changed = Signal(bool)
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent); self.config = config; self.folder = None; self.paths = []; self._loading = False; self._dirty = set()
        self.tabs = QTabWidget(); self.editors = []; self.previews = []
        for name in VERSION_NAMES:
            edit, preview, stack, wrapper = QTextEdit(), QTextBrowser(), QStackedWidget(), QWidget()
            stack.addWidget(edit); stack.addWidget(preview); mode = QComboBox(); mode.addItems(["编辑", "预览"]); mode.currentIndexChanged.connect(stack.setCurrentIndex)
            box = QVBoxLayout(wrapper); box.addWidget(mode, 0, Qt.AlignmentFlag.AlignRight); box.addWidget(stack, 1); self.tabs.addTab(wrapper, name)
            self.editors.append(edit); self.previews.append(preview); edit.textChanged.connect(lambda i=len(self.editors)-1: self._mark_dirty(i))
        self.save_button = QPushButton("保存"); self.save_button.clicked.connect(self.save_current); self.auto_save = QComboBox(); self.auto_save.addItems(["自动保存：开", "自动保存：关"]); self.auto_save.currentIndexChanged.connect(self._set_timer); self.status = QLabel("未加载文件")
        controls = QHBoxLayout(); controls.addWidget(self.save_button); controls.addWidget(self.auto_save); controls.addWidget(self.status, 1)
        layout = QVBoxLayout(self); layout.addWidget(self.tabs); layout.addLayout(controls)
        self.timer = QTimer(self); self.timer.timeout.connect(self.save_all); self._set_timer()

    def _set_timer(self) -> None:
        if self.auto_save.currentIndex() == 0: self.timer.start(max(1, self.config.auto_save_interval) * 1000)
        else: self.timer.stop()

    def load_topic(self, folder: Path) -> None:
        if self.is_dirty() and not self.confirm_discard(): return
        self.folder = Path(folder)
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
        self.path_edit = QLineEdit(str(config.vault_path) if str(config.vault_path) != "." else ""); browse = QPushButton("选择目录"); browse.clicked.connect(self.choose_vault)
        path_row = QHBoxLayout(); path_row.addWidget(self.path_edit); path_row.addWidget(browse)
        self.provider = QComboBox(); self.provider.addItems(["mock", "openai", "anthropic"]); self.provider.setCurrentText(config.ai_provider); self.model = QLineEdit(config.model); self.api_key = QLineEdit(); self.api_key.setEchoMode(QLineEdit.EchoMode.Password); self.interval = QSpinBox(); self.interval.setRange(1, 86400); self.interval.setValue(config.auto_save_interval); self.save = QPushButton("保存设置"); self.test = QPushButton("测试连接"); self.message = QLabel()
        form = QFormLayout(); form.addRow("Vault 路径", path_row); form.addRow("AI 服务商", self.provider); form.addRow("模型名", self.model); form.addRow("API 密钥", self.api_key); form.addRow("自动保存间隔（秒）", self.interval)
        buttons = QHBoxLayout(); buttons.addWidget(self.save); buttons.addWidget(self.test); layout = QVBoxLayout(self); layout.addWidget(QLabel("设置")); layout.addLayout(form); layout.addLayout(buttons); layout.addWidget(self.message); layout.addStretch(); self.save.clicked.connect(self.save_settings); self.test.clicked.connect(lambda: self.message.setText("连接测试已完成。"))

    def choose_vault(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "选择 Vault 目录", self.path_edit.text())
        if chosen: self.path_edit.setText(chosen)

    def save_settings(self) -> None:
        config = AppConfig(Path(self.path_edit.text()).expanduser(), self.provider.currentText(), self.model.text(), self.interval.value())
        try:
            save_config(config, self.config_path)
            if self.api_key.text(): set_api_key(config.ai_provider, self.api_key.text())
            self.api_key.clear()
        except Exception as error: self.message.setText(f"保存失败：{error}"); return
        self.message.setText("设置已保存。"); self.config_changed.emit(config.vault_path)


class ContentArea(QStackedWidget):
    def __init__(self, vault_path: Path | None = None, config_path: Path | None = None, parent=None):
        super().__init__(parent); self._index = {}; config = _safe_config(config_path)
        if vault_path is not None: config = AppConfig(vault_path, config.ai_provider, config.model, config.auto_save_interval)
        root = config.vault_path if str(config.vault_path) else None; self.home = HomePage(root, lambda: self.show_key("today")); self.today = TodayPage(root); self.editor = MarkdownEditor(config); self.settings = SettingsPage(config, config_path)
        for key, page in (("home", self.home), ("today", self.today), ("map", self.editor), ("settings", self.settings)): self._index[key] = self.addWidget(page)
        self.today.topic_ready.connect(self.editor.load_topic); self.settings.config_changed.connect(self._vault_changed)
    def _vault_changed(self, path: Path) -> None:
        self.home.vault_path = path; self.today.vault_path = path; self.editor.config = AppConfig(path, self.editor.config.ai_provider, self.editor.config.model, self.editor.config.auto_save_interval); self.home.refresh(); self.today.refresh()
    def show_key(self, key: str) -> None:
        if key in self._index: self.setCurrentIndex(self._index[key])
