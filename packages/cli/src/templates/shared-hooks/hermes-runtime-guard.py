#!/usr/bin/env python3
"""Hermes runtime guard hook.

This hook delegates record validation to `.trellis/scripts/hermes/` so platform
hooks stay adapters instead of becoming the source of truth.
"""
from __future__ import annotations

import json
import os
import re
import shlex
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
INLINE_SCRIPT_FLAGS = {
    "python": {"-c"},
    "python3": {"-c"},
    "node": {"-e", "--eval", "-p", "--print"},
    "nodejs": {"-e", "--eval", "-p", "--print"},
    "perl": {"-e"},
    "ruby": {"-e"},
}
INLINE_SCRIPT_FLAG_PREFIXES = {
    "node": ("--eval=", "--print="),
    "nodejs": ("--eval=", "--print="),
}
INLINE_SCRIPT_SHORT_EVAL_FLAGS = {
    "python": {"c"},
    "python3": {"c"},
    "node": {"e", "p"},
    "nodejs": {"e", "p"},
    "perl": {"e", "E"},
    "ruby": {"e"},
}
INLINE_SCRIPT_SHORT_COMBO_FLAGS = {
    "node": {"e", "p"},
    "nodejs": {"e", "p"},
    "perl": {"e", "E", "w"},
    "ruby": {"e", "w"},
}
INLINE_FILE_API_MARKERS = (
    "require('fs')",
    'require("fs")',
    "require('node:fs')",
    'require("node:fs")',
    "node:fs",
    "from 'fs'",
    'from "fs"',
    "from 'node:fs'",
    'from "node:fs"',
    "from os import",
    "import os",
    "from shutil import",
    "import shutil",
    "from pathlib import",
    "import pathlib",
    "open(",
    "Path(",
    "write_text(",
    "write_bytes(",
    ".write(",
    ".unlink(",
    ".copyFile(",
    ".rename(",
    ".mkdir(",
    "os.remove(",
    "os.unlink(",
    "os.rename(",
    "os.mkdir(",
    "os.makedirs(",
    "shutil.copyfile(",
    "shutil.copy(",
    "shutil.move(",
    "shutil.rmtree(",
    "writeFile(",
    "appendFile(",
    "copyFile(",
    "rename(",
    "mkdir(",
    "rm(",
    "unlink(",
    "unlink ",
    "writeFileSync(",
    "appendFileSync(",
    "copyFileSync(",
    "renameSync(",
    "rename ",
    "mkdirSync(",
    "rmSync(",
    "unlinkSync(",
    "fs.rm(",
    "fs.unlink(",
    "fs.writeFile(",
    "fs.appendFile(",
    "fs.copyFile(",
    "fs.rename(",
    "fs.mkdir(",
    "fs.promises.copyFile",
    "fs.promises.rename",
    "fs.promises.mkdir",
    "FileUtils",
    "FileUtils.cp(",
    "FileUtils.copy(",
    "FileUtils.mv(",
    "FileUtils.mkdir(",
    "FileUtils.mkdir_p(",
    "FileUtils.rm(",
    "FileUtils.rm_rf(",
    "FileUtils.touch(",
    "File.delete(",
    "File.rename(",
    "Dir.mkdir(",
    "File::Copy",
)


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


def shell_tokens(command: str) -> list[str] | None:
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return None


def has_shell_control(command: str, tokens: list[str]) -> bool:
    control_tokens = {
        "|",
        "||",
        "&",
        "&&",
        "<",
        ">",
        ">>",
        "1>",
        "1>>",
        "2>",
        "2>>",
        "&>",
        "&>>",
    }
    if "\n" in command or ";" in command or "`" in command or "$(" in command:
        return True
    return any(
        token in control_tokens
        or token.startswith((">", ">>", "1>", "1>>", "2>", "2>>", "&>", "&>>", "<"))
        for token in tokens
    )


def is_allowed_record_jsonl_path(raw_path: str) -> bool:
    path = raw_path.strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    if path.startswith("/") or ".." in path.split("/"):
        return False
    return (
        re.fullmatch(r"\.trellis/tasks/[^/]+/hermes/[^/]+\.jsonl", path) is not None
        or re.fullmatch(r"\.ai/records/[^/]+\.jsonl", path) is not None
    )


