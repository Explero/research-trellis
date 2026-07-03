#!/usr/bin/env python3
"""Hermes runtime guard hook.

This hook delegates validation and timeout checks to `.trellis/scripts/hermes/`
so platform hooks stay adapters instead of becoming the source of truth.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


WRITE_TOOL_NAMES = {"Edit", "Write", "MultiEdit", "apply_patch", "Bash"}


def find_trellis_root(start: Path) -> Path | None:
    current = start.resolve()
    while current != current.parent:
        if (current / ".trellis").is_dir():
            return current
        current = current.parent
    return None


def detect_platform(input_data: dict[str, Any]) -> str | None:
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        return "claude"
    script_name = sys.argv[0]
    script_parts = Path(script_name).parts
    if os.environ.get("CODEX_PROJECT_DIR") or ".codex" in script_parts:
        return "codex"
    if ".claude" in script_parts:
        return "claude"
    return None


def resolve_active_task(root: Path, input_data: dict[str, Any]) -> str | None:
    scripts_dir = root / ".trellis" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from common.active_task import resolve_active_task as resolve  # type: ignore[import-not-found]
    except Exception:
        return None

    active = resolve(root, input_data, platform=detect_platform(input_data))
    if not active.task_path:
        return None
    task_path = Path(active.task_path)
    if task_path.is_absolute():
        return task_path.name
    return task_path.name


def run_runtime(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )


def block_payload(event_name: str, reason: str) -> dict[str, Any]:
    if event_name in {"Stop", "SubagentStop"}:
        return {"decision": "block", "reason": reason}
    return {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": reason,
        }
    }


def deny_tool_payload(event_name: str, reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def context_payload(event_name: str, context: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": context,
        }
    }


def validate_worker_records(root: Path, runtime_root: Path, task: str) -> str | None:
    validate = run_runtime(
        root,
        [str(runtime_root / "validate.py"), "--task", task, "--kind", "worker"],
    )
    if validate.returncode != 0:
        return validate.stderr.strip() or "Hermes worker records are invalid."

    jobs = run_runtime(
        root,
        [str(runtime_root / "jobs.py"), "check", "--task", task],
    )
    if jobs.returncode != 0:
        return jobs.stderr.strip() or "Hermes worker job is stalled."
    return None


def missing_worker_records_reason(worker_records: Path) -> str:
    return (
        "Hermes Runtime: active task has no worker_records.jsonl at "
        f"{worker_records.as_posix()}; denying by default until a unique "
        "task_card is recorded."
    )


def read_worker_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                value = json.loads(line)
                if isinstance(value, dict):
                    records.append(value)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return []
    return records


def has_task_card(records: list[dict[str, Any]]) -> bool:
    return any(record.get("type") == "task_card" for record in records)


def normalize_target_path(root: Path, raw_path: str) -> str | None:
    text = raw_path.strip().replace("\\", "/")
    if not text:
        return None
    path = Path(text)
    if path.is_absolute():
        try:
            return path.resolve(strict=False).relative_to(root).as_posix()
        except ValueError:
            return text
    while text.startswith("./"):
        text = text[2:]
    return text or None


def add_unique_target(targets: list[str], root: Path, raw_path: str) -> None:
    normalized = normalize_target_path(root, raw_path)
    if normalized and normalized not in targets:
        targets.append(normalized)


def extract_patch_targets(root: Path, patch_text: str) -> list[str]:
    targets: list[str] = []
    prefixes = (
        "*** Add File: ",
        "*** Update File: ",
        "*** Delete File: ",
        "*** Move to: ",
    )
    for line in patch_text.splitlines():
        for prefix in prefixes:
            if line.startswith(prefix):
                add_unique_target(targets, root, line[len(prefix) :])
    return targets


def collect_tool_target_files(
    root: Path,
    tool_name: str,
    value: Any,
    key: str | None = None,
) -> list[str]:
    targets: list[str] = []
    path_keys = {
        "file",
        "file_path",
        "filename",
        "new_path",
        "old_path",
        "path",
        "target_file",
        "target_path",
    }
    patch_keys = {"content", "input", "patch"}
    if isinstance(value, dict):
        for nested_key, nested_value in value.items():
            for target in collect_tool_target_files(
                root,
                tool_name,
                nested_value,
                str(nested_key),
            ):
                if target not in targets:
                    targets.append(target)
    elif isinstance(value, list):
        for item in value:
            for target in collect_tool_target_files(root, tool_name, item, key):
                if target not in targets:
                    targets.append(target)
    elif isinstance(value, str):
        normalized_key = (key or "").lower()
        if normalized_key in path_keys:
            add_unique_target(targets, root, value)
        if tool_name == "apply_patch" and normalized_key in patch_keys:
            for target in extract_patch_targets(root, value):
                if target not in targets:
                    targets.append(target)
    return targets


def bash_command_from_tool_input(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("command", "cmd", "script"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        for nested in value.values():
            candidate = bash_command_from_tool_input(nested)
            if candidate:
                return candidate
    if isinstance(value, list):
        for item in value:
            candidate = bash_command_from_tool_input(item)
            if candidate:
                return candidate
    return None


def looks_like_bash_write(command: str) -> bool:
    write_markers = (
        ">",
        "tee ",
        "write_text",
        "write_bytes",
        ".write(",
        "open(",
        "Path(",
        "touch ",
        "mkdir ",
        "rm ",
        "mv ",
        "cp ",
        "sed -i",
        "perl -pi",
        "cat <<",
    )
    return any(marker in command for marker in write_markers)


def add_bash_target(targets: list[str], root: Path, value: str) -> None:
    if value in {"-", "/dev/null"}:
        return
    if value.startswith("&"):
        return
    add_unique_target(targets, root, value)


def extract_bash_targets(root: Path, command: str) -> tuple[list[str], str | None]:
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError as exc:
        return [], f"cannot safely parse Bash write targets: {exc}"

    targets: list[str] = []
    redirect_tokens = {">", ">>", "1>", "1>>", "2>", "2>>", "&>", "&>>", ">|"}
    redirect_prefix = re.compile(r"^(?:\d?>{1,2}|&>{1,2}|\|>)(.+)$")
    write_like_but_unparsed = False

    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in redirect_tokens:
            if index + 1 >= len(tokens):
                return targets, "cannot safely parse Bash write targets: missing redirect target"
            add_bash_target(targets, root, tokens[index + 1])
            index += 2
            continue
        match = redirect_prefix.match(token)
        if match:
            add_bash_target(targets, root, match.group(1))
            index += 1
            continue
        if token == "tee":
            tee_index = index + 1
            while tee_index < len(tokens) and tokens[tee_index].startswith("-"):
                tee_index += 1
            if tee_index >= len(tokens):
                return targets, "cannot safely parse Bash write targets: missing tee target"
            add_bash_target(targets, root, tokens[tee_index])
            index = tee_index + 1
            continue
        if token in {"python", "python3", "node", "perl", "ruby"}:
            remainder = " ".join(tokens[index + 1 :])
            if looks_like_bash_write(remainder):
                write_like_but_unparsed = True
        index += 1

    if not targets and write_like_but_unparsed:
        return targets, "cannot safely parse Bash write targets from write-like command"
    return targets, None


def extract_job_id_from_tool_input(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("job_id", "jobId", "hermes_job_id", "hermesJobId"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        for nested in value.values():
            candidate = extract_job_id_from_tool_input(nested)
            if candidate:
                return candidate
    if isinstance(value, list):
        for item in value:
            candidate = extract_job_id_from_tool_input(item)
            if candidate:
                return candidate
    return None


def unresolved_task_card_job_ids(records: list[dict[str, Any]]) -> list[str]:
    terminal_jobs = {
        str(record.get("job_id"))
        for record in records
        if record.get("type") in {"result", "rejection"}
        and isinstance(record.get("job_id"), str)
    }
    job_ids: list[str] = []
    for record in records:
        job_id = record.get("job_id")
        if record.get("type") != "task_card" or not isinstance(job_id, str):
            continue
        if job_id in terminal_jobs or job_id in job_ids:
            continue
        job_ids.append(job_id)
    return job_ids


def guard_tool_input_permissions(
    root: Path,
    runtime_root: Path,
    task: str,
    worker_records: Path,
    data: dict[str, Any],
) -> str | None:
    tool_name = str(data.get("tool_name") or "")
    tool_input = data.get("tool_input", {})
    if tool_name == "Bash":
        command = bash_command_from_tool_input(tool_input)
        if command is None:
            return "Hermes Runtime: cannot safely parse Bash tool_input; denying by default."
        target_files, parse_error = extract_bash_targets(root, command)
        if parse_error is not None:
            return f"Hermes Runtime: {parse_error}; denying by default."
        if not target_files and not looks_like_bash_write(command):
            return None
        if not target_files:
            return "Hermes Runtime: cannot safely parse Bash write targets; denying by default."
    else:
        target_files = collect_tool_target_files(root, tool_name, tool_input)
    if not target_files:
        return None

    records = read_worker_records(worker_records)
    job_id = extract_job_id_from_tool_input(tool_input)
    if job_id is None:
        candidates = unresolved_task_card_job_ids(records)
        if len(candidates) == 1:
            job_id = candidates[0]
    if job_id is None:
        return (
            "Hermes Runtime: cannot check current write because tool_input "
            "does not include job_id and there is no unique active task_card."
        )

    guard = run_runtime(
        root,
        [
            str(runtime_root / "guard.py"),
            "--task",
            task,
            "--job-id",
            job_id,
            "--changed-files",
            ",".join(target_files),
        ],
    )
    if guard.returncode != 0:
        return guard.stderr.strip() or "Hermes Runtime: current write violates task_card permissions."
    return None


def main() -> int:
    if os.environ.get("TRELLIS_HOOKS") == "0" or os.environ.get("TRELLIS_DISABLE_HOOKS") == "1":
        return 0

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}

    cwd = Path(str(data.get("cwd") or os.getcwd()))
    root = find_trellis_root(cwd)
    if root is None:
        return 0

    task = resolve_active_task(root, data)
    if not task:
        return 0

    worker_records = (
        root / ".trellis" / "tasks" / task / "hermes" / "worker_records.jsonl"
    )

    event_name = str(data.get("hook_event_name") or "")
    runtime_root = root / ".trellis" / "scripts" / "hermes"

    if event_name in {"Stop", "SubagentStop"}:
        if not worker_records.exists():
            print(json.dumps(
                block_payload(event_name, missing_worker_records_reason(worker_records)),
                ensure_ascii=False,
            ))
            return 0
        reason = validate_worker_records(root, runtime_root, task)
        if reason is not None:
            print(json.dumps(block_payload(event_name, reason), ensure_ascii=False))
            return 0
        if not has_task_card(read_worker_records(worker_records)):
            print(json.dumps(
                block_payload(event_name, "Hermes worker records are missing task_card."),
                ensure_ascii=False,
            ))
            return 0

    if event_name == "PreToolUse":
        tool_name = str(data.get("tool_name") or "")
        if tool_name in WRITE_TOOL_NAMES:
            if not worker_records.exists():
                print(json.dumps(
                    deny_tool_payload(event_name, missing_worker_records_reason(worker_records)),
                    ensure_ascii=False,
                ))
                return 0
            reason = validate_worker_records(root, runtime_root, task)
            if reason is not None:
                print(json.dumps(deny_tool_payload(event_name, reason), ensure_ascii=False))
                return 0
            reason = guard_tool_input_permissions(
                root,
                runtime_root,
                task,
                worker_records,
                data,
            )
            if reason is not None:
                print(json.dumps(deny_tool_payload(event_name, reason), ensure_ascii=False))
                return 0
            context = (
                "Hermes Runtime: before accepting worker output, run "
                f"`python3 ./.trellis/scripts/hermes/validate.py --task {task} --kind worker` "
                "and the matching guard.py changed-files check."
            )
            print(json.dumps(context_payload(event_name, context), ensure_ascii=False))
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
