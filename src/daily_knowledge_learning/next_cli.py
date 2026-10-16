from __future__ import annotations

import argparse
from pathlib import Path

from .topic_selector import build_study_prompt, select_next_topic


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Select and prepare today's study topic.")
    parser.add_argument("--vault", required=True, type=Path, help="Obsidian Vault or learning project root")
    parser.add_argument("--subject", required=True, choices=("经济学", "心理学"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = select_next_topic(args.vault, args.subject)
    if result.topic is None:
        print(result.reason)
        for item in result.deferred:
            print(f"暂缓：{item.topic}（{item.reason}）")
        return 1

    prompt = build_study_prompt(result)
    print(f"今日主题：{prompt.topic}")
    print(f"所属模块：{result.module or '未分类'}")
    print(f"选择理由：{result.reason}")
    print(f"与上一个知识点的关系：{prompt.relationship}")
    print(f"核心问题：{prompt.core_question}")
    print("搜索关键词：" + "；".join(prompt.search_keywords))
    print("时间安排：" + "；".join(prompt.schedule))
    for item in result.deferred:
        print(f"暂缓：{item.topic}（{item.reason}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
