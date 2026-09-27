from __future__ import annotations

import argparse
from pathlib import Path

from .vault_scan import scan_vault


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan an Obsidian learning Vault.")
    parser.add_argument(
        "vault",
        type=Path,
        help="Obsidian Vault root, for example C:/Users/name/Documents/Obsidian Vault",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    records = scan_vault(args.vault)
    if not records:
        print("没有发现支持的学习记录。")
        return 0
    for record in records:
        print(f"{record.subject} | {record.date} | {record.topic} | {record.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