def is_safe_git_pathspec(raw_path: str) -> bool:
    path = raw_path.strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    if not path or path == "." or path.startswith("/") or path.startswith(":"):
        return False
    if any(char in path for char in "*?[]{}$~`()"):
        return False
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    for part in parts:
        lower_part = part.lower()
        if (
            lower_part == "env"
            or ".env" in lower_part
            or lower_part.endswith(".env")
        ):
            return False
    return True


def split_git_options_and_paths(
    args: list[str],
    allowed_options: set[str],
    required_options: set[str] | None = None,
    *,
    require_paths: bool = False,
) -> tuple[set[str], list[str]] | None:
    seen_separator = False
    seen_options: set[str] = set()
    paths: list[str] = []
    for arg in args:
        if seen_separator:
            paths.append(arg)
            continue
        if arg == "--":
            seen_separator = True
            continue
        if arg in allowed_options:
            seen_options.add(arg)
            continue
        return None

    if required_options is not None and not (seen_options & required_options):
        return None
    if require_paths and not paths:
        return None
    if any(not is_safe_git_pathspec(path) for path in paths):
        return None
    return seen_options, paths


def is_readonly_git_command(tokens: list[str]) -> bool:
    if len(tokens) < 2 or tokens[0] != "git":
        return False
    subcommand = tokens[1]
    args = tokens[2:]
    if subcommand == "status":
        allowed_status_options = {
            "--short",
            "-s",
            "-sb",
            "--branch",
            "-b",
            "--porcelain",
            "--porcelain=v1",
            "--porcelain=v2",
            "--show-stash",
            "--ahead-behind",
            "--no-ahead-behind",
        }
        short_status_options = {
            "--short",
            "-s",
            "-sb",
            "--porcelain",
            "--porcelain=v1",
            "--porcelain=v2",
        }
        return (
            split_git_options_and_paths(
                args,
                allowed_status_options,
                short_status_options,
                require_paths=True,
            )
            is not None
        )
    if subcommand == "diff":
        allowed_diff_options = {
            "--name-only",
            "--stat",
            "--cached",
            "--staged",
            "--no-renames",
        }
        return (
            split_git_options_and_paths(
                args,
                allowed_diff_options,
                {"--name-only", "--stat"},
                require_paths=True,
            )
            is not None
        )
    if subcommand == "log":
        allowed_log_options = {"--oneline", "--stat"}
        return (
            split_git_options_and_paths(
                args,
                allowed_log_options,
                {"--oneline", "--stat"},
                require_paths=True,
            )
            is not None
        )
    return False


def is_readonly_record_cat(tokens: list[str]) -> bool:
    if not tokens or tokens[0] != "cat":
        return False
    operands = [token for token in tokens[1:] if not token.startswith("-")]
    return bool(operands) and all(is_allowed_record_jsonl_path(token) for token in operands)


def is_readonly_record_jq(tokens: list[str]) -> bool:
    if not tokens or tokens[0] != "jq":
        return False
    file_reading_options = {
        "-f",
        "--from-file",
        "--slurpfile",
        "--rawfile",
        "--argfile",
    }
    if any(
        token in file_reading_options
        or token.startswith(("--from-file=", "--slurpfile=", "--rawfile=", "--argfile="))
        for token in tokens[1:]
    ):
        return False

    positional: list[str] = []
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token == "--":
            positional.extend(tokens[index + 1 :])
            break
        if token in {"--arg", "--argjson"}:
            index += 3
            continue
        if token in {"--indent", "-L"}:
            index += 2
            continue
        if token.startswith("-") and token != "-":
            index += 1
            continue
        positional.append(token)
        index += 1

    if len(positional) < 2:
        return False

    file_operands = positional[1:]
    return bool(file_operands) and all(
        is_allowed_record_jsonl_path(token) for token in file_operands
    )


