#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from runtime import (
    find_task_card,
    permission_errors,
    read_jsonl,
    record_path,
    repo_root,
    task_card_error,
)


def split_files(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Hermes worker file permissions.")
    parser.add_argument("--task", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--changed-files", required=True)
    args = parser.parse_args()

    root = repo_root()
    try:
        path = record_path(root, args.task, "worker")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    records, errors = read_jsonl(path)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    card_error = task_card_error(records, args.job_id)
    if card_error is not None:
        print(card_error, file=sys.stderr)
        return 1
    task_card = find_task_card(records, args.job_id)
    if task_card is None:
        print(f"missing task_card for job_id {args.job_id}", file=sys.stderr)
        return 1

    failures = permission_errors(task_card, split_files(args.changed_files))
    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print("allowed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
