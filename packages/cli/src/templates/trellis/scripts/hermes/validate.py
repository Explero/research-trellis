#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from runtime import record_path, repo_root, validate_records


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Hermes JSONL records.")
    parser.add_argument("--task", required=True)
    parser.add_argument("--kind", required=True)
    args = parser.parse_args()

    root = repo_root()
    try:
        path = record_path(root, args.task, args.kind)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    errors = validate_records(path, args.kind)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"valid {path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