def is_main_control_bash(command: str) -> bool:
    tokens = shell_tokens(command)
    if not tokens or has_shell_control(command, tokens):
        return False
    index = 0
    executable = command_basename(tokens[index]).casefold()
    if executable not in {"python", "python3", "py"}:
        return False
    index += 1
    if executable == "py" and index < len(tokens) and tokens[index] == "-3":
        index += 1
    if index + 1 < len(tokens) and tokens[index] == "-X":
        index += 2
    if index >= len(tokens):
        return False
    script = tokens[index].replace("\\", "/")
    while script.startswith("./"):
        script = script[2:]
    index += 1
    if index >= len(tokens):
        return False
    allowed: dict[str, set[str]] = {
        ".trellis/scripts/hermes/dispatch.py": {
            "create", "validate", "show", "run", "apply", "list", "status", "schema", "supersede",
        },
        ".trellis/scripts/closure.py": {
            "status", "next", "capsule", "validate", "package-start", "package-check",
            "package-done", "package-block", "audit", "repair", "amend", "handoff", "close",
        },
        ".trellis/scripts/task.py": {"current", "archive", "finish"},
    }
    return tokens[index] in allowed.get(script, set())


def is_main_readonly_bash(command: str) -> bool:
    tokens = shell_tokens(command)
    if not tokens or has_shell_control(command, tokens):
        return False
    return (
        is_readonly_git_command(tokens)
        or is_readonly_record_cat(tokens)
        or is_readonly_record_jq(tokens)
        or is_main_control_bash(command)
    )


def is_runner_bash_work(command: str) -> bool:
    tokens = shell_tokens(command) or []
    if not tokens:
        return True
    command_name = tokens[0]
    if command_name in {"npm", "pnpm", "yarn", "pytest", "rm"}:
        return True
    if command_name == "go" and len(tokens) > 1 and tokens[1] == "test":
        return True
    if command_name == "cargo" and len(tokens) > 1 and tokens[1] == "test":
        return True
    if command_name == "git" and len(tokens) > 1 and tokens[1] in {"add", "commit", "push"}:
        return True
    return "pytest" in tokens


