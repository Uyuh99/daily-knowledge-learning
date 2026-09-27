from pathlib import Path

from daily_knowledge_learning.models import TopicStatus
from daily_knowledge_learning.vault_scan import scan_subject, scan_vault


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "vault_minimal"


def test_opportunity_cost_is_completed_only_with_explicit_status() -> None:
    records = scan_subject(FIXTURE_ROOT / "经济学", "经济学")

    opportunity_cost = next(item for item in records if item.topic == "机会成本")

    assert opportunity_cost.status is TopicStatus.COMPLETED
    assert opportunity_cost.has_folder is True
    assert set(opportunity_cost.versions) == {
        "01-交流前版.md",
        "02-交流后版.md",
        "03-AI参考版.md",
    }


def test_sunk_cost_is_in_progress_even_when_after_version_has_text() -> None:
    records = scan_subject(FIXTURE_ROOT / "经济学", "经济学")

    sunk_cost = next(item for item in records if item.topic == "沉没成本")

    assert sunk_cost.status is TopicStatus.IN_PROGRESS


def test_legacy_single_note_is_retained_as_to_learn() -> None:
    records = scan_subject(FIXTURE_ROOT / "经济学", "经济学")

    legacy = next(item for item in records if item.topic == "边际分析")

    assert legacy.status is TopicStatus.TO_LEARN
    assert legacy.has_folder is False
    assert legacy.path.name == "2026-09-23-边际分析.md"


def test_scan_vault_supports_both_subjects() -> None:
    records = scan_vault(FIXTURE_ROOT)

    assert {record.subject for record in records} == {"经济学", "心理学"}
