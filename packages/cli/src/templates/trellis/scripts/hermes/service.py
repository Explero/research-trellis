#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from runtime import (
    JsonlRecord,
    append_record,
    make_record_id,
    now_utc,
    read_jsonl,
    record_path,
    repo_root,
    service_queue_status,
    validate_service_queue_records,
)


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def load_queue(task: str) -> tuple[Path, list[JsonlRecord], list[str]]:
    root = repo_root()
    try:
        path = record_path(root, task, "service_queue")
    except ValueError as exc:
        return Path(), [], [str(exc)]
    records, errors = read_jsonl(path)
    if errors:
        return path, records, errors
    errors.extend(validate_service_queue_records(records))
    return path, records, errors


def active_count(records: list[JsonlRecord]) -> int:
    statuses = service_queue_status(records)
    return sum(1 for status in statuses.values() if status in {"queued", "running"})


def enqueue_command(args: argparse.Namespace) -> int:
    path, records, errors = load_queue(args.task)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    max_active = args.max_active
    if active_count(records) >= max_active:
        print(f"max_active exceeded: {max_active}", file=sys.stderr)
        return 1
    record = {
        "type": "service_enqueue",
        "id": make_record_id("svc", args.job_id),
        "timestamp": now_utc(),
        "job_id": args.job_id,
        "status": "queued",
        "command": args.command,
        "max_active": max_active,
    }
    validation_errors = validate_service_queue_records(records + [JsonlRecord(len(records) + 1, record)])
    if validation_errors:
        for error in validation_errors:
            print(error, file=sys.stderr)
        return 1
    append_record(path, record)
    print(json_dump({"status": "queued", "job_id": args.job_id}))
    return 0


def status_command(args: argparse.Namespace) -> int:
    _, records, errors = load_queue(args.task)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    statuses = service_queue_status(records)
    jobs = [
        {"job_id": job_id, "status": status}
        for job_id, status in sorted(statuses.items())
    ]
    print(json_dump({"jobs": jobs, "active": sum(1 for job in jobs if job["status"] in {"queued", "running"})}))
    return 0


def cancel_command(args: argparse.Namespace) -> int:
    path, records, errors = load_queue(args.task)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    statuses = service_queue_status(records)
    if statuses.get(args.job_id) not in {"queued", "running"}:
        print(f"cannot cancel inactive service job_id {args.job_id}", file=sys.stderr)
        return 1
    record = {
        "type": "service_cancel",
        "id": make_record_id("svc-cancel", args.job_id),
        "timestamp": now_utc(),
        "job_id": args.job_id,
        "status": "cancelled",
        "reason": args.reason,
    }
    validation_errors = validate_service_queue_records(records + [JsonlRecord(len(records) + 1, record)])
    if validation_errors:
        for error in validation_errors:
            print(error, file=sys.stderr)
        return 1
    append_record(path, record)
    print(json_dump({"status": "cancelled", "job_id": args.job_id}))
    return 0


def retry_command(args: argparse.Namespace) -> int:
    path, records, errors = load_queue(args.task)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    if active_count(records) >= args.max_active:
        print(f"max_active exceeded: {args.max_active}", file=sys.stderr)
        return 1
    record = {
        "type": "service_retry",
        "id": make_record_id("svc-retry", args.job_id),
        "timestamp": now_utc(),
        "job_id": args.job_id,
        "status": "queued",
        "source_job_id": args.source_job_id,
        "command": args.command,
        "max_active": args.max_active,
    }
    validation_errors = validate_service_queue_records(records + [JsonlRecord(len(records) + 1, record)])
    if validation_errors:
        for error in validation_errors:
            print(error, file=sys.stderr)
        return 1
    append_record(path, record)
    print(json_dump({"status": "queued", "job_id": args.job_id, "source_job_id": args.source_job_id}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage a local Hermes service queue.")
    subparsers = parser.add_subparsers(dest="command_name", required=True)

    enqueue = subparsers.add_parser("enqueue")
    enqueue.add_argument("--task", required=True)
    enqueue.add_argument("--job-id", required=True)
    enqueue.add_argument("--command", required=True)
    enqueue.add_argument("--max-active", type=int, default=1)

    status = subparsers.add_parser("status")
    status.add_argument("--task", required=True)

    cancel = subparsers.add_parser("cancel")
    cancel.add_argument("--task", required=True)
    cancel.add_argument("--job-id", required=True)
    cancel.add_argument("--reason", required=True)

    retry = subparsers.add_parser("retry")
    retry.add_argument("--task", required=True)
    retry.add_argument("--job-id", required=True)
    retry.add_argument("--source-job-id", required=True)
    retry.add_argument("--command", required=True)
    retry.add_argument("--max-active", type=int, default=1)

    args = parser.parse_args()
    if getattr(args, "max_active", 1) < 1:
        print("--max-active must be a positive integer", file=sys.stderr)
        return 2
    if args.command_name == "enqueue":
        return enqueue_command(args)
    if args.command_name == "status":
        return status_command(args)
    if args.command_name == "cancel":
        return cancel_command(args)
    if args.command_name == "retry":
        return retry_command(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
