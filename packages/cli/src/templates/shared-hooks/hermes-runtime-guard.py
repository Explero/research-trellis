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
from pathlib import Path
from typing import Any


MUTATION_TOOL_NAMES = {"Edit", "Write", "MultiEdit", "apply_patch"}
WRITE_TOOL_NAMES = {*MUTATION_TOOL_NAMES, "Bash"}
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
    "builder",
    "coder",
    "runner",
    "reviewer",
    "researcher",
    "analyst",
    "literature",
    "evaluator",
    "trellis_implement",
    "trellis_check",
    "trellis_research",
    "trellis_spec_review",
    "trellis_code_review",
    "trellis_code_architecture_review",
    "trellis_merge_review",
    "trellis_improve_codebase_architecture",
    "hermes_coder",
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
    return value.strip().lower().replace("-", "_").replace(" ", "_")


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


def is_main_readonly_bash(command: str) -> bool:
    tokens = shell_tokens(command)
    if not tokens or has_shell_control(command, tokens):
        return False
    return (
        is_readonly_git_command(tokens)
        or is_readonly_record_cat(tokens)
        or is_readonly_record_jq(tokens)
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
        else "dispatch the appropriate researcher or analyst subagent"
    )
    return (
        "Hermes Runtime: main agent firewall denied Bash. Main agent is "
        "coordinator only and may run only read-only routing commands: "
        "git status --short -- <path>, git diff --name-only/--stat -- <path>, "
        "git log --oneline/--stat -- <path>, "
        "or cat/jq against RecordBus JSONL. "
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


def task_cards_by_job(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    for record in records:
        if record.get("type") != "task_card":
            continue
        job_id = record.get("job_id")
        if isinstance(job_id, str) and job_id not in cards:
            cards[job_id] = record
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
        if (
            job_id == coder_job_id
            or card.get("parent_job_id") == coder_job_id
            or record.get("parent_job_id") == coder_job_id
        ):
            matches.append(record)
    return matches


def completed_coder_results(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards = task_cards_by_job(records)
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
    evidence_refs = runner_result.get("evidence_refs")
    if not isinstance(evidence_refs, list):
        return False
    for evidence_ref in evidence_refs:
        if not isinstance(evidence_ref, str):
            continue
        manifest = run_manifests.get(evidence_ref)
        if manifest is not None and manifest.get("exit_code") == 0:
            return True
    return False


def stop_completion_reason(
    root: Path,
    runtime_root: Path,
    task: str,
    records: list[dict[str, Any]],
) -> str | None:
    coder_results = completed_coder_results(records)
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

    cards = task_cards_by_job(records)
    run_manifests = read_run_manifest_index(root, task)
    for result in matching_results:
        job_id = record_job_id(result)
        if job_id is None:
            continue
        runner_results = related_records(records, cards, job_id, "runner", {"result"})
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
            f"--changed-files={','.join(target_files)}",
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

    event_name = str(data.get("hook_event_name") or "")
    runtime_root = root / ".trellis" / "scripts" / "hermes"
    task = resolve_active_task(root, data)
    worker_records = (
        root / ".trellis" / "tasks" / task / "hermes" / "worker_records.jsonl"
        if task
        else None
    )

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
            if tool_name == "Bash":
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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
