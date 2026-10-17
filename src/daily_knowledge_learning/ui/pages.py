"""Right-hand content pages, one per navigation entry.

Every page is a placeholder for now — this task only validates that the UI
skeleton runs and switches correctly.  The Markdown sample deliberately
exercises ``QTextEdit.setMarkdown`` so the tech-choice write-up can report
what actually renders.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# One Markdown sample that covers the constructs the app will really show:
# headings, bold/italic, lists, inline code, a fenced code block and a table.
MARKDOWN_SAMPLE = """# 机会成本

**机会成本**是指为了得到某种东西而所要放弃的另一些东西的最大价值。

## 要点

- 决策依据是*被放弃的最佳选项*，不是账面支出
- 沉没成本不参与决策
- 边际分析看的是"再多一单位"的得失

## 示例

```python
def opportunity_cost(chosen, alternatives):
    return max(alternatives, key=lambda a: a.value).value
```

| 选项 | 收益 | 机会成本 |
| --- | --- | --- |
| 读研 | 学历提升 | 两年工资 |
| 工作 | 经验 + 收入 | 学历提升 |
"""

PLACEHOLDER_TEXT: dict[str, tuple[str, str]] = {
    "home": (
        "首页",
        "这里将展示：今日学习入口、连续学习天数、近期待复习知识点。\n\n（占位内容，UI 骨架验证用）",
    ),
    "today": (
        "今日学习",
        "这里将展示：今天的知识点正文、交流记录输入框、AI 参考版对照。\n\n（占位内容，UI 骨架验证用）",
    ),
    "map": (
        "学习地图",
        "这里将展示：心理学 / 经济学知识点树、掌握度标记、旧版本待学习记录。\n\n（占位内容，UI 骨架验证用）",
    ),
    "settings": (
        "设置",
        "这里将展示：Obsidian Vault 路径、API Key 安全存储、同步与备份选项。\n\n（占位内容，UI 骨架验证用）",
    ),
}


class PlaceholderPage(QWidget):
    """A simple titled placeholder page."""

    def __init__(self, title: str, body: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        heading = QLabel(title)
        heading.setObjectName("pageHeading")
        layout.addWidget(heading)

        text = QLabel(body)
        text.setObjectName("pageBody")
        text.setWordWrap(True)
        text.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(text, 1)


class MarkdownPreviewPage(QWidget):
    """Placeholder page that renders Markdown via ``QTextEdit.setMarkdown``."""

    def __init__(self, title: str, markdown: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        heading = QLabel(title)
        heading.setObjectName("pageHeading")
        layout.addWidget(heading)

        self.viewer = QTextEdit()
        self.viewer.setObjectName("markdownViewer")
        self.viewer.setReadOnly(True)
        self.viewer.setMarkdown(markdown)
        layout.addWidget(self.viewer, 1)


class ContentArea(QStackedWidget):
    """Swaps pages as the sidebar selection changes."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("contentArea")
        self._index: dict[str, int] = {}

        for key, (title, body) in PLACEHOLDER_TEXT.items():
            page = PlaceholderPage(title, body)
            self._index[key] = self.addWidget(page)

        preview_title, preview_body = PLACEHOLDER_TEXT["home"]
        preview = MarkdownPreviewPage(
            f"{preview_title} · Markdown 渲染验证", MARKDOWN_SAMPLE
        )
        self._index["_markdown_preview"] = self.addWidget(preview)

    def show_key(self, key: str) -> None:
        index = self._index.get(key)
        if index is None:
            return
        self.setCurrentIndex(index)
