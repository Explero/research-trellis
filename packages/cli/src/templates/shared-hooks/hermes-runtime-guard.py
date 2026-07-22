#!/usr/bin/env python3
"""Hermes runtime guard hook.

This hook delegates record validation to `.trellis/scripts/hermes/` so platform
hooks stay adapters instead of becoming the source of truth.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any


MUTATION_TOOL_NAMES = {"Edit", "Write", "MultiEdit", "apply_patch"}
WRITE_TOOL_NAMES = {*MUTATION_TOOL_NAMES, "Bash"}
READ_TOOL_NAMES = {"Read", "Glob", "Grep"}
AGENT_IDENTITY_KEYS = {
    "agent_role",
    "agent_name",
    "subagent_name",
    "subagent_type",
    "subagentType",
    "subagent",
    "agent_type",
    "role",
}
MAIN_AGENT_IDENTITIES = {"main", "coordinator", "main_agent"}
SUBAGENT_IDENTITIES = {
    "planner",
    "builder",
    "coder",
    "runner",
    "reviewer",
    "researcher",
    "research_scout",
    "analyst",
    "literature",
    "evaluator",
    "scientist",
    "claim_reviewer",
    "evidence_curator",
    "trellis_implement",
    "trellis_check",
    "trellis_research",
    "trellis_spec_review",
    "trellis_code_review",
    "trellis_code_architecture_review",
    "trellis_merge_review",
    "trellis_improve_codebase_architecture",
    "hermes_coder",
    "hermes_planner",
    "hermes_researcher",
    "hermes_runner",
    "hermes_reviewer",
    "hermes_literature",
    "hermes_evaluator",
    "hermes_claim_reviewer",
    "hermes_scientist",
}
BASH_EXECUTION_ROLES = {"coder", "runner"}


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


def updated_tool_output_payload(
    summary: dict[str, Any],
    tool_response: Any,
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    if not isinstance(tool_response, dict):
        return block_payload(
            "PostToolUse",
            "Hermes Context Firewall: Agent output shape is unsupported; raw output was not accepted.",
        )
    replacement = dict(tool_response)
    replacement["content"] = [
        {
            "type": "text",
            "text": json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
        }
    ]
    output: dict[str, Any] = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "updatedToolOutput": replacement,
        }
    }
    if reason:
        output["decision"] = "block"
        output["reason"] = reason
    return {
        **output,
    }


def validate_worker_records(
    root: Path,
    runtime_root: Path,
    task: str,
    *,
    check_jobs: bool = False,
) -> str | None:
    validate = run_runtime(
        root,
        [str(runtime_root / "validate.py"), "--task", task, "--kind", "worker"],
    )
    if validate.returncode != 0:
        return sanitize_runtime_error(
            validate.stderr,
            "Hermes worker records are invalid.",
        )

    if not check_jobs:
        return None

    jobs = run_runtime(
        root,
        [str(runtime_root / "jobs.py"), "check", "--task", task],
    )
    if jobs.returncode != 0:
        return sanitize_runtime_error(
            jobs.stderr,
            "Hermes worker job is stalled.",
        )
    return None


def sanitize_runtime_error(stderr: str, fallback: str) -> str:
    raw = stderr.strip()
    if not raw:
        return fallback
    lines = [
        sanitize_runtime_error_line(line)
        for line in raw.splitlines()
        if line.strip()
    ]
    summary = "; ".join(line for line in lines if line)
    if not summary:
        return fallback
    return f"{fallback.rstrip('.')}: {summary}"


def sanitize_runtime_error_line(line: str) -> str:
    text = line.strip()
    text = re.sub(
        r"(?:[A-Za-z]:)?[/\\][^:\n]*?\.jsonl:(\d+):\s*",
        r"line \1: ",
        text,
    )
    text = re.sub(
        r"\.trellis[/\\]tasks[/\\][^:\n]*?\.jsonl:(\d+):\s*",
        r"line \1: ",
        text,
    )
    text = re.sub(r"(?:[A-Za-z]:)?[/\\]\S*?\.jsonl\b", "record file", text)
    text = re.sub(r"\.trellis[/\\]tasks[/\\]\S*?\.jsonl\b", "record file", text)
    return text.strip(" :")


def missing_worker_records_reason(_worker_records: Path) -> str:
    return (
        "Hermes Runtime: active task has no worker_records.jsonl; denying "
        "by default until a unique task_card is recorded."
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


def read_jsonl_records(path: Path) -> list[dict[str, Any]]:
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


def normalized_agent_identity(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace("-", "_")
        .replace("/", "_")
        .replace(" ", "_")
    )


def direct_agent_identity_values(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    values: list[str] = []
    for key in AGENT_IDENTITY_KEYS:
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            values.append(candidate)
    return values


def agent_identity_values(data: dict[str, Any]) -> list[str]:
    return direct_agent_identity_values(data)


def is_main_agent_request(data: dict[str, Any]) -> bool:
    identities = [normalized_agent_identity(value) for value in agent_identity_values(data)]
    if any(identity in SUBAGENT_IDENTITIES for identity in identities):
        return False
    if any(identity in MAIN_AGENT_IDENTITIES for identity in identities):
        return True
    return True


def is_main_bash_allowed(command: str) -> bool:
    """Classify the small coordinator command surface without parsing shell.

    This is deliberately an explicit command matrix, not a shell-security
    parser. Any shell composition is rejected before the command family is
    checked. Main agents use Read for records; Bash is only for deterministic
    task/closure control and narrowly scoped Git inspection.
    """
    normalized = command.strip().replace("\\", "/")
    if not normalized or any(
        marker in normalized
        for marker in (";", "&", "|", ">", "<", "`", "$", "\n", "\r")
    ):
        return False
    tokens = normalized.split()
    if not tokens:
        return False
    if tokens[0] == "git":
        return is_main_git_read_allowed(tokens)
    if tokens[0] not in {"python", "python3"} or len(tokens) < 3:
        return False

    script = tokens[1]
    while script.startswith("./"):
        script = script[2:]
    subcommand = tokens[2]
    arguments = tokens[3:]
    if script == ".trellis/scripts/task.py":
        return is_main_task_command_allowed(subcommand, arguments)
    if script == ".trellis/scripts/hermes/dispatch.py":
        return subcommand in {
            "create",
            "validate",
            "show",
            "run",
            "apply",
            "list",
            "status",
            "supersede",
        }
    if script == ".trellis/scripts/closure.py":
        return subcommand in {
            "plan",
            "route",
            "grill",
            "validate",
            "status",
            "next",
            "capsule",
            "package-start",
            "package-check",
            "package-done",
            "package-block",
            "amend",
            "repair",
            "audit",
            "close",
        }
    return False


def is_main_task_command_allowed(subcommand: str, arguments: list[str]) -> bool:
    """Allow deterministic task coordination, never archive auto-commit."""
    coordination_commands = {
        "create",
        "add-context",
        "validate",
        "list-context",
        "start",
        "current",
        "finish",
        "set-branch",
        "set-base-branch",
        "set-scope",
        "list",
        "list-archive",
        "add-subtask",
        "remove-subtask",
    }
    if subcommand in coordination_commands:
        return True
    # task.py archive can stage and commit unless this explicit no-write flag
    # is present. Main may advance the task lifecycle, not write Git history.
    return subcommand == "archive" and "--no-commit" in arguments


def is_main_git_read_allowed(tokens: list[str]) -> bool:
    """Allow a small, non-writing Git inspection matrix.

    Git accepts many diff options and pathspec forms. We do not try to parse
    them generally: only the read forms below are coordinator commands.
    """
    if len(tokens) < 2:
        return False
    command = tokens[1]
    arguments = tokens[2:]
    if any(
        value == "--output"
        or value.startswith("--output=")
        or value in {"--ext-diff", "--no-index"}
        or value.startswith("--ext-diff=")
        or value.startswith("--no-index=")
        for value in arguments
    ):
        return False
    if command == "branch":
        return arguments == ["--show-current"]
    if command == "status":
        allowed_options = {
            "--short",
            "-s",
            "--branch",
            "-b",
            "--porcelain",
            "--porcelain=v1",
            "--porcelain=v2",
            "--untracked-files=no",
            "--untracked-files=normal",
            "--untracked-files=all",
        }
        if "--" not in arguments:
            return all(value in allowed_options for value in arguments)
        separator = arguments.index("--")
        options = arguments[:separator]
        pathspecs = arguments[separator + 1:]
        return (
            bool(pathspecs)
            and all(value in allowed_options for value in options)
            and all(is_safe_main_git_pathspec(value) for value in pathspecs)
        )
    if command == "diff":
        return is_main_git_diff_allowed(arguments)
    if command == "log":
        return is_main_git_log_allowed(arguments)
    return False


def is_main_git_diff_allowed(arguments: list[str]) -> bool:
    allowed_options = {
        "--name-only",
        "--name-status",
        "--stat",
        "--summary",
        "--check",
        "--cached",
        "--staged",
        "--no-ext-diff",
        "--no-textconv",
    }
    if not arguments:
        return True
    if "--" not in arguments:
        return all(value in allowed_options for value in arguments)
    separator = arguments.index("--")
    options = arguments[:separator]
    pathspecs = arguments[separator + 1:]
    return (
        bool(pathspecs)
        and all(value in allowed_options for value in options)
        and all(is_safe_main_git_pathspec(value) for value in pathspecs)
    )


def is_main_git_log_allowed(arguments: list[str]) -> bool:
    allowed_options = {
        "--oneline",
        "--decorate",
        "--no-decorate",
        "--stat",
        "--name-only",
        "--name-status",
        "--no-ext-diff",
        "--no-textconv",
    }
    for value in arguments:
        if value == "--":
            return False
        if value in allowed_options or value.startswith("--max-count="):
            continue
        if value.startswith("-n") and value[2:].isdigit():
            continue
        return False
    return True


def is_safe_main_git_pathspec(value: str) -> bool:
    normalized = value.replace("\\", "/").strip()
    if (
        not normalized
        or normalized.startswith(("/", "../", "./../", ":"))
        or ".." in Path(normalized).parts
    ):
        return False
    name = Path(normalized).name.casefold()
    return not (
        name.startswith(".env")
        or "credential" in name
        or "secret" in name
        or name in {"id_rsa", "id_ed25519"}
    )


def main_agent_firewall_reason(data: dict[str, Any]) -> str | None:
    tool_name = str(data.get("tool_name") or "")
    if tool_name in MUTATION_TOOL_NAMES:
        return (
            "Hermes Runtime: main agent firewall denied "
            f"{tool_name}. Main agent is coordinator only; next step: "
            "dispatch a coder subagent with task_card allowed_files and "
            "forbidden_files."
        )
    if tool_name != "Bash":
        return None
    command = bash_command_from_tool_input(data.get("tool_input", {}))
    if command and is_main_bash_allowed(command):
        return None
    return (
        "Hermes Runtime: main agent firewall denied Bash. Main agent may inspect "
        "task state or use Hermes control commands, but implementation, tests, "
        "and experiments must be delegated to a runner subagent or the appropriate "
        "specialist subagent."
    )


def declared_worker_role(data: dict[str, Any]) -> str | None:
    aliases = {
        "builder": "coder",
        "coder": "coder",
        "hermes_coder": "coder",
        "trellis_implement": "coder",
        "runner": "runner",
        "hermes_runner": "runner",
    }
    for value in agent_identity_values(data):
        normalized = normalized_agent_identity(value)
        if normalized in aliases:
            return aliases[normalized]
    return None


def is_worker_bash_command_allowed(role: str, command: str) -> bool:
    """Allow role-specific commands without attempting to parse a shell."""
    normalized = command.strip().replace("\\", "/")
    if not normalized or any(
        marker in normalized
        for marker in (";", "&", "|", ">", "<", "`", "$", "\n", "\r")
    ):
        return False
    tokens = normalized.split()
    if role == "coder":
        return bool(tokens) and tokens[0] == "git" and is_main_git_read_allowed(tokens)
    if role != "runner" or len(tokens) < 3 or tokens[0] not in {"python", "python3"}:
        return False
    script = tokens[1]
    while script.startswith("./"):
        script = script[2:]
    return (
        script == ".trellis/scripts/hermes/runner.py"
        and tokens[2] in {"run", "replay", "validate"}
    )


def no_active_task_tool_denial(tool_name: str) -> str:
    return (
        "Hermes Runtime: no active task is selected; denying "
        f"{tool_name} by default. Select an active task and record a "
        "task_card before running write or execution tools."
    )


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


def git_output_lines(root: Path, args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def git_changed_files(root: Path) -> list[str]:
    changed: list[str] = []
    for file_path in git_output_lines(root, ["diff", "--name-only", "--"]):
        add_changed_file(changed, file_path)
    for file_path in git_output_lines(root, ["diff", "--cached", "--name-only", "--"]):
        add_changed_file(changed, file_path)
    for file_path in git_output_lines(root, ["ls-files", "--others", "--exclude-standard"]):
        add_changed_file(changed, file_path)
    return [file_path for file_path in changed if not file_path.startswith(".trellis/")]


def add_changed_file(files: list[str], raw_path: str) -> None:
    normalized = raw_path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized and normalized not in files:
        files.append(normalized)


def normalize_task_card_for_gate(
    root: Path,
    card: dict[str, Any],
) -> dict[str, Any]:
    scripts_dir = root / ".trellis" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from common.roles import normalize_task_card  # type: ignore[import-not-found]

        normalized, _warnings = normalize_task_card(card)
        return normalized
    except (ImportError, ValueError):
        return card


def task_cards_by_job(
    records: list[dict[str, Any]],
    root: Path,
) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    for record in records:
        if record.get("type") != "task_card":
            continue
        job_id = record.get("job_id")
        if isinstance(job_id, str) and job_id not in cards:
            cards[job_id] = normalize_task_card_for_gate(root, record)
    return cards


def record_job_id(record: dict[str, Any]) -> str | None:
    job_id = record.get("job_id")
    return job_id if isinstance(job_id, str) and job_id.strip() else None


def is_completion_handoff(record: dict[str, Any]) -> bool:
    status = record.get("status")
    handoff = record.get("handoff")
    completion_states = {"review", "claim_ready"}
    return (
        isinstance(status, str)
        and status.strip().lower() in completion_states
    ) or (
        isinstance(handoff, str)
        and handoff.strip().lower() in completion_states
    )


def changed_files_from_record(record: dict[str, Any]) -> list[str]:
    changed = record.get("changed_files")
    if not isinstance(changed, list):
        return []
    return [item for item in changed if isinstance(item, str) and item.strip()]


def _parent_job_value(record: dict[str, Any]) -> tuple[bool, str | None]:
    if "parent_job_id" not in record:
        return False, None
    value = record.get("parent_job_id")
    if value is None:
        return True, None
    if isinstance(value, str) and value.strip():
        return True, value.strip()
    return True, ""


def _legacy_parent_candidates(
    cards: dict[str, dict[str, Any]],
    child_job_id: str,
    work_package: Any,
) -> set[str]:
    return {
        candidate_job_id
        for candidate_job_id, candidate in cards.items()
        if candidate_job_id != child_job_id
        and candidate.get("role") != "reviewer"
        and candidate.get("work_package") == work_package
    }


def record_matches_parent(
    record: dict[str, Any],
    cards: dict[str, dict[str, Any]],
    parent_job_id: str,
) -> bool:
    child_job_id = record_job_id(record)
    if child_job_id is None:
        return False
    card = cards.get(child_job_id)
    parent_card = cards.get(parent_job_id)
    if card is None or parent_card is None:
        return False
    explicit_card, card_parent = _parent_job_value(card)
    explicit_record, record_parent = _parent_job_value(record)
    if explicit_card:
        return (
            card_parent == parent_job_id
            and (not explicit_record or record_parent == card_parent)
            and parent_card.get("work_package") == card.get("work_package")
        )
    if explicit_record:
        return (
            record_parent == parent_job_id
            and parent_card.get("work_package") == card.get("work_package")
        )
    # Legacy records can only use the one same-package candidate. This avoids
    # inferring relationships from result ordering or timestamps.
    return _legacy_parent_candidates(
        cards,
        child_job_id,
        card.get("work_package"),
    ) == {parent_job_id}


def related_records(
    records: list[dict[str, Any]],
    cards: dict[str, dict[str, Any]],
    coder_job_id: str,
    role: str,
    record_types: set[str],
    profiles: set[str] | None = None,
    legacy_warnings: list[str] | None = None,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for record in records:
        if record.get("type") not in record_types:
            continue
        job_id = record_job_id(record)
        if job_id is None:
            continue
        card = cards.get(job_id)
        if card is None or card.get("role") != role:
            continue
        if profiles is not None and card.get("profile") not in profiles:
            continue
        if record_matches_parent(record, cards, coder_job_id):
            matches.append(record)
            explicit_card, _ = _parent_job_value(card)
            explicit_record, _ = _parent_job_value(record)
            if legacy_warnings is not None and not explicit_card and not explicit_record:
                package = card.get("work_package") or "task-level"
                legacy_warnings.append(
                    "Hermes Runtime compatibility warning: legacy job "
                    f"{job_id} has no parent_job_id and was matched to "
                    f"{coder_job_id} only because it is the sole non-reviewer "
                    f"candidate in work_package {package}. New dispatches must "
                    "record parent_job_id explicitly."
                )
    return matches


def completed_coder_results(
    records: list[dict[str, Any]],
    root: Path,
) -> list[dict[str, Any]]:
    cards = task_cards_by_job(records, root)
    results: list[dict[str, Any]] = []
    for record in records:
        if record.get("type") != "result":
            continue
        job_id = record_job_id(record)
        if job_id is None:
            continue
        card = cards.get(job_id)
        if card is None or card.get("role") != "coder":
            continue
        if record.get("status") == "done" and is_completion_handoff(record):
            results.append(record)
    return results


def completed_noncode_results(
    records: list[dict[str, Any]],
    root: Path,
) -> list[dict[str, Any]]:
    """Return completed research/configuration results when code work is absent."""
    cards = task_cards_by_job(records, root)
    results: list[dict[str, Any]] = []
    for record in records:
        if record.get("type") != "result" or not is_completion_handoff(record):
            continue
        job_id = record_job_id(record)
        card = cards.get(job_id or "")
        if card is None:
            continue
        role = card.get("role")
        profile = card.get("profile")
        if role in {"planner", "researcher", "runner"} or (
            role == "coder" and profile == "configuration"
        ):
            results.append(record)
    return results


def result_covers_changed_files(result: dict[str, Any], changed_files: list[str]) -> bool:
    if not changed_files:
        return True
    recorded = set(changed_files_from_record(result))
    return all(file_path in recorded for file_path in changed_files)


def read_run_manifest_index(root: Path, task: str) -> dict[str, dict[str, Any]]:
    path = root / ".trellis" / "tasks" / task / "hermes" / "run_manifest.jsonl"
    manifests: dict[str, dict[str, Any]] = {}
    for record in read_jsonl_records(path):
        run_id = record.get("id")
        if isinstance(run_id, str) and run_id.strip():
            manifests[run_id] = record
    return manifests


def runner_result_has_passing_test(
    runner_result: dict[str, Any],
    run_manifests: dict[str, dict[str, Any]],
) -> bool:
    run_refs = runner_result.get("run_refs")
    if not isinstance(run_refs, list):
        run_refs = runner_result.get("evidence_refs")
    if not isinstance(run_refs, list):
        return False
    for run_ref in run_refs:
        if not isinstance(run_ref, str):
            continue
        manifest = run_manifests.get(run_ref)
        if manifest is not None and manifest.get("exit_code") == 0:
            return True
    return False


def stop_completion_reason(
    root: Path,
    runtime_root: Path,
    task: str,
    records: list[dict[str, Any]],
    legacy_warnings: list[str] | None = None,
) -> str | None:
    changed_files = git_changed_files(root)
    cards = task_cards_by_job(records, root)
    code_cards = [
        card for card in cards.values()
        if card.get("role") == "coder"
        and card.get("profile") in {"implementation", "tests", "repair"}
    ]
    # The repository may already contain unrelated user changes. Route Stop by
    # the current task's cards, not by global worktree cleanliness.
    if not code_cards:
        research_results = completed_noncode_results(records, root)
        if not research_results:
            return (
                "Hermes Runtime: Stop requires a completed planner, researcher, "
                "runner, or configuration result before completion."
            )
        run_manifest_path = root / ".trellis" / "tasks" / task / "hermes" / "run_manifest.jsonl"
        if run_manifest_path.exists():
            validate_run_manifest = run_runtime(
                root,
                [str(runtime_root / "validate.py"), "--task", task, "--kind", "run_manifest"],
            )
            if validate_run_manifest.returncode != 0:
                return (
                    "Hermes Runtime: run manifest is invalid; inspect task "
                    "Hermes logs locally."
                )
        run_manifests = read_run_manifest_index(root, task)
        for result in research_results:
            job_id = record_job_id(result)
            card = cards.get(job_id or "")
            if job_id is None or card is None:
                continue
            if card.get("role") == "runner" and not runner_result_has_passing_test(
                result, run_manifests
            ):
                continue
            review_records = related_records(
                records,
                cards,
                job_id,
                "reviewer",
                {"checkpoint", "result"},
                {"quality", "evidence", "claim", "safety", "closure", "statistics"},
                legacy_warnings,
            )
            if review_records:
                return None
        return (
            "Hermes Runtime: Stop requires a related independent reviewer record; "
            "formal runner work also requires a successful run manifest."
        )

    coder_results = completed_coder_results(records, root)
    if not coder_results:
        return (
            "Hermes Runtime: Stop requires a completed coder result in "
            "worker_records.jsonl before completion."
        )

    matching_results = [
        result for result in coder_results if result_covers_changed_files(result, changed_files)
    ]
    if not matching_results:
        changed_count = len(changed_files)
        file_label = "file" if changed_count == 1 else "files"
        return (
            "Hermes Runtime: git diff contains "
            f"{changed_count} changed {file_label} not covered by a completed "
            "coder result."
        )

    run_manifest_path = root / ".trellis" / "tasks" / task / "hermes" / "run_manifest.jsonl"
    if run_manifest_path.exists():
        validate_run_manifest = run_runtime(
            root,
            [str(runtime_root / "validate.py"), "--task", task, "--kind", "run_manifest"],
        )
        if validate_run_manifest.returncode != 0:
            return (
                "Hermes Runtime: run manifest is invalid; inspect task "
                "Hermes logs locally."
            )

    run_manifests = read_run_manifest_index(root, task)
    for result in matching_results:
        job_id = record_job_id(result)
        if job_id is None:
            continue
        runner_results = related_records(
            records,
            cards,
            job_id,
            "runner",
            {"result"},
            {"test", "build", "validation"},
            legacy_warnings,
        )
        has_passing_test = any(
            runner_result_has_passing_test(runner_result, run_manifests)
            for runner_result in runner_results
        )
        if not has_passing_test:
            return (
                "Hermes Runtime: Stop requires a related runner result with a "
                "passing test run in run_manifest.jsonl."
            )

        review_records = related_records(
            records,
            cards,
            job_id,
            "reviewer",
            {"checkpoint", "result"},
            {"quality", "safety"},
            legacy_warnings,
        )
        if not review_records:
            return (
                "Hermes Runtime: Stop requires a related reviewer record before completion."
            )
        return None

    return "Hermes Runtime: Stop could not match completion records to current task state."


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
        if not command:
            return "Hermes Runtime: Bash command is missing."
        role: str | None = None
        agent_id = data.get("agent_id")
        if isinstance(agent_id, str) and agent_id:
            scripts_dir = root / ".trellis" / "scripts"
            if str(scripts_dir) not in sys.path:
                sys.path.insert(0, str(scripts_dir))
            try:
                from common.dispatch import load_dispatch_for_agent  # type: ignore[import-not-found]

                bound_dispatch = load_dispatch_for_agent(
                    root / ".trellis" / "tasks" / task,
                    agent_id,
                )
            except Exception:
                return "Hermes Runtime: Bash caller has no valid dispatch binding."
            role = str(bound_dispatch.get("role") or "")
        else:
            role = declared_worker_role(data)
        if role not in BASH_EXECUTION_ROLES:
            return f"Hermes Runtime: {role or 'unbound'} dispatch cannot execute Bash."
        if not is_worker_bash_command_allowed(role, command):
            return (
                "Hermes Runtime: Bash command is outside the role's bounded command surface. "
                "Use runner.py for registered execution or delegate the work."
            )
        return None
    else:
        target_files = collect_tool_target_files(root, tool_name, tool_input)
    if not target_files:
        return None
    for target in target_files:
        if _target_crosses_symlink(root, target):
            return f"Hermes Runtime: write target crosses a symlink or repository boundary: {target}"

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
            f"--changed-files={','.join(target_files)}",
        ],
    )
    if guard.returncode != 0:
        return guard.stderr.strip() or "Hermes Runtime: current write violates task_card permissions."
    return None


def _target_crosses_symlink(root: Path, target: str) -> bool:
    normalized = normalize_target_path(root, target)
    if normalized is None or normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        return True
    current = root.absolute()
    for part in Path(normalized).parts:
        current = current / part
        try:
            if current.is_symlink():
                return True
        except OSError:
            return True
    return False


def _read_target_allowed(target: str, refs: list[str], patterns: list[str]) -> bool:
    normalized = target.replace("\\", "/").removeprefix("./").rstrip("/")
    if normalized in refs:
        return True
    if any(ref.startswith(normalized + "/") for ref in refs):
        return True
    return any(
        fnmatchcase(normalized, pattern)
        or Path(normalized).match(pattern)
        or pattern.startswith(normalized + "/")
        for pattern in patterns
    )


def guard_agent_read_permissions(
    root: Path,
    task: str,
    data: dict[str, Any],
) -> str | None:
    agent_id = data.get("agent_id")
    agent_type = data.get("agent_type")
    if not isinstance(agent_id, str) or not agent_id:
        return "Hermes Context Firewall: subagent read has no bound agent_id."
    scripts_dir = root / ".trellis" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from common.dispatch import (  # type: ignore[import-not-found]
            DispatchError,
            load_dispatch_for_agent,
            validate_agent_binding,
        )
    except ImportError:
        return "Hermes Context Firewall: dispatch read guard is unavailable."
    task_dir = root / ".trellis" / "tasks" / task
    try:
        dispatch = load_dispatch_for_agent(task_dir, agent_id)
        validate_agent_binding(
            dispatch,
            agent_id=agent_id,
            agent_type=str(agent_type or "") or None,
            session_id=str(data.get("session_id") or "") or None,
        )
    except DispatchError as exc:
        return f"Hermes Context Firewall: {exc.code}."
    targets = collect_tool_target_files(
        root,
        str(data.get("tool_name") or ""),
        data.get("tool_input", {}),
    )
    if not targets:
        return "Hermes Context Firewall: read/search target is not explicit."
    refs = [str(item) for item in dispatch.get("refs") or [] if isinstance(item, str)]
    patterns = [
        str(item)
        for item in dispatch.get("allowed_files") or []
        if isinstance(item, str)
    ]
    for target in targets:
        if _target_crosses_symlink(root, target):
            return f"Hermes Context Firewall: read target crosses a symlink or repository boundary: {target}"
        lowered = target.casefold()
        if dispatch.get("blind_review") and any(
            marker in lowered
            for marker in (
                "worker_records.jsonl",
                ".result.json",
                ".raw.jsonl",
                "hermes-traces",
                "handoff.md",
            )
        ):
            return "Hermes Context Firewall: blind reviewer cannot read worker explanations or raw traces."
        if not _read_target_allowed(target, refs, patterns):
            return f"Hermes Context Firewall: read target is outside dispatch refs/allowed_files: {target}"
    return None


def read_active_task_data(root: Path, task: str | None) -> dict[str, Any]:
    if not task:
        return {}
    path = root / ".trellis" / "tasks" / task / "task.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def is_hermes_closure_task(task_data: dict[str, Any]) -> bool:
    return bool(task_data) and any(
        key in task_data for key in ("closure_state", "hermes_phase", "work_packages")
    )


def record_hook_heartbeat(
    root: Path,
    platform: str | None,
    *,
    task_id: str | None = None,
    session_id: str | None = None,
) -> None:
    if platform not in {"claude", "codex"}:
        return
    scripts_dir = root / ".trellis" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from common.firewall import record_firewall_heartbeat  # type: ignore[import-not-found]

        record_firewall_heartbeat(
            root,
            platform,
            "hooks",
            task_id=task_id,
            session_id=session_id,
        )
    except Exception:
        pass


def _agent_result_text(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list):
        parts = [_agent_result_text(item) for item in value]
        text = "\n".join(part for part in parts if part)
        return text or None
    if not isinstance(value, dict):
        return None
    if value.get("job_id") and value.get("conclusion"):
        return json.dumps(value, ensure_ascii=False)
    for key in ("text", "output", "result", "content", "message", "response"):
        if key in value:
            text = _agent_result_text(value.get(key))
            if text:
                return text
    return None


def extract_agent_result(data: dict[str, Any]) -> str | None:
    for key in (
        "last_assistant_message",
        "tool_response",
        "tool_output",
        "updated_tool_output",
        "response",
        "result",
        "output",
    ):
        text = _agent_result_text(data.get(key))
        if text:
            return text
    transcript = data.get("transcript_path")
    if isinstance(transcript, str) and transcript:
        try:
            path = Path(transcript).resolve()
            raw = path.read_text(encoding="utf-8", errors="replace")[-262144:]
        except OSError:
            return None
        for line in reversed(raw.splitlines()):
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = _agent_result_text(value)
            if text and "job_id" in text:
                return text
    return None


def _job_id_from_result(raw_result: str | None) -> str | None:
    if not raw_result:
        return None
    try:
        value = json.loads(raw_result)
    except json.JSONDecodeError:
        match = re.search(r"(?im)^\s*job_id\s*[:=]\s*([A-Za-z0-9][A-Za-z0-9._-]{0,79})\s*$", raw_result)
        return match.group(1) if match else None
    if isinstance(value, dict):
        job_id = value.get("job_id")
        if isinstance(job_id, str):
            return job_id
    return None


def agent_event_identity(
    data: dict[str, Any],
    event_name: str,
) -> tuple[str | None, str | None]:
    if event_name == "PostToolUse":
        tool_input = data.get("tool_input")
        tool_response = data.get("tool_response")
        agent_type = tool_input.get("subagent_type") if isinstance(tool_input, dict) else None
        agent_id = tool_response.get("agentId") if isinstance(tool_response, dict) else None
        return (
            str(agent_type) if isinstance(agent_type, str) else None,
            str(agent_id) if isinstance(agent_id, str) else None,
        )
    agent_type = data.get("agent_type")
    agent_id = data.get("agent_id")
    return (
        str(agent_type) if isinstance(agent_type, str) else None,
        str(agent_id) if isinstance(agent_id, str) else None,
    )


def handle_agent_result_event(
    root: Path,
    task: str,
    task_data: dict[str, Any],
    data: dict[str, Any],
    event_name: str,
) -> dict[str, Any] | None:
    task_dir = root / ".trellis" / "tasks" / task
    dispatches = task_dir / "hermes" / "dispatches"
    if not dispatches.is_dir():
        return None
    raw_result = extract_agent_result(data)
    agent_type, agent_id = agent_event_identity(data, event_name)
    scripts_dir = root / ".trellis" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from common.dispatch import (  # type: ignore[import-not-found]
            DispatchError,
            accept_result_text,
            load_dispatch,
            load_dispatch_for_agent,
            load_sanitized_result,
            role_for_agent_type,
            sanitized_summary,
            validate_agent_binding,
        )
    except ImportError:
        return block_payload(event_name, "Hermes Context Firewall runtime is unavailable.")

    if role_for_agent_type(agent_type) is None:
        return None
    if not agent_id:
        return block_payload(event_name, "Hermes Context Firewall: Hermes Agent result has no agent_id binding.")
    try:
        initial_state = load_dispatch_for_agent(task_dir, agent_id)
        validate_agent_binding(
            initial_state,
            agent_id=agent_id,
            agent_type=agent_type,
            session_id=str(data.get("session_id") or "") or None,
        )
    except DispatchError as exc:
        return block_payload(event_name, f"Hermes Context Firewall: {exc.code}.")
    job_id = str(initial_state["job_id"])
    result_job_id = _job_id_from_result(raw_result)
    if result_job_id is not None and result_job_id != job_id:
        return block_payload(event_name, "Hermes Context Firewall: result job_id does not match bound agent_id.")
    existing = load_sanitized_result(task_dir, job_id)
    terminal_state = initial_state.get("status") in {"blocked", "failed", "stale"}
    if existing is None and raw_result and not terminal_state:
        try:
            accept_result_text(task_dir, task_data, root, job_id, raw_result)
        except DispatchError as exc:
            try:
                state = load_dispatch(task_dir, job_id)
            except DispatchError:
                state = {}
            if event_name == "SubagentStop" and state.get("status") != "blocked":
                return block_payload(
                    event_name,
                    f"Hermes Context Firewall: rewrite the final JSON result ({exc.code}).",
                )
    elif existing is None:
        try:
            state = load_dispatch(task_dir, job_id)
        except DispatchError:
            state = {}
        if state.get("status") not in {"blocked", "failed", "stale"}:
            return block_payload(event_name, "Hermes Context Firewall: final Agent result is missing.")

    if event_name == "PostToolUse":
        tool_response = data.get("tool_response")
        if isinstance(tool_response, dict) and tool_response.get("status") == "async_launched":
            return updated_tool_output_payload(
                sanitized_summary(task_dir, job_id),
                tool_response,
                reason="Hermes Context Firewall: background Agent output cannot satisfy a validated dispatch.",
            )
        return updated_tool_output_payload(
            sanitized_summary(task_dir, job_id),
            tool_response,
        )
    return None


def handle_subagent_start_event(
    root: Path,
    task: str,
    task_data: dict[str, Any],
    data: dict[str, Any],
) -> dict[str, Any] | None:
    agent_type, agent_id = agent_event_identity(data, "SubagentStart")
    scripts_dir = root / ".trellis" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from common.dispatch import (  # type: ignore[import-not-found]
            DispatchError,
            bind_claude_agent,
            role_for_agent_type,
        )
    except ImportError:
        return block_payload("SubagentStart", "Hermes Context Firewall runtime is unavailable.")
    if role_for_agent_type(agent_type) is None:
        return None
    if not agent_id or not agent_type:
        return block_payload("SubagentStart", "Hermes Agent start is missing agent identity.")
    try:
        dispatch = bind_claude_agent(
            root / ".trellis" / "tasks" / task,
            task_data,
            root,
            agent_type=agent_type,
            agent_id=agent_id,
            session_id=str(data.get("session_id") or "") or None,
        )
    except DispatchError as exc:
        return block_payload("SubagentStart", f"Hermes Context Firewall: {exc.code}.")
    return context_payload(
        "SubagentStart",
        f"Hermes binding active for job_id={dispatch['job_id']}; return only its Result Envelope.",
    )


def closure_dispatch_stop_reason(task_dir: Path, task_data: dict[str, Any]) -> str | None:
    dispatches = task_dir / "hermes" / "dispatches"
    if not dispatches.is_dir():
        return None
    if task_data.get("closure_state") == "closed" and task_data.get("hermes_phase") == "closed":
        return None
    unfinished = {"created", "validated", "running", "result_returned", "rewrite_required"}
    for path in dispatches.glob("*.dispatch.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return "Hermes Context Firewall: dispatch state is invalid; repair it before stopping."
        if value.get("status") in unfinished:
            return "Hermes Context Firewall: a dispatch result is still unconfirmed."
    packages = [item for item in task_data.get("work_packages") or [] if isinstance(item, dict)]
    if any(item.get("status") not in {"done", "deferred", "waived"} for item in packages):
        return "Hermes Context Firewall: work packages remain undisposed."
    return "Hermes Context Firewall: closure conditions are ready; run closure audit/close before stopping."


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

    event_name = str(data.get("hook_event_name") or "")
    platform = detect_platform(data)
    runtime_root = root / ".trellis" / "scripts" / "hermes"
    task = resolve_active_task(root, data)
    task_data = read_active_task_data(root, task)
    record_hook_heartbeat(
        root,
        platform,
        task_id=str(task_data.get("id") or task or "") or None,
        session_id=str(data.get("session_id") or "") or None,
    )
    if task and not is_hermes_closure_task(task_data):
        return 0
    worker_records = (
        root / ".trellis" / "tasks" / task / "hermes" / "worker_records.jsonl"
        if task
        else None
    )

    if event_name == "SubagentStart" and task:
        payload = handle_subagent_start_event(root, task, task_data, data)
        if payload is not None:
            print(json.dumps(payload, ensure_ascii=False))
        return 0

    if event_name == "PostToolUse" and task:
        tool_name = str(data.get("tool_name") or data.get("toolName") or "")
        if tool_name.casefold() in {"agent", "task"}:
            payload = handle_agent_result_event(root, task, task_data, data, event_name)
            if payload is not None:
                print(json.dumps(payload, ensure_ascii=False))
            return 0

    if event_name == "SubagentStop" and task:
        payload = handle_agent_result_event(root, task, task_data, data, event_name)
        if payload is not None:
            print(json.dumps(payload, ensure_ascii=False))
            return 0

    if event_name in {"Stop", "SubagentStop"}:
        if not task or worker_records is None:
            return 0
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
        if event_name == "Stop":
            closure_reason = closure_dispatch_stop_reason(
                root / ".trellis" / "tasks" / task,
                task_data,
            )
            if closure_reason is not None:
                print(json.dumps(block_payload(event_name, closure_reason), ensure_ascii=False))
                return 0
            records = read_worker_records(worker_records)
            legacy_warnings: list[str] = []
            reason = stop_completion_reason(
                root,
                runtime_root,
                task,
                records,
                legacy_warnings,
            )
            if reason is not None:
                print(json.dumps(block_payload(event_name, reason), ensure_ascii=False))
                return 0
            if legacy_warnings:
                warning = " ".join(dict.fromkeys(legacy_warnings))
                print(json.dumps(context_payload(event_name, warning), ensure_ascii=False))
                return 0

    if event_name == "PreToolUse":
        tool_name = str(data.get("tool_name") or "")
        if is_main_agent_request(data):
            reason = main_agent_firewall_reason(data)
            if reason is not None:
                print(json.dumps(deny_tool_payload(event_name, reason), ensure_ascii=False))
                return 0
            if tool_name == "Bash" or tool_name in READ_TOOL_NAMES:
                return 0
        if not task or worker_records is None:
            if tool_name in WRITE_TOOL_NAMES:
                print(json.dumps(
                    deny_tool_payload(event_name, no_active_task_tool_denial(tool_name)),
                    ensure_ascii=False,
                ))
                return 0
            return 0
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
        if tool_name in READ_TOOL_NAMES:
            reason = guard_agent_read_permissions(root, task, data)
            if reason is not None:
                print(json.dumps(deny_tool_payload(event_name, reason), ensure_ascii=False))
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
