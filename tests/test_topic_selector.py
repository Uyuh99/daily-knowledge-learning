from pathlib import Path
import shutil

from daily_knowledge_learning.map_parser import StudyMap, parse_learning_map
from daily_knowledge_learning.models import TopicStatus
from daily_knowledge_learning.topic_selector import build_study_prompt, select_next_topic


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "vault_minimal"
SUBJECT = "经济学"


def _copy_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    shutil.copytree(FIXTURE_ROOT, root)
    return root


def _set_status(root: Path, topic: str, status: str) -> None:
    note = root / SUBJECT / "每日记录" / f"2026-09-26-{topic}" / "02-交流后版.md"
    note.write_text(f"---\nstatus: {status}\n---\n", encoding="utf-8")


def test_in_progress_topic_takes_priority_over_route() -> None:
    result = select_next_topic(FIXTURE_ROOT, SUBJECT)

    assert result.topic == "沉没成本"
    assert result.module == "经济学的思维工具"
    assert "继续" in result.reason


def test_route_order_and_vault_status_override_index_description(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    _set_status(root, "沉没成本", "已完成")
    index = root / SUBJECT / "经济学学习路线与已学索引.md"
    index.write_text(index.read_text(encoding="utf-8").replace("| A3 | 边际分析 | 分析额外一单位的收益与成本 | 待学习 |", "| A3 | 边际分析 | 分析额外一单位的收益与成本 | 已完成 |"), encoding="utf-8")

    result = select_next_topic(root, SUBJECT)
    prompt = build_study_prompt(result)

    assert result.topic == "边际分析"
    assert result.module == "经济学的思维工具"
    assert result.previous_topic == "沉没成本"
    assert "边际分析" in prompt.core_question
    assert len(prompt.search_keywords) == 3
    assert len(prompt.schedule) == 3
    assert "答案" not in prompt.core_question


def test_unmet_prerequisites_defer_existing_topic(tmp_path: Path) -> None:
    root = _copy_fixture(tmp_path)
    _set_status(root, "沉没成本", "已完成")
    deferred = root / SUBJECT / "每日记录" / "2026-09-27-比较优势"
    deferred.mkdir()
    (deferred / "02-交流后版.md").write_text("---\nstatus: 暂缓\n---\n", encoding="utf-8")

    result = select_next_topic(root, SUBJECT)

    assert result.topic == "边际分析"
    assert any(item.topic == "比较优势" for item in result.deferred)
    assert "前置知识尚未完成" in next(item.reason for item in result.deferred if item.topic == "比较优势")


def test_missing_or_malformed_map_returns_empty_and_selection_does_not_crash(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    (root / SUBJECT).mkdir(parents=True)

    assert parse_learning_map(root, SUBJECT) == StudyMap()
    assert select_next_topic(root, SUBJECT).topic is None

    map_path = root / SUBJECT / "经济学学习路线与已学索引.md"
    map_path.write_bytes(b"\xff\xfe invalid encoding")
    assert parse_learning_map(root, SUBJECT) == StudyMap()
    assert select_next_topic(root, SUBJECT).topic is None


def test_unrecognized_map_format_returns_empty(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    subject_root = root / SUBJECT
    subject_root.mkdir(parents=True)
    (subject_root / "经济学学习路线与已学索引.md").write_text("# New unsupported layout\nNo route table", encoding="utf-8")

    assert parse_learning_map(root, SUBJECT) == StudyMap()


def test_psychology_map_table_is_parsed(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    subject_root = root / "心理学"
    subject_root.mkdir(parents=True)
    (subject_root / "心理学学习地图与进度.md").write_text(
        "## 当前模块：认知心理学\n\n"
        "| 顺序 | 知识点 | 与前一节点的关系 |\n"
        "| --- | --- | --- |\n"
        "| 1 | 工作记忆 | 信息的短时保持与操作 |\n"
        "| 2 | 注意控制 | 选择加工哪些信息 |\n",
        encoding="utf-8",
    )

    study_map = parse_learning_map(root, "心理学")

    assert len(study_map.modules) == 1
    assert study_map.modules[0].name == "认知心理学"
    assert [topic.name for topic in study_map.modules[0].topics] == ["工作记忆", "注意控制"]
    assert study_map.modules[0].topics[1].prerequisites == ("工作记忆",)