def main_agent_bash_denial(command: str) -> str:
    next_step = (
        "dispatch a runner subagent"
        if is_runner_bash_work(command)
        else "dispatch the appropriate researcher or planner subagent"
    )
    return (
        "Hermes Runtime: main agent firewall denied Bash. Main agent is "
        "coordinator only and may run only read-only routing commands: "
        "git status --short -- <path>, git diff --name-only/--stat -- <path>, "
        "git log --oneline/--stat -- <path>, "
        "cat/jq against RecordBus JSONL, or parameterized Hermes "
        "dispatch/closure/task control-plane commands. "
        f"Next step: {next_step} with a task_card."
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
    if command is None:
        return (
            "Hermes Runtime: main agent firewall denied Bash because the "
            "command could not be parsed. Next step: dispatch a runner "
            "subagent with a task_card."
        )
    if is_main_readonly_bash(command):
        return None
    return main_agent_bash_denial(command)


def no_active_task_tool_denial(tool_name: str) -> str:
    return (
        "Hermes Runtime: no active task is selected; denying "
        f"{tool_name} by default. Select an active task and record a "
        "task_card before running write or execution tools."
    )


def looks_like_bash_write(command: str) -> bool:
    write_markers = (
        ">",
        "tee ",
        "write_text",
        "write_bytes",
        ".write(",
        ".unlink(",
        ".copyFile(",
        ".rename(",
        ".mkdir(",
        "open(",
        "os.remove(",
        "os.unlink(",
        "os.rename(",
        "os.mkdir(",
        "os.makedirs(",
        "shutil.copyfile(",
        "shutil.copy(",
        "shutil.move(",
        "shutil.rmtree(",
        "writeFileSync(",
        "appendFileSync(",
        "copyFileSync(",
        "renameSync(",
        "mkdirSync(",
        "copyFile(",
        "rename(",
        "mkdir(",
        "rmSync(",
        "unlinkSync(",
        "FileUtils.cp(",
        "FileUtils.copy(",
        "FileUtils.mv(",
        "FileUtils.mkdir(",
        "FileUtils.mkdir_p(",
        "FileUtils.rm(",
        "FileUtils.rm_rf(",
        "FileUtils.touch(",
        "File.delete(",
        "File.rename(",
        "Dir.mkdir(",
        "File::Copy",
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


def command_basename(token: str) -> str:
    return Path(token).name


def inline_script_code(tokens: list[str], interpreter_index: int) -> str | None:
    interpreter = command_basename(tokens[interpreter_index])
    flags = INLINE_SCRIPT_FLAGS.get(interpreter)
    if flags is None:
        return None
    prefixes = INLINE_SCRIPT_FLAG_PREFIXES.get(interpreter, ())
    short_eval_flags = INLINE_SCRIPT_SHORT_EVAL_FLAGS.get(interpreter, set())
    short_combo_flags = INLINE_SCRIPT_SHORT_COMBO_FLAGS.get(
        interpreter,
        short_eval_flags,
    )
    index = interpreter_index + 1
    while index < len(tokens):
        token = tokens[index]
        for prefix in prefixes:
            if token.startswith(prefix):
                return token[len(prefix) :]
        for flag in flags:
            if token == flag:
                if index + 1 >= len(tokens):
                    return ""
                return tokens[index + 1]
        if token.startswith("-") and not token.startswith("--") and token != "-":
            short_options = token[1:]
            if (
                len(short_options) > 1
                and any(option in short_eval_flags for option in short_options)
                and all(option in short_combo_flags for option in short_options)
            ):
                if index + 1 >= len(tokens):
                    return ""
                return tokens[index + 1]
            if short_options and short_options[0] in short_eval_flags:
                return short_options[1:]
        index += 1
    return None


def inline_script_has_unparsed_file_api(tokens: list[str], interpreter_index: int) -> bool:
    code = inline_script_code(tokens, interpreter_index)
    if code is None:
        return False
    if not code.strip():
        return True
    return any(marker in code for marker in INLINE_FILE_API_MARKERS)


def add_bash_target(targets: list[str], root: Path, value: str) -> None:
    if value in {"-", "/dev/null"}:
        return
    if value.startswith("&"):
        return
    add_unique_target(targets, root, value)


def is_shell_separator(token: str) -> bool:
    return token in {"|", "||", "&", "&&", ";"} or token.endswith(";")


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
            found_tee_target = False
            seen_tee_separator = False
            while tee_index < len(tokens):
                candidate = tokens[tee_index]
                if is_shell_separator(candidate):
                    break
                if not seen_tee_separator and candidate == "--":
                    seen_tee_separator = True
                    tee_index += 1
                    continue
                if not seen_tee_separator and candidate.startswith("-"):
                    tee_index += 1
                    continue
                add_bash_target(targets, root, candidate)
                found_tee_target = True
                tee_index += 1
            if not found_tee_target:
                return targets, "cannot safely parse Bash write targets: missing tee target"
            index = tee_index
            continue
        if command_basename(token) in INLINE_SCRIPT_FLAGS:
            if inline_script_has_unparsed_file_api(tokens, index):
                write_like_but_unparsed = True
        index += 1

    if write_like_but_unparsed:
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


def related_records(
    records: list[dict[str, Any]],
    cards: dict[str, dict[str, Any]],
    coder_job_id: str,
    role: str,
    record_types: set[str],
    profiles: set[str] | None = None,
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
        if (
            job_id == coder_job_id
            or card.get("parent_job_id") == coder_job_id
            or record.get("parent_job_id") == coder_job_id
        ):
            matches.append(record)
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
) -> str | None:
    coder_results = completed_coder_results(records, root)
    if not coder_results:
        return (
            "Hermes Runtime: Stop requires a completed coder result in "
            "worker_records.jsonl before completion."
        )

    changed_files = git_changed_files(root)
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

    cards = task_cards_by_job(records, root)
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
        if command is None:
            return "Hermes Runtime: cannot safely parse Bash tool_input; denying by default."
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
            if role in {"planner", "researcher"}:
                return f"Hermes Runtime: {role} dispatch cannot execute Bash."
            if role == "reviewer" and not is_readonly_git_command(shell_tokens(command) or []):
                return "Hermes Runtime: reviewer Bash is limited to scoped read-only git inspection."
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
            reason = stop_completion_reason(root, runtime_root, task, records)
            if reason is not None:
                print(json.dumps(block_payload(event_name, reason), ensure_ascii=False))
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
