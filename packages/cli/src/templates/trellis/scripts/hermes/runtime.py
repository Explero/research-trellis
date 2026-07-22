from __future__ import annotations

import json
import hashlib
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from fnmatch import fnmatchcase

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common.roles import (
    ACTIVE_WRITER_ROLES,
    CODE_REVIEW_PROFILES,
    CODE_RUNNER_PROFILES,
    RoleProfileError,
    normalize_task_card,
)


DIR_WORKFLOW = ".trellis"
DIR_TASKS = "tasks"
DIR_HERMES = "hermes"

WORKER_FILE = "worker_records.jsonl"
EVIDENCE_FILE = "evidence_ledger.jsonl"
CLAIM_FILE = "claim_ledger.jsonl"
ARTIFACT_FILE = "artifact_ledger.jsonl"
APPROVAL_FILE = "approval_records.jsonl"
STATE_FILE = "state_transition_log.jsonl"
EXPERIMENT_FILE = "experiment.yaml"
RUN_MANIFEST_FILE = "run_manifest.jsonl"
COMPARE_FILE = "compare.jsonl"
REPORT_FILE = "report.md"
METRICS_SCHEMA_FILE = "metrics_schema.yaml"
PROVENANCE_FILE = "provenance_ledger.jsonl"
AUDIT_FILE = "audit_ledger.jsonl"
SERVICE_QUEUE_FILE = "service_queue.jsonl"
PLAN_CHANGE_FILE = "plan_change_log.jsonl"
RUN_MANIFEST_REQUIRED_FIELDS = [
    "command",
    "cwd",
    "env_summary",
    "inputs",
    "outputs",
    "exit_code",
    "started_at",
    "finished_at",
]
CODER_REVIEW_HANDOFFS = {"review", "claim_ready"}
TERMINAL_WORKER_RECORD_TYPES = {"result", "rejection", "stalled"}
INDEPENDENT_REVIEWER_PROFILES = {"closure", "safety"}
APPROVAL_CHANGE_ID_FIELDS = {
    "change_id",
    "change_ids",
    "subject_id",
    "subject_ids",
    "approved_change_id",
    "approved_change_ids",
    "metric_change_id",
    "metric_change_ids",
    "split_change_id",
    "split_change_ids",
    "baseline_change_id",
    "baseline_change_ids",
}

RECORD_FILES = {
    "worker": WORKER_FILE,
    "evidence": EVIDENCE_FILE,
    "claim": CLAIM_FILE,
    "artifact": ARTIFACT_FILE,
    "provenance": PROVENANCE_FILE,
    "audit": AUDIT_FILE,
    "service_queue": SERVICE_QUEUE_FILE,
    "plan_change": PLAN_CHANGE_FILE,
    "approval": APPROVAL_FILE,
    "state": STATE_FILE,
    "run_manifest": RUN_MANIFEST_FILE,
    "compare": COMPARE_FILE,
    "metrics_schema": METRICS_SCHEMA_FILE,
}

EXPERIMENT_REQUIRED_FIELDS = [
    "question",
    "hypothesis",
    "dataset",
    "model",
    "metrics",
    "seed",
    "environment",
    "allowed_commands",
    "artifact_dir",
]
DATA_PREFLIGHT_CHANGE_FIELDS = {"dataset", "split", "preprocessing"}
DATA_PREFLIGHT_CHECKS = ("schema", "missing", "duplicates", "split_leakage")
DATA_PREFLIGHT_STATES = {"checked", "not_applicable"}
SECRET_ENV_NAME_PATTERN = re.compile(
    r"\b[A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE_KEY|API_KEY|ACCESS_KEY)[A-Z0-9_]*\b"
)

REQUIRED_FIELDS = {
    "task_card": [
        "type",
        "id",
        "timestamp",
        "job_id",
        "role",
        "worktree_id",
        "status",
        "allowed_files",
        "forbidden_files",
        "heartbeat_interval",
        "timeout_at",
        "checkpoint",
        "resume_from",
        "record_uri",
        "evidence_refs",
        "risk_flags",
    ],
    "heartbeat": [
        "type",
        "id",
        "timestamp",
        "job_id",
        "status",
        "checkpoint",
        "summary",
        "next_check_at",
    ],
    "checkpoint": [
        "type",
        "id",
        "timestamp",
        "job_id",
        "checkpoint",
        "resume_from",
        "evidence_refs",
        "open_items",
    ],
    "result": [
        "type",
        "id",
        "timestamp",
        "job_id",
        "status",
        "summary",
        "changed_files",
        "evidence_refs",
        "risk_flags",
        "handoff",
    ],
    "risk": [
        "type",
        "id",
        "timestamp",
        "job_id",
        "severity",
        "summary",
        "evidence_refs",
        "proposed_mitigation",
    ],
    "rejection": [
        "type",
        "id",
        "timestamp",
        "job_id",
        "reason",
        "required_fix",
    ],
    "stalled": [
        "type",
        "id",
        "timestamp",
        "job_id",
        "reason",
        "checkpoint",
        "resume_from",
        "required_fix",
    ],
    "evidence": [
        "type",
        "id",
        "timestamp",
        "source",
        "summary",
        "limits",
    ],
    "artifact": [
        "type",
        "id",
        "path",
        "hash",
        "run_id",
        "command_ref",
        "summary",
    ],
    "provenance": [
        "type",
        "id",
        "timestamp",
        "dataset",
        "model",
        "code",
        "env",
        "artifact",
    ],
    "audit": [
        "type",
        "id",
        "timestamp",
        "event",
        "actor",
        "boundary",
        "decision",
        "summary",
    ],
    "service_enqueue": [
        "type",
        "id",
        "timestamp",
        "job_id",
        "status",
        "command",
        "max_active",
    ],
    "service_cancel": [
        "type",
        "id",
        "timestamp",
        "job_id",
        "status",
        "reason",
    ],
    "service_retry": [
        "type",
        "id",
        "timestamp",
        "job_id",
        "status",
        "source_job_id",
        "command",
        "max_active",
    ],
    "claim": [
        "type",
        "id",
        "timestamp",
        "text",
        "evidence_ids",
        "scope",
        "limits",
        "state",
    ],
    "human_approval": [
        "type",
        "id",
        "timestamp",
        "claim_id",
        "approver",
        "decision",
        "notes",
    ],
    "state_transition": [
        "type",
        "id",
        "timestamp",
        "from",
        "to",
        "status",
        "reason",
    ],
    "compare": [
        "type",
        "id",
        "timestamp",
        "metric",
        "direction",
        "threshold",
        "baseline",
        "new",
        "delta",
        "passed",
        "evidence_refs",
        "claim_refs",
        "conclusion_state",
    ],
    "plan_change": [
        "type",
        "id",
        "timestamp",
        "plan_ref",
        "change_summary",
        "reason",
        "requested_by",
        "decision_state",
        "evidence_refs",
        "supersedes",
    ],
}

PLAN_CHANGE_DECISION_STATES = {"proposed", "accepted", "rejected", "superseded"}


@dataclass
class JsonlRecord:
    line_number: int
    value: dict[str, Any]


def repo_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    while current != current.parent:
        if (current / DIR_WORKFLOW).is_dir():
            return current
        current = current.parent
    return Path.cwd().resolve()


def task_dir(root: Path, task: str) -> Path:
    raw = task.strip().replace("\\", "/")
    if not raw:
        raise ValueError("task is required")
    if raw.startswith("/") or (len(raw) > 2 and raw[1] == ":" and raw[2] == "/"):
        raise ValueError("absolute task path is not allowed")

    while raw.startswith("./"):
        raw = raw[2:]

    parts = [part for part in raw.split("/") if part and part != "."]
    if not parts:
        raise ValueError("task is required")
    if any(part == ".." for part in parts):
        raise ValueError("task path traversal is not allowed")
    if parts[:2] == [DIR_WORKFLOW, DIR_TASKS]:
        parts = parts[2:]
    elif parts[:1] == [DIR_TASKS]:
        parts = parts[1:]
    if not parts:
        raise ValueError("task path must name a task under .trellis/tasks")

    tasks_root = (root / DIR_WORKFLOW / DIR_TASKS).resolve()
    candidate = tasks_root.joinpath(*parts).resolve(strict=False)
    try:
        candidate.relative_to(tasks_root)
    except ValueError as exc:
        raise ValueError("task path must stay under .trellis/tasks") from exc
    return candidate


