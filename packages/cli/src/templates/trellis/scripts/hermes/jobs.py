#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from runtime import (
    add_seconds,
    append_record,
    latest_record,
    make_record_id,
    now_utc,
    parse_interval_seconds,
    parse_timestamp,
    read_jsonl,
    record_path,
    repo_root,
    validate_worker_records,
)


def resume_point(
    job_id: str,
    task_card: dict[str, Any],
    checkpoint: dict[str, Any] | None,
) -> dict[str, Any]:
    if checkpoint is not None:
        return {
            "job_id": job_id,
            "checkpoint": checkpoint.get("checkpoint", "unknown"),
            "resume_from": checkpoint.get("resume_from", "checkpoint"),
            "source": "checkpoint",
            "open_items": checkpoint.get("open_items", []),
        }
    return {
        "job_id": job_id,
        "checkpoint": task_card.get("checkpoint", "not-started"),
        "resume_from": task_card.get("resume_from", "task_card"),
        "source": "task_card",
        "open_items": [],
    }


def build_timeout_rejection(
    job_id: str,
    task_card: dict[str, Any],
    checkpoint: dict[str, Any] | None,
    reason: str,
) -> dict[str, Any]:
    resume_from = "task_card"
    if checkpoint and isinstance(checkpoint.get("resume_from"), str):
        resume_from = checkpoint["resume_from"]
    return {
        "type": "rejection",
        "id": make_record_id("rj", reason),
        "timestamp": now_utc(),
        "job_id": job_id,
        "rejected_record_id": task_card.get("id", ""),
        "reason": reason,
        "required_fix": f"resume from {resume_from}",
    }


def build_stalled_record(
    job_id: str,
    task_card: dict[str, Any],
    checkpoint: dict[str, Any] | None,
    reason: str,
) -> dict[str, Any]:
    point = resume_point(job_id, task_card, checkpoint)
    return {
        "type": "stalled",
        "id": make_record_id("st", reason),
        "timestamp": now_utc(),
        "job_id": job_id,
        "reason": reason,
        "checkpoint": point["checkpoint"],
        "resume_from": point["resume_from"],
        "required_fix": f"resume from {point['resume_from']}",
        "source": point["source"],
    }


def expected_next_check(
    task_card: dict[str, Any],
    heartbeat: dict[str, Any] | None,
) -> Any:
    if heartbeat is not None:
        return parse_timestamp(heartbeat.get("next_check_at"))
    interval_seconds = parse_interval_seconds(task_card.get("heartbeat_interval"))
    timestamp = task_card.get("timestamp")
    if interval_seconds is None or not isinstance(timestamp, str):
        return None
    expected = add_seconds(timestamp, interval_seconds)
    return parse_timestamp(expected)


def load_worker_records(task: str) -> tuple[Any, Any, list[str]]:
    root = repo_root()
    try:
        path = record_path(root, task, "worker")
    except ValueError as exc:
        return root, None, [str(exc)]
    records, errors = read_jsonl(path)
    if errors:
        return root, None, errors
    validation_errors = validate_worker_records(records)
    if validation_errors:
        return root, None, validation_errors
    return root, (path, records), []


def check_jobs(args: argparse.Namespace) -> int:
    _, loaded, errors = load_worker_records(args.task)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    path, records = loaded

    now = parse_timestamp(args.now) if args.now else parse_timestamp(now_utc())
    if now is None:
        print("invalid --now timestamp", file=sys.stderr)
        return 2

    stalled: list[str] = []
    for entry in records:
        value = entry.value
        if value.get("type") != "task_card":
            continue
        job_id = value.get("job_id")
        if not isinstance(job_id, str):
            continue
        if latest_record(records, job_id, "result") is not None:
            continue
        if latest_record(records, job_id, "rejection") is not None:
            continue
        if latest_record(records, job_id, "stalled") is not None:
            continue

        timeout_at = parse_timestamp(value.get("timeout_at"))
        reason: str | None = None
        if timeout_at is not None and timeout_at <= now:
            reason = "timeout"
        else:
            heartbeat = latest_record(records, job_id, "heartbeat")
            next_check = expected_next_check(value, heartbeat)
            if next_check is not None and next_check <= now:
                reason = "heartbeat_timeout"

        if reason is not None:
            checkpoint = latest_record(records, job_id, "checkpoint")
            rejection = build_timeout_rejection(job_id, value, checkpoint, reason)
            stalled_record = build_stalled_record(job_id, value, checkpoint, reason)
            try:
                append_record(path, rejection)
                append_record(path, stalled_record)
            except OSError as exc:
                print(f"cannot append stalled record: {exc}", file=sys.stderr)
                return 1
            stalled.append(job_id)

    if stalled:
        print(f"stalled jobs: {', '.join(stalled)}", file=sys.stderr)
        return 1

    print("no stalled jobs")
    return 0


def show_resume(args: argparse.Namespace) -> int:
    _, loaded, errors = load_worker_records(args.task)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    _, records = loaded
    task_card = None
    for entry in records:
        value = entry.value
        if value.get("type") == "task_card" and value.get("job_id") == args.job_id:
            task_card = value
            break
    if task_card is None:
        print(f"missing task_card for job_id {args.job_id}", file=sys.stderr)
        return 1
    checkpoint = latest_record(records, args.job_id, "checkpoint")
    print(json.dumps(resume_point(args.job_id, task_card, checkpoint), separators=(",", ":")))
    return 0


def show_status(args: argparse.Namespace) -> int:
    _, loaded, errors = load_worker_records(args.task)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    _, records = loaded
    jobs: list[dict[str, Any]] = []
    for entry in records:
        value = entry.value
        if value.get("type") != "task_card":
            continue
        job_id = value.get("job_id")
        if not isinstance(job_id, str):
            continue
        checkpoint = latest_record(records, job_id, "checkpoint")
        status = "running"
        result = latest_record(records, job_id, "result")
        rejection = latest_record(records, job_id, "rejection")
        stalled = latest_record(records, job_id, "stalled")
        if result is not None:
            status = str(result.get("status", "done"))
        elif stalled is not None:
            status = "stalled"
        elif rejection is not None:
            status = "rejected"
        point = resume_point(job_id, value, checkpoint)
        jobs.append({**point, "status": status})
    print(json.dumps({"jobs": jobs}, separators=(",", ":")))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect Hermes worker jobs.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--task", required=True)
    check_parser.add_argument("--now", required=False)
    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("--task", required=True)
    resume_parser.add_argument("--job-id", required=True)
    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--task", required=True)
    args = parser.parse_args()

    if args.command == "check":
        return check_jobs(args)
    if args.command == "resume":
        return show_resume(args)
    if args.command == "status":
        return show_status(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
