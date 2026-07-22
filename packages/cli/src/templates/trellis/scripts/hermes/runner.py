#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from runtime import (
    add_seconds,
    append_record,
    find_task_card,
    format_timestamp,
    make_record_id,
    now_utc,
    normalize_path,
    parse_interval_seconds,
    parse_timestamp,
    read_jsonl,
    record_path,
    repo_root,
    experiment_path,
    load_experiment_config,
    run_manifest_path,
    task_card_error,
    validate_experiment_config,
    validate_data_preflight,
    validate_run_manifest_records,
)


def relative_to_root(root: Path, path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
    except ValueError:
        return path.as_posix()


def command_after_separator(argv: list[str]) -> list[str]:
    if argv and argv[0] == "--":
        return argv[1:]
    return argv


def load_worker(task: str, job_id: str) -> tuple[Path, Path, dict[str, Any], list[str]]:
    root = repo_root()
    try:
        path = record_path(root, task, "worker")
    except ValueError as exc:
        return root, Path(), {}, [str(exc)]
    records, errors = read_jsonl(path)
    if errors:
        return root, path, {}, errors
    error = task_card_error(records, job_id)
    if error is not None:
        return root, path, {}, [error]
    card = find_task_card(records, job_id)
    if card is None:
        return root, path, {}, [f"missing task_card for job_id {job_id}"]
    return root, path, card, []


def next_check(timestamp: str, interval_seconds: int) -> str:
    return add_seconds(timestamp, interval_seconds) or now_utc()


def heartbeat_record(
    job_id: str,
    checkpoint: str,
    summary: str,
    interval_seconds: int,
) -> dict[str, Any]:
    timestamp = now_utc()
    return {
        "type": "heartbeat",
        "id": make_record_id("hb", job_id),
        "timestamp": timestamp,
        "job_id": job_id,
        "status": "running",
        "checkpoint": checkpoint,
        "summary": summary,
        "next_check_at": next_check(timestamp, interval_seconds),
    }


def checkpoint_record(
    args: argparse.Namespace,
    parent_job_id: Any = None,
    *,
    has_parent_field: bool = False,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "type": "checkpoint",
        "id": make_record_id("cp", args.job_id),
        "timestamp": now_utc(),
        "job_id": args.job_id,
        "checkpoint": args.checkpoint,
        "resume_from": args.resume_from,
        "evidence_refs": [],
        "open_items": [],
    }
    if has_parent_field:
        record["parent_job_id"] = parent_job_id
    return record


def result_record(
    args: argparse.Namespace,
    manifest_id: str,
    outputs: list[str],
    parent_job_id: Any = None,
    *,
    has_parent_field: bool = False,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "type": "result",
        "id": make_record_id("rs", args.job_id),
        "timestamp": now_utc(),
        "job_id": args.job_id,
        "status": "done",
        "summary": args.summary,
        "changed_files": outputs,
        "evidence_refs": [manifest_id],
        "risk_flags": [],
        "handoff": f"run manifest {manifest_id}",
    }
    if has_parent_field:
        record["parent_job_id"] = parent_job_id
    return record


def rejection_record(
    args: argparse.Namespace,
    manifest_id: str,
    exit_code: int,
    stderr_path: str,
) -> dict[str, Any]:
    return {
        "type": "rejection",
        "id": make_record_id("rj", args.job_id),
        "timestamp": now_utc(),
        "job_id": args.job_id,
        "rejected_record_id": manifest_id,
        "reason": "runner_command_failed",
        "required_fix": (
            f"inspect {stderr_path}; resume from {args.resume_from}; "
            f"exit_code={exit_code}"
        ),
    }


def split_values(values: list[str] | None) -> list[str]:
    if not values:
        return []
    return [value for value in values if value]


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def path_entry(root: Path, cwd: Path, value: str, kind: str) -> dict[str, Any]:
    candidate = Path(value)
    resolved = candidate if candidate.is_absolute() else cwd / candidate
    entry: dict[str, Any] = {
        "path": relative_to_root(root, resolved),
        "kind": kind,
    }
    file_hash = sha256_file(resolved)
    if file_hash is not None:
        entry["hash"] = file_hash
        entry["bytes"] = resolved.stat().st_size
    return entry


def env_summary() -> dict[str, str]:
    return {
        "python": sys.version.split()[0],
        "platform": sys.platform,
    }


def command_display(command: list[str]) -> str:
    return " ".join(command)


def command_allowed(command: list[str], allowed_commands: Any) -> bool:
    if not command or not isinstance(allowed_commands, list):
        return False
    executable = Path(command[0]).name
    full = command_display(command)
    for allowed in allowed_commands:
        if not isinstance(allowed, str):
            continue
        text = allowed.strip()
        if not text:
            continue
        if text == command[0] or text == executable:
            return True
        if full == text or full.startswith(text + " "):
            return True
    return False


def redact_secret_text(value: str) -> str:
    secret_name_pattern = re.compile(
        r"\b[A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE_KEY|API_KEY|ACCESS_KEY)[A-Z0-9_]*\b"
    )
    return secret_name_pattern.sub("[redacted-secret-env]", value)


def manifest_command(command: list[str]) -> list[str]:
    return [redact_secret_text(part) for part in command]


def resolve_repo_path(root: Path, base: Path, value: str, label: str) -> tuple[Path | None, str | None]:
    raw = value.strip()
    if not raw:
        return None, f"{label} path must be non-empty"
    candidate = Path(raw)
    resolved = candidate if candidate.is_absolute() else base / candidate
    resolved = resolved.resolve(strict=False)
    try:
        resolved.relative_to(root.resolve(strict=False))
    except ValueError:
        if label == "cwd":
            return None, f"cwd must stay inside repository: {value}"
        return None, f"{label} path must stay inside repository: {value}"
    return resolved, None


def validate_paths_inside_repo(
    root: Path,
    cwd: Path,
    values: list[str],
    label: str,
) -> list[str]:
    errors: list[str] = []
    for value in values:
        _, error = resolve_repo_path(root, cwd, value, label)
        if error is not None:
            errors.append(error)
    return errors


def run_command(args: argparse.Namespace) -> int:
    task = args.task
    job_id = args.job_id
    command = command_after_separator(args.command)
    if not command:
        print("runner run requires a command after --", file=sys.stderr)
        return 2

    root, worker_path, task_card, errors = load_worker(task, job_id)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    exp_path = experiment_path(root, task)
    experiment_errors = validate_experiment_config(exp_path)
    if experiment_errors:
        for error in experiment_errors:
            print(error, file=sys.stderr)
        return 1
    experiment, experiment_load_errors = load_experiment_config(exp_path)
    if experiment_load_errors:
        for error in experiment_load_errors:
            print(error, file=sys.stderr)
        return 1
    if not command_allowed(command, experiment.get("allowed_commands")):
        print(
            f"command not allowed by experiment allowed_commands: {command_display(command)}",
            file=sys.stderr,
        )
        return 1

    interval_text = args.heartbeat_interval or str(task_card.get("heartbeat_interval", "5m"))
    interval_seconds = parse_interval_seconds(interval_text)
    if interval_seconds is None:
        print("invalid --heartbeat-interval; use values like 30s, 5m, or 1h", file=sys.stderr)
        return 2

    if args.cwd is None:
        cwd = root
    else:
        cwd, cwd_error = resolve_repo_path(root, root, args.cwd, "cwd")
        if cwd_error is not None or cwd is None:
            print(cwd_error or "cwd must stay inside repository", file=sys.stderr)
            return 2
    if not cwd.is_dir():
        print(f"cwd is not readable: {cwd}", file=sys.stderr)
        return 2
    outputs = split_values(args.output)
    inputs = split_values(args.input)
    path_errors = validate_paths_inside_repo(root, cwd, inputs, "input")
    path_errors.extend(validate_paths_inside_repo(root, cwd, outputs, "output"))
    if path_errors:
        for error in path_errors:
            print(error, file=sys.stderr)
        return 2
    preflight_paths, preflight_errors = validate_data_preflight(exp_path, experiment)
    if preflight_errors:
        for error in preflight_errors:
            print(error, file=sys.stderr)
        return 1
    declared_inputs = {
        resolved
        for value in inputs
        for resolved, error in [resolve_repo_path(root, cwd, value, "input")]
        if error is None and resolved is not None
    }
    missing_preflight_inputs = [
        path.relative_to(root).as_posix()
        for path in preflight_paths
        if path not in declared_inputs
    ]
    if missing_preflight_inputs:
        print(
            "data_preflight files must be declared with --input: "
            + ", ".join(missing_preflight_inputs),
            file=sys.stderr,
        )
        return 1
    # Snapshot declared input hashes before process launch. The command may
    # legitimately transform an input later, but the manifest must preserve
    # the exact pre-run material it received.
    input_entries = [path_entry(root, cwd, value, "input") for value in inputs]
    hermes_dir = worker_path.parent
    runs_dir = hermes_dir / "runs"
    run_id = make_record_id("run", job_id)
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"
    started_at = now_utc()
    has_parent_field = "parent_job_id" in task_card
    parent_job_id = task_card.get("parent_job_id")
    append_record(
        worker_path,
        checkpoint_record(
            args,
            parent_job_id,
            has_parent_field=has_parent_field,
        ),
    )
    append_record(worker_path, heartbeat_record(args.job_id, args.checkpoint, args.summary, interval_seconds))
    last_heartbeat = time.monotonic()
    launch_error: OSError | None = None

    with stdout_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
        try:
            process = subprocess.Popen(
                command,
                cwd=str(cwd),
                stdout=stdout_handle,
                stderr=stderr_handle,
            )
        except OSError as exc:
            launch_error = exc
            stderr_handle.write(f"cannot start command: {exc}\n".encode("utf-8"))
            exit_code = 127
        else:
            while process.poll() is None:
                now = time.monotonic()
                if now - last_heartbeat >= interval_seconds:
                    append_record(
                        worker_path,
                        heartbeat_record(args.job_id, args.checkpoint, args.summary, interval_seconds),
                    )
                    last_heartbeat = now
                time.sleep(min(0.1, max(interval_seconds / 10, 0.01)))
            exit_code = int(process.returncode or 0)

    finished_at = now_utc()

    output_entries = [path_entry(root, cwd, value, "artifact") for value in outputs]
    log_entries = [
        path_entry(root, root, relative_to_root(root, stdout_path), "stdout"),
        path_entry(root, root, relative_to_root(root, stderr_path), "stderr"),
    ]
    manifest_record = {
        "id": run_id,
        "job_id": args.job_id,
        "command": manifest_command(command),
        "cwd": relative_to_root(root, cwd),
        "env_summary": env_summary(),
        "inputs": input_entries,
        "outputs": output_entries + log_entries,
        "exit_code": exit_code,
        "started_at": started_at,
        "finished_at": finished_at,
        "checkpoint": args.checkpoint,
        "resume_from": args.resume_from,
    }
    if launch_error is not None:
        manifest_record["error"] = f"cannot start command: {launch_error}"
    manifest_path = run_manifest_path(root, task)
    append_record(manifest_path, manifest_record)

    if exit_code == 0:
        append_record(
            worker_path,
            result_record(
                args,
                run_id,
                [entry["path"] for entry in output_entries],
                parent_job_id,
                has_parent_field=has_parent_field,
            ),
        )
    else:
        append_record(
            worker_path,
            rejection_record(args, run_id, exit_code, relative_to_root(root, stderr_path)),
        )

    print(f"run manifest appended to {manifest_path.relative_to(root)}")
    return exit_code


def load_manifest_records(task: str) -> tuple[Path, list[Any], list[str]]:
    root = repo_root()
    try:
        path = run_manifest_path(root, task)
    except ValueError as exc:
        return root, [], [str(exc)]
    records, errors = read_jsonl(path)
    if errors:
        return root, records, errors
    validation_errors = validate_run_manifest_records(path, records)
    return root, records, validation_errors


def resolve_manifest_output_path(root: Path, cwd: str, value: str) -> Path | None:
    normalized = normalize_path(value)
    if normalized is None:
        candidate = Path(value)
        return candidate if candidate.is_absolute() else None
    root_candidate = (root / normalized).resolve(strict=False)
    if root_candidate.is_file():
        return root_candidate
    cwd_path = Path(cwd)
    cwd_root = cwd_path if cwd_path.is_absolute() else root / cwd_path
    return (cwd_root / normalized).resolve(strict=False)


def replay_output_errors(root: Path, record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    cwd = record.get("cwd")
    if not isinstance(cwd, str) or not cwd.strip():
        return ["run manifest cwd must be a non-empty string"]
    outputs = record.get("outputs")
    if not isinstance(outputs, list):
        return ["run manifest outputs must be a list"]
    for output in outputs:
        if not isinstance(output, dict):
            errors.append("output entry must be an object with path and hash")
            continue
        output_path = output.get("path")
        if not isinstance(output_path, str) or not output_path.strip():
            errors.append("output path must be a non-empty string")
            continue
        resolved = resolve_manifest_output_path(root, cwd, output_path)
        if resolved is None or not resolved.is_file():
            errors.append(f"output path is not readable: {output_path}")
            continue
        expected_hash = output.get("hash")
        if not isinstance(expected_hash, str) or not expected_hash.strip():
            errors.append(f"output hash is required: {output_path}")
            continue
        digest = expected_hash.removeprefix("sha256:")
        if (
            digest == expected_hash
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            errors.append(f"output hash is invalid: {output_path}")
            continue
        actual_hash = sha256_file(resolved)
        if actual_hash != expected_hash:
            errors.append(
                f"output hash mismatch: {output_path} expected {expected_hash} got {actual_hash}"
            )
    return errors


def replay(args: argparse.Namespace) -> int:
    task = args.task
    root, records, errors = load_manifest_records(task)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    for entry in records:
        if entry.value.get("id") == args.run_id:
            replay_errors = replay_output_errors(root, entry.value)
            if replay_errors:
                for error in replay_errors:
                    print(error, file=sys.stderr)
                return 1
            print(json.dumps({"status": "replayable", "run_id": args.run_id}, separators=(",", ":")))
            return 0
    print(f"missing run_id {args.run_id}", file=sys.stderr)
    return 1


def add_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--resume-from", default="run manifest")
    parser.add_argument("--heartbeat-interval")
    parser.add_argument("--cwd")
    parser.add_argument("--input", action="append")
    parser.add_argument("--output", action="append")
    parser.add_argument("command", nargs=argparse.REMAINDER)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Hermes commands with heartbeats and manifests.")
    subparsers = parser.add_subparsers(dest="command_name", required=True)
    run_parser = subparsers.add_parser("run")
    add_run_arguments(run_parser)
    replay_parser = subparsers.add_parser("replay")
    replay_parser.add_argument("--task", required=True)
    replay_parser.add_argument("--run-id", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--task", required=True)

    args = parser.parse_args()
    if args.command_name == "run":
        return run_command(args)
    if args.command_name == "replay":
        return replay(args)
    if args.command_name == "validate":
        root = repo_root()
        task = args.task
        path = run_manifest_path(root, task)
        records, errors = read_jsonl(path)
        errors.extend(validate_run_manifest_records(path, records))
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print(f"valid {path.relative_to(root)}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
