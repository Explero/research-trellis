#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time
from typing import Any

from runtime import (
    add_seconds,
    append_record,
    find_task_card,
    format_timestamp,
    make_record_id,
    now_utc,
    parse_interval_seconds,
    parse_timestamp,
    read_jsonl,
    record_path,
    repo_root,
    task_card_error,
)


def next_check_at(timestamp: str, interval_seconds: int) -> str:
    calculated = add_seconds(timestamp, interval_seconds)
    return calculated or now_utc()


def load_task_card(task: str, job_id: str) -> tuple[Any, Any, Any]:
    root = repo_root()
    try:
        path = record_path(root, task, "worker")
    except ValueError as exc:
        return root, None, str(exc)

    records, errors = read_jsonl(path)
    if errors:
        return root, None, "\n".join(errors)

    error = task_card_error(records, job_id)
    if error is not None:
        return root, None, error
    task_card = find_task_card(records, job_id)
    if task_card is None:
        return root, None, f"missing task_card for job_id {job_id}"
    return root, (path, task_card), None


def build_record(args: argparse.Namespace, task_card: dict[str, Any]) -> dict[str, Any]:
    timestamp = args.now or now_utc()
    parsed_timestamp = parse_timestamp(timestamp)
    if parsed_timestamp is None:
        raise ValueError("invalid --now timestamp")
    timestamp = format_timestamp(parsed_timestamp)
    interval = args.interval or str(task_card.get("heartbeat_interval", "5m"))
    interval_seconds = parse_interval_seconds(interval)
    next_check = args.next_check_at
    if next_check is not None and parse_timestamp(next_check) is None:
        raise ValueError("invalid --next-check-at timestamp")
    if next_check is None and interval_seconds is not None:
        next_check = next_check_at(timestamp, interval_seconds)
    if next_check is None:
        next_check = str(task_card.get("timeout_at", timestamp))
    record = {
        "type": "heartbeat",
        "id": make_record_id("hb", args.job_id),
        "timestamp": timestamp,
        "job_id": args.job_id,
        "status": args.status,
        "checkpoint": args.checkpoint,
        "summary": args.summary,
        "next_check_at": next_check,
    }
    return record


def append_heartbeat(args: argparse.Namespace) -> int:
    root, loaded, error = load_task_card(args.task, args.job_id)
    if error is not None:
        print(error, file=sys.stderr)
        return 2 if "not allowed" in error or "required" in error else 1

    path, task_card = loaded
    try:
        record = build_record(args, task_card)
        append_record(path, record)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"cannot append heartbeat: {exc}", file=sys.stderr)
        return 1
    print(f"heartbeat appended to {path.relative_to(root)}")
    return 0


def watch(args: argparse.Namespace) -> int:
    root, loaded, error = load_task_card(args.task, args.job_id)
    if error is not None:
        print(error, file=sys.stderr)
        return 2 if "not allowed" in error or "required" in error else 1

    path, task_card = loaded
    interval = args.interval or str(task_card.get("heartbeat_interval", "5m"))
    interval_seconds = parse_interval_seconds(interval)
    if interval_seconds is None:
        print("invalid --interval; use values like 30s, 5m, or 1h", file=sys.stderr)
        return 2

    count = 0
    while args.count == 0 or count < args.count:
        try:
            record = build_record(args, task_card)
            append_record(path, record)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        except OSError as exc:
            print(f"cannot append heartbeat: {exc}", file=sys.stderr)
            return 1
        print(f"heartbeat appended to {path.relative_to(root)}")
        count += 1
        if args.count != 0 and count >= args.count:
            break
        time.sleep(interval_seconds)
    return 0


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--status", default="running")
    parser.add_argument("--interval")
    parser.add_argument("--next-check-at")
    parser.add_argument("--now")


def main() -> int:
    parser = argparse.ArgumentParser(description="Append Hermes heartbeat records.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    beat_parser = subparsers.add_parser("beat")
    add_common_arguments(beat_parser)

    watch_parser = subparsers.add_parser("watch")
    add_common_arguments(watch_parser)
    watch_parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="number of heartbeats to write; 0 runs until interrupted",
    )

    args = parser.parse_args()
    if args.command == "beat":
        return append_heartbeat(args)
    if args.command == "watch":
        return watch(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