def hermes_dir(root: Path, task: str) -> Path:
    return task_dir(root, task) / DIR_HERMES


def record_path(root: Path, task: str, record_type: str) -> Path:
    try:
        file_name = RECORD_FILES[record_type]
    except KeyError as exc:
        raise ValueError(f"unknown record type: {record_type}") from exc
    return hermes_dir(root, task) / file_name


def experiment_path(root: Path, task: str) -> Path:
    return hermes_dir(root, task) / EXPERIMENT_FILE


def run_manifest_path(root: Path, task: str) -> Path:
    return hermes_dir(root, task) / RUN_MANIFEST_FILE


def worker_records_path(root: Path, task: str) -> Path:
    return hermes_dir(root, task) / WORKER_FILE


def compare_path(root: Path, task: str) -> Path:
    return hermes_dir(root, task) / COMPARE_FILE


def report_path(root: Path, task: str) -> Path:
    return hermes_dir(root, task) / REPORT_FILE


def metrics_schema_path(root: Path, task: str) -> Path:
    return hermes_dir(root, task) / METRICS_SCHEMA_FILE


def append_record(path: Path, record: dict[str, Any]) -> None:
    if has_symlink_component(path):
        raise OSError(f"refusing to write through symlink: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if has_symlink_component(path):
        raise OSError(f"refusing to write through symlink: {path}")
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")


def has_symlink_component(path: Path) -> bool:
    current = Path(path.anchor)
    for part in path.parts[1:] if path.is_absolute() else path.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def read_jsonl(path: Path) -> tuple[list[JsonlRecord], list[str]]:
    records: list[JsonlRecord] = []
    errors: list[str] = []
    if not path.exists():
        return records, errors
    if has_symlink_component(path):
        return records, [f"{path}: refusing to read through symlink"]
    try:
        with path.open("r", encoding="utf-8") as handle:
            for index, line in enumerate(handle, start=1):
                line = line.rstrip("\n")
                if line.endswith("\r"):
                    line = line[:-1]
                if not line.strip():
                    errors.append(f"{path}:{index}: blank line is not valid JSONL")
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    errors.append(f"{path}:{index}: invalid JSON: {exc.msg}")
                    continue
                if not isinstance(value, dict):
                    errors.append(f"{path}:{index}: record must be a JSON object")
                    continue
                records.append(JsonlRecord(index, value))
    except (OSError, UnicodeDecodeError) as exc:
        return records, [f"{path}: cannot read file: {exc}"]
    return records, errors


def validate_required_fields(record: dict[str, Any], line_number: int) -> list[str]:
    record_type = record.get("type")
    if not isinstance(record_type, str) or not record_type:
        return [f"line {line_number}: missing type"]
    required = REQUIRED_FIELDS.get(record_type)
    if required is None:
        return [f"line {line_number}: unknown record type {record_type}"]
    missing = [field for field in required if field not in record]
    if missing:
        return [f"line {line_number}: missing required fields: {', '.join(missing)}"]
    return []


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_optional_string_list(
    record: dict[str, Any],
    field: str,
    line_number: int,
) -> list[str]:
    if field not in record:
        return []
    value = record.get(field)
    if not isinstance(value, list):
        return [f"line {line_number}: {field} must be a list of strings"]
    invalid = [
        item
        for item in value
        if not isinstance(item, str) or not item.strip()
    ]
    if invalid:
        return [f"line {line_number}: {field} must contain only non-empty strings"]
    return []


def load_artifact_context(path: Path) -> tuple[list[JsonlRecord], list[str], dict[str, JsonlRecord]]:
    artifact_path = path.parent / ARTIFACT_FILE
    artifact_records, artifact_errors = read_jsonl(artifact_path)
    errors = list(artifact_errors)
    errors.extend(validate_artifact_records(artifact_records, repo_root(path)))
    artifact_index: dict[str, JsonlRecord] = {}
    for entry in artifact_records:
        artifact_id = entry.value.get("id")
        if isinstance(artifact_id, str):
            artifact_index[artifact_id] = entry
    return artifact_records, errors, artifact_index


def validate_artifact_records(records: list[JsonlRecord], root: Path | None = None) -> list[str]:
    errors: list[str] = []
    artifact_lines: dict[str, list[int]] = {}
    root = root or repo_root()

    for entry in records:
        errors.extend(validate_required_fields(entry.value, entry.line_number))
        record = entry.value
        if record.get("type") != "artifact":
            continue
        if not is_nonempty_string(record.get("path")):
            errors.append(
                f"line {entry.line_number}: artifact path must be a non-empty string"
            )
        if not is_nonempty_string(record.get("hash")):
            errors.append(
                f"line {entry.line_number}: artifact hash must be a non-empty string"
            )
        if not is_nonempty_string(record.get("run_id")):
            errors.append(
                f"line {entry.line_number}: artifact run_id must be a non-empty string"
            )
        if not is_nonempty_string(record.get("command_ref")):
            errors.append(
                f"line {entry.line_number}: artifact command_ref must be a non-empty string"
            )
        if not is_nonempty_string(record.get("summary")):
            errors.append(
                f"line {entry.line_number}: artifact summary must be a non-empty string"
            )
        errors.extend(validate_artifact_file(root, record, entry.line_number))
        artifact_id = record.get("id")
        if isinstance(artifact_id, str):
            artifact_lines.setdefault(artifact_id, []).append(entry.line_number)

    for artifact_id, lines in artifact_lines.items():
        if len(lines) > 1:
            errors.append(
                f"duplicate artifact for id {artifact_id}: lines {', '.join(str(line) for line in lines)}"
            )

    return errors


def validate_ref_mapping(
    record: dict[str, Any],
    field: str,
    line_number: int,
) -> list[str]:
    value = record.get(field)
    if not isinstance(value, dict):
        return [f"line {line_number}: {field} must be a mapping"]
    ref = value.get("ref")
    if not is_nonempty_string(ref):
        return [f"line {line_number}: {field}.ref is required"]
    has_trace = any(is_nonempty_string(value.get(key)) for key in ["hash", "version", "source"])
    if not has_trace:
        return [f"line {line_number}: {field} must include hash, version, or source"]
    return []


def validate_provenance_records(records: list[JsonlRecord]) -> list[str]:
    errors: list[str] = []
    provenance_ids: dict[str, list[int]] = {}
    for entry in records:
        errors.extend(validate_required_fields(entry.value, entry.line_number))
        record = entry.value
        if record.get("type") != "provenance":
            continue
        if parse_timestamp(record.get("timestamp")) is None:
            errors.append(f"line {entry.line_number}: invalid provenance timestamp")
        provenance_id = record.get("id")
        if isinstance(provenance_id, str) and provenance_id.strip():
            provenance_ids.setdefault(provenance_id, []).append(entry.line_number)
        for field in ["dataset", "model", "code", "env", "artifact"]:
            errors.extend(validate_ref_mapping(record, field, entry.line_number))
    for provenance_id, lines in provenance_ids.items():
        if len(lines) > 1:
            errors.append(
                f"duplicate provenance id {provenance_id}: lines {', '.join(str(line) for line in lines)}"
            )
    return errors


def validate_audit_records(records: list[JsonlRecord]) -> list[str]:
    errors: list[str] = []
    audit_ids: dict[str, list[int]] = {}
    allowed_events = {
        "security_gate",
        "external_write_boundary",
        "secret_redaction",
        "sandbox_gate",
        "approval_boundary",
    }
    allowed_decisions = {"allowed", "blocked", "redacted", "recorded", "cancelled"}
    for entry in records:
        errors.extend(validate_required_fields(entry.value, entry.line_number))
        record = entry.value
        if record.get("type") != "audit":
            continue
        if parse_timestamp(record.get("timestamp")) is None:
            errors.append(f"line {entry.line_number}: invalid audit timestamp")
        audit_id = record.get("id")
        if isinstance(audit_id, str) and audit_id.strip():
            audit_ids.setdefault(audit_id, []).append(entry.line_number)
        if record.get("event") not in allowed_events:
            errors.append(
                f"line {entry.line_number}: audit event must be one of {', '.join(sorted(allowed_events))}"
            )
        if record.get("decision") not in allowed_decisions:
            errors.append(
                f"line {entry.line_number}: audit decision must be one of {', '.join(sorted(allowed_decisions))}"
            )
        for field in ["actor", "boundary", "summary"]:
            if not is_nonempty_string(record.get(field)):
                errors.append(f"line {entry.line_number}: audit {field} must be a non-empty string")
    for audit_id, lines in audit_ids.items():
        if len(lines) > 1:
            errors.append(
                f"duplicate audit id {audit_id}: lines {', '.join(str(line) for line in lines)}"
            )
    return errors


def service_queue_status(records: list[JsonlRecord]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for entry in records:
        record = entry.value
        job_id = record.get("job_id")
        status = record.get("status")
        if isinstance(job_id, str) and isinstance(status, str):
            statuses[job_id] = status
    return statuses


def validate_service_queue_records(records: list[JsonlRecord]) -> list[str]:
    errors: list[str] = []
    statuses: dict[str, str] = {}
    for entry in records:
        errors.extend(validate_required_fields(entry.value, entry.line_number))
        record = entry.value
        record_type = record.get("type")
        if record_type not in {"service_enqueue", "service_cancel", "service_retry"}:
            continue
        if parse_timestamp(record.get("timestamp")) is None:
            errors.append(f"line {entry.line_number}: invalid service queue timestamp")
        job_id = record.get("job_id")
        if not is_nonempty_string(job_id):
            errors.append(f"line {entry.line_number}: service job_id must be a non-empty string")
            continue
        if record_type in {"service_enqueue", "service_retry"}:
            if statuses.get(str(job_id)) in {"queued", "running"}:
                errors.append(f"line {entry.line_number}: duplicate active service job_id {job_id}")
            if not is_nonempty_string(record.get("command")):
                errors.append(f"line {entry.line_number}: service command must be a non-empty string")
            max_active = record.get("max_active")
            if not isinstance(max_active, int) or isinstance(max_active, bool) or max_active < 1:
                errors.append(f"line {entry.line_number}: max_active must be a positive integer")
        if record_type == "service_cancel":
            previous = statuses.get(str(job_id))
            if previous not in {"queued", "running"}:
                errors.append(f"line {entry.line_number}: cannot cancel inactive service job_id {job_id}")
            if not is_nonempty_string(record.get("reason")):
                errors.append(f"line {entry.line_number}: service cancel reason must be a non-empty string")
        statuses[str(job_id)] = str(record.get("status"))
    return errors


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def is_valid_sha256(value: str) -> bool:
    digest = value.removeprefix("sha256:")
    return (
        digest != value
        and len(digest) == 64
        and all(character in "0123456789abcdef" for character in digest)
    )


def validate_artifact_file(
    root: Path,
    record: dict[str, Any],
    line_number: int,
) -> list[str]:
    path_value = record.get("path")
    hash_value = record.get("hash")
    if not is_nonempty_string(path_value) or not is_nonempty_string(hash_value):
        return []
    normalized = normalize_path(str(path_value))
    if normalized is None:
        return [f"line {line_number}: artifact path is not readable: {path_value}"]
    resolved = (root / normalized).resolve(strict=False)
    if not resolved.is_file():
        return [f"line {line_number}: artifact path is not readable: {path_value}"]
    if not is_valid_sha256(str(hash_value)):
        return [f"line {line_number}: artifact hash is invalid: {path_value}"]
    actual_hash = sha256_file(resolved)
    if actual_hash != hash_value:
        return [
            f"line {line_number}: artifact hash mismatch: {path_value} expected {hash_value} got {actual_hash}"
        ]
    return []


def _manifest_path_value(item: Any) -> str | None:
    if isinstance(item, str):
        return item
    if isinstance(item, dict) and isinstance(item.get("path"), str):
        return item["path"]
    return None


def _resolve_manifest_path(root: Path, cwd: str, value: str) -> Path | None:
    normalized = normalize_path(value)
    if normalized is None:
        candidate = Path(value)
        if candidate.is_absolute():
            return candidate
        return None
    cwd_path = Path(cwd)
    if cwd_path.is_absolute():
        base = cwd_path
    else:
        base = root / cwd_path
    return (base / normalized).resolve(strict=False)


def validate_manifest_paths(
    root: Path,
    cwd: str,
    items: Any,
    field: str,
    line_number: int,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(items, list):
        return [f"line {line_number}: {field} must be a list"]
    for item in items:
        item_path = _manifest_path_value(item)
        if item_path is None or not item_path.strip():
            errors.append(f"line {line_number}: {field} path must be a non-empty string")
            continue
        resolved = _resolve_manifest_path(root, cwd, item_path)
        if resolved is None or not resolved.is_file():
            errors.append(f"line {line_number}: {field} path is not readable: {item_path}")
    return errors


def validate_run_manifest_records(path: Path, records: list[JsonlRecord]) -> list[str]:
    errors: list[str] = []
    root = repo_root(path)
    run_ids: dict[str, list[int]] = {}

    for entry in records:
        record = entry.value
        missing = [field for field in RUN_MANIFEST_REQUIRED_FIELDS if field not in record]
        if missing:
            errors.append(
                f"line {entry.line_number}: missing run_manifest fields: {', '.join(missing)}"
            )
            continue

        run_id = record.get("id")
        if isinstance(run_id, str) and run_id.strip():
            run_ids.setdefault(run_id, []).append(entry.line_number)

        command = record.get("command")
        if isinstance(command, list):
            if not command or not all(is_nonempty_string(item) for item in command):
                errors.append(
                    f"line {entry.line_number}: command must contain non-empty strings"
                )
        elif not is_nonempty_string(command):
            errors.append(
                f"line {entry.line_number}: command must be a non-empty string or list"
            )

        cwd = record.get("cwd")
        if not is_nonempty_string(cwd):
            errors.append(f"line {entry.line_number}: cwd must be a non-empty string")
            cwd = "."
        cwd_path = Path(str(cwd))
        resolved_cwd = cwd_path if cwd_path.is_absolute() else root / cwd_path
        if not resolved_cwd.is_dir():
            errors.append(f"line {entry.line_number}: cwd is not readable: {cwd}")

        if not isinstance(record.get("env_summary"), dict):
            errors.append(f"line {entry.line_number}: env_summary must be a mapping")
        elif manifest_has_secret_text(record.get("env_summary")):
            errors.append(f"line {entry.line_number}: env_summary must not contain secret env names or values")
        if manifest_has_secret_text(record.get("command")):
            errors.append(f"line {entry.line_number}: command must not contain secret env names or values")
        if manifest_has_secret_text(record.get("inputs")) or manifest_has_secret_text(record.get("outputs")):
            errors.append(f"line {entry.line_number}: inputs and outputs must not contain secret env names or values")

        errors.extend(
            validate_manifest_paths(root, str(cwd), record.get("inputs"), "input", entry.line_number)
        )
        errors.extend(
            validate_manifest_paths(root, str(cwd), record.get("outputs"), "output", entry.line_number)
        )

        if not isinstance(record.get("exit_code"), int):
            errors.append(f"line {entry.line_number}: exit_code must be an integer")

        started = parse_timestamp(record.get("started_at"))
        finished = parse_timestamp(record.get("finished_at"))
        if started is None:
            errors.append(f"line {entry.line_number}: invalid started_at")
        if finished is None:
            errors.append(f"line {entry.line_number}: invalid finished_at")
        if started is not None and finished is not None and finished < started:
            errors.append(f"line {entry.line_number}: finished_at must be after started_at")

    for run_id, lines in run_ids.items():
        if len(lines) > 1:
            errors.append(
                f"duplicate run_manifest id {run_id}: lines {', '.join(str(line) for line in lines)}"
            )

    return errors


def manifest_has_secret_text(value: Any) -> bool:
    if isinstance(value, str):
        if SECRET_ENV_NAME_PATTERN.search(value):
            return True
        lowered = value.lower()
        return any(marker in lowered for marker in ["test-secret-value", "secret=", "token=", "password="])
    if isinstance(value, dict):
        return any(manifest_has_secret_text(key) or manifest_has_secret_text(item) for key, item in value.items())
    if isinstance(value, list):
        return any(manifest_has_secret_text(item) for item in value)
    return False


def validate_compare_records(records: list[JsonlRecord]) -> list[str]:
    errors: list[str] = []
    compare_ids: dict[str, list[int]] = {}

    for entry in records:
        errors.extend(validate_required_fields(entry.value, entry.line_number))
        record = entry.value
        if record.get("type") != "compare":
            continue

        compare_id = record.get("id")
        if isinstance(compare_id, str) and compare_id.strip():
            compare_ids.setdefault(compare_id, []).append(entry.line_number)

        if not is_nonempty_string(record.get("metric")):
            errors.append(f"line {entry.line_number}: metric must be a non-empty string")

        direction = record.get("direction")
        if direction not in {"higher_is_better", "lower_is_better"}:
            errors.append(
                f"line {entry.line_number}: direction must be higher_is_better or lower_is_better"
            )

        for field in ["threshold", "baseline", "new", "delta"]:
            if not isinstance(record.get(field), (int, float)) or isinstance(record.get(field), bool):
                errors.append(f"line {entry.line_number}: {field} must be numeric")

        if not isinstance(record.get("passed"), bool):
            errors.append(f"line {entry.line_number}: passed must be boolean")

        errors.extend(
            validate_optional_string_list(record, "evidence_refs", entry.line_number)
        )
        errors.extend(
            validate_optional_string_list(record, "claim_refs", entry.line_number)
        )

        sample_count = record.get("sample_count")
        if sample_count is not None and (
            not isinstance(sample_count, int)
            or isinstance(sample_count, bool)
            or sample_count < 1
        ):
            errors.append(f"line {entry.line_number}: sample_count must be a positive integer")

        variance = record.get("variance")
        if variance is not None and (
            not isinstance(variance, (int, float))
            or isinstance(variance, bool)
            or variance < 0
        ):
            errors.append(f"line {entry.line_number}: variance must be a non-negative number")

        confidence_interval = record.get("confidence_interval")
        if confidence_interval is not None:
            if (
                isinstance(confidence_interval, list)
                and len(confidence_interval) == 2
                and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in confidence_interval)
                and confidence_interval[0] <= confidence_interval[1]
            ):
                pass
            elif (
                isinstance(confidence_interval, dict)
                and isinstance(confidence_interval.get("lower"), (int, float))
                and isinstance(confidence_interval.get("upper"), (int, float))
                and not isinstance(confidence_interval.get("lower"), bool)
                and not isinstance(confidence_interval.get("upper"), bool)
                and confidence_interval["lower"] <= confidence_interval["upper"]
            ):
                pass
            else:
                errors.append(
                    f"line {entry.line_number}: confidence_interval must be [lower, upper] or a lower/upper mapping"
                )

        if record.get("conclusion_state") != "claim_ready":
            errors.append(
                f"line {entry.line_number}: conclusion_state must remain claim_ready"
            )

    for compare_id, lines in compare_ids.items():
        if len(lines) > 1:
            errors.append(
                f"duplicate compare id {compare_id}: lines {', '.join(str(line) for line in lines)}"
            )

    return errors


def validate_plan_change_records(records: list[JsonlRecord]) -> list[str]:
    errors: list[str] = []
    plan_change_ids: dict[str, list[int]] = {}

    for entry in records:
        errors.extend(validate_required_fields(entry.value, entry.line_number))
        record = entry.value
        if record.get("type") != "plan_change":
            errors.append(f"line {entry.line_number}: expected plan_change record")
            continue

        plan_change_id = record.get("id")
        if isinstance(plan_change_id, str) and plan_change_id.strip():
            plan_change_ids.setdefault(plan_change_id, []).append(entry.line_number)
        elif "id" in record:
            errors.append(f"line {entry.line_number}: plan_change id must be a non-empty string")

        if parse_timestamp(record.get("timestamp")) is None:
            errors.append(f"line {entry.line_number}: invalid plan_change timestamp")

        for field in ["plan_ref", "change_summary", "reason", "requested_by"]:
            if not is_nonempty_string(record.get(field)):
                errors.append(
                    f"line {entry.line_number}: plan_change {field} must be a non-empty string"
                )

        if record.get("decision_state") not in PLAN_CHANGE_DECISION_STATES:
            errors.append(
                f"line {entry.line_number}: decision_state must be one of {', '.join(sorted(PLAN_CHANGE_DECISION_STATES))}"
            )

        errors.extend(
            validate_optional_string_list(record, "evidence_refs", entry.line_number)
        )
        errors.extend(
            validate_optional_string_list(record, "supersedes", entry.line_number)
        )

    for plan_change_id, lines in plan_change_ids.items():
        if len(lines) > 1:
            errors.append(
                f"duplicate plan_change id {plan_change_id}: lines {', '.join(str(line) for line in lines)}"
            )

    return errors


def validate_metrics_schema(path: Path) -> list[str]:
    if not path.exists():
        return [f"{path}: missing metrics_schema.yaml"]
    if has_symlink_component(path):
        return [f"{path}: refusing to read through symlink"]
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{path}: cannot read file: {exc}"]

    parsed = parse_simple_yaml(content)
    metrics = parsed.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        return [f"{path}: metrics must be a non-empty list"]

    changes = metric_schema_change_records(content)
    if changes and not has_human_gate_approval(path.parent, changes):
        change_ids = ", ".join(changes)
        return [
            f"{path}: HumanGate approval required for metric, split, or baseline changes: {change_ids}"
        ]
    return []


def metric_schema_change_records(content: str) -> list[str]:
    change_records: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    in_changes = False
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            in_changes = stripped == "change_records:"
            if not in_changes and current is not None:
                change_records.append(current)
                current = None
            continue
        if not in_changes:
            continue
        if stripped.startswith("- "):
            if current is not None:
                change_records.append(current)
            current = {}
            remainder = stripped[2:].strip()
            if ":" in remainder:
                key, _, value = remainder.partition(":")
                current[key.strip()] = _unquote(_strip_inline_comment(value).strip())
            continue
        if current is not None and ":" in stripped:
            key, _, value = stripped.partition(":")
            current[key.strip()] = _unquote(_strip_inline_comment(value).strip())
    if current is not None:
        change_records.append(current)

    changes: list[str] = []
    for index, change in enumerate(change_records, start=1):
        field = change.get("field") or change.get("type")
        changed_fields = set()
        if isinstance(field, str):
            changed_fields.add(field.strip().lower())
        fields = change.get("fields")
        if isinstance(fields, str):
            changed_fields.update(part.strip().lower() for part in fields.split(","))
        if changed_fields & {"metric", "metrics", "split", "baseline"}:
            change_id = change.get("id")
            changes.append(str(change_id) if is_nonempty_string(change_id) else f"change-{index}")
    return changes


def has_human_gate_approval(hermes_path: Path, change_ids: list[str]) -> bool:
    approval_records, approval_errors = read_jsonl(hermes_path / APPROVAL_FILE)
    if approval_errors:
        return False
    claim_records, claim_errors = read_jsonl(hermes_path / CLAIM_FILE)
    if claim_errors:
        return False
    evidence_records, evidence_errors = read_jsonl(hermes_path / EVIDENCE_FILE)
    if evidence_errors:
        return False

    claims_by_id = {
        str(entry.value["id"]): entry.value
        for entry in claim_records
        if isinstance(entry.value.get("id"), str)
    }
    evidence_by_id = {
        str(entry.value["id"]): entry.value
        for entry in evidence_records
        if isinstance(entry.value.get("id"), str)
    }
    approved_change_ids: set[str] = set()
    normalized_change_ids = {change_id: change_id.lower() for change_id in change_ids}

    for entry in approval_records:
        approval = entry.value
        if (
            approval.get("type") != "human_approval"
            or approval.get("approver") != "human/root"
            or approval.get("decision") != "approved"
        ):
            continue

        claim_id = approval.get("claim_id")
        if not is_nonempty_string(claim_id):
            continue
        claim = claims_by_id.get(str(claim_id))
        if claim is None or claim.get("state") != "claim_ready":
            continue
        claim_evidence_ids = claim.get("evidence_ids")
        if not isinstance(claim_evidence_ids, list) or not claim_evidence_ids:
            continue
        if any(
            not isinstance(evidence_id, str) or evidence_id not in evidence_by_id
            for evidence_id in claim_evidence_ids
        ):
            continue

        approval_change_ids = approval_change_id_values(approval)
        approved_change_ids.update(
            change_id
            for change_id, normalized in normalized_change_ids.items()
            if normalized in approval_change_ids
        )
        if approved_change_ids.issuperset(change_ids):
            return True
    return False


def approval_change_id_values(approval: dict[str, Any]) -> set[str]:
    values: set[str] = set()

    def add_value(value: Any) -> None:
        if is_nonempty_string(value):
            values.update(part.strip().lower() for part in str(value).split(",") if part.strip())
        elif isinstance(value, list):
            for item in value:
                add_value(item)

    for field in APPROVAL_CHANGE_ID_FIELDS:
        add_value(approval.get(field))
    return values


def artifact_ref_errors(
    record: dict[str, Any],
    line_number: int,
    artifact_index: dict[str, JsonlRecord],
) -> list[str]:
    errors: list[str] = []
    if "artifact_refs" in record:
        errors.extend(validate_optional_string_list(record, "artifact_refs", line_number))
        refs = record.get("artifact_refs")
        if isinstance(refs, list):
            missing = [
                artifact_id
                for artifact_id in refs
                if isinstance(artifact_id, str) and artifact_id not in artifact_index
            ]
            if missing:
                errors.append(
                    f"line {line_number}: missing artifact ids: {', '.join(missing)}; HumanGate required for metric, split, or baseline changes"
                )
    if "command_refs" in record:
        errors.extend(validate_optional_string_list(record, "command_refs", line_number))
    return errors


def validate_worker_records(records: list[JsonlRecord]) -> list[str]:
    errors: list[str] = []
    task_cards: dict[str, list[JsonlRecord]] = {}
    checkpoints: dict[str, dict[str, Any]] = {}
    terminal_jobs: set[str] = set()

    for entry in records:
        errors.extend(validate_required_fields(entry.value, entry.line_number))
        record_type = entry.value.get("type")
        if record_type == "task_card":
            try:
                normalized, _warnings = normalize_task_card(entry.value)
                entry.value = normalized
            except RoleProfileError as exc:
                errors.append(f"line {entry.line_number}: {exc}")
        job_id = entry.value.get("job_id")
        if isinstance(job_id, str):
            if record_type == "task_card":
                task_cards.setdefault(job_id, []).append(entry)
            elif record_type == "checkpoint":
                checkpoints[job_id] = entry.value
            if record_type in TERMINAL_WORKER_RECORD_TYPES:
                terminal_jobs.add(job_id)
        if record_type == "heartbeat":
            if parse_timestamp(entry.value.get("next_check_at")) is None:
                errors.append(
                    f"line {entry.line_number}: invalid heartbeat next_check_at"
                )

    for job_id, entries in task_cards.items():
        if len(entries) > 1:
            lines = ", ".join(str(entry.line_number) for entry in entries)
            errors.append(f"duplicate task_card for job_id {job_id}: lines {lines}")
            continue
        errors.extend(_parent_job_card_errors(entries[0], task_cards))

    active_writers: dict[str, list[JsonlRecord]] = {}
    for job_id, entries in task_cards.items():
        if len(entries) != 1 or job_id in terminal_jobs:
            continue
        entry = entries[0]
        role = entry.value.get("role")
        worktree_id = entry.value.get("worktree_id")
        if role in ACTIVE_WRITER_ROLES and isinstance(worktree_id, str) and worktree_id.strip():
            active_writers.setdefault(worktree_id, []).append(entry)
    for worktree_id, entries in active_writers.items():
        if len(entries) > 1:
            jobs = ", ".join(str(entry.value.get("job_id")) for entry in entries)
            lines = ", ".join(str(entry.line_number) for entry in entries)
            errors.append(
                f"multiple active writers in worktree {worktree_id}: jobs {jobs}; lines {lines}"
            )

    for entry in records:
        value = entry.value
        record_type = value.get("type")
        job_id = value.get("job_id")
        if record_type in {"heartbeat", "checkpoint", "result", "risk", "rejection", "stalled"}:
            if isinstance(job_id, str) and job_id not in task_cards:
                errors.append(
                    f"line {entry.line_number}: missing task_card for job_id {job_id}"
                )
        if record_type == "result" and isinstance(job_id, str):
            entries = task_cards.get(job_id, [])
            card = entries[0].value if len(entries) == 1 else None
            if card is not None:
                errors.extend(_parent_job_result_errors(entry, card))
            if card and not is_change_set_allowed(card, value.get("changed_files", [])):
                errors.append(
                    f"line {entry.line_number}: result changed files violate task_card permissions"
                )
        if record_type == "result" and isinstance(job_id, str):
            entries = task_cards.get(job_id, [])
            card = entries[0].value if len(entries) == 1 else None
            interval = card.get("heartbeat_interval") if card else None
            if interval and job_id not in checkpoints:
                errors.append(
                    f"line {entry.line_number}: missing checkpoint for job_id {job_id}"
                )
            if (
                card
                and card.get("role") == "coder"
                and card.get("profile") != "configuration"
                and is_coder_review_handoff(value)
            ):
                if not has_related_record(
                    records,
                    task_cards,
                    job_id,
                    "runner",
                    {"result"},
                    entry.line_number,
                    CODE_RUNNER_PROFILES,
                ):
                    errors.append(
                        f"line {entry.line_number}: coder review handoff requires runner result"
                    )
                if not has_related_record(
                    records,
                    task_cards,
                    job_id,
                    "reviewer",
                    {"checkpoint", "result"},
                    entry.line_number,
                    CODE_REVIEW_PROFILES,
                ):
                    errors.append(
                        f"line {entry.line_number}: coder review handoff requires reviewer result or checkpoint"
                    )

    return errors


def is_coder_review_handoff(record: dict[str, Any]) -> bool:
    status = record.get("status")
    handoff = record.get("handoff")
    return (
        isinstance(status, str)
        and status.strip().lower() in CODER_REVIEW_HANDOFFS
    ) or (
        isinstance(handoff, str)
        and handoff.strip().lower() in CODER_REVIEW_HANDOFFS
    )


def _parent_job_value(value: dict[str, Any]) -> tuple[bool, str | None]:
    """Return whether a record uses the new parent field and its valid value."""
    if "parent_job_id" not in value:
        return False, None
    parent = value.get("parent_job_id")
    if parent is None:
        return True, None
    if isinstance(parent, str) and parent.strip():
        return True, parent.strip()
    return True, ""


def _parent_job_card_errors(
    entry: JsonlRecord,
    task_cards: dict[str, list[JsonlRecord]],
) -> list[str]:
    card = entry.value
    job_id = card.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        return []
    explicit, parent_job_id = _parent_job_value(card)
    role = card.get("role")
    profile = card.get("profile")
    if not explicit:
        return []
    if parent_job_id == "":
        return [f"line {entry.line_number}: parent_job_id must be a non-empty string or null"]
    if (
        role == "reviewer"
        and profile not in INDEPENDENT_REVIEWER_PROFILES
        and parent_job_id is None
    ):
        return [
            f"line {entry.line_number}: reviewer task_card requires parent_job_id unless profile is closure or safety"
        ]
    if parent_job_id is None:
        return []
    if parent_job_id == job_id:
        return [f"line {entry.line_number}: parent_job_id cannot equal job_id"]
    parent_entries = task_cards.get(parent_job_id, [])
    if len(parent_entries) != 1:
        return [f"line {entry.line_number}: parent_job_id {parent_job_id} has no unique task_card"]
    parent = parent_entries[0].value
    if parent.get("work_package") != card.get("work_package"):
        return [
            f"line {entry.line_number}: parent_job_id {parent_job_id} must use the same work_package"
        ]
    return []


def _parent_job_result_errors(entry: JsonlRecord, card: dict[str, Any]) -> list[str]:
    explicit_card, card_parent = _parent_job_value(card)
    explicit_result, result_parent = _parent_job_value(entry.value)
    if not explicit_card or not explicit_result:
        return []
    if result_parent == "":
        return [f"line {entry.line_number}: result parent_job_id must be a non-empty string or null"]
    if result_parent != card_parent:
        return [f"line {entry.line_number}: result parent_job_id does not match task_card"]
    return []


def _legacy_parent_candidates(
    task_cards: dict[str, list[JsonlRecord]],
    child_job_id: str,
    work_package: Any,
) -> set[str]:
    candidates: set[str] = set()
    for candidate_job_id, entries in task_cards.items():
        if candidate_job_id == child_job_id or len(entries) != 1:
            continue
        candidate = entries[0].value
        if candidate.get("role") == "reviewer":
            continue
        if candidate.get("work_package") == work_package:
            candidates.add(candidate_job_id)
    return candidates


def _record_matches_parent(
    record: dict[str, Any],
    card: dict[str, Any],
    task_cards: dict[str, list[JsonlRecord]],
    parent_job_id: str,
) -> bool:
    explicit_card, card_parent = _parent_job_value(card)
    explicit_record, record_parent = _parent_job_value(record)
    parent_entries = task_cards.get(parent_job_id, [])
    if len(parent_entries) != 1:
        return False
    same_package = parent_entries[0].value.get("work_package") == card.get("work_package")
    if explicit_card:
        return same_package and card_parent == parent_job_id and (
            not explicit_record or record_parent == card_parent
        )
    if explicit_record:
        return same_package and record_parent == parent_job_id
    child_job_id = card.get("job_id")
    if not isinstance(child_job_id, str):
        return False
    # Old records did not carry parent_job_id. Keep compatibility only when
    # same-package ownership has exactly one possible parent; never infer by
    # timestamp or result ordering.
    return _legacy_parent_candidates(
        task_cards,
        child_job_id,
        card.get("work_package"),
    ) == {parent_job_id}


def has_related_record(
    records: list[JsonlRecord],
    task_cards: dict[str, list[JsonlRecord]],
    coder_job_id: str,
    role: str,
    record_types: set[str],
    before_line: int,
    profiles: set[str] | None = None,
) -> bool:
    for entry in records:
        value = entry.value
        if entry.line_number >= before_line or value.get("type") not in record_types:
            continue
        result_job_id = value.get("job_id")
        if not isinstance(result_job_id, str):
            continue
        entries = task_cards.get(result_job_id, [])
        if len(entries) != 1:
            continue
        card = entries[0].value
        if card.get("role") != role:
            continue
        if profiles is not None and card.get("profile") not in profiles:
            continue
        if _record_matches_parent(value, card, task_cards, coder_job_id):
            return True
    return False


def compatibility_warnings(path: Path, kind: str) -> list[str]:
    if kind != "worker" or not path.exists():
        return []
    records, errors = read_jsonl(path)
    if errors:
        return []
    warnings: list[str] = []
    seen: set[str] = set()
    for entry in records:
        if entry.value.get("type") != "task_card":
            continue
        try:
            _normalized, card_warnings = normalize_task_card(entry.value)
        except RoleProfileError:
            continue
        for warning in card_warnings:
            if warning in seen:
                continue
            seen.add(warning)
            message = f"line {entry.line_number}: {warning}"
            warnings.append(message)
        role = entry.value.get("role")
        if role in {"runner", "reviewer"} and "parent_job_id" not in entry.value:
            message = (
                f"line {entry.line_number}: legacy task_card has no parent_job_id; "
                "relationship matching is limited to one unambiguous same-work_package candidate"
            )
            if message not in seen:
                seen.add(message)
                warnings.append(message)
    return warnings


def validate_records(path: Path, kind: str) -> list[str]:
    if kind == "metrics_schema":
        return validate_metrics_schema(path)
    if not path.exists():
        return [f"{path}: missing record file"]
    records, errors = read_jsonl(path)
    if errors:
        return errors
    if kind == "worker":
        errors.extend(validate_worker_records(records))
    elif kind == "artifact":
        errors.extend(validate_artifact_records(records, repo_root(path)))
    elif kind == "provenance":
        errors.extend(validate_provenance_records(records))
    elif kind == "audit":
        errors.extend(validate_audit_records(records))
    elif kind == "service_queue":
        errors.extend(validate_service_queue_records(records))
    elif kind == "run_manifest":
        errors.extend(validate_run_manifest_records(path, records))
    elif kind == "compare":
        errors.extend(validate_compare_records(records))
    elif kind == "plan_change":
        errors.extend(validate_plan_change_records(records))
    else:
        for entry in records:
            errors.extend(validate_required_fields(entry.value, entry.line_number))
    _artifact_records, artifact_errors, artifact_index = load_artifact_context(path)
    if kind in {"evidence", "claim", "approval"}:
        if artifact_errors:
            errors.extend(artifact_errors)
    if kind == "evidence":
        for entry in records:
            if entry.value.get("type") == "evidence":
                errors.extend(
                    artifact_ref_errors(entry.value, entry.line_number, artifact_index)
                )
    if kind == "claim":
        evidence_records, evidence_errors = read_jsonl(path.parent / EVIDENCE_FILE)
        if evidence_errors:
            errors.extend(evidence_errors)
        evidence_by_id = {
            str(entry.value["id"]): entry
            for entry in evidence_records
            if isinstance(entry.value.get("id"), str)
        }
        for entry in records:
            claim = entry.value
            if claim.get("type") == "claim" and claim.get("state") == "claim_ready":
                if not claim.get("evidence_ids"):
                    errors.append(
                        f"line {entry.line_number}: claim_ready requires evidence_ids"
                    )
                    continue
                missing = [
                    evidence_id
                    for evidence_id in claim.get("evidence_ids", [])
                    if evidence_id not in evidence_by_id
                ]
                if missing:
                    errors.append(
                        f"line {entry.line_number}: missing evidence ids: {', '.join(missing)}"
                    )
                    continue
                for evidence_id in claim.get("evidence_ids", []):
                    evidence_entry = evidence_by_id.get(str(evidence_id))
                    if evidence_entry is None:
                        continue
                    errors.extend(
                        artifact_ref_errors(
                            evidence_entry.value,
                            evidence_entry.line_number,
                            artifact_index,
                        )
                    )
    if kind == "approval":
        claim_records, claim_errors = read_jsonl(path.parent / CLAIM_FILE)
        if claim_errors:
            errors.extend(claim_errors)
        claims_by_id = {
            str(entry.value["id"]): entry.value
            for entry in claim_records
            if isinstance(entry.value.get("id"), str)
        }
        evidence_records, evidence_errors = read_jsonl(path.parent / EVIDENCE_FILE)
        if evidence_errors:
            errors.extend(evidence_errors)
        evidence_by_id = {
            str(entry.value["id"]): entry
            for entry in evidence_records
            if isinstance(entry.value.get("id"), str)
        }
        for entry in records:
            approval = entry.value
            if approval.get("type") == "human_approval":
                if approval.get("approver") != "human/root":
                    errors.append(
                        f"line {entry.line_number}: approval approver must be human/root"
                    )
                if approval.get("decision") != "approved":
                    errors.append(
                        f"line {entry.line_number}: approval decision must be approved"
                    )
                claim_id = approval.get("claim_id")
                claim = claims_by_id.get(str(claim_id))
                if claim is None:
                    errors.append(
                        f"line {entry.line_number}: approval references unknown claim_id {claim_id}"
                    )
                elif claim.get("state") != "claim_ready":
                    errors.append(
                        f"line {entry.line_number}: approval requires claim_ready claim_id {claim_id}"
                    )
                else:
                    claim_evidence_ids = claim.get("evidence_ids")
                    if not isinstance(claim_evidence_ids, list) or not claim_evidence_ids:
                        errors.append(
                            f"line {entry.line_number}: approval claim missing evidence ids"
                        )
                    else:
                        missing = [
                            evidence_id
                            for evidence_id in claim_evidence_ids
                            if not isinstance(evidence_id, str)
                            or evidence_id not in evidence_by_id
                        ]
                        if missing:
                            errors.append(
                                f"line {entry.line_number}: approval claim missing evidence ids: {', '.join(str(evidence_id) for evidence_id in missing)}"
                            )
                            continue
                        for evidence_id in claim_evidence_ids:
                            evidence_entry = evidence_by_id.get(str(evidence_id))
                            if evidence_entry is None:
                                continue
                            errors.extend(
                                artifact_ref_errors(
                                    evidence_entry.value,
                                    evidence_entry.line_number,
                                    artifact_index,
                                )
                            )
    return errors


def collect_record_ids(path: Path) -> set[str]:
    records, _ = read_jsonl(path)
    return {
        str(entry.value["id"])
        for entry in records
        if isinstance(entry.value.get("id"), str)
    }


def normalize_path(path: str) -> str | None:
    normalized = path.strip().replace("\\", "/")
    if (
        not normalized
        or normalized.startswith("/")
        or (len(normalized) > 2 and normalized[1] == ":" and normalized[2] == "/")
    ):
        return None
    while normalized.startswith("./"):
        normalized = normalized[2:]
    parts: list[str] = []
    for part in normalized.split("/"):
        if not part or part == ".":
            continue
        if part == "..":
            return None
        parts.append(part)
    if not parts:
        return None
    return "/".join(parts)


def pattern_matches(path: str, pattern: str) -> bool:
    normalized_path = normalize_path(path)
    normalized_pattern = normalize_path(pattern)
    if normalized_path is None or normalized_pattern is None:
        return False
    return match_path_segments(normalized_path.split("/"), normalized_pattern.split("/"))


def match_path_segments(path_parts: list[str], pattern_parts: list[str]) -> bool:
    if not pattern_parts:
        return not path_parts
    head = pattern_parts[0]
    if head == "**":
        if len(pattern_parts) == 1:
            return True
        return any(
            match_path_segments(path_parts[index:], pattern_parts[1:])
            for index in range(len(path_parts) + 1)
        )
    if not path_parts:
        return False
    if not fnmatchcase(path_parts[0], head):
        return False
    return match_path_segments(path_parts[1:], pattern_parts[1:])


def is_allowed_file(path: str, allowed_files: Any) -> bool:
    if not isinstance(allowed_files, list) or not allowed_files:
        return False
    return any(
        isinstance(pattern, str) and pattern_matches(path, pattern)
        for pattern in allowed_files
    )


def is_forbidden_file(path: str, forbidden_files: Any) -> bool:
    if not isinstance(forbidden_files, list):
        return False
    return any(
        isinstance(pattern, str) and pattern_matches(path, pattern)
        for pattern in forbidden_files
    )


def is_change_set_allowed(task_card: dict[str, Any], changed_files: Any) -> bool:
    if not isinstance(changed_files, list):
        return False
    for changed_file in changed_files:
        if not isinstance(changed_file, str):
            return False
        if is_forbidden_file(changed_file, task_card.get("forbidden_files")):
            return False
        if not is_allowed_file(changed_file, task_card.get("allowed_files")):
            return False
    return True


def permission_errors(
    task_card: dict[str, Any],
    changed_files: list[str],
) -> list[str]:
    errors: list[str] = []
    outside = [
        file_path
        for file_path in changed_files
        if not is_allowed_file(file_path, task_card.get("allowed_files"))
    ]
    forbidden = [
        file_path
        for file_path in changed_files
        if is_forbidden_file(file_path, task_card.get("forbidden_files"))
    ]
    if outside:
        errors.append(f"outside allowed_files: {', '.join(outside)}")
    if forbidden:
        errors.append(f"matches forbidden_files: {', '.join(forbidden)}")
    return errors


def latest_records_by_job(records: list[JsonlRecord]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in records:
        job_id = entry.value.get("job_id")
        if isinstance(job_id, str):
            grouped.setdefault(job_id, []).append(entry.value)
    return grouped


def find_task_card(records: list[JsonlRecord], job_id: str) -> dict[str, Any] | None:
    matches = task_card_entries(records, job_id)
    if len(matches) != 1:
        return None
    return matches[0].value


def task_card_entries(records: list[JsonlRecord], job_id: str) -> list[JsonlRecord]:
    return [
        entry
        for entry in records
        if entry.value.get("type") == "task_card" and entry.value.get("job_id") == job_id
    ]


def task_card_error(records: list[JsonlRecord], job_id: str) -> str | None:
    matches = task_card_entries(records, job_id)
    if not matches:
        return f"missing task_card for job_id {job_id}"
    if len(matches) > 1:
        lines = ", ".join(str(entry.line_number) for entry in matches)
        return f"duplicate task_card for job_id {job_id}: lines {lines}"
    return None


def latest_record(
    records: list[JsonlRecord],
    job_id: str,
    record_type: str,
) -> dict[str, Any] | None:
    found: dict[str, Any] | None = None
    for entry in records:
        if entry.value.get("job_id") == job_id and entry.value.get("type") == record_type:
            found = entry.value
    return found


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_interval_seconds(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    units = {"s": 1, "m": 60, "h": 60 * 60}
    text = value.strip().lower()
    if not text:
        return None
    unit = text[-1]
    amount = text[:-1]
    if unit not in units or not amount.isdigit():
        return None
    seconds = int(amount) * units[unit]
    return seconds if seconds > 0 else None


def add_seconds(timestamp: str, seconds: int) -> str | None:
    parsed = parse_timestamp(timestamp)
    if parsed is None:
        return None
    return format_timestamp(parsed + timedelta(seconds=seconds))


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_record_id(prefix: str, slug: str = "runtime") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{stamp}-{slug}"


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def _strip_inline_comment(value: str) -> str:
    in_quote: str | None = None
    for idx, ch in enumerate(value):
        if in_quote:
            if ch == in_quote:
                in_quote = None
            continue
        if ch in ('"', "'"):
            in_quote = ch
            continue
        if ch == "#" and (idx == 0 or value[idx - 1].isspace()):
            return value[:idx]
    return value


def _next_content_line(lines: list[str], start: int) -> tuple[int, str]:
    i = start
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped and not stripped.startswith("#"):
            return i, lines[i]
        i += 1
    return i, ""


def _parse_yaml_block(
    lines: list[str], start: int, min_indent: int, target: dict[str, Any]
) -> int:
    i = start
    current_list: list[Any] | None = None

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        indent = len(line) - len(line.lstrip())
        if indent < min_indent:
            break

        if stripped.startswith("- "):
            if current_list is not None:
                current_list.append(_unquote(stripped[2:].strip()))
            i += 1
        elif ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = _strip_inline_comment(value).strip()
            value = _unquote(value)
            current_list = None

            if value:
                target[key] = value
                i += 1
            else:
                next_i, next_line = _next_content_line(lines, i + 1)
                if next_i >= len(lines):
                    target[key] = {}
                    i = next_i
                elif next_line.strip().startswith("- "):
                    current_list = []
                    target[key] = current_list
                    i += 1
                else:
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent > indent:
                        nested: dict[str, Any] = {}
                        target[key] = nested
                        i = _parse_yaml_block(lines, i + 1, next_indent, nested)
                    else:
                        target[key] = {}
                        i += 1
        else:
            i += 1

    return i


def parse_simple_yaml(content: str) -> dict[str, Any]:
    lines = content.splitlines()
    result: dict[str, Any] = {}
    _parse_yaml_block(lines, 0, 0, result)
    return result


def validate_experiment_config(path: Path) -> list[str]:
    parsed, errors = load_experiment_config(path)
    if errors:
        return errors

    if not isinstance(parsed, dict):
        return [f"{path}: experiment.yaml must be a mapping"]

    missing = [field for field in EXPERIMENT_REQUIRED_FIELDS if field not in parsed]
    if missing:
        return [f"{path}: missing required fields: {', '.join(missing)}"]

    if not isinstance(parsed.get("question"), str) or not parsed["question"].strip():
        return [f"{path}: question must be a non-empty string"]
    if not isinstance(parsed.get("hypothesis"), str) or not parsed["hypothesis"].strip():
        return [f"{path}: hypothesis must be a non-empty string"]
    if not isinstance(parsed.get("dataset"), str) or not parsed["dataset"].strip():
        return [f"{path}: dataset must be a non-empty string"]
    if not isinstance(parsed.get("model"), str) or not parsed["model"].strip():
        return [f"{path}: model must be a non-empty string"]
    if not isinstance(parsed.get("metrics"), list) or not all(
        isinstance(metric, str) and metric.strip() for metric in parsed["metrics"]
    ):
        return [f"{path}: metrics must be a non-empty list of strings"]
    seed = parsed.get("seed")
    if isinstance(seed, str):
        if not seed.isdigit():
            return [f"{path}: seed must be an integer"]
    elif not isinstance(seed, int):
        return [f"{path}: seed must be an integer"]
    if not isinstance(parsed.get("environment"), dict):
        return [f"{path}: environment must be a mapping"]
    if not isinstance(parsed.get("allowed_commands"), list) or not all(
        isinstance(command, str) and command.strip()
        for command in parsed["allowed_commands"]
    ):
        return [f"{path}: allowed_commands must be a non-empty list of strings"]
    if not isinstance(parsed.get("artifact_dir"), str) or not parsed["artifact_dir"].strip():
        return [f"{path}: artifact_dir must be a non-empty string"]

    _, preflight_errors = validate_data_preflight(path, parsed)
    return preflight_errors


def _repo_file(root: Path, value: Any, label: str) -> tuple[Path | None, str | None]:
    if not isinstance(value, str) or not value.strip():
        return None, f"{label} must be a non-empty repository-relative path"
    normalized = value.strip().replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized) or ".." in Path(normalized).parts:
        return None, f"{label} must stay inside the repository"
    candidate = (root / normalized).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError:
        return None, f"{label} must stay inside the repository"
    if not candidate.is_file() or has_symlink_component(candidate):
        return None, f"{label} does not exist as a regular repository file: {normalized}"
    return candidate, None


def _task_requires_data_preflight(path: Path) -> tuple[bool, list[str]]:
    task_path = path.parent.parent / "task.json"
    if not task_path.is_file():
        return False, [
            f"{path}: task.json is missing; formal experiment validation requires task state"
        ]
    if has_symlink_component(task_path):
        return False, [
            f"{path}: task.json cannot be read through a symlink for formal experiment validation"
        ]
    try:
        content = task_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return False, [f"{path}: task.json cannot be read: {exc}"]
    try:
        task = json.loads(content)
    except json.JSONDecodeError as exc:
        return False, [f"{path}: task.json contains invalid JSON: {exc.msg}"]
    if not isinstance(task, dict):
        return False, [f"{path}: task.json must be a mapping"]
    # Legacy non-closure tasks keep their existing experiment behavior. Only
    # closure tasks with an explicit data-changing exploration route require
    # data_preflight.
    if not any(key in task for key in ("closure_state", "hermes_phase", "work_packages")):
        return False, []
    if task.get("research_route") != "exploration":
        return False, []
    fields = task.get("research_change_fields")
    normalized_fields = {
        item.strip().casefold()
        for item in fields
        if isinstance(item, str) and item.strip()
    } if isinstance(fields, list) else set()
    return bool(DATA_PREFLIGHT_CHANGE_FIELDS.intersection(normalized_fields)), []


def _load_preflight_checks(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        content = path.read_text(encoding="utf-8")
        parsed = json.loads(content) if path.suffix.casefold() == ".json" else parse_simple_yaml(content)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return {}, f"data_preflight.checks_ref cannot be parsed: {exc}"
    if not isinstance(parsed, dict):
        return {}, "data_preflight.checks_ref must contain a mapping"
    checks = parsed.get("checks", parsed)
    if not isinstance(checks, dict):
        return {}, "data_preflight.checks_ref checks must be a mapping"
    return checks, None


def validate_data_preflight(
    path: Path,
    experiment: dict[str, Any],
) -> tuple[list[Path], list[str]]:
    required, task_errors = _task_requires_data_preflight(path)
    if task_errors:
        return [], task_errors
    preflight = experiment.get("data_preflight")
    if preflight is None:
        if required:
            return [], [f"{path}: data_preflight is required for exploration changes to dataset, split, or preprocessing"]
        return [], []
    if not isinstance(preflight, dict):
        return [], [f"{path}: data_preflight must be a mapping"]

    errors: list[str] = []
    for field in ("source", "version"):
        if not isinstance(preflight.get(field), str) or not str(preflight[field]).strip():
            errors.append(f"{path}: data_preflight.{field} must be a non-empty string")

    input_manifest = preflight.get("input_manifest")
    data_path = preflight.get("data_path")
    selected = [
        (name, value)
        for name, value in (("input_manifest", input_manifest), ("data_path", data_path))
        if isinstance(value, str) and value.strip()
    ]
    if len(selected) != 1:
        errors.append(f"{path}: data_preflight requires exactly one of input_manifest or data_path")

    root = repo_root(path)
    tracked_paths: list[Path] = []
    data_file: Path | None = None
    if len(selected) == 1:
        field, value = selected[0]
        data_file, error = _repo_file(root, value, f"data_preflight.{field}")
        if error:
            errors.append(f"{path}: {error}")
        elif data_file is not None:
            tracked_paths.append(data_file)

    expected_hash = preflight.get("hash")
    if not isinstance(expected_hash, str) or not is_valid_sha256(expected_hash):
        errors.append(f"{path}: data_preflight.hash must be sha256:<64 lowercase hex>")
    elif data_file is not None:
        actual_hash = sha256_file(data_file)
        if actual_hash != expected_hash:
            errors.append(
                f"{path}: data_preflight hash mismatch for {data_file.relative_to(root).as_posix()}"
            )

    checks_path, checks_error = _repo_file(
        root,
        preflight.get("checks_ref"),
        "data_preflight.checks_ref",
    )
    if checks_error:
        errors.append(f"{path}: {checks_error}")
    elif checks_path is not None:
        tracked_paths.append(checks_path)
        checks, parse_error = _load_preflight_checks(checks_path)
        if parse_error:
            errors.append(f"{path}: {parse_error}")
        else:
            for check in DATA_PREFLIGHT_CHECKS:
                raw = checks.get(check)
                if isinstance(raw, dict):
                    raw = raw.get("status")
                state = str(raw).strip().casefold() if raw is not None else ""
                if state not in DATA_PREFLIGHT_STATES:
                    errors.append(
                        f"{path}: data_preflight check {check} must be checked or not_applicable"
                    )
    return tracked_paths, errors


def parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    return None


def load_experiment_config(path: Path) -> tuple[dict[str, Any], list[str]]:
    if not path.exists():
        return {}, [f"{path}: missing experiment.yaml"]
    if has_symlink_component(path):
        return {}, [f"{path}: refusing to read through symlink"]

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {}, [f"{path}: cannot read file: {exc}"]

    try:
        parsed = parse_simple_yaml(content)
    except Exception as exc:  # pragma: no cover - defensive guard for malformed YAML
        return {}, [f"{path}: cannot parse experiment.yaml: {exc}"]

    if not isinstance(parsed, dict):
        return {}, [f"{path}: experiment.yaml must be a mapping"]
    return parsed, []


def write_experiment_skeleton(path: Path, task: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            "# Task-scoped Hermes experiment config.",
            "",
            'question: "Describe the experiment question."',
            'hypothesis: "Describe the expected result."',
            'dataset: "Describe the dataset or fixture."',
            'model: "Describe the model, command, or system under test."',
            "metrics:",
            '  - "exit_code"',
            "seed: 0",
            "environment:",
            '  os: "ubuntu-24.04"',
            '  shell: "bash"',
            "allowed_commands:",
            '  - "python3"',
            f'artifact_dir: ".trellis/tasks/{task}/hermes/runs"',
            "",
        ]
    )
    path.write_text(content, encoding="utf-8")
    return True


def ensure_run_manifest(path: Path) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    return True


def ensure_worker_records(path: Path) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    return True
