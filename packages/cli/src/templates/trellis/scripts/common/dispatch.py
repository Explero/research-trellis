"""Deterministic Hermes dispatch and result-envelope firewall."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from .closure import (
    ClosureError,
    closure_constraints,
    is_closure_task,
    now_utc,
    package_by_id,
    save_task,
    task_state_lock,
    write_handoff,
)
from .firewall import closure_mode_gate, record_firewall_heartbeat
from .io import path_has_symlink, read_json, write_json_atomic
from .roles import RoleProfileError, normalize_role_profile


DISPATCH_SCHEMA = "hermes-dispatch/v1"
RESULT_SCHEMA = "hermes-result/v1"
MAX_REFS = 3
MAX_DISPATCH_BODY_CHARS = 2000
MAX_CONCLUSION_CHARS = 1200
MAX_RAW_RESULT_CHARS = 16000
MAX_RESULT_LINES = 80
MAX_INVALID_RESULTS = 2
EXECUTION_ROLES = {"coder", "runner"}
TASK_LEVEL_ROLES = {"planner", "researcher", "reviewer"}
INDEPENDENT_REVIEWER_PROFILES = {"closure", "safety"}
PROJECT_CONTEXT_FILES = {
    "background": ".trellis/project/BACKGROUND.md",
    "research_plan": ".trellis/project/RESEARCH_PLAN.md",
    "constraints": ".trellis/project/CONSTRAINTS.md",
}
PROJECT_CONTEXT_BY_ROLE_PROFILE = {
    "planner": {
        "research_design": ("background", "research_plan", "constraints"),
        "task_planning": ("background", "constraints"),
        "root_cause": ("constraints",),
        "method_selection": ("background", "research_plan", "constraints"),
    },
    "researcher": {
        "literature": ("background", "research_plan"),
        "codebase": ("background", "constraints"),
        "external_docs": ("constraints",),
        "prior_art": ("background", "research_plan"),
    },
    "coder": {
        "implementation": ("constraints",),
        "tests": ("constraints",),
        "configuration": ("constraints",),
        "repair": ("constraints",),
    },
    "runner": {
        "experiment": ("research_plan", "constraints"),
        "test": ("constraints",),
        "build": ("constraints",),
        "validation": ("research_plan", "constraints"),
    },
    "reviewer": {
        "quality": ("constraints",),
        "evidence": ("research_plan", "constraints"),
        "claim": ("research_plan", "constraints"),
        "safety": ("constraints",),
        "closure": ("constraints",),
        "statistics": ("research_plan", "constraints"),
    },
}
AGENT_ROLE_ALIASES = {
    "hermes-planner": "planner",
    "hermes-researcher": "researcher",
    "hermes-coder": "coder",
    "hermes-runner": "runner",
    "hermes-reviewer": "reviewer",
    "hermes-scientist": "planner",
    "hermes-literature": "researcher",
    "hermes-evaluator": "reviewer",
    "hermes-claim-reviewer": "reviewer",
    "trellis-implement": "coder",
    "trellis-check": "reviewer",
    "trellis-research": "researcher",
}
JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
ABSOLUTE_USER_PATH_RE = re.compile(
    r"(?i)(?:^|[\s\"'])/(?:home|users)/[^/\s]+/|(?:^|[\s\"'])[A-Z]:[\\/]Users[\\/][^\\/\s]+"
)
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[opusr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{16,}=*"),
    re.compile(r"(?i)\bauthorization\s*:\s*(?:basic|bearer|token)\s+[^\s,;]{8,}"),
    re.compile(r"(?i)\b(?:api[_ -]?key|access[_ -]?token|password|passwd|secret)\s*[:=]\s*[^\s,;]{8,}"),
    re.compile(r"(?i)https?://[^\s/:]+:[^\s/@]+@"),
)
TRACE_USER_PATH_RE = re.compile(
    r"(?i)(^|[\s\"'])(?:/(?:home|users)/[^/\s\"']+(?:/[^\s\"']*)*|[A-Z]:[\\/]Users[\\/][^\\/\s\"']+(?:[\\/][^\s\"']*)*)"
)
TRACE_FEATURES = (
    ("full_diff", re.compile(r"(?m)^(?:diff --git |@@\s+-\d|\+\+\+\s+|---\s+)")),
    ("patch", re.compile(r"(?m)^\*\*\* (?:Begin|End) Patch$")),
    ("search_process", re.compile(r"(?i)(?:tool_call|search process|searched for|grep output|rg output|glob output)")),
    ("stack_trace", re.compile(r"(?m)^\s*(?:Traceback \(most recent call last\):|at \S+ \([^\n]+:\d+:\d+\))")),
)
RESULT_FIELDS = {
    "schema",
    "schema_version",
    "job_id",
    "task_revision",
    "role",
    "profile",
    "parent_job_id",
    "status",
    "conclusion",
    "uncertainties",
    "changed_files",
    "evidence_refs",
    "artifact_refs",
    "run_refs",
    "verification",
    "risks",
    "risk_flags",
    "next_action",
    "review_judgment",
    "decision_requests",
}


class DispatchError(ValueError):
    """A dispatch or result failed a deterministic firewall check."""

    def __init__(self, code: str, message: str, details: list[str] | None = None):
        super().__init__(message)
        self.code = code
        self.details = list(details or [])


def dispatch_dir(task_dir: Path) -> Path:
    return task_dir / "hermes" / "dispatches"


def dispatch_path(task_dir: Path, job_id: str) -> Path:
    _validate_job_id(job_id)
    return dispatch_dir(task_dir) / f"{job_id}.dispatch.json"


def result_path(task_dir: Path, job_id: str) -> Path:
    _validate_job_id(job_id)
    return dispatch_dir(task_dir) / f"{job_id}.result.json"


def _write_task_runtime_json(task_dir: Path, path: Path, value: dict[str, Any]) -> None:
    if task_dir.is_symlink() or path_has_symlink(path, task_dir):
        raise DispatchError("symlink_path", "Hermes dispatch path crosses a symlink")
    if not write_json_atomic(path, value):
        raise DispatchError("write_failed", f"cannot write {path.name}")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def raw_trace_path(repo_root: Path, task_dir: Path, job_id: str) -> Path:
    task_key = hashlib.sha256(str(task_dir.resolve()).encode("utf-8")).hexdigest()[:12]
    return (
        repo_root
        / ".trellis"
        / ".runtime"
        / "hermes-traces"
        / task_key
        / f"{job_id}.raw.jsonl"
    )


def create_dispatch(
    task_dir: Path,
    task: dict[str, Any],
    spec: dict[str, Any],
    repo_root: Path,
) -> tuple[dict[str, Any], list[str]]:
    if not is_closure_task(task):
        raise DispatchError("not_hermes_task", "dispatch is available only for Hermes closure tasks")
    revision = _task_revision(task)
    objective = _required_text(spec.get("objective"), "objective")
    _check_sensitive_text(objective, "objective")
    try:
        normalized = normalize_role_profile(
            spec.get("role"),
            spec.get("profile"),
            context=objective,
            for_write=True,
        )
    except RoleProfileError as exc:
        raise DispatchError("invalid_role_profile", str(exc)) from exc
    if not normalized.dispatchable or normalized.role is None or normalized.profile is None:
        raise DispatchError("invalid_role_profile", "role is not dispatchable")

    role = normalized.role
    profile = normalized.profile
    work_package = _normalize_optional_text(spec.get("work_package"))
    parent_job_id = _normalize_optional_text(spec.get("parent_job_id"))
    constraints = closure_constraints(task)
    allowed_files = _normalize_patterns(spec.get("allowed_files"), "allowed_files")
    forbidden_files = _normalize_patterns(spec.get("forbidden_files"), "forbidden_files")
    handoff_writer = _is_handoff_writer(
        task_dir,
        repo_root,
        role,
        profile,
        work_package,
        allowed_files,
    )
    _validate_handoff_file_boundary(task_dir, repo_root, allowed_files, handoff_writer)
    _validate_role_write_scope(task_dir, repo_root, role, allowed_files)
    _validate_work_package(task, role, work_package, allow_task_handoff=handoff_writer)
    refs = _normalize_refs(
        task_dir,
        repo_root,
        _merged_dispatch_refs(task, spec.get("refs"), repo_root, role, profile),
        role,
    )
    if role == "coder" and not allowed_files:
        raise DispatchError("missing_allowed_files", "coder dispatch requires allowed_files")
    if not forbidden_files:
        forbidden_files = [".env", "**/.env", "**/*secret*", "**/*credential*"]
    forbidden_files = list(dict.fromkeys([
        *forbidden_files,
        *_normalize_patterns(constraints["excluded_paths"], "constraints.excluded_paths"),
    ]))

    requested_job_id = _normalize_optional_text(spec.get("job_id"))
    job_id = requested_job_id or _generated_job_id(
        task_dir.name,
        revision,
        role,
        profile,
        work_package,
        parent_job_id,
        objective,
    )
    _validate_job_id(job_id)
    path = dispatch_path(task_dir, job_id)
    if path.exists():
        raise DispatchError("duplicate_job", f"dispatch already exists for {job_id}")
    _validate_parent_job(
        task_dir,
        task,
        repo_root,
        job_id=job_id,
        role=role,
        profile=profile,
        work_package=work_package,
        parent_job_id=parent_job_id,
    )

    mode = str(task.get("closure_mode") or "lean")
    gate_errors, gate_warnings = closure_mode_gate(
        repo_root,
        mode,
        task_id=str(task.get("id") or task_dir.name),
    )
    if gate_errors:
        gate_warnings.extend(
            f"{message}; dispatch creation is allowed, but execution and close remain blocked"
            for message in gate_errors
        )
    platform = str(spec.get("platform") or "auto").casefold()
    if platform not in {"auto", "claude", "codex"}:
        raise DispatchError("unsupported_platform", "platform must be claude or codex")
    if platform in constraints["excluded_platforms"]:
        raise DispatchError("excluded_platform", f"{platform} is excluded by task constraints")
    blind_review = role == "reviewer" and spec.get("blind_review") is not False
    created_at = now_utc()
    dispatch: dict[str, Any] = {
        "schema": DISPATCH_SCHEMA,
        "schema_version": DISPATCH_SCHEMA,
        "job_id": job_id,
        "task_id": str(task.get("id") or task_dir.name),
        "task_path": _repo_relative(task_dir, repo_root),
        "task_revision": revision,
        "hermes_revision": revision,
        "closure_mode": mode,
        "constraints": constraints,
        "role": role,
        "profile": profile,
        "work_package": work_package,
        "parent_job_id": parent_job_id,
        "handoff_writer": handoff_writer,
        "objective": objective,
        "allowed_refs": refs,
        "refs": refs,
        "allowed_files": allowed_files,
        "forbidden": forbidden_files,
        "forbidden_files": forbidden_files,
        "output_contract": {
            "schema": RESULT_SCHEMA,
            "conclusion_max_chars": MAX_CONCLUSION_CHARS,
            "uncertainties_required": True,
        },
        "worktree_id": str(spec.get("worktree_id") or "main"),
        "heartbeat_interval": str(spec.get("heartbeat_interval") or "5m"),
        "timeout_at": str(spec.get("timeout_at") or _default_timeout()),
        "risk_flags": _string_list(spec.get("risk_flags")),
        "human_gate": str(spec.get("human_gate") or "external human/root approval only"),
        "blind_review": blind_review,
        "platform": platform,
        "status": "validated",
        "invalid_result_attempts": 0,
        "created_at": created_at,
        "created_by": str(spec.get("created_by") or task.get("assignee") or task.get("creator") or "unknown"),
        "validated_at": created_at,
    }
    _validate_dispatch_payload(dispatch)
    body = build_canonical_prompt(dispatch)
    dispatch["body"] = body
    dispatch["audit"] = _dispatch_audit(dispatch)
    _write_task_runtime_json(task_dir, path, dispatch)
    _append_worker_task_card(task_dir, dispatch)
    _append_dispatch_audit(task_dir, dispatch, "dispatch_validated", "allowed", {
        "body_chars": len(body),
        "objective_chars": len(objective),
        "ref_count": len(refs),
    })
    return dispatch, gate_warnings


def load_dispatch(task_dir: Path, job_id: str) -> dict[str, Any]:
    path = dispatch_path(task_dir, job_id)
    if task_dir.is_symlink() or path_has_symlink(path, task_dir):
        raise DispatchError("symlink_path", "dispatch path crosses a symlink")
    value = read_json(path)
    if not isinstance(value, dict):
        raise DispatchError("missing_dispatch", f"missing dispatch for {job_id}")
    return value


def role_for_agent_type(agent_type: str | None) -> str | None:
    if not isinstance(agent_type, str):
        return None
    normalized = agent_type.rsplit(":", 1)[-1].strip().casefold().replace("_", "-")
    return AGENT_ROLE_ALIASES.get(normalized)


def bind_claude_agent(
    task_dir: Path,
    task: dict[str, Any],
    repo_root: Path,
    *,
    agent_type: str,
    agent_id: str,
    session_id: str | None,
) -> dict[str, Any]:
    role = role_for_agent_type(agent_type)
    if role is None or not agent_id:
        raise DispatchError("non_hermes_agent", "agent is not a Hermes dispatch target")
    matches: list[dict[str, Any]] = []
    for path in dispatch_dir(task_dir).glob("*.dispatch.json"):
        value = read_json(path)
        if not isinstance(value, dict):
            continue
        if value.get("agent_id") == agent_id:
            matches.append(value)
            continue
        if value.get("status") != "running" or value.get("platform") != "claude":
            continue
        if value.get("role") != role or value.get("agent_id"):
            continue
        if session_id and value.get("host_session_id") != session_id:
            continue
        matches.append(value)
    if len(matches) != 1:
        raise DispatchError(
            "agent_binding_ambiguous",
            "Claude agent could not be bound to exactly one running dispatch",
        )
    dispatch = matches[0]
    validate_dispatch(task_dir, task, dispatch, repo_root)
    dispatch["agent_id"] = agent_id
    dispatch["agent_type"] = agent_type
    dispatch["agent_bound_at"] = now_utc()
    _write_task_runtime_json(
        task_dir,
        dispatch_path(task_dir, str(dispatch["job_id"])),
        dispatch,
    )
    return dispatch


def load_dispatch_for_agent(task_dir: Path, agent_id: str) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for path in dispatch_dir(task_dir).glob("*.dispatch.json"):
        value = read_json(path)
        if isinstance(value, dict) and value.get("agent_id") == agent_id:
            matches.append(value)
    if len(matches) != 1:
        raise DispatchError("agent_binding_missing", "agent_id is not bound to one dispatch")
    return matches[0]


def validate_agent_binding(
    dispatch: dict[str, Any],
    *,
    agent_id: str | None,
    agent_type: str | None,
    session_id: str | None,
) -> None:
    if not agent_id or dispatch.get("agent_id") != agent_id:
        raise DispatchError("agent_binding_mismatch", "agent_id does not match dispatch")
    role = role_for_agent_type(agent_type)
    if role is None or role != dispatch.get("role"):
        raise DispatchError("agent_binding_mismatch", "agent role does not match dispatch")
    bound_session = dispatch.get("host_session_id")
    if bound_session and session_id and bound_session != session_id:
        raise DispatchError("agent_binding_mismatch", "agent session does not match dispatch")


def validate_dispatch(
    task_dir: Path,
    task: dict[str, Any],
    dispatch: dict[str, Any],
    repo_root: Path,
    *,
    before_execution: bool = True,
) -> list[str]:
    errors: list[str] = []
    try:
        _validate_dispatch_payload(dispatch)
    except DispatchError as exc:
        errors.append(exc.code)
    if dispatch.get("schema") != DISPATCH_SCHEMA or dispatch.get("schema_version") != DISPATCH_SCHEMA:
        errors.append("schema_version")
    try:
        _validate_job_id(dispatch.get("job_id"))
    except DispatchError:
        errors.append("job_id")
    if dispatch.get("task_id") != str(task.get("id") or task_dir.name):
        errors.append("task_id")
    if before_execution and dispatch.get("hermes_revision") != _task_revision(task):
        raise DispatchError(
            "stale_dispatch",
            "dispatch revision does not match current task state",
            [
                f"dispatch_revision={dispatch.get('hermes_revision')}",
                f"current_revision={_task_revision(task)}",
            ],
        )
    if dispatch.get("task_revision") != dispatch.get("hermes_revision"):
        errors.append("task_revision")
    try:
        parent_job_id = _normalize_optional_text(dispatch.get("parent_job_id"))
        if dispatch.get("parent_job_id") != parent_job_id:
            errors.append("parent_job_id")
        _validate_parent_job(
            task_dir,
            task,
            repo_root,
            job_id=str(dispatch.get("job_id") or ""),
            role=str(dispatch.get("role") or ""),
            profile=str(dispatch.get("profile") or ""),
            work_package=_normalize_optional_text(dispatch.get("work_package")),
            parent_job_id=parent_job_id,
        )
    except DispatchError as exc:
        errors.append(exc.code)
    if dispatch.get("allowed_refs") != dispatch.get("refs"):
        errors.append("allowed_refs")
    if dispatch.get("forbidden") != dispatch.get("forbidden_files"):
        errors.append("forbidden")
    if dispatch.get("constraints") != closure_constraints(task):
        errors.append("constraints")
    try:
        normalized = normalize_role_profile(
            dispatch.get("role"),
            dispatch.get("profile"),
            context=str(dispatch.get("objective") or ""),
            for_write=True,
        )
        if normalized.role != dispatch.get("role") or normalized.profile != dispatch.get("profile"):
            errors.append("role_profile")
    except RoleProfileError:
        errors.append("role_profile")
    try:
        handoff_writer = _is_handoff_writer(
            task_dir,
            repo_root,
            str(dispatch.get("role") or ""),
            str(dispatch.get("profile") or ""),
            dispatch.get("work_package"),
            _string_list(dispatch.get("allowed_files")),
        )
        if dispatch.get("handoff_writer") is not handoff_writer:
            errors.append("handoff_writer")
        _validate_handoff_file_boundary(
            task_dir,
            repo_root,
            _string_list(dispatch.get("allowed_files")),
            handoff_writer,
        )
        _validate_work_package(
            task,
            str(dispatch.get("role") or ""),
            dispatch.get("work_package"),
            allow_task_handoff=handoff_writer,
        )
    except DispatchError as exc:
        errors.append(exc.code)
    try:
        expected_refs = _normalize_refs(
            task_dir,
            repo_root,
            _merged_dispatch_refs(
                task,
                dispatch.get("refs"),
                repo_root,
                str(dispatch.get("role") or ""),
                str(dispatch.get("profile") or ""),
            ),
            str(dispatch.get("role") or ""),
        )
        if expected_refs != dispatch.get("refs"):
            errors.append("refs")
    except DispatchError as exc:
        errors.append(exc.code)
    try:
        expected_body = build_canonical_prompt({**dispatch, "body": None, "audit": None})
        if dispatch.get("body") != expected_body:
            errors.append("body_not_canonical")
    except DispatchError as exc:
        errors.append(exc.code)
    if errors:
        raise DispatchError("invalid_dispatch", "dispatch validation failed", sorted(set(errors)))
    return []


def prepare_dispatch_for_agent(
    task_dir: Path,
    task: dict[str, Any],
    repo_root: Path,
    job_id: str,
    *,
    platform: str,
    role: str | None = None,
    hook_active: bool = True,
    session_id: str | None = None,
) -> dict[str, Any]:
    dispatch = load_dispatch(task_dir, job_id)
    validate_dispatch(task_dir, task, dispatch, repo_root)
    if platform in closure_constraints(task)["excluded_platforms"]:
        raise DispatchError("excluded_platform", f"{platform} is excluded by task constraints")
    if role and dispatch.get("role") != role:
        raise DispatchError("role_mismatch", "Agent role does not match validated dispatch")
    mode = str(task.get("closure_mode") or "lean")
    task_id = str(task.get("id") or task_dir.name)
    if hook_active:
        record_firewall_heartbeat(
            repo_root,
            platform,
            "hooks",
            task_id=task_id,
            job_id=job_id,
            session_id=session_id,
        )
    gate_errors, _ = closure_mode_gate(
        repo_root,
        mode,
        platform=platform,
        mechanism="hooks" if hook_active else None,
        task_id=task_id,
        job_id=job_id,
        session_id=session_id if hook_active else None,
    )
    if gate_errors:
        raise DispatchError("firewall_unavailable", gate_errors[0], gate_errors)
    if platform == "claude" and hook_active:
        for active_path in dispatch_dir(task_dir).glob("*.dispatch.json"):
            active = read_json(active_path)
            if not isinstance(active, dict) or active.get("job_id") == job_id:
                continue
            if (
                active.get("status") == "running"
                and active.get("platform") == "claude"
                and active.get("role") == dispatch.get("role")
                and active.get("host_session_id") == session_id
                and not active.get("agent_id")
            ):
                raise DispatchError(
                    "agent_binding_ambiguous",
                    "another unbound Claude dispatch for this role is already running",
                )
    dispatch["status"] = "running"
    dispatch["platform"] = platform
    dispatch["host_session_id"] = session_id
    dispatch["started_at"] = now_utc()
    _write_task_runtime_json(task_dir, dispatch_path(task_dir, job_id), dispatch)
    _append_dispatch_audit(task_dir, dispatch, "dispatch_started", "allowed", {
        "body_chars": len(str(dispatch.get("body") or "")),
        "ref_count": len(dispatch.get("refs") or []),
    })
    return dispatch


def build_canonical_prompt(dispatch: dict[str, Any]) -> str:
    refs = _string_list(dispatch.get("refs"))
    raw_constraints = dispatch.get("constraints")
    constraints: dict[str, Any] = raw_constraints if isinstance(raw_constraints, dict) else {}
    verification_level = constraints.get("validation_level", "targeted")
    excluded_platforms = _string_list(constraints.get("excluded_platforms"))
    excluded_paths = _string_list(constraints.get("excluded_paths"))
    lines = [
        "Hermes Agent Context Firewall dispatch",
        f"job_id: {dispatch.get('job_id')}",
        f"task: {dispatch.get('task_path')} @ revision {dispatch.get('hermes_revision')}",
        f"role: {dispatch.get('role')}:{dispatch.get('profile')}",
        f"work_package: {dispatch.get('work_package') or 'null'}",
        f"parent_job_id: {dispatch.get('parent_job_id') or 'null'}",
        f"objective: {dispatch.get('objective')}",
        "refs: " + (", ".join(refs) if refs else "none"),
        "allowed_files: " + (", ".join(_string_list(dispatch.get("allowed_files"))) or "none"),
        "forbidden_files: " + (", ".join(_string_list(dispatch.get("forbidden_files"))) or "none"),
        "verification_level: " + str(verification_level),
        "excluded_platforms: " + (", ".join(excluded_platforms) or "none"),
        "excluded_paths: " + (", ".join(excluded_paths) or "none"),
        "Read only these refs unless the objective names a deterministic ledger check.",
        "For targeted verification, run only the current work package's directed check and record basic evidence; do not claim completion from chat.",
        "Do not include logs, diffs, search history, tool traces, secrets, or absolute user paths.",
        "Return exactly one JSON object with: schema, job_id, task_revision, role, profile, parent_job_id when present, status(success|failure|blocked), conclusion, evidence_refs, artifact_refs, changed_files, verification, risks, uncertainties, next_action.",
        f"conclusion must be <= {MAX_CONCLUSION_CHARS} characters; uncertainties is required.",
    ]
    if dispatch.get("blind_review"):
        lines.append("Blind review: do not read coder/runner explanations or worker result prose; judge current artifacts and ledgers only.")
    if dispatch.get("handoff_writer"):
        lines.append(
            "Handoff writer: run closure.py handoff for this task. Do not edit task state or other files; report HANDOFF.md as the only changed file."
        )
    body = "\n".join(lines)
    _check_sensitive_text(body, "dispatch body")
    if ABSOLUTE_USER_PATH_RE.search(body):
        raise DispatchError("absolute_user_path", "dispatch body contains an absolute user path")
    if len(body) > MAX_DISPATCH_BODY_CHARS:
        raise DispatchError(
            "dispatch_too_long",
            f"dispatch body exceeds {MAX_DISPATCH_BODY_CHARS} characters",
            [f"body_chars={len(body)}"],
        )
    return body


def accept_result_text(
    task_dir: Path,
    task: dict[str, Any],
    repo_root: Path,
    job_id: str,
    raw_text: str,
) -> dict[str, Any]:
    dispatch = load_dispatch(task_dir, job_id)
    _store_raw_trace(repo_root, task_dir, job_id, raw_text, "agent_result")
    stored = load_sanitized_result(task_dir, job_id)
    if stored is not None and _task_confirms_dispatch(task, dispatch):
        dispatch["status"] = "confirmed" if stored.get("status") == "success" else "failed"
        dispatch["confirmed_revision"] = _task_revision(task)
        dispatch["confirmed_at"] = dispatch.get("confirmed_at") or now_utc()
        _write_task_runtime_json(task_dir, dispatch_path(task_dir, job_id), dispatch)
        return stored
    try:
        validate_dispatch(task_dir, task, dispatch, repo_root)
        result = validate_result_envelope(task_dir, task, dispatch, raw_text, repo_root)
    except DispatchError as exc:
        if exc.code in {"stale_dispatch", "missing_dispatch"}:
            _mark_dispatch_terminal(task_dir, dispatch, "stale", exc.code)
            raise
        _record_invalid_result(task_dir, task, dispatch, exc)
        raise

    with task_state_lock(task_dir):
        current = read_json(task_dir / "task.json")
        if not isinstance(current, dict):
            raise DispatchError("state_confirmation_failed", "cannot reload task state")
        validate_dispatch(task_dir, current, dispatch, repo_root)
        sanitized = _sanitized_result(dispatch, result, raw_text)
        dispatch["status"] = "result_returned"
        dispatch["result_returned_at"] = now_utc()
        _write_task_runtime_json(task_dir, dispatch_path(task_dir, job_id), dispatch)
        _write_task_runtime_json(task_dir, result_path(task_dir, job_id), sanitized)

        updated_task = deepcopy(current)
        _apply_result_state(updated_task, dispatch, sanitized)
        try:
            save_task(task_dir, updated_task, lock_held=True)
            if dispatch.get("handoff_writer") and sanitized["status"] == "success":
                dispatch["status"] = "confirmed"
                dispatch["confirmed_revision"] = _task_revision(updated_task)
                dispatch["confirmed_at"] = now_utc()
                dispatch["result_sha256"] = sanitized["audit"]["result_sha256"]
                _write_task_runtime_json(task_dir, dispatch_path(task_dir, job_id), dispatch)
                write_handoff(task_dir, updated_task, repo_root)
            _append_worker_result(task_dir, dispatch, sanitized)
        except (ClosureError, DispatchError, OSError) as exc:
            raise DispatchError("state_confirmation_failed", "result was stored but state confirmation failed") from exc
        task.clear()
        task.update(updated_task)

        dispatch["status"] = "confirmed" if sanitized["status"] == "success" else "failed"
        dispatch["confirmed_revision"] = _task_revision(task)
        dispatch["confirmed_at"] = now_utc()
        dispatch["result_sha256"] = sanitized["audit"]["result_sha256"]
        try:
            _write_task_runtime_json(task_dir, dispatch_path(task_dir, job_id), dispatch)
        except DispatchError as exc:
            raise DispatchError("state_confirmation_failed", "task state updated but dispatch confirmation failed") from exc
    _append_dispatch_audit(task_dir, dispatch, "result_confirmed", "allowed", sanitized["audit"]["metrics"])
    return sanitized


def _task_confirms_dispatch(task: dict[str, Any], dispatch: dict[str, Any]) -> bool:
    job_id = str(dispatch.get("job_id"))
    if job_id in _string_list(task.get("confirmed_dispatches")):
        return True
    package_id = dispatch.get("work_package")
    if not package_id:
        return False
    try:
        package = package_by_id(task, str(package_id))
    except ClosureError:
        return False
    return job_id in _string_list(package.get("confirmed_dispatches"))


def validate_result_envelope(
    task_dir: Path,
    task: dict[str, Any],
    dispatch: dict[str, Any],
    raw_text: str,
    repo_root: Path,
) -> dict[str, Any]:
    if len(raw_text) > MAX_RAW_RESULT_CHARS:
        raise DispatchError("result_too_long", "result exceeds the raw envelope limit")
    if len(raw_text.splitlines()) > MAX_RESULT_LINES:
        raise DispatchError("long_log", "result contains too many lines")
    _check_sensitive_text(raw_text, "result")
    if ABSOLUTE_USER_PATH_RE.search(raw_text):
        raise DispatchError("absolute_user_path", "result contains an absolute user path")
    for code, pattern in TRACE_FEATURES:
        if pattern.search(raw_text):
            raise DispatchError(code, f"result contains forbidden {code} content")
    if _looks_like_log(raw_text):
        raise DispatchError("long_log", "result resembles a log stream")
    try:
        value = json.loads(raw_text.strip())
    except json.JSONDecodeError as exc:
        raise DispatchError("invalid_json", "result must be exactly one JSON object") from exc
    if not isinstance(value, dict):
        raise DispatchError("invalid_json", "result must be a JSON object")
    unknown = sorted(set(value) - RESULT_FIELDS)
    if unknown:
        raise DispatchError("unknown_result_fields", "result contains unsupported fields", unknown)
    required = {
        "schema",
        "job_id",
        "task_revision",
        "role",
        "profile",
        "status",
        "conclusion",
        "uncertainties",
        "changed_files",
        "evidence_refs",
        "artifact_refs",
        "verification",
        "risks",
        "next_action",
    }
    missing = sorted(required - set(value))
    if missing:
        raise DispatchError("missing_result_fields", "result is missing required fields", missing)
    if value.get("job_id") != dispatch.get("job_id"):
        raise DispatchError("job_mismatch", "result job_id does not match dispatch")
    if value.get("schema") != RESULT_SCHEMA:
        raise DispatchError("result_schema_mismatch", "result schema does not match the canonical envelope")
    if value.get("task_revision") != dispatch.get("task_revision", dispatch.get("hermes_revision")):
        raise DispatchError("result_revision_mismatch", "result task_revision does not match dispatch")
    if value.get("role") != dispatch.get("role") or value.get("profile") != dispatch.get("profile"):
        raise DispatchError("result_role_mismatch", "result role/profile does not match dispatch")
    result_parent_job_id = _normalize_optional_text(value.get("parent_job_id"))
    dispatch_parent_job_id = _normalize_optional_text(dispatch.get("parent_job_id"))
    if "parent_job_id" in value and result_parent_job_id != dispatch_parent_job_id:
        raise DispatchError("result_parent_mismatch", "result parent_job_id does not match dispatch")
    if value.get("status") not in {"success", "failure", "blocked"}:
        raise DispatchError("invalid_result_status", "status must be success, failure, or blocked")
    conclusion = _required_text(value.get("conclusion"), "conclusion")
    if len(conclusion) > MAX_CONCLUSION_CHARS:
        raise DispatchError("conclusion_too_long", "conclusion exceeds 1200 characters")
    if _looks_like_log(conclusion):
        raise DispatchError("long_log", "conclusion resembles a log stream")
    for code, pattern in TRACE_FEATURES:
        if pattern.search(conclusion):
            raise DispatchError(code, f"conclusion contains forbidden {code} content")
    uncertainties = _bounded_string_list(value.get("uncertainties"), "uncertainties", 12, 300)
    changed_files = _bounded_string_list(value.get("changed_files"), "changed_files", 30, 240)
    evidence_refs = _bounded_string_list(value.get("evidence_refs"), "evidence_refs", 30, 160)
    artifact_refs = _bounded_string_list(value.get("artifact_refs", []), "artifact_refs", 30, 160)
    verification = value.get("verification")
    if not isinstance(verification, dict):
        raise DispatchError("invalid_result_field", "verification must be an object")
    _validate_dispatch_payload(verification)
    run_refs = _bounded_string_list(
        verification.get("run_refs", value.get("run_refs", [])),
        "verification.run_refs",
        30,
        160,
    )
    risk_flags = _bounded_string_list(value.get("risks"), "risks", 12, 300)
    decision_requests = _bounded_string_list(value.get("decision_requests", []), "decision_requests", 12, 300)
    next_action = _normalize_optional_text(value.get("next_action")) or "Confirm the result against current task state."
    if len(next_action) > 300:
        raise DispatchError("next_action_too_long", "next_action exceeds 300 characters")
    for path in changed_files:
        _validate_relative_path(path, "changed_files")
    if not _changes_allowed(changed_files, dispatch):
        raise DispatchError("unauthorized_changes", "changed_files violate dispatch permissions")
    role = str(dispatch.get("role") or "")
    profile = str(dispatch.get("profile") or "")
    if role == "runner" and evidence_refs:
        raise DispatchError("runner_evidence_forbidden", "runner results cannot accept evidence_refs")
    _validate_fact_refs(task_dir, role, value.get("status"), evidence_refs, artifact_refs, run_refs)
    judgment = value.get("review_judgment")
    if role == "reviewer" and profile in {"evidence", "claim"}:
        if not isinstance(judgment, dict) or judgment.get("state") not in {
            "proposed",
            "needs_changes",
            "insufficient",
        }:
            raise DispatchError(
                "review_authority_violation",
                "evidence/claim review requires a proposed review_judgment",
            )
    if _contains_close_or_approval_authority(value):
        raise DispatchError(
            "decision_authority_violation",
            "agent results cannot close tasks or create human approval",
        )
    return {
        "schema": RESULT_SCHEMA,
        "schema_version": RESULT_SCHEMA,
        "job_id": value["job_id"],
        "task_revision": value["task_revision"],
        "role": value["role"],
        "profile": value["profile"],
        "parent_job_id": dispatch_parent_job_id,
        "status": value["status"],
        "conclusion": conclusion,
        "uncertainties": uncertainties,
        "changed_files": changed_files,
        "evidence_refs": evidence_refs,
        "artifact_refs": artifact_refs,
        "run_refs": run_refs,
        "verification": {**verification, "run_refs": run_refs},
        "risks": risk_flags,
        "risk_flags": risk_flags,
        "next_action": next_action,
        "review_judgment": judgment,
        "decision_requests": decision_requests,
    }


def load_sanitized_result(task_dir: Path, job_id: str) -> dict[str, Any] | None:
    path = result_path(task_dir, job_id)
    if task_dir.is_symlink() or path_has_symlink(path, task_dir):
        raise DispatchError("symlink_path", "result path crosses a symlink")
    value = read_json(path)
    return value if isinstance(value, dict) else None


def sanitized_summary(task_dir: Path, job_id: str) -> dict[str, Any]:
    dispatch = load_dispatch(task_dir, job_id)
    result = load_sanitized_result(task_dir, job_id)
    if result is not None:
        return {
            field: result.get(field)
            for field in (
                "schema",
                "job_id",
                "task_revision",
                "role",
                "profile",
                "parent_job_id",
                "status",
                "conclusion",
                "uncertainties",
                "changed_files",
                "evidence_refs",
                "artifact_refs",
                "run_refs",
                "verification",
                "risks",
                "risk_flags",
                "next_action",
                "decision_requests",
            )
        }
    status = str(dispatch.get("status") or "unknown")
    attempts = int(dispatch.get("invalid_result_attempts") or 0)
    return {
        "schema": RESULT_SCHEMA,
        "job_id": job_id,
        "task_revision": dispatch.get("task_revision", dispatch.get("hermes_revision")),
        "role": dispatch.get("role"),
        "profile": dispatch.get("profile"),
        "parent_job_id": dispatch.get("parent_job_id"),
        "status": "blocked" if status == "blocked" else status,
        "conclusion": "Result envelope was rejected by the context firewall.",
        "uncertainties": [f"invalid_result_attempts={attempts}"],
        "changed_files": [],
        "evidence_refs": [],
        "artifact_refs": [],
        "run_refs": [],
        "verification": {"status": "invalid", "run_refs": []},
        "risks": ["invalid_result_envelope"],
        "risk_flags": ["invalid_result_envelope"],
        "next_action": str(dispatch.get("next_action") or "Rewrite the result as the required JSON envelope."),
        "decision_requests": [],
    }


def list_dispatches(task_dir: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for path in sorted(dispatch_dir(task_dir).glob("*.dispatch.json")):
        value = read_json(path)
        if not isinstance(value, dict):
            values.append({"job_id": path.name.removesuffix(".dispatch.json"), "status": "invalid"})
            continue
        values.append({
            "job_id": value.get("job_id"),
            "role": value.get("role"),
            "profile": value.get("profile"),
            "work_package": value.get("work_package"),
            "parent_job_id": value.get("parent_job_id"),
            "hermes_revision": value.get("hermes_revision"),
            "status": value.get("status"),
            "invalid_result_attempts": value.get("invalid_result_attempts", 0),
        })
    return values


def supersede_dispatch(
    task_dir: Path,
    task: dict[str, Any],
    repo_root: Path,
    job_id: str,
    *,
    reason: str,
    replacement_job_id: str | None = None,
) -> dict[str, Any]:
    dispatch = load_dispatch(task_dir, job_id)
    if dispatch.get("status") == "confirmed":
        raise DispatchError("confirmed_dispatch", "a confirmed dispatch cannot be superseded")
    if dispatch.get("status") == "superseded":
        return dispatch
    replacement: dict[str, Any] | None = None
    if replacement_job_id:
        replacement = load_dispatch(task_dir, replacement_job_id)
        validate_dispatch(task_dir, task, replacement, repo_root, before_execution=False)
        if replacement.get("work_package") != dispatch.get("work_package"):
            raise DispatchError("replacement_mismatch", "replacement must target the same work package")
        if replacement.get("role") != dispatch.get("role"):
            raise DispatchError("replacement_mismatch", "replacement must use the same role")
    if not reason.strip():
        raise DispatchError("missing_reason", "supersede requires a reason")
    updated = deepcopy(task)
    package_id = dispatch.get("work_package")
    if package_id:
        package = package_by_id(updated, str(package_id))
        package["dispatch_blockers"] = [
            item for item in _string_list(package.get("dispatch_blockers")) if item != job_id
        ]
        if package.get("status") == "blocked" and package.get("blocker") == f"dispatch {job_id} blocked":
            restored = str(package.pop("dispatch_blocked_from_status", "running"))
            package["status"] = restored if restored in {"running", "review"} else "running"
            package["blocker"] = None
    dispatch["status"] = "superseded"
    dispatch["superseded_at"] = now_utc()
    dispatch["supersede_reason"] = reason.strip()
    dispatch["replacement_job_id"] = replacement_job_id
    updated["next_action"] = (
        f"Continue with replacement dispatch {replacement_job_id}."
        if replacement_job_id
        else f"Create a replacement for superseded dispatch {job_id}."
    )
    save_task(task_dir, updated)
    task.clear()
    task.update(updated)
    if replacement is not None:
        replacement["hermes_revision"] = _task_revision(task)
        replacement["task_revision"] = _task_revision(task)
        replacement["body"] = build_canonical_prompt(replacement)
        replacement["audit"] = _dispatch_audit(replacement)
        _write_task_runtime_json(
            task_dir,
            dispatch_path(task_dir, str(replacement["job_id"])),
            replacement,
        )
    _write_task_runtime_json(task_dir, dispatch_path(task_dir, job_id), dispatch)
    _append_dispatch_audit(
        task_dir,
        dispatch,
        "dispatch_superseded",
        "recorded",
        {"replacement_job_id": replacement_job_id or "", "reason": reason.strip()},
    )
    return dispatch


def result_json_schema() -> dict[str, Any]:
    string_array = {"type": "array", "items": {"type": "string"}}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Hermes Result Envelope",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema",
            "job_id",
            "task_revision",
            "role",
            "profile",
            "status",
            "conclusion",
            "uncertainties",
            "changed_files",
            "evidence_refs",
            "artifact_refs",
            "verification",
            "risks",
            "next_action",
        ],
        "properties": {
            "schema": {"type": "string", "const": RESULT_SCHEMA},
            "schema_version": {"type": "string", "const": RESULT_SCHEMA},
            "job_id": {"type": "string", "pattern": JOB_ID_RE.pattern},
            "task_revision": {"type": "integer", "minimum": 0},
            "role": {"type": "string", "enum": ["planner", "researcher", "coder", "runner", "reviewer"]},
            "profile": {"type": "string"},
            "parent_job_id": {"type": ["string", "null"], "pattern": JOB_ID_RE.pattern},
            "status": {"type": "string", "enum": ["success", "failure", "blocked"]},
            "conclusion": {"type": "string", "maxLength": MAX_CONCLUSION_CHARS},
            "uncertainties": string_array,
            "changed_files": string_array,
            "evidence_refs": string_array,
            "artifact_refs": string_array,
            "run_refs": string_array,
            "risk_flags": string_array,
            "verification": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "status": {"type": "string"},
                    "run_refs": string_array,
                    "commands": string_array,
                },
            },
            "risks": string_array,
            "next_action": {"type": "string", "maxLength": 300},
            "review_judgment": {"type": ["object", "null"]},
            "decision_requests": string_array,
        },
    }


def _dispatch_audit(dispatch: dict[str, Any]) -> dict[str, Any]:
    body = str(dispatch.get("body") or "")
    objective = str(dispatch.get("objective") or "")
    return {
        "checks": {
            "schema": "pass",
            "revision": "pass",
            "role_profile": "pass",
            "work_package": "pass",
            "parent_job": "pass",
            "refs": "pass",
            "sensitive_content": "pass",
            "absolute_user_path": "pass",
            "length": "pass",
        },
        "metrics": {
            "body_chars": len(body),
            "objective_chars": len(objective),
            "ref_count": len(dispatch.get("refs") or []),
            "allowed_file_patterns": len(dispatch.get("allowed_files") or []),
            "forbidden_file_patterns": len(dispatch.get("forbidden_files") or []),
            "has_parent_job": dispatch.get("parent_job_id") is not None,
        },
        "dispatch_sha256": _stable_hash(dispatch, {"audit"}),
    }


def _sanitized_result(
    dispatch: dict[str, Any],
    result: dict[str, Any],
    raw_text: str,
) -> dict[str, Any]:
    sanitized = dict(result)
    sanitized["schema"] = RESULT_SCHEMA
    sanitized["task_revision"] = dispatch.get("task_revision", dispatch.get("hermes_revision"))
    sanitized["dispatch_revision"] = dispatch.get("hermes_revision")
    sanitized["role"] = dispatch.get("role")
    sanitized["profile"] = dispatch.get("profile")
    sanitized["parent_job_id"] = dispatch.get("parent_job_id")
    sanitized["work_package"] = dispatch.get("work_package")
    verification = dict(result.get("verification") or {})
    verification["run_refs"] = list(result.get("run_refs") or [])
    verification.setdefault(
        "status",
        "passed" if result.get("status") == "success" and result.get("run_refs") else "not_recorded",
    )
    sanitized["verification"] = verification
    sanitized["risks"] = list(result.get("risk_flags") or [])
    sanitized["confirmed"] = True
    sanitized["audit"] = {
        "checks": {
            "json": "pass",
            "schema": "pass",
            "length": "pass",
            "trace_filter": "pass",
            "sensitive_content": "pass",
            "permissions": "pass",
            "fact_authority": "pass",
        },
        "metrics": {
            "raw_chars": len(raw_text),
            "conclusion_chars": len(result["conclusion"]),
            "uncertainty_count": len(result["uncertainties"]),
            "changed_file_count": len(result["changed_files"]),
            "evidence_ref_count": len(result["evidence_refs"]),
            "artifact_ref_count": len(result["artifact_refs"]),
            "run_ref_count": len(result["run_refs"]),
        },
        "raw_trace_stored": True,
    }
    sanitized["audit"]["result_sha256"] = _stable_hash(sanitized, {"audit"})
    return sanitized


def _record_invalid_result(
    task_dir: Path,
    task: dict[str, Any],
    dispatch: dict[str, Any],
    error: DispatchError,
) -> None:
    with task_state_lock(task_dir):
        current_task = read_json(task_dir / "task.json")
        current_dispatch = read_json(dispatch_path(task_dir, str(dispatch["job_id"])))
        if not isinstance(current_task, dict) or not isinstance(current_dispatch, dict):
            raise DispatchError("state_confirmation_failed", "cannot reload invalid-result state")
        attempts = int(current_dispatch.get("invalid_result_attempts") or 0) + 1
        current_dispatch["invalid_result_attempts"] = attempts
        current_dispatch["last_result_error"] = error.code
        current_dispatch["last_result_error_at"] = now_utc()
        if attempts >= MAX_INVALID_RESULTS:
            current_dispatch["status"] = "blocked"
            current_dispatch["next_action"] = "Create a replacement dispatch after resolving the result-envelope failure."
            updated = deepcopy(current_task)
            package_id = current_dispatch.get("work_package")
            if package_id:
                package = package_by_id(updated, str(package_id))
                blockers = _string_list(package.get("dispatch_blockers"))
                if current_dispatch["job_id"] not in blockers:
                    blockers.append(current_dispatch["job_id"])
                package["dispatch_blockers"] = blockers
                if package.get("status") not in {"done", "deferred", "waived", "blocked"}:
                    package["dispatch_blocked_from_status"] = package.get("status")
                    package["status"] = "blocked"
                    package["blocker"] = f"dispatch {current_dispatch['job_id']} blocked"
            updated["next_action"] = f"Resolve blocked dispatch {current_dispatch['job_id']}; do not complete the package from chat output."
            save_task(task_dir, updated, lock_held=True)
            task.clear()
            task.update(updated)
        else:
            current_dispatch["status"] = "rewrite_required"
            current_dispatch["next_action"] = "Return only the required JSON result envelope."
        dispatch.clear()
        dispatch.update(current_dispatch)
        _write_task_runtime_json(
            task_dir,
            dispatch_path(task_dir, str(dispatch["job_id"])),
            dispatch,
        )
        _append_dispatch_audit(task_dir, dispatch, "result_rejected", "blocked", {
            "invalid_attempt": attempts,
            "error_code": error.code,
        })


def _apply_result_state(
    task: dict[str, Any],
    dispatch: dict[str, Any],
    result: dict[str, Any],
) -> None:
    job_id = str(dispatch["job_id"])
    task_confirmed = _string_list(task.get("confirmed_dispatches"))
    if job_id not in task_confirmed:
        task_confirmed.append(job_id)
    task["confirmed_dispatches"] = task_confirmed
    package_id = dispatch.get("work_package")
    if package_id:
        package = package_by_id(task, str(package_id))
        completed = _string_list(package.get("confirmed_dispatches"))
        if job_id not in completed:
            completed.append(job_id)
        package["confirmed_dispatches"] = completed
        package["dispatch_blockers"] = [
            item for item in _string_list(package.get("dispatch_blockers")) if item != job_id
        ]
    if result["status"] == "success":
        if dispatch.get("role") == "coder":
            task["next_action"] = f"Review confirmed coder result {job_id}, then run package-check."
        elif dispatch.get("role") == "runner":
            task["next_action"] = f"Review run records for {job_id}; evidence must come from ledgers, not runner success."
        elif dispatch.get("role") == "reviewer":
            task["next_action"] = f"Resolve reviewer judgment from {job_id} against current artifacts and ledgers."
        else:
            task["next_action"] = f"Confirm {job_id} against current task state before the next dispatch."
    else:
        if package_id:
            package = package_by_id(task, str(package_id))
            blockers = _string_list(package.get("dispatch_blockers"))
            if job_id not in blockers:
                blockers.append(job_id)
            package["dispatch_blockers"] = blockers
            if package.get("status") not in {"done", "deferred", "waived", "blocked"}:
                package["dispatch_blocked_from_status"] = package.get("status")
                package["status"] = "blocked"
                package["blocker"] = f"dispatch {job_id} blocked"
        task["next_action"] = f"Resolve failed dispatch {job_id}; keep the current package open."


def _apply_failed_execution_state(
    task_dir: Path,
    task: dict[str, Any],
    dispatch: dict[str, Any],
    message: str,
) -> None:
    updated = deepcopy(task)
    updated["next_action"] = f"Resolve failed dispatch {dispatch['job_id']}: {message}"
    package_id = dispatch.get("work_package")
    if package_id:
        package = package_by_id(updated, str(package_id))
        blockers = _string_list(package.get("dispatch_blockers"))
        if dispatch["job_id"] not in blockers:
            blockers.append(dispatch["job_id"])
        package["dispatch_blockers"] = blockers
        if package.get("status") not in {"done", "deferred", "waived", "blocked"}:
            package["dispatch_blocked_from_status"] = package.get("status")
            package["status"] = "blocked"
            package["blocker"] = f"dispatch {dispatch['job_id']} blocked"
    save_task(task_dir, updated)
    task.clear()
    task.update(updated)


def _append_worker_task_card(task_dir: Path, dispatch: dict[str, Any]) -> None:
    record = {
        "type": "task_card",
        "id": f"tc-{dispatch['job_id']}",
        "timestamp": dispatch["created_at"],
        "job_id": dispatch["job_id"],
        "role": dispatch["role"],
        "profile": dispatch["profile"],
        "objective": dispatch["objective"],
        "work_package": dispatch["work_package"],
        "parent_job_id": dispatch["parent_job_id"],
        "hermes_revision": dispatch["hermes_revision"],
        "worktree_id": dispatch["worktree_id"],
        "status": "queued",
        "allowed_files": dispatch["allowed_files"],
        "forbidden_files": dispatch["forbidden_files"],
        "heartbeat_interval": dispatch["heartbeat_interval"],
        "timeout_at": dispatch["timeout_at"],
        "checkpoint": "not-started",
        "resume_from": "validated dispatch",
        "record_uri": f"{dispatch['task_path']}/hermes/worker_records.jsonl",
        "evidence_refs": [],
        "risk_flags": dispatch["risk_flags"],
    }
    _append_jsonl(task_dir / "hermes" / "worker_records.jsonl", record)


def _append_worker_result(
    task_dir: Path,
    dispatch: dict[str, Any],
    result: dict[str, Any],
) -> None:
    worker_path = task_dir / "hermes" / "worker_records.jsonl"
    checkpoint = {
        "type": "checkpoint",
        "id": f"cp-{dispatch['job_id']}",
        "timestamp": now_utc(),
        "job_id": dispatch["job_id"],
        "parent_job_id": dispatch.get("parent_job_id"),
        "checkpoint": "result-envelope-validated",
        "resume_from": "sanitized result",
        "evidence_refs": result["evidence_refs"],
        "open_items": result["uncertainties"],
    }
    _append_jsonl(worker_path, checkpoint)
    record = {
        "type": "result",
        "id": f"rs-{dispatch['job_id']}",
        "timestamp": now_utc(),
        "job_id": dispatch["job_id"],
        "parent_job_id": dispatch.get("parent_job_id"),
        "status": "done" if result["status"] == "success" else result["status"],
        "summary": result["conclusion"],
        "uncertainties": result["uncertainties"],
        "changed_files": result["changed_files"],
        "evidence_refs": result["evidence_refs"],
        "artifact_refs": result["artifact_refs"],
        "run_refs": result["run_refs"],
        "risk_flags": result["risk_flags"],
        "handoff": result["next_action"],
        "work_package": dispatch["work_package"],
        "dispatch_revision": dispatch["hermes_revision"],
    }
    _append_jsonl(worker_path, record)


def _append_dispatch_audit(
    task_dir: Path,
    dispatch: dict[str, Any],
    event: str,
    decision: str,
    metrics: dict[str, Any],
) -> None:
    audit_source = f"{event}:{dispatch.get('job_id')}:{now_utc()}"
    record = {
        "type": "dispatch_audit",
        "id": f"da-{hashlib.sha256(audit_source.encode()).hexdigest()[:16]}",
        "timestamp": now_utc(),
        "job_id": dispatch.get("job_id"),
        "hermes_revision": dispatch.get("hermes_revision"),
        "event": event,
        "decision": decision,
        "metrics": metrics,
    }
    _append_jsonl(task_dir / "hermes" / "dispatch_audit.jsonl", record)


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    task_dir = path.parent.parent
    if task_dir.is_symlink() or path_has_symlink(path, task_dir):
        raise DispatchError("symlink_path", "Hermes record path crosses a symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    record_id = record.get("id")
    if isinstance(record_id, str) and record_id in _jsonl_ids(path):
        return
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    os.chmod(path, 0o600)
    with os.fdopen(descriptor, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _store_raw_trace(
    repo_root: Path,
    task_dir: Path,
    job_id: str,
    raw_text: str,
    source: str,
) -> None:
    path = raw_trace_path(repo_root, task_dir, job_id)
    if path_has_symlink(path, repo_root):
        raise DispatchError("symlink_path", "raw trace path crosses a symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    stored_text, redacted = _redact_sensitive_trace(raw_text)
    record = {
        "timestamp": now_utc(),
        "source": source,
        "chars": len(raw_text),
        "sha256": hashlib.sha256(raw_text.encode("utf-8", errors="replace")).hexdigest(),
        "raw": stored_text,
        "redacted": redacted,
    }
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    os.chmod(path, 0o600)
    with os.fdopen(descriptor, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _redact_sensitive_trace(text: str) -> tuple[str, bool]:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    redacted = TRACE_USER_PATH_RE.sub(
        lambda match: f"{match.group(1)}[REDACTED_PATH]",
        redacted,
    )
    for name, value in os.environ.items():
        if not re.search(r"(?i)(?:token|secret|password|passwd|api[_-]?key|private[_-]?key)", name):
            continue
        if len(value) >= 8:
            redacted = redacted.replace(value, "[REDACTED_ENV]")
    return redacted, redacted != text


def _mark_dispatch_terminal(
    task_dir: Path,
    dispatch: dict[str, Any],
    status: str,
    reason: str,
) -> None:
    dispatch["status"] = status
    dispatch["terminal_reason"] = reason
    dispatch["finished_at"] = now_utc()
    _write_task_runtime_json(
        task_dir,
        dispatch_path(task_dir, str(dispatch["job_id"])),
        dispatch,
    )


def _is_handoff_writer(
    task_dir: Path,
    repo_root: Path,
    role: str,
    profile: str,
    work_package: Any,
    allowed_files: list[str],
) -> bool:
    expected = f"{_repo_relative(task_dir, repo_root)}/HANDOFF.md"
    return (
        role == "coder"
        and profile == "configuration"
        and _normalize_optional_text(work_package) is None
        and allowed_files == [expected]
    )


def _validate_handoff_file_boundary(
    task_dir: Path,
    repo_root: Path,
    allowed_files: list[str],
    handoff_writer: bool,
) -> None:
    expected = f"{_repo_relative(task_dir, repo_root)}/HANDOFF.md"
    if any(_path_matches(expected, pattern) for pattern in allowed_files) and not handoff_writer:
        raise DispatchError(
            "handoff_path_reserved",
            "HANDOFF.md is reserved for the dedicated coder:configuration handoff dispatch",
        )


def _validate_role_write_scope(
    task_dir: Path,
    repo_root: Path,
    role: str,
    allowed_files: list[str],
) -> None:
    if role == "coder" or not allowed_files:
        return
    task_ref = _repo_relative(task_dir, repo_root)
    roots = {
        "planner": [f"{task_ref}/hermes/analysis"],
        "researcher": [f"{task_ref}/research", f"{task_ref}/hermes/research"],
        "reviewer": [f"{task_ref}/hermes/reviews"],
        "runner": [],
    }.get(role, [])
    invalid = [
        pattern
        for pattern in allowed_files
        if not any(pattern == root or pattern.startswith(root + "/") for root in roots)
    ]
    if invalid:
        raise DispatchError(
            "role_write_scope",
            f"{role} allowed_files may only target its task-scoped record directory",
            invalid,
        )


def _validate_parent_job(
    task_dir: Path,
    task: dict[str, Any],
    repo_root: Path,
    *,
    job_id: str,
    role: str,
    profile: str,
    work_package: str | None,
    parent_job_id: str | None,
) -> None:
    """Bind formal review work to one existing job in the same package."""
    requires_parent = role == "reviewer" and profile not in INDEPENDENT_REVIEWER_PROFILES
    if role == "runner" and profile in {"test", "build"}:
        requires_parent = True
    if role == "runner" and profile == "validation" and parent_job_id is None:
        dispatch_dir = task_dir / "hermes" / "dispatches"
        for candidate_path in dispatch_dir.glob("*.dispatch.json"):
            try:
                candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if (
                isinstance(candidate, dict)
                and candidate.get("role") == "coder"
                and candidate.get("work_package") == work_package
                and candidate.get("status") != "superseded"
            ):
                requires_parent = True
                break
    if parent_job_id is None:
        if requires_parent:
            raise DispatchError(
                "missing_parent_job",
                f"{role}:{profile} dispatch requires parent_job_id for the work being checked",
            )
        return
    _validate_job_id(parent_job_id)
    if parent_job_id == job_id:
        raise DispatchError("parent_job_self_reference", "parent_job_id cannot equal job_id")
    parent = load_dispatch(task_dir, parent_job_id)
    if parent.get("job_id") != parent_job_id:
        raise DispatchError("parent_job_invalid", "parent dispatch job_id does not match its record")
    expected_task_id = str(task.get("id") or task_dir.name)
    if parent.get("task_id") != expected_task_id:
        raise DispatchError("parent_job_task_mismatch", "parent dispatch belongs to a different task")
    if parent.get("task_path") != _repo_relative(task_dir, repo_root):
        raise DispatchError("parent_job_task_mismatch", "parent dispatch path does not match this task")
    try:
        parent_work_package = _normalize_optional_text(parent.get("work_package"))
    except DispatchError as exc:
        raise DispatchError("parent_job_invalid", "parent dispatch has an invalid work_package") from exc
    if parent_work_package != work_package:
        raise DispatchError(
            "parent_job_work_package_mismatch",
            "parent dispatch must use the same work_package",
        )


def _validate_work_package(
    task: dict[str, Any],
    role: str,
    work_package: Any,
    *,
    allow_task_handoff: bool = False,
) -> None:
    current = task.get("current_work_package")
    normalized = _normalize_optional_text(work_package)
    if role in EXECUTION_ROLES and not allow_task_handoff:
        if not normalized:
            raise DispatchError("missing_work_package", f"{role} dispatch requires work_package")
        if normalized != current:
            raise DispatchError("work_package_mismatch", "execution dispatch must bind the current work package")
    elif normalized is not None:
        if current is not None and normalized != current:
            raise DispatchError("work_package_mismatch", "dispatch work_package is not current")
    if normalized is not None:
        try:
            package_by_id(task, normalized)
        except ClosureError as exc:
            raise DispatchError("unknown_work_package", str(exc)) from exc


def _normalize_refs(
    task_dir: Path,
    repo_root: Path,
    value: Any,
    role: str,
) -> list[str]:
    refs = _string_list(value)
    if len(refs) > MAX_REFS:
        raise DispatchError("too_many_refs", f"dispatch supports at most {MAX_REFS} refs")
    normalized: list[str] = []
    task_relative_root = _repo_relative(task_dir, repo_root)
    for raw in refs:
        _check_sensitive_text(raw, "ref")
        candidate = raw.replace("\\", "/").strip()
        if candidate.startswith("/") or re.match(r"^[A-Za-z]:/", candidate):
            raise DispatchError("absolute_user_path", "absolute refs are not allowed")
        if candidate.startswith("./"):
            candidate = candidate[2:]
        if "/" not in candidate and (task_dir / candidate).is_file():
            candidate = f"{task_relative_root}/{candidate}"
        resolved = (repo_root / candidate).resolve(strict=False)
        try:
            relative = resolved.relative_to(repo_root.resolve()).as_posix()
        except ValueError as exc:
            raise DispatchError("ref_out_of_bounds", "ref leaves the repository") from exc
        if any(part == ".." for part in Path(candidate).parts) or not resolved.is_file():
            raise DispatchError("invalid_ref", f"ref is not a readable repository file: {raw}")
        lowered = relative.casefold()
        if _sensitive_path(lowered):
            raise DispatchError("sensitive_ref", "sensitive files cannot be dispatch refs")
        if role == "reviewer" and any(
            marker in lowered
            for marker in ("worker_records.jsonl", ".raw.jsonl", ".result.json", "handoff.md")
        ):
            raise DispatchError("blind_review_ref", "blind review cannot reference worker explanations")
        if relative not in normalized:
            normalized.append(relative)
    return normalized


def _merged_dispatch_refs(
    task: dict[str, Any],
    value: Any,
    repo_root: Path,
    role: str,
    profile: str,
) -> list[str]:
    """Keep explicit task context first, then add fitting project context."""
    merged: list[str] = []
    for raw in [*_string_list(task.get("context_pins")), *_string_list(value)]:
        if raw not in merged:
            merged.append(raw)
    if len(merged) >= MAX_REFS:
        return merged

    role_profiles = PROJECT_CONTEXT_BY_ROLE_PROFILE.get(role, {})
    for context_key in role_profiles.get(profile, ()):
        project_ref = PROJECT_CONTEXT_FILES[context_key]
        if not (repo_root / project_ref).is_file() or project_ref in merged:
            continue
        merged.append(project_ref)
        if len(merged) >= MAX_REFS:
            break
    return merged


def _normalize_patterns(value: Any, field: str) -> list[str]:
    patterns = _string_list(value)
    if len(patterns) > 60:
        raise DispatchError("too_many_patterns", f"{field} has too many entries")
    result: list[str] = []
    for pattern in patterns:
        normalized = pattern.replace("\\", "/").strip()
        if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
            raise DispatchError("absolute_user_path", f"{field} cannot contain absolute paths")
        if ".." in Path(normalized).parts or not normalized:
            raise DispatchError("invalid_path_pattern", f"invalid {field} entry")
        while normalized.startswith("./"):
            normalized = normalized[2:]
        if normalized not in result:
            result.append(normalized)
    return result


def _validate_fact_refs(
    task_dir: Path,
    role: str,
    status: Any,
    evidence_refs: list[str],
    artifact_refs: list[str],
    run_refs: list[str],
) -> None:
    evidence_ids = _jsonl_ids(task_dir / "hermes" / "evidence_ledger.jsonl")
    artifact_ids = _jsonl_ids(task_dir / "hermes" / "artifact_ledger.jsonl")
    run_index = _jsonl_index(task_dir / "hermes" / "run_manifest.jsonl")
    run_ids = set(run_index)
    if any(ref not in evidence_ids for ref in evidence_refs):
        raise DispatchError("unknown_evidence_ref", "evidence_refs must already exist in the evidence ledger")
    if any(ref not in artifact_ids for ref in artifact_refs):
        raise DispatchError("unknown_artifact_ref", "artifact_refs must already exist in the artifact ledger")
    if any(ref not in run_ids for ref in run_refs):
        raise DispatchError("unknown_run_ref", "run_refs must already exist in the run manifest")
    if role == "runner" and status == "success" and not run_refs:
        raise DispatchError("missing_run_ref", "runner success requires an existing run_ref")
    if role == "runner" and status == "success" and any(
        run_index[ref].get("exit_code") != 0
        or str(run_index[ref].get("status") or "success").casefold() in {"failed", "failure", "blocked"}
        for ref in run_refs
    ):
        raise DispatchError("failed_run_ref", "runner success requires run_refs with exit_code=0")


def _jsonl_ids(path: Path) -> set[str]:
    return set(_jsonl_index(path))


def _jsonl_index(path: Path) -> dict[str, dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get("id"), str):
            values[value["id"]] = value
    return values


def _changes_allowed(changed_files: list[str], dispatch: dict[str, Any]) -> bool:
    allowed = _string_list(dispatch.get("allowed_files"))
    forbidden = _string_list(dispatch.get("forbidden_files"))
    if not changed_files:
        return True
    for file_path in changed_files:
        if forbidden and any(_path_matches(file_path, pattern) for pattern in forbidden):
            return False
        if not allowed or not any(_path_matches(file_path, pattern) for pattern in allowed):
            return False
    return True


def _path_matches(path: str, pattern: str) -> bool:
    return fnmatchcase(path, pattern) or Path(path).match(pattern)


def _contains_close_or_approval_authority(value: dict[str, Any]) -> bool:
    forbidden_keys = {"closure_state", "hermes_phase", "task_status", "approval", "approved_by"}
    if forbidden_keys.intersection(value):
        return True
    judgment = value.get("review_judgment")
    if isinstance(judgment, dict):
        state = str(judgment.get("state") or "").casefold()
        if state in {"approved", "accepted", "closed", "completed"}:
            return True
    return False


def _looks_like_log(raw_text: str) -> bool:
    log_lines = 0
    pattern = re.compile(r"(?i)^\s*(?:\d{4}-\d{2}-\d{2}[T ][0-9:.+-]+\s+)?(?:DEBUG|INFO|WARN(?:ING)?|ERROR|TRACE)\b")
    for line in raw_text.splitlines():
        if pattern.search(line):
            log_lines += 1
    return log_lines >= 6


def _check_sensitive_text(text: str, field: str) -> None:
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise DispatchError("sensitive_content", f"{field} contains sensitive content")
    for name, value in os.environ.items():
        if not re.search(r"(?i)(?:token|secret|password|passwd|api[_-]?key|private[_-]?key)", name):
            continue
        if len(value) >= 8 and value in text:
            raise DispatchError("environment_secret", f"{field} contains the value of a sensitive environment variable")


def _validate_dispatch_payload(value: dict[str, Any]) -> None:
    list_limits = {
        "refs": MAX_REFS,
        "allowed_files": 60,
        "forbidden_files": 60,
        "risk_flags": 12,
    }
    per_field_chars = {
        "objective": 1200,
        "human_gate": 300,
        "worktree_id": 120,
        "heartbeat_interval": 40,
        "timeout_at": 80,
    }
    for key, item in value.items():
        if key in {"body", "audit"} or item is None:
            continue
        if isinstance(item, str):
            limit = per_field_chars.get(key, 500)
            if len(item) > limit:
                raise DispatchError("dispatch_field_too_long", f"{key} exceeds {limit} characters")
            _check_sensitive_text(item, key)
            if ABSOLUTE_USER_PATH_RE.search(item):
                raise DispatchError("absolute_user_path", f"{key} contains an absolute user path")
        elif isinstance(item, list):
            limit = list_limits.get(key, 60)
            if len(item) > limit:
                raise DispatchError("dispatch_field_too_large", f"{key} exceeds {limit} entries")
            for entry in item:
                if not isinstance(entry, str) or len(entry) > 300:
                    raise DispatchError("invalid_dispatch_field", f"{key} entries must be short strings")
                _check_sensitive_text(entry, key)
                if ABSOLUTE_USER_PATH_RE.search(entry):
                    raise DispatchError("absolute_user_path", f"{key} contains an absolute user path")
        elif isinstance(item, dict):
            _validate_dispatch_payload(item)


def _sensitive_path(value: str) -> bool:
    name = Path(value).name.casefold()
    return (
        name == ".env"
        or name.startswith(".env.")
        or any(marker in name for marker in ("credential", "private_key", "id_rsa", "id_ed25519"))
    )


def _validate_relative_path(value: str, field: str) -> None:
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        raise DispatchError("absolute_user_path", f"{field} must use repository-relative paths")
    if ".." in Path(normalized).parts or not normalized:
        raise DispatchError("path_out_of_bounds", f"{field} contains an invalid path")
    if _sensitive_path(normalized.casefold()):
        raise DispatchError("sensitive_path", f"{field} contains a sensitive path")


def _bounded_string_list(value: Any, field: str, count: int, chars: int) -> list[str]:
    if not isinstance(value, list):
        raise DispatchError("invalid_result_field", f"{field} must be an array of strings")
    result = _string_list(value)
    if len(result) != len(value):
        raise DispatchError("invalid_result_field", f"{field} must contain non-empty strings")
    if len(result) > count or any(len(item) > chars for item in result):
        raise DispatchError("result_field_too_long", f"{field} exceeds its bounded size")
    return result


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DispatchError("missing_field", f"{field} is required")
    return value.strip()


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise DispatchError("invalid_field", "optional text fields must be strings or null")
    stripped = value.strip()
    return stripped or None


def _validate_job_id(value: Any) -> None:
    if not isinstance(value, str) or JOB_ID_RE.fullmatch(value) is None:
        raise DispatchError("invalid_job_id", "job_id must use 1-80 letters, digits, dot, underscore, or dash")


def _generated_job_id(
    task_name: str,
    revision: int,
    role: str,
    profile: str,
    work_package: str | None,
    parent_job_id: str | None,
    objective: str,
) -> str:
    payload = json.dumps(
        [task_name, revision, role, profile, work_package, parent_job_id, objective],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"job-{role}-{digest}"


def _task_revision(task: dict[str, Any]) -> int:
    value = task.get("hermes_revision", 0)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise DispatchError("invalid_revision", "task hermes_revision must be a non-negative integer")
    return value


def _default_timeout() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")


def _repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError as exc:
        raise DispatchError("path_out_of_bounds", "task directory is outside the repository") from exc


def _stable_hash(value: dict[str, Any], omitted: set[str]) -> str:
    payload = {key: item for key, item in value.items() if key not in omitted}
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(serialized.encode('utf-8')).hexdigest()}"


def _codex_capability_errors(codex_bin: str, repo_root: Path) -> list[str]:
    try:
        result = subprocess.run(
            [codex_bin, "exec", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ["codex executable is unavailable"]
    output = f"{result.stdout}\n{result.stderr}"
    if result.returncode != 0:
        return ["codex exec is unavailable"]
    missing = [flag for flag in ("--output-schema", "--json", "-o") if flag not in output]
    return [f"codex exec is missing required capability {flag}" for flag in missing]
