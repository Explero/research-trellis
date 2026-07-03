#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from runtime import (
    ensure_run_manifest,
    ensure_worker_records,
    experiment_path,
    repo_root,
    run_manifest_path,
    validate_experiment_config,
    worker_records_path,
    write_experiment_skeleton,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Hermes experiment config.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--task", required=True)
    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--task", required=True)

    args = parser.parse_args()

    root = repo_root()
    try:
        exp_path = experiment_path(root, args.task)
        manifest_path = run_manifest_path(root, args.task)
        worker_path = worker_records_path(root, args.task)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.command == "init":
        write_experiment_skeleton(exp_path, args.task)
        ensure_run_manifest(manifest_path)
        ensure_worker_records(worker_path)
        print(f"experiment config: {exp_path.relative_to(root)}")
        print(f"run manifest: {manifest_path.relative_to(root)}")
        print(f"worker records: {worker_path.relative_to(root)}")
        return 0

    if args.command == "validate":
        errors = validate_experiment_config(exp_path)
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1

        print(f"valid {exp_path.relative_to(root)}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
