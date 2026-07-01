#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from runtime import append_record, record_path, repo_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Append Hermes JSONL records.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    append_parser = subparsers.add_parser("append")
    append_parser.add_argument("--task", required=True)
    append_parser.add_argument("--record-type", required=True)
    append_parser.add_argument("--json", required=True)

    args = parser.parse_args()
    root = repo_root()

    try:
        record = json.loads(args.json)
    except json.JSONDecodeError as exc:
        print(f"invalid JSON: {exc.msg}", file=sys.stderr)
        return 2
    if not isinstance(record, dict):
        print("record must be a JSON object", file=sys.stderr)
        return 2

    try:
        path = record_path(root, args.task, args.record_type)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        append_record(path, record)
    except OSError as exc:
        print(f"cannot append record: {exc}", file=sys.stderr)
        return 1
    print(f"appended {record.get('type', 'record')} to {path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
