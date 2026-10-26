from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel

from daily_knowledge_learning.models import TopicStatus
from daily_knowledge_learning.ui.map_page import MapPage
from daily_knowledge_learning.ui.notes_page import NotesPage

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "vault_minimal"


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication(["notes-map-test"])


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    shutil.copytree(FIXTURE_ROOT, root)
    return root


def test_notes_list_contains_topics_and_filters_status(app: QApplication, vault: Path) -> None:
    page = NotesPage(vault)
    labels = [page.topic_list.item(i).text() for i in range(page.topic_list.count())]
    assert any("机会成本" in label for label in labels)
    page.status_filter.setCurrentText(TopicStatus.COMPLETED.value)
    assert page.topic_list.count() == 1
    assert "机会成本" in page.topic_list.item(0).text()


def test_notes_search_filters_by_topic_and_can_be_cleared(app: QApplication, vault: Path) -> None:
    page = NotesPage(vault)
    page.search.setText("机会成本")
    assert page.topic_list.count() == 1
    assert page._visible[0].topic == "机会成本"
    assert page.result_count.text() == f"显示 1 / {len(page.records)} 个主题"
    page.search.clear()
    assert page.topic_list.count() == len(page.records)
    page.close()


def test_legacy_note_is_rendered_in_one_column(app: QApplication, vault: Path) -> None:
    page = NotesPage(vault)
    row = next(i for i, record in enumerate(page._visible) if record.topic == "工作记忆的容量限制")
    page.topic_list.setCurrentRow(row)
    assert not page.readers[0].isHidden()
    assert "工作记忆的容量限制" in page.readers[0].toPlainText()
    assert page.readers[1].isHidden()


def test_three_versions_render_and_missing_version_has_placeholder(app: QApplication, vault: Path) -> None:
    page = NotesPage(vault)
    row = next(i for i, record in enumerate(page._visible) if record.topic == "机会成本")
    page.topic_list.setCurrentRow(row)
    assert all("机会成本" in reader.toPlainText() for reader in page.readers)
    folder = vault / "经济学" / "每日记录" / "2026-09-22-机会成本"
    (folder / "02-交流后版.md").unlink()
    page.records = [
        record for record in page.records
        if record.topic != "机会成本"
    ] + [
        type(page.records[0])("经济学", "机会成本", "2026-09-22", folder, TopicStatus.IN_PROGRESS, True, ("01-交流前版.md", "03-AI参考版.md"))
    ]
    page.refresh()
    row = next(i for i, record in enumerate(page._visible) if record.topic == "机会成本")
    page.topic_list.setCurrentRow(row)
    assert "此版本尚未创建" in page.readers[1].toPlainText()


def test_readers_strip_frontmatter_and_narrow_mode_selects_one_version(app: QApplication, vault: Path) -> None:
    page = NotesPage(vault)
    page.resize(760, 480)
    page.show()
    app.processEvents()
    row = next(i for i, record in enumerate(page._visible) if record.topic == "机会成本")
    path = page._visible[row].path / "01-交流前版.md"
    path.write_text("---\ndate: 2026-09-22\nstatus: 待学习\n---\n\n# 正文标题\n\n正文内容", encoding="utf-8")
    page.topic_list.setCurrentRow(row)
    app.processEvents()
    assert "date:" not in page.readers[0].toPlainText()
    assert "正文内容" in page.readers[0].toPlainText()
    assert page.version_picker.isVisible()
    assert sum(not column.isHidden() for column in page.reader_columns) == 1
    page.close()


def test_map_displays_modules_topics_and_prerequisite(app: QApplication, vault: Path) -> None:
    (vault / "经济学" / "经济学学习路线与已学索引.md").write_text(
        "### 模块 A｜经济学基础\n\n"
        "| 顺序 | 知识点 | 核心关联 |\n| --- | --- | --- |\n"
        "| A1 | 机会成本 | 基础概念 |\n| A2 | 沉没成本 | 决策应用 |\n",
        encoding="utf-8",
    )
    page = MapPage(vault)
    page.subject_filter.setCurrentText("经济学")
    labels = [label.text() for label in page.content.findChildren(QLabel)]
    assert "经济学基础" in labels
    assert any("机会成本" in label for label in labels)
    assert "前置：机会成本" in labels


def test_map_missing_file_shows_empty_state(app: QApplication, vault: Path) -> None:
    page = MapPage(vault)
    page.subject_filter.setCurrentText("心理学")
    labels = [label.text() for label in page.content.findChildren(QLabel)]
    assert "学习地图文件缺失或格式无法识别" in labels


def test_map_subjects_can_include_custom_learning_route(app: QApplication, vault: Path) -> None:
    custom = vault / "哲学"
    custom.mkdir()
    (custom / "每日记录").mkdir()
    (custom / "哲学学习地图.md").write_text(
        "# 哲学学习地图\n\n## 学习路线\n\n"
        "| 主题 | 状态 |\n| --- | --- |\n| 苏格拉底问题 | 待学习 |\n",
        encoding="utf-8",
    )
    page = MapPage(vault, ("心理学", "经济学", "哲学"))
    page.subject_filter.setCurrentText("哲学")
    labels = [label.text() for label in page.content.findChildren(QLabel)]
    assert "苏格拉底问题" in labels
    page.close()
