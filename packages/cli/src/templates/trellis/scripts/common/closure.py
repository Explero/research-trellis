"""Lean Research Closure state, audit, capsule, and report helpers."""

from __future__ import annotations

import json
import re
import subprocess
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .firewall import closure_mode_gate
from .io import file_lock, read_json, write_json_atomic, write_text_atomic
from .paths import FILE_TASK_JSON, get_current_task, get_developer, get_repo_root
from .task_utils import resolve_task_dir


CLOSURE_MODES = {"lean", "standard", "publication"}
HERMES_PHASES = {"planning", "ready", "running", "review", "blocked", "closed"}
VALIDATION_LEVELS = {"targeted", "basic", "standard"}
CONSTRAINT_FIELDS = {"excluded_platforms", "excluded_paths", "validation_level"}
RESEARCH_ROUTES = {"delivery", "execution", "exploration"}
RESEARCH_CHANGE_FIELDS = {
    "hypothesis",
    "model_architecture",
    "dataset",
    "split",
    "preprocessing",
    "objective_loss",
    "metric_definition",
    "baseline",
    "claim_scope",
}
RESEARCH_CHANGE_ALIASES = {
    "objective": "objective_loss",
    "loss": "objective_loss",
    "objective/loss": "objective_loss",
}
RESEARCH_ROUTE_LABELS = {
    "delivery": "delivery",
    "execution": "execution",
    "exploration": "exploration",
}
PACKAGE_STATUSES = {
    "pending",
    "ready",
    "running",
    "review",
    "done",
    "blocked",
    "deferred",
    "waived",
}
DISPOSED_PACKAGE_STATUSES = {"done", "deferred", "waived"}
HIGH_RISK_FIELDS = {
    "closure_mode",
    "hypothesis",
    "model_architecture",
    "dataset",
    "split",
    "preprocessing",
    "objective",
    "loss",
    "objective_loss",
    "metric_definition",
    "baseline",
    "claim_scope",
    "in_scope",
    "out_of_scope",
    "max_repair_count",
}
AMENDABLE_CLOSURE_FIELDS = {
    "closure_mode",
    "intent",
    "in_scope",
    "out_of_scope",
    "definition_of_done",
    "context_pins",
    "max_repair_count",
}
AMENDABLE_PACKAGE_FIELDS = {
    "title",
    "outcome",
    "done_when",
    "evidence_required",
    "depends_on",
}
EVENT_TYPES = {
    "phase_changed",
    "package_started",
    "package_completed",
    "package_blocked",
    "plan_amended",
    "research_route_updated",
    "grill_completed",
    "repair_started",
    "task_closed",
}
MICROSTEP_RE = re.compile(
    r"^(?:read|open|inspect|view|modify (?:a )?file|edit (?:a )?file|"
    r"run (?:a |the )?(?:command|script)|check (?:the )?output|"
    r"读取(?:文件)?|打开(?:文件)?|查看(?:文件|输出)?|修改文件|运行(?:命令|脚本))(?:\b|$)",
    re.IGNORECASE,
)
PRD_DONE_HEADINGS = re.compile(
    r"^(?:definition of done|acceptance criteria|验收标准|完成定义|完成条件)\s*$",
    re.IGNORECASE,
)
VALIDATION_ONLY_RE = re.compile(
    r"^(?:(?:unit|integration|e2e|smoke|regression)\s+)?tests?\s+(?:pass|passes)|"
    r"^(?:lint|typecheck|type-check|build|format(?:ting)?)\s+(?:pass|passes)|"
    r"^(?:测试|单元测试|集成测试|回归测试|构建|类型检查|代码检查)(?:全部)?通过$",
    re.IGNORECASE,
)
IMPLEMENT_SECTION_RE = re.compile(
    r"^(?:work\s+packages?|implementation\s+units?|工作包|实施单元)\s*$",
    re.IGNORECASE,
)
IMPLEMENT_UNIT_RE = re.compile(
    r"^(?:(?:work\s+package|package|implementation\s+unit|WP)\s*#?\d*|工作包\s*\d*|实施单元\s*\d*)\s*[:：-]\s*(.+)$",
    re.IGNORECASE,
)
IMPLEMENT_OUTCOME_RE = re.compile(
    r"^(?:[-*]\s*)?(?:outcome|result|deliverable|产出|结果)\s*[:：]\s*(.+)$",
    re.IGNORECASE,
)
IMPLEMENT_DONE_RE = re.compile(
    r"^(?:[-*]\s*)?(?:done\s+when|acceptance|verification|完成条件|验收|验证)\s*[:：]\s*(.*)$",
    re.IGNORECASE,
)


class ClosureError(ValueError):
    """Raised for a user-correctable closure contract violation."""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def default_repair_limit(mode: str) -> int:
    return 1 if mode == "lean" else 2


def is_closure_task(data: dict[str, Any] | None) -> bool:
    return bool(data) and (
        "closure_state" in data
        or "hermes_phase" in data
        or "work_packages" in data
    )


def closure_defaults(mode: str = "lean") -> dict[str, Any]:
    return {
        "hermes_phase": "planning",
        "closure_state": "open",
        "closure_mode": mode,
        "intent": "",
        "in_scope": [],
        "out_of_scope": [],
        "definition_of_done": [],
        "context_pins": [],
        "research_route": "delivery",
        "research_change_fields": [],
        "grill_completed": False,
        "constraints": {
            "excluded_platforms": [],
            "excluded_paths": [],
            "validation_level": "targeted",
        },
        "work_packages": [],
        "current_work_package": None,
        "next_action": None,
        "blockers": [],
        "repair_count": 0,
        "max_repair_count": default_repair_limit(mode),
        "hermes_revision": 0,
        "confirmed_dispatches": [],
    }


def ensure_closure_defaults(data: dict[str, Any], mode: str | None = None) -> None:
    selected_mode = mode or str(data.get("closure_mode") or "lean")
    if selected_mode not in CLOSURE_MODES:
        selected_mode = "lean"
    defaults = closure_defaults(selected_mode)
    for key, value in defaults.items():
        if key not in data:
            data[key] = deepcopy(value)
    constraints = data.get("constraints")
    if not isinstance(constraints, dict):
        data["constraints"] = deepcopy(defaults["constraints"])
    else:
        for key, value in defaults["constraints"].items():
            constraints.setdefault(key, deepcopy(value))
    data["closure_mode"] = selected_mode
    if not isinstance(data.get("max_repair_count"), int):
        data["max_repair_count"] = default_repair_limit(selected_mode)


def resolve_closure_task(
    task_ref: str | None,
    repo_root: Path | None = None,
) -> tuple[Path, dict[str, Any], Path]:
    root = repo_root or get_repo_root()
    resolved_ref = task_ref or get_current_task(root)
    if not resolved_ref:
        raise ClosureError("no task supplied and no active task is available")
    task_dir = resolve_task_dir(resolved_ref, root)
    task_json = task_dir / FILE_TASK_JSON
    if not task_dir.is_dir() or not task_json.is_file():
        raise ClosureError(f"task not found: {resolved_ref}")
    data = read_json(task_json)
    if not isinstance(data, dict):
        raise ClosureError(f"cannot read {task_json}")
    return task_dir, data, root


def task_state_lock(task_dir: Path):
    return file_lock(task_dir / "hermes" / ".task-state.lock")


def save_task(
    task_dir: Path,
    data: dict[str, Any],
    *,
    lock_held: bool = False,
) -> None:
    if not lock_held:
        with task_state_lock(task_dir):
            save_task(task_dir, data, lock_held=True)
        return
    revision = data.get("hermes_revision", 0)
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise ClosureError("hermes_revision must be a non-negative integer")
    current = read_json(task_dir / FILE_TASK_JSON)
    if not isinstance(current, dict):
        raise ClosureError("failed to read current task.json under task lock")
    current_revision = current.get("hermes_revision", 0)
    if current_revision != revision:
        raise ClosureError(
            f"stale task revision: expected {revision}, current {current_revision}"
        )
    data["hermes_revision"] = revision + 1
    if not write_json_atomic(task_dir / FILE_TASK_JSON, data):
        data["hermes_revision"] = revision
        raise ClosureError("failed to write task.json")


def append_event(
    task_dir: Path,
    event_type: str,
    *,
    actor: str,
    old_state: str = "",
    new_state: str = "",
    package_id: str | None = None,
    reason: str = "",
    evidence_refs: list[str] | None = None,
    extra: dict[str, Any] | None = None,
    lock_held: bool = False,
) -> dict[str, Any]:
    if event_type not in EVENT_TYPES:
        raise ClosureError(f"unsupported closure event: {event_type}")
    record: dict[str, Any] = {
        "event_id": f"evt-{uuid.uuid4().hex[:16]}",
        "event_type": event_type,
        "timestamp": now_utc(),
        "actor": actor or "unknown",
        "old_state": old_state,
        "new_state": new_state,
        "package_id": package_id,
        "reason": reason,
        "evidence_refs": list(evidence_refs or []),
    }
    if extra:
        record.update(extra)
    if not lock_held:
        with task_state_lock(task_dir):
            return append_event(
                task_dir,
                event_type,
                actor=actor,
                old_state=old_state,
                new_state=new_state,
                package_id=package_id,
                reason=reason,
                evidence_refs=evidence_refs,
                extra=extra,
                lock_held=True,
            )
    path = task_dir / "hermes" / "task-events.jsonl"
    try:
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError as exc:
        raise ClosureError("failed to read task event log") from exc
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    if not write_text_atomic(path, existing + line):
        raise ClosureError("failed to write task event log")
    return record


def actor_name(root: Path, explicit: str | None = None) -> str:
    return explicit or get_developer(root) or "unknown"


def parse_prd_definition_of_done(prd_path: Path) -> list[str]:
    if not prd_path.is_file():
        return []
    try:
        lines = prd_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    in_section = False
    values: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if PRD_DONE_HEADINGS.match(heading):
                in_section = True
                continue
            if in_section:
                break
        if not in_section:
            continue
        match = re.match(r"^[-*]\s+\[[ xX]\]\s+(.+)$", stripped)
        if match:
            values.append(match.group(1).strip())
    return values


def is_microstep(value: str) -> bool:
    return bool(MICROSTEP_RE.search(value.strip()))


def is_validation_only(value: str) -> bool:
    return bool(VALIDATION_ONLY_RE.search(value.strip()))


def closure_constraints(data: dict[str, Any]) -> dict[str, Any]:
    """Return compatible, bounded closure constraints without mutating a task."""
    raw = data.get("constraints")
    constraints = raw if isinstance(raw, dict) else {}
    platforms = [
        item.casefold()
        for item in _string_list(constraints.get("excluded_platforms"))
    ]
    paths = _string_list(constraints.get("excluded_paths"))
    level = constraints.get("validation_level")
    return {
        "excluded_platforms": _dedupe(platforms),
        "excluded_paths": _dedupe(paths),
        "validation_level": level if level in VALIDATION_LEVELS else "targeted",
    }


def research_route(data: dict[str, Any]) -> str:
    """Return the compatible route for a closure task without mutating it."""
    value = data.get("research_route")
    return value if value in RESEARCH_ROUTES else "delivery"


def research_route_rule(data: dict[str, Any]) -> str:
    route = research_route(data)
    if route == "exploration":
        return "Protocol or functional model change: record a completed grill before validate."
    if route == "execution":
        return "Frozen protocol: run seeds or pre-approved parameter search only."
    return "No protocol change: equivalent refactors and performance work stay delivery."


def research_route_summary(data: dict[str, Any]) -> str:
    route = research_route(data)
    changes = _compact_list(_research_change_fields(data), 3) or "-"
    grill = "complete" if data.get("grill_completed") is True else (
        "required" if route == "exploration" else "not required"
    )
    return (
        f"Route: {RESEARCH_ROUTE_LABELS[route]} | "
        f"Research changes: {changes} | Grill: {grill}"
    )


def _research_change_fields(data: dict[str, Any]) -> list[str]:
    raw = data.get("research_change_fields")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str) and item.strip()]


def _normalize_research_change_fields(values: list[str]) -> list[str]:
    normalized = [RESEARCH_CHANGE_ALIASES.get(value.strip(), value.strip()) for value in values]
    invalid = sorted({value for value in normalized if value not in RESEARCH_CHANGE_FIELDS})
    if invalid:
        raise ClosureError(
            "unknown research change field: " + ", ".join(invalid)
        )
    return _dedupe(normalized)


def _short_title(value: str, index: int) -> str:
    compact = re.sub(r"\s+", " ", value).strip().rstrip("。.")
    if not compact:
        return f"Work package {index}"
    return compact if len(compact) <= 60 else compact[:57].rstrip() + "..."


def candidate_work_packages(
    intent: str,
    definition_of_done: list[str],
) -> list[dict[str, Any]]:
    criteria = [item.strip() for item in definition_of_done if item.strip()]
    outcome = intent.strip() or "Complete the task's observable result"
    return [
        {
            "id": "WP1",
            "title": _short_title(outcome, 1),
            "outcome": outcome,
            "done_when": criteria or [outcome],
            "evidence_required": [],
            "depends_on": [],
            "status": "pending",
            "evidence_refs": [],
            "blocker": None,
        }
    ]


def parse_implement_work_packages(
    implement_path: Path,
    definition_of_done: list[str],
) -> list[dict[str, Any]]:
    """Read explicit implementation units without treating every DoD item as a unit."""
    if not implement_path.is_file():
        return []
    try:
        lines = implement_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    units: list[dict[str, Any]] = []
    section_level: int | None = None
    current: dict[str, Any] | None = None
    collecting_done = False
    for line in lines:
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            level = len(heading.group(1))
            text = heading.group(2).strip()
            if IMPLEMENT_SECTION_RE.match(text):
                section_level = level
                current = None
                collecting_done = False
                continue
            explicit = IMPLEMENT_UNIT_RE.match(text)
            if explicit or (section_level is not None and level > section_level):
                title = (explicit.group(1) if explicit else text).strip()
                current = {"title": title, "outcome": title, "done_when": []}
                units.append(current)
                collecting_done = False
                continue
            if section_level is not None and level <= section_level:
                section_level = None
            current = None
            collecting_done = False
            continue
        if current is None:
            continue
        outcome = IMPLEMENT_OUTCOME_RE.match(line.strip())
        if outcome:
            current["outcome"] = outcome.group(1).strip()
            collecting_done = False
            continue
        done = IMPLEMENT_DONE_RE.match(line.strip())
        if done:
            value = done.group(1).strip()
            if value:
                current["done_when"].append(value)
            collecting_done = True
            continue
        bullet = re.match(r"^\s*[-*]\s+(.+)$", line)
        if collecting_done and bullet:
            current["done_when"].append(bullet.group(1).strip())
        elif line.strip():
            collecting_done = False

    packages: list[dict[str, Any]] = []
    for index, unit in enumerate(units, start=1):
        outcome = str(unit["outcome"]).strip()
        if not outcome:
            continue
        packages.append(
            normalize_package(
                {
                    "id": f"WP{index}",
                    "title": _short_title(str(unit["title"]), index),
                    "outcome": outcome,
                    "done_when": _dedupe(unit["done_when"]) or [outcome],
                },
                index,
            )
        )
    if packages:
        known = " ".join(
            f"{item['title']} {item['outcome']} {' '.join(item['done_when'])}"
            for item in packages
        ).casefold()
        unmatched = [item for item in definition_of_done if item.casefold() not in known]
        if unmatched:
            packages[-1]["done_when"] = _dedupe([*packages[-1]["done_when"], *unmatched])
    return packages


def normalize_package(raw: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": str(raw.get("id") or f"WP{index}"),
        "title": str(raw.get("title") or f"Work package {index}"),
        "outcome": str(raw.get("outcome") or ""),
        "done_when": _string_list(raw.get("done_when")),
        "evidence_required": _string_list(raw.get("evidence_required")),
        "depends_on": _string_list(raw.get("depends_on")),
        "status": str(raw.get("status") or "pending"),
        "evidence_refs": _string_list(raw.get("evidence_refs")),
        "blocker": raw.get("blocker") if isinstance(raw.get("blocker"), str) else None,
    }


def plan_closure(
    task_dir: Path,
    data: dict[str, Any],
    *,
    intent: str | None = None,
    in_scope: list[str] | None = None,
    out_of_scope: list[str] | None = None,
    definition_of_done: list[str] | None = None,
    packages: list[dict[str, Any]] | None = None,
    context_pins: list[str] | None = None,
    mode: str | None = None,
    research_route_name: str | None = None,
    research_change_fields: list[str] | None = None,
) -> list[str]:
    old_phase = str(data.get("hermes_phase") or "planning")
    if is_closure_task(data) and old_phase != "planning":
        raise ClosureError("validated or active plans must change through closure.py amend")
    ensure_closure_defaults(data, mode)
    if intent is not None:
        data["intent"] = intent.strip()
    if not str(data.get("intent") or "").strip():
        data["intent"] = str(data.get("description") or data.get("title") or "").strip()
    if in_scope is not None:
        data["in_scope"] = _dedupe(in_scope)
    if out_of_scope is not None:
        data["out_of_scope"] = _dedupe(out_of_scope)
    if definition_of_done is not None:
        data["definition_of_done"] = _dedupe(definition_of_done)
    if context_pins is not None:
        data["context_pins"] = _dedupe(context_pins)
    normalized_research_changes: list[str] | None = None
    if research_change_fields is not None:
        normalized_research_changes = _normalize_research_change_fields(
            research_change_fields
        )
        if normalized_research_changes:
            if research_route_name in {"delivery", "execution"}:
                raise ClosureError(
                    "research protocol changes require the exploration route"
                )
            if research_route_name is None:
                research_route_name = "exploration"
    if research_route_name is not None:
        if research_route_name not in RESEARCH_ROUTES:
            raise ClosureError("research route must be delivery, execution, or exploration")
        data["research_route"] = research_route_name
        data["grill_completed"] = False
    if normalized_research_changes is not None:
        data["research_change_fields"] = normalized_research_changes
        data["grill_completed"] = False
    if not _string_list(data.get("definition_of_done")):
        data["definition_of_done"] = parse_prd_definition_of_done(task_dir / "prd.md")

    selected = packages
    warnings: list[str] = []
    if selected is None and not isinstance(data.get("work_packages"), list):
        selected = []
    if selected is None and not data.get("work_packages"):
        selected = parse_implement_work_packages(
            task_dir / "implement.md",
            _string_list(data.get("definition_of_done")),
        )
        if not selected:
            selected = candidate_work_packages(
                str(data.get("intent") or ""),
                _string_list(data.get("definition_of_done")),
            )
            warnings.append(
                "No explicit work package or implementation unit found in implement.md; created one safe work package."
            )
    if selected is not None:
        data["work_packages"] = [normalize_package(item, i) for i, item in enumerate(selected, start=1)]

    _reset_incomplete_packages(data)
    data["status"] = "planning"
    data["hermes_phase"] = "planning"
    data["closure_state"] = "open"
    data["current_work_package"] = None
    data["next_action"] = "Run closure.py validate before starting work."
    if mode:
        data["max_repair_count"] = default_repair_limit(str(data["closure_mode"]))
    save_task(task_dir, data)
    count = len(data.get("work_packages") or [])
    if count >= 5:
        warnings.append(
            f"{count} work packages exceed the lean default; consider multiple Trellis tasks."
        )
    return warnings


def set_research_route(
    task_dir: Path,
    data: dict[str, Any],
    *,
    route: str | None,
    research_change_fields: list[str] | None,
    clear_research_changes: bool,
    actor: str,
) -> dict[str, Any]:
    """Record a planning-time research route without adding another workflow."""
    if route is None and research_change_fields is None and not clear_research_changes:
        raise ClosureError("set --route, --research-change, or --clear-research-changes")
    ensure_closure_defaults(data)
    if data.get("hermes_phase") != "planning":
        raise ClosureError("research route can only be marked during planning")
    if route is not None and route not in RESEARCH_ROUTES:
        raise ClosureError("research route must be delivery, execution, or exploration")
    if research_change_fields is not None and clear_research_changes:
        raise ClosureError("cannot combine --research-change with --clear-research-changes")

    before = {
        "research_route": research_route(data),
        "research_change_fields": _research_change_fields(data),
        "grill_completed": data.get("grill_completed") is True,
    }
    normalized_research_changes: list[str] | None = None
    if research_change_fields is not None:
        normalized_research_changes = _normalize_research_change_fields(
            research_change_fields
        )
    next_route = route if route is not None else research_route(data)
    next_fields = (
        normalized_research_changes
        if normalized_research_changes is not None
        else [] if clear_research_changes else _research_change_fields(data)
    )
    if next_fields and next_route in {"delivery", "execution"}:
        if route is not None:
            raise ClosureError("research protocol changes require the exploration route")
        next_route = "exploration"

    data["research_route"] = next_route
    data["research_change_fields"] = next_fields

    changed = before["research_route"] != research_route(data) or (
        before["research_change_fields"] != _research_change_fields(data)
    )
    if changed:
        data["grill_completed"] = False
    data["next_action"] = closure_next_action(data)
    save_task(task_dir, data)
    after = {
        "research_route": research_route(data),
        "research_change_fields": _research_change_fields(data),
        "grill_completed": data.get("grill_completed") is True,
    }
    append_event(
        task_dir,
        "research_route_updated",
        actor=actor,
        old_state=json.dumps(before, ensure_ascii=False, separators=(",", ":")),
        new_state=json.dumps(after, ensure_ascii=False, separators=(",", ":")),
        reason="planning-time research route recorded",
    )
    return after


def mark_grill_complete(
    task_dir: Path,
    data: dict[str, Any],
    *,
    actor: str,
) -> None:
    ensure_closure_defaults(data)
    if data.get("hermes_phase") != "planning":
        raise ClosureError("grill completion can only be marked during planning")
    if research_route(data) != "exploration":
        raise ClosureError("grill completion is only required for exploration")
    if not _research_change_fields(data):
        raise ClosureError("exploration must record at least one research change field")
    if data.get("grill_completed") is True:
        return
    data["grill_completed"] = True
    data["next_action"] = closure_next_action(data)
    save_task(task_dir, data)
    append_event(
        task_dir,
        "grill_completed",
        actor=actor,
        old_state="pending",
        new_state="complete",
        reason="exploration grill completed",
    )


def validate_closure(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if data.get("closure_mode") not in CLOSURE_MODES:
        errors.append("closure_mode must be lean, standard, or publication")
    errors.extend(_validate_research_route(data))
    phase = data.get("hermes_phase")
    closure_state = data.get("closure_state")
    if phase not in HERMES_PHASES:
        errors.append("hermes_phase is invalid")
    if closure_state not in {"open", "closed"}:
        errors.append("closure_state must be open or closed")
    # hermes_phase is authoritative for closure tasks. The legacy status field
    # remains an interoperability hint and must not send ready/running/review
    # work back through the legacy planning workflow.
    task_status = data.get("status")
    if task_status is not None and not isinstance(task_status, str):
        warnings.append("legacy task status is not a string; hermes_phase remains authoritative")
    if phase == "closed" and closure_state != "closed":
        errors.append("closed phase requires closure_state=closed")
    if phase != "closed" and closure_state == "closed":
        errors.append("closure_state=closed requires hermes_phase=closed")
    if phase in {"planning", "ready", "closed"} and data.get("current_work_package") is not None:
        errors.append(f"hermes_phase {phase} cannot have a current work package")
    current_id = data.get("current_work_package")
    current_package = next(
        (
            package for package in data.get("work_packages") or []
            if isinstance(package, dict) and package.get("id") == current_id
        ),
        None,
    )
    if current_id is not None and current_package is None:
        errors.append(f"current_work_package references unknown package {current_id}")
    expected_current_status = {
        "running": "running",
        "review": "review",
        "blocked": "blocked",
    }.get(str(phase))
    if phase == "running" and current_package is None and not any(
        isinstance(package, dict) and package.get("status") in {"pending", "ready"}
        for package in data.get("work_packages") or []
    ):
        errors.append("running phase without a current package requires pending or ready work")
    if current_package is not None and expected_current_status:
        if current_package.get("status") != expected_current_status:
            errors.append(
                f"current package status {current_package.get('status')} conflicts with hermes_phase {phase}"
            )
    for field in ("repair_count", "max_repair_count"):
        value = data.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"{field} must be a non-negative integer")
    revision = data.get("hermes_revision", 0)
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        errors.append("hermes_revision must be a non-negative integer")
    if not str(data.get("intent") or "").strip():
        errors.append("intent is required")
    if not _string_list(data.get("definition_of_done")):
        errors.append("definition_of_done is required")
    if _string_list(data.get("blockers")):
        errors.append("unresolved blockers must be resolved before validation")

    pins = _string_list(data.get("context_pins"))
    if isinstance(data.get("context_pins"), list) and len(pins) != len(data.get("context_pins")):
        errors.append("context_pins must be an array of non-empty strings")
    if len(pins) > 3:
        errors.append("context_pins supports at most 3 entries")
    raw_constraints = data.get("constraints")
    if raw_constraints is not None and not isinstance(raw_constraints, dict):
        errors.append("constraints must be an object")
    elif isinstance(raw_constraints, dict):
        unknown_constraints = sorted(set(raw_constraints) - CONSTRAINT_FIELDS)
        if unknown_constraints:
            errors.append("constraints contains unsupported fields: " + ", ".join(unknown_constraints))
        for field in ("excluded_platforms", "excluded_paths"):
            value = raw_constraints.get(field, [])
            if not isinstance(value, list) or len(_string_list(value)) != len(value):
                errors.append(f"constraints.{field} must be an array of non-empty strings")
        for path in _string_list(raw_constraints.get("excluded_paths")):
            normalized = path.replace("\\", "/")
            if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized) or ".." in Path(normalized).parts:
                errors.append("constraints.excluded_paths must use repository-relative patterns")
                break
        level = raw_constraints.get("validation_level", "targeted")
        if level not in VALIDATION_LEVELS:
            errors.append("constraints.validation_level must be targeted, basic, or standard")

    packages = data.get("work_packages")
    if not isinstance(packages, list) or not packages:
        errors.append("at least one work package is required")
        packages = []
    if len(packages) >= 5:
        warnings.append("5 or more work packages: consider splitting into multiple Trellis tasks")

    ids: list[str] = []
    normalized_packages: list[dict[str, Any]] = []
    for index, raw in enumerate(packages, start=1):
        if not isinstance(raw, dict):
            errors.append(f"WP{index} must be an object")
            continue
        package = normalize_package(raw, index)
        normalized_packages.append(package)
        package_id = package["id"]
        if not package_id:
            errors.append(f"WP{index} id is required")
        elif package_id in ids:
            errors.append(f"duplicate work package id: {package_id}")
        ids.append(package_id)
        if not package["outcome"].strip():
            errors.append(f"{package_id}: outcome is required")
        if not package["title"].strip():
            errors.append(f"{package_id}: title is required")
        if not package["done_when"]:
            errors.append(f"{package_id}: done_when is required")
        if package["status"] not in PACKAGE_STATUSES:
            errors.append(f"{package_id}: invalid status {package['status']}")
        if is_microstep(package["outcome"]):
            errors.append(f"{package_id}: outcome describes a microstep, not an observable result")
        if is_validation_only(package["outcome"]):
            errors.append(f"{package_id}: validation belongs in done_when, not a separate package")

    id_set = set(ids)
    graph: dict[str, list[str]] = {}
    for package in normalized_packages:
        package_id = package["id"]
        deps = package["depends_on"]
        graph[package_id] = deps
        for dependency in deps:
            if dependency not in id_set:
                errors.append(f"{package_id}: unknown dependency {dependency}")
            if dependency == package_id:
                errors.append(f"{package_id}: package cannot depend on itself")
    if _has_dependency_cycle(graph):
        errors.append("work package dependencies contain a cycle")

    in_scope = _string_list(data.get("in_scope"))
    out_scope = _string_list(data.get("out_of_scope"))
    for package in normalized_packages:
        text = f"{package['title']} {package['outcome']}".casefold()
        for excluded in out_scope:
            excluded_text = excluded.casefold().strip()
            if excluded_text and _scope_phrase_in_text(excluded_text, text) and not any(
                _scope_phrase_in_text(excluded_text, item.casefold()) for item in in_scope
            ):
                errors.append(f"{package['id']}: conflicts with out_of_scope item '{excluded}'")
    return _dedupe(errors), _dedupe(warnings)


def _validate_research_route(data: dict[str, Any]) -> list[str]:
    """Validate optional route state while accepting older closure task files."""
    route_present = "research_route" in data
    related_present = any(
        field in data for field in ("research_change_fields", "grill_completed")
    )
    if not route_present and not related_present:
        return []

    errors: list[str] = []
    route = data.get("research_route")
    if route not in RESEARCH_ROUTES:
        return ["research_route must be delivery, execution, or exploration"]
    raw_fields = data.get("research_change_fields")
    if not isinstance(raw_fields, list) or any(
        not isinstance(item, str) or not item.strip() for item in raw_fields
    ):
        errors.append("research_change_fields must be an array of non-empty strings")
        fields: list[str] = []
    else:
        fields = _dedupe(raw_fields)
        invalid = sorted(set(fields) - RESEARCH_CHANGE_FIELDS)
        if invalid:
            errors.append(
                "research_change_fields contains unsupported fields: "
                + ", ".join(invalid)
            )
    grill_completed = data.get("grill_completed")
    if not isinstance(grill_completed, bool):
        errors.append("grill_completed must be a boolean")
    if route == "exploration":
        if not fields:
            errors.append("exploration requires at least one research change field")
        if grill_completed is not True:
            errors.append("exploration requires a completed grill before validation")
    elif fields:
        errors.append("research protocol changes require the exploration route")
    if "model_architecture" in fields and route != "exploration":
        errors.append("model_architecture changes require the exploration route")
    return errors


def validate_and_ready(
    task_dir: Path,
    data: dict[str, Any],
    *,
    actor: str,
) -> tuple[list[str], list[str]]:
    ensure_closure_defaults(data)
    if data.get("closure_state") == "closed":
        return ["closed tasks must be reopened through closure.py plan"], []
    errors, warnings = validate_closure(data)
    if errors:
        return errors, warnings
    old_phase = str(data.get("hermes_phase") or "planning")
    _refresh_ready_packages(data)
    data["hermes_phase"] = "ready"
    data["status"] = "in_progress"
    data["next_action"] = closure_next_action(data)
    save_task(task_dir, data)
    if old_phase != "ready":
        append_event(
            task_dir,
            "phase_changed",
            actor=actor,
            old_state=old_phase,
            new_state="ready",
            reason="closure plan validated",
        )
    return [], warnings


def package_by_id(data: dict[str, Any], package_id: str) -> dict[str, Any]:
    for package in data.get("work_packages") or []:
        if isinstance(package, dict) and package.get("id") == package_id:
            return package
    raise ClosureError(f"unknown work package: {package_id}")


def next_ready_package_id(data: dict[str, Any]) -> str | None:
    """Return the next dependency-ready package without persisting state."""
    _refresh_ready_packages(data)
    package = next(
        (
            item for item in data.get("work_packages") or []
            if isinstance(item, dict) and item.get("status") == "ready"
        ),
        None,
    )
    return str(package.get("id")) if package else None


def start_package(
    task_dir: Path,
    data: dict[str, Any],
    package_id: str | None,
    *,
    actor: str,
    reason: str = "",
) -> dict[str, Any]:
    ensure_closure_defaults(data)
    errors, _ = validate_closure(data)
    if errors:
        raise ClosureError("plan is not valid: " + "; ".join(errors))
    if data.get("hermes_phase") == "planning":
        raise ClosureError("run closure.py validate before starting a package")
    current = data.get("current_work_package")
    if current:
        current_package = package_by_id(data, str(current))
        if current_package.get("status") in {"running", "review", "blocked"}:
            raise ClosureError(f"{current} is still {current_package.get('status')}")
    _refresh_ready_packages(data)
    if package_id:
        package = package_by_id(data, package_id)
    else:
        package = next(
            (item for item in data.get("work_packages") or [] if item.get("status") == "ready"),
            None,
        )
        if package is None:
            raise ClosureError("no ready work package")
    if package.get("status") != "ready":
        raise ClosureError(f"{package.get('id')} is not ready")
    old_phase = str(data.get("hermes_phase") or "ready")
    package["status"] = "running"
    package["blocker"] = None
    data["current_work_package"] = package["id"]
    data["hermes_phase"] = "running"
    data["status"] = "in_progress"
    data["next_action"] = closure_next_action(data)
    save_task(task_dir, data)
    if old_phase != "running":
        append_event(
            task_dir,
            "phase_changed",
            actor=actor,
            old_state=old_phase,
            new_state="running",
            package_id=package["id"],
            reason=reason or "work package started",
        )
    append_event(
        task_dir,
        "package_started",
        actor=actor,
        old_state="ready",
        new_state="running",
        package_id=package["id"],
        reason=reason,
    )
    return package


def check_package(
    task_dir: Path,
    data: dict[str, Any],
    package_id: str | None,
    *,
    actor: str,
) -> dict[str, Any]:
    resolved = package_id or str(data.get("current_work_package") or "")
    if not resolved:
        raise ClosureError("no current work package")
    package = package_by_id(data, resolved)
    if package.get("status") != "running":
        raise ClosureError(f"{resolved} must be running before review")
    dispatch_blockers = _string_list(package.get("dispatch_blockers"))
    if dispatch_blockers:
        raise ClosureError(
            f"{resolved} has unresolved dispatch blockers: {', '.join(dispatch_blockers)}"
        )
    old_phase = str(data.get("hermes_phase") or "running")
    package["status"] = "review"
    data["current_work_package"] = resolved
    data["hermes_phase"] = "review"
    data["status"] = "in_progress"
    data["next_action"] = closure_next_action(data)
    save_task(task_dir, data)
    append_event(
        task_dir,
        "phase_changed",
        actor=actor,
        old_state=old_phase,
        new_state="review",
        package_id=resolved,
        reason="work package entered review",
    )
    return package


def complete_package(
    task_dir: Path,
    data: dict[str, Any],
    package_id: str | None,
    *,
    actor: str,
    evidence_refs: list[str] | None = None,
    disposition: str = "done",
    reason: str = "",
) -> dict[str, Any]:
    if disposition not in DISPOSED_PACKAGE_STATUSES:
        raise ClosureError("disposition must be done, deferred, or waived")
    resolved = package_id or str(data.get("current_work_package") or "")
    if not resolved:
        raise ClosureError("no current work package")
    package = package_by_id(data, resolved)
    old_status = str(package.get("status") or "")
    if old_status in DISPOSED_PACKAGE_STATUSES:
        return package
    current_id = data.get("current_work_package")
    if current_id and current_id != resolved:
        raise ClosureError(f"{current_id} is still the current work package")
    dispatch_blockers = _string_list(package.get("dispatch_blockers"))
    if dispatch_blockers:
        raise ClosureError(
            f"{resolved} has unresolved dispatch blockers: {', '.join(dispatch_blockers)}"
        )
    refs = _dedupe([*package.get("evidence_refs", []), *(evidence_refs or [])])
    if disposition == "done":
        if old_status != "review":
            raise ClosureError(f"{resolved} must be in review before done")
        if not refs:
            raise ClosureError(f"{resolved} requires validation evidence before done")
        invalid_refs = _invalid_evidence_refs(task_dir, refs)
        if invalid_refs:
            raise ClosureError(
                f"{resolved} evidence refs must be existing repository files or evidence ledger ids: "
                + ", ".join(invalid_refs)
            )
        missing_required = _missing_required_evidence(task_dir, package, refs)
        if missing_required:
            raise ClosureError(
                f"{resolved} is missing required evidence: " + ", ".join(missing_required)
            )
    elif not reason.strip():
        raise ClosureError(f"{disposition} requires a reason")
    if disposition == "done":
        _validate_blank_bootstrap_completion(task_dir, data, resolved)
    package["status"] = disposition
    package["evidence_refs"] = refs
    package["blocker"] = None
    data["current_work_package"] = None
    data["blockers"] = [
        item for item in _string_list(data.get("blockers"))
        if resolved not in item
    ]
    _refresh_ready_packages(data)
    if all(
        item.get("status") in DISPOSED_PACKAGE_STATUSES
        for item in data.get("work_packages") or []
    ):
        data["hermes_phase"] = "review"
        data["next_action"] = closure_next_action(data)
    else:
        data["hermes_phase"] = "running"
        data["next_action"] = closure_next_action(data)
    data["status"] = "in_progress"
    save_task(task_dir, data)
    new_phase = str(data.get("hermes_phase") or "running")
    old_phase = "review"
    append_event(
        task_dir,
        "package_completed",
        actor=actor,
        old_state=old_status,
        new_state=disposition,
        package_id=resolved,
        reason=reason,
        evidence_refs=refs,
    )
    if new_phase != old_phase:
        append_event(
            task_dir,
            "phase_changed",
            actor=actor,
            old_state=old_phase,
            new_state=new_phase,
            package_id=resolved,
            reason="work package disposed",
        )
    return package


def block_package(
    task_dir: Path,
    data: dict[str, Any],
    package_id: str | None,
    *,
    actor: str,
    reason: str,
) -> dict[str, Any]:
    resolved = package_id or str(data.get("current_work_package") or "")
    if not resolved:
        raise ClosureError("no current work package")
    if not reason.strip():
        raise ClosureError("block reason is required")
    package = package_by_id(data, resolved)
    old_phase = str(data.get("hermes_phase") or "running")
    old_status = str(package.get("status") or "")
    if old_status in DISPOSED_PACKAGE_STATUSES:
        raise ClosureError("completed packages cannot be blocked")
    package["status"] = "blocked"
    package["blocker"] = reason.strip()
    data["current_work_package"] = resolved
    blocker = f"{resolved}: {reason.strip()}"
    data["blockers"] = _dedupe([*_string_list(data.get("blockers")), blocker])
    data["hermes_phase"] = "blocked"
    data["status"] = "in_progress"
    data["next_action"] = f"Resolve blocker for {resolved}; do not widen task scope."
    save_task(task_dir, data)
    append_event(
        task_dir,
        "package_blocked",
        actor=actor,
        old_state=old_status,
        new_state="blocked",
        package_id=resolved,
        reason=reason,
    )
    if old_phase != "blocked":
        append_event(
            task_dir,
            "phase_changed",
            actor=actor,
            old_state=old_phase,
            new_state="blocked",
            package_id=resolved,
            reason=reason,
        )
    write_handoff(task_dir, data, get_repo_root(task_dir))
    return package


def audit_closure(
    task_dir: Path,
    data: dict[str, Any],
    *,
    write_report: bool = False,
) -> dict[str, Any]:
    gaps: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors, _ = validate_closure(data)
    for error in errors:
        gaps.append(_gap(None, error, "修正 task.json closure plan 后重新 validate"))
    packages = [item for item in data.get("work_packages") or [] if isinstance(item, dict)]
    if data.get("hermes_phase") == "planning":
        gaps.append(_gap(None, "validated closure plan", "运行 closure.py validate"))
    if data.get("hermes_phase") == "blocked":
        gaps.append(_gap(None, "blocked closure phase", "解决阻塞或取得人工批准"))
    for package in packages:
        package_id = str(package.get("id") or "")
        status = package.get("status")
        dispatch_blockers = _string_list(package.get("dispatch_blockers"))
        if dispatch_blockers:
            gaps.append(
                _gap(
                    package_id,
                    f"dispatch blockers: {', '.join(dispatch_blockers)}",
                    "supersede or resolve the blocked dispatch",
                )
            )
        if status not in DISPOSED_PACKAGE_STATUSES:
            gaps.append(_gap(package_id, f"package status is {status}", "完成、defer 或 waive 该工作包"))
        if status == "done":
            evidence_refs = _string_list(package.get("evidence_refs"))
            invalid_refs = _invalid_evidence_refs(task_dir, evidence_refs)
            if not evidence_refs:
                gaps.append(_gap(package_id, "validation evidence", "登记基础验证 evidence_refs"))
            elif invalid_refs:
                gaps.append(
                    _gap(
                        package_id,
                        "invalid evidence refs: " + ", ".join(invalid_refs),
                        "使用已有仓库文件或 evidence ledger id 重新登记证据",
                    )
                )
            missing_required = _missing_required_evidence(task_dir, package, evidence_refs)
            if missing_required:
                gaps.append(
                    _gap(
                        package_id,
                        "required evidence: " + ", ".join(missing_required),
                        "补齐 evidence_required 对应引用",
                    )
                )
    gaps.extend(_blank_bootstrap_gaps(task_dir, data))

    done_clauses = {
        clause.casefold().strip()
        for package in packages
        if package.get("status") == "done"
        for clause in _string_list(package.get("done_when"))
    }
    for item in _string_list(data.get("definition_of_done")):
        normalized = item.casefold().strip()
        if normalized and not any(
            normalized == clause or normalized in clause or clause in normalized
            for clause in done_clauses
        ):
            gaps.append(_gap(None, item, "由已完成工作包覆盖并登记验证证据"))

    blockers = _string_list(data.get("blockers"))
    for blocker in blockers:
        gaps.append(_gap(None, blocker, "解决 blocker 或经批准调整计划"))

    mode = str(data.get("closure_mode") or "lean")
    runtime_errors, runtime_warnings = closure_mode_gate(
        get_repo_root(task_dir),
        mode,
        task_id=str(data.get("id") or task_dir.name),
    )
    for error in runtime_errors:
        gaps.append(_gap(None, "context firewall", error))
    warnings.extend(runtime_warnings)
    gaps.extend(_dispatch_gaps(task_dir, mode))
    if mode in {"standard", "publication"}:
        gaps.extend(_standard_gaps(task_dir))
    if mode == "publication":
        gaps.extend(_publication_gaps(task_dir))

    gaps = _dedupe_gaps(gaps)
    if not gaps and write_report:
        write_closure_report(task_dir, data)
    if not gaps and not (task_dir / "closure-report.md").is_file() and write_report:
        gaps.append(_gap(None, "closure-report.md", "生成简短 closure report"))

    status = "all_met" if not gaps else "blocked" if blockers or data.get("hermes_phase") == "blocked" else "has_gaps"
    return {"status": status, "gaps": gaps, "mode": mode, "warnings": warnings}


def _is_blank_bootstrap(data: dict[str, Any]) -> bool:
    meta = data.get("meta")
    return (
        isinstance(meta, dict)
        and meta.get("hermes_bootstrap_kind") == "blank"
        and str(data.get("id") or "") == "00-bootstrap-guidelines"
    )


def _project_context_has_content(path: Path) -> bool:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for line in lines:
        value = line.strip()
        if not value or value.startswith("#") or value.startswith("<!--"):
            continue
        if re.match(r"^-\s+[^:]+:\s*$", value):
            continue
        return True
    return False


def _first_planned_task(task_dir: Path) -> Path | None:
    for candidate in sorted(task_dir.parent.iterdir()):
        if not candidate.is_dir() or candidate.name in {"archive", task_dir.name}:
            continue
        data = read_json(candidate / FILE_TASK_JSON)
        if not isinstance(data, dict):
            continue
        intent = str(data.get("intent") or "").strip()
        done_when = _string_list(data.get("definition_of_done"))
        packages = data.get("work_packages")
        if intent and intent.casefold() != "tbd" and done_when and all(
            item.casefold() != "tbd" for item in done_when
        ) and isinstance(packages, list) and packages:
            return candidate
    return None


def _blank_bootstrap_gaps(task_dir: Path, data: dict[str, Any]) -> list[dict[str, Any]]:
    if not _is_blank_bootstrap(data):
        return []
    packages = {str(item.get("id")): item for item in data.get("work_packages") or [] if isinstance(item, dict)}
    gaps: list[dict[str, Any]] = []
    wp1 = packages.get("WP1")
    if wp1 and wp1.get("status") == "done":
        missing = [
            name
            for name in ("BACKGROUND.md", "RESEARCH_PLAN.md", "CONSTRAINTS.md")
            if not _project_context_has_content(task_dir.parent.parent / "project" / name)
        ]
        if missing:
            gaps.append(_gap("WP1", "project contract: " + ", ".join(missing), "填写已确认事实后重新登记 WP1"))
    wp2 = packages.get("WP2")
    if wp2 and wp2.get("status") == "done" and _first_planned_task(task_dir) is None:
        gaps.append(_gap("WP2", "planned first task", "创建首个任务并填写 intent、definition_of_done 和 work_packages"))
    return gaps


def _validate_blank_bootstrap_completion(task_dir: Path, data: dict[str, Any], package_id: str) -> None:
    if not _is_blank_bootstrap(data):
        return
    if package_id == "WP1":
        missing = [
            name
            for name in ("BACKGROUND.md", "RESEARCH_PLAN.md", "CONSTRAINTS.md")
            if not _project_context_has_content(task_dir.parent.parent / "project" / name)
        ]
        if missing:
            raise ClosureError("WP1 requires confirmed project context in: " + ", ".join(missing))
    elif package_id == "WP2" and _first_planned_task(task_dir) is None:
        raise ClosureError("WP2 requires a first task with intent, definition_of_done, and work_packages")


def _evidence_ledger_ids(task_dir: Path) -> set[str]:
    return {
        str(item.get("id")).strip()
        for item in _read_jsonl_values(task_dir / "hermes" / "evidence_ledger.jsonl")
        if isinstance(item.get("id"), str) and str(item.get("id")).strip()
    }


def _repository_evidence_ref(task_dir: Path, reference: str) -> str | None:
    normalized = reference.replace("\\", "/").strip()
    if (
        not normalized
        or normalized.startswith("/")
        or re.match(r"^[A-Za-z]:/", normalized)
        or ".." in Path(normalized).parts
    ):
        return None
    root = get_repo_root(task_dir).resolve()
    try:
        candidate = (root / normalized).resolve(strict=True)
        relative = candidate.relative_to(root)
    except (OSError, ValueError):
        return None
    if not candidate.is_file():
        return None
    return relative.as_posix()


def _invalid_evidence_refs(task_dir: Path, refs: list[str]) -> list[str]:
    ledger_ids = _evidence_ledger_ids(task_dir)
    invalid: list[str] = []
    for reference in refs:
        normalized = reference.strip()
        if normalized in ledger_ids or _repository_evidence_ref(task_dir, normalized):
            continue
        invalid.append(reference)
    return _dedupe(invalid)


def _missing_required_evidence(
    task_dir: Path,
    package: dict[str, Any],
    refs: list[str],
) -> list[str]:
    required = _string_list(package.get("evidence_required"))
    if not required:
        return []
    valid_refs = [ref for ref in refs if ref not in _invalid_evidence_refs(task_dir, refs)]
    if len(valid_refs) < len(required):
        return ["sufficient evidence refs"]
    file_refs = {
        normalized
        for ref in valid_refs
        if (normalized := _repository_evidence_ref(task_dir, ref)) is not None
    }
    missing: list[str] = []
    for requirement in required:
        required_file = _repository_evidence_ref(task_dir, requirement)
        if required_file is not None and required_file not in file_refs:
            missing.append(requirement)
    return _dedupe(missing)


def repair_closure(
    task_dir: Path,
    data: dict[str, Any],
    *,
    actor: str,
) -> dict[str, Any]:
    ensure_closure_defaults(data)
    before = audit_closure(task_dir, data, write_report=False)
    if before["status"] == "all_met":
        return before
    has_package_gap = any(gap.get("package") for gap in before.get("gaps") or [])
    if before["status"] == "blocked" and not has_package_gap:
        data["hermes_phase"] = "blocked"
        data["status"] = "in_progress"
        data["next_action"] = "Resolve the recorded blocker or obtain required human approval."
        save_task(task_dir, data)
        write_handoff(task_dir, data, get_repo_root(task_dir))
        return before
    count = int(data.get("repair_count") or 0)
    limit = int(data.get("max_repair_count") or default_repair_limit(str(data.get("closure_mode"))))
    if count >= limit:
        return _block_repair_limit(task_dir, data, actor, before, count, limit)
    data["repair_count"] = count + 1
    old_phase = str(data.get("hermes_phase") or "review")
    repair_package = _prepare_repair_package(data, before)
    if repair_package and repair_package.get("status") == "running":
        data["hermes_phase"] = "running"
    elif repair_package and repair_package.get("status") == "review":
        data["hermes_phase"] = "review"
    else:
        data["hermes_phase"] = "review"
    data["status"] = "in_progress"
    repair_gap = next(
        (
            gap for gap in before.get("gaps") or []
            if repair_package and gap.get("package") == repair_package.get("id")
        ),
        before["gaps"][0] if before.get("gaps") else None,
    )
    data["next_action"] = str(repair_gap["action"]) if repair_gap else "Re-run audit."
    save_task(task_dir, data)
    append_event(
        task_dir,
        "repair_started",
        actor=actor,
        old_state=old_phase,
        new_state=str(data["hermes_phase"]),
        package_id=str(repair_package.get("id")) if repair_package else None,
        reason="; ".join(str(item["missing"]) for item in before["gaps"][:3]),
    )
    after = audit_closure(task_dir, data, write_report=True)
    return after


def amend_plan(
    task_dir: Path,
    data: dict[str, Any],
    *,
    field: str,
    new_value: Any,
    reason: str,
    actor: str,
    affected_packages: list[str] | None = None,
    approved_by: str | None = None,
) -> dict[str, Any]:
    if not field or not reason.strip():
        raise ClosureError("field and change reason are required")
    _validate_amend_field(data, field)
    for package_id in affected_packages or []:
        package_by_id(data, package_id)
    root_field = field.split(".", 1)[0]
    risk_field = field.split(".")[-1]
    research_parts = _research_field_parts(field)
    research_change = next(
        (part for part in research_parts if part in RESEARCH_CHANGE_FIELDS),
        None,
    )
    high_risk = (
        root_field in HIGH_RISK_FIELDS
        or risk_field in HIGH_RISK_FIELDS
        or research_change is not None
    )
    old_phase = str(data.get("hermes_phase") or "planning")
    old_value = _read_change_value(data, field)
    incomplete_ids = [
        str(package.get("id"))
        for package in data.get("work_packages") or []
        if isinstance(package, dict)
        and package.get("status") not in DISPOSED_PACKAGE_STATUSES
        and package.get("id")
    ]
    semantic_ids = list(affected_packages or [])
    if not semantic_ids and field.startswith("work_packages."):
        semantic_ids = [field.split(".", 2)[1]]
    affected_ids = _dedupe([*semantic_ids, *incomplete_ids])
    human_approved = str(approved_by or "").casefold() in {"human", "root", "human/root"}
    requires_independent_task = (
        research_change == "model_architecture" and human_approved
    )
    applied = not high_risk or human_approved
    if requires_independent_task:
        applied = False
        previous_route = research_route(data)
        previous_changes = _research_change_fields(data)
        data["research_route"] = "exploration"
        data["research_change_fields"] = _dedupe(
            [*previous_changes, "model_architecture"]
        )
        data["grill_completed"] = False
        blocker = "model architecture requires an independent exploration task"
        data["blockers"] = _dedupe([*_string_list(data.get("blockers")), blocker])
        data["closure_state"] = "open"
        data["hermes_phase"] = "blocked"
        data["status"] = "in_progress"
        data["next_action"] = (
            "Create a new exploration task for the model architecture change and "
            "complete its grill before validation."
        )
    elif applied:
        _write_change_value(data, field, new_value)
        _reset_incomplete_packages(data)
        data["closure_state"] = "open"
        data["hermes_phase"] = "planning"
        data["status"] = "planning"
        if research_change is not None:
            data["research_route"] = "exploration"
            data["research_change_fields"] = _dedupe(
                [*_research_change_fields(data), research_change]
            )
            data["grill_completed"] = False
            data["next_action"] = closure_next_action(data)
        else:
            data["next_action"] = "Run closure.py validate after the plan amendment."
        approval_blocker = f"high-risk plan change requires human approval: {field}"
        data["blockers"] = [
            item for item in _string_list(data.get("blockers"))
            if item != approval_blocker
        ]
        if field == "closure_mode" and str(new_value) in CLOSURE_MODES:
            data["max_repair_count"] = default_repair_limit(str(new_value))
        if field == "max_repair_count":
            data["blockers"] = [
                item for item in _string_list(data.get("blockers"))
                if not item.startswith("repair limit reached")
            ]
    else:
        blocker = f"high-risk plan change requires human approval: {field}"
        data["blockers"] = _dedupe([*_string_list(data.get("blockers")), blocker])
        data["hermes_phase"] = "blocked"
        data["status"] = "in_progress"
        data["next_action"] = f"Obtain human approval for {field} before applying the amendment."
    save_task(task_dir, data)
    append_event(
        task_dir,
        "plan_amended",
        actor=actor,
        old_state=json.dumps(old_value, ensure_ascii=False, separators=(",", ":")),
        new_state=json.dumps(new_value, ensure_ascii=False, separators=(",", ":")),
        reason=reason,
        extra={
            "affected_packages": affected_ids,
            "field": field,
            "approval_requirement": "human" if high_risk else "none",
            "approved_by": approved_by,
            "applied": applied,
            "research_change": research_change,
        },
    )
    if requires_independent_task:
        append_event(
            task_dir,
            "research_route_updated",
            actor=actor,
            old_state=json.dumps(
                {
                    "research_route": previous_route,
                    "research_change_fields": previous_changes,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            new_state=json.dumps(
                {
                    "research_route": data["research_route"],
                    "research_change_fields": data["research_change_fields"],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            reason="model architecture change requires an independent exploration task",
        )
    new_phase = str(data.get("hermes_phase") or old_phase)
    if new_phase != old_phase:
        append_event(
            task_dir,
            "phase_changed",
            actor=actor,
            old_state=old_phase,
            new_state=new_phase,
            reason=f"plan amendment: {field}",
        )
    if not applied:
        write_handoff(task_dir, data, get_repo_root(task_dir))
    if requires_independent_task:
        raise ClosureError(
            "model architecture requires an independent exploration task; "
            "create a new task and plan it as exploration"
        )
    if high_risk and not human_approved:
        raise ClosureError(f"high-risk change {field} requires --approved-by human/root")
    return {"field": field, "old_value": old_value, "new_value": new_value, "high_risk": high_risk}


def close_task(
    task_dir: Path,
    data: dict[str, Any],
    *,
    actor: str,
) -> dict[str, Any]:
    with task_state_lock(task_dir):
        current = read_json(task_dir / FILE_TASK_JSON)
        if not isinstance(current, dict):
            raise ClosureError("cannot read task.json while closing")
        if current.get("hermes_revision", 0) != data.get("hermes_revision", 0):
            raise ClosureError("task changed while close was being prepared; rerun audit")
        if current.get("closure_state") == "closed" and current.get("hermes_phase") == "closed":
            data.clear()
            data.update(current)
            return audit_closure(task_dir, data, write_report=True)
        result = audit_closure(task_dir, current, write_report=True)
        if result["status"] != "all_met":
            return result
        old_phase = str(current.get("hermes_phase") or "review")
        original = deepcopy(current)
        closed = deepcopy(current)
        closed["hermes_phase"] = "closed"
        closed["closure_state"] = "closed"
        closed["status"] = "completed"
        closed["completedAt"] = datetime.now().strftime("%Y-%m-%d")
        closed["current_work_package"] = None
        closed["next_action"] = "Archive the closed Trellis task when ready."
        save_task(task_dir, closed, lock_held=True)
        try:
            append_event(
                task_dir,
                "task_closed",
                actor=actor,
                old_state=old_phase,
                new_state="closed",
                reason="closure audit passed",
                lock_held=True,
            )
        except ClosureError:
            if not write_json_atomic(task_dir / FILE_TASK_JSON, original):
                raise ClosureError(
                    "task close event failed and task rollback also failed; manual recovery required"
                )
            data.clear()
            data.update(original)
            raise
        data.clear()
        data.update(closed)
    try:
        write_handoff(task_dir, data, get_repo_root(task_dir))
    except OSError:
        pass
    return {
        "status": "all_met",
        "gaps": [],
        "mode": data.get("closure_mode"),
        "warnings": result.get("warnings") or [],
    }


def _dispatch_gaps(task_dir: Path, mode: str) -> list[dict[str, Any]]:
    dispatch_dir = task_dir / "hermes" / "dispatches"
    if not dispatch_dir.is_dir():
        return []
    gaps: list[dict[str, Any]] = []
    unfinished = {"created", "validated", "running", "result_returned", "rewrite_required"}
    for path in sorted(dispatch_dir.glob("*.dispatch.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            gaps.append(_gap(None, "invalid dispatch state", "修复或移除损坏的派发记录"))
            continue
        job_id = str(value.get("job_id") or path.name.removesuffix(".dispatch.json"))
        status = value.get("status")
        if status in unfinished:
            gaps.append(_gap(value.get("work_package"), f"unconfirmed dispatch {job_id}", "确认或处置派发结果"))
        if status in {"blocked", "failed"}:
            gaps.append(_gap(value.get("work_package"), f"blocked dispatch {job_id}", "修复派发或取得所需人工处置"))
    return gaps


def build_capsule(task_dir: Path, data: dict[str, Any], root: Path | None = None) -> str:
    current_id = data.get("current_work_package")
    current = None
    if current_id:
        try:
            current = package_by_id(data, str(current_id))
        except ClosureError:
            current = None
    scope = _compact_list(_string_list(data.get("in_scope")), 2)
    excluded = _compact_list(_string_list(data.get("out_of_scope")), 2)
    blockers = _compact_list(_string_list(data.get("blockers")), 2)
    constraints = closure_constraints(data)
    lines = [
        f"Task: {data.get('id') or task_dir.name} | {data.get('title') or task_dir.name}",
        f"Intent: {_clip(str(data.get('intent') or data.get('description') or ''), 180)}",
        f"Scope: {scope or '-'} | Out: {excluded or '-'}",
        f"Mode/Phase: {data.get('closure_mode', 'lean')} / {data.get('hermes_phase', 'planning')}",
        research_route_summary(data),
        "Route rule: " + research_route_rule(data),
        f"Verify: {constraints['validation_level']} | Excluded platforms: {_compact_list(constraints['excluded_platforms'], 2) or '-'}",
        f"Current: {current_id or '-'}" + (f" - {_clip(str(current.get('outcome') or ''), 140)}" if current else ""),
    ]
    if current:
        lines.append("Done when: " + _compact_list(_string_list(current.get("done_when")), 3, 240))
    lines.append(f"Next: {_clip(closure_next_action(data), 180)}")
    lines.append(f"Blockers: {blockers or '-'}")
    refs = _context_refs(task_dir, data, root or get_repo_root())[:3]
    if refs:
        lines.append("Refs: " + ", ".join(refs))
    capsule = "\n".join(lines)
    return capsule if len(capsule) <= 1000 else capsule[:997].rstrip() + "..."


def write_handoff(task_dir: Path, data: dict[str, Any], root: Path | None = None) -> Path:
    repo_root = root or get_repo_root(task_dir)
    packages = [item for item in data.get("work_packages") or [] if isinstance(item, dict)]
    completed = [str(item.get("id")) for item in packages if item.get("status") == "done"]
    evidence = _dedupe([
        ref
        for item in packages
        for ref in _string_list(item.get("evidence_refs"))
    ])
    changed = _git_changed_files(repo_root)
    failed_attempts = _recent_event_reasons(task_dir, {"package_blocked", "repair_started"})
    content = "\n".join(
        [
            "# Task Handoff",
            "",
            "## Current Goal",
            str(data.get("intent") or data.get("title") or "-"),
            "",
            "## Current Phase",
            str(data.get("hermes_phase") or "-"),
            "",
            "## Current Package",
            str(data.get("current_work_package") or "-"),
            "",
            "## Completed Packages",
            _markdown_items(completed),
            "",
            "## Files Changed",
            _markdown_items(changed),
            "",
            "## Artifacts/Evidence",
            _markdown_items(evidence),
            "",
            "## Failed Attempts",
            _markdown_items(failed_attempts),
            "",
            "## Blockers",
            _markdown_items(_string_list(data.get("blockers"))),
            "",
            "## Next Action",
            str(data.get("next_action") or "-"),
            "",
            "## Do Not Do",
            "- Do not widen scope or change research contracts without an approved amend event.",
            "",
        ]
    )
    path = task_dir / "HANDOFF.md"
    path.write_text(content, encoding="utf-8")
    return path


def write_closure_report(task_dir: Path, data: dict[str, Any]) -> Path:
    packages = [item for item in data.get("work_packages") or [] if isinstance(item, dict)]
    results = [
        f"- {item.get('id')}: {item.get('status')} - {item.get('outcome')}"
        for item in packages
    ]
    evidence = _dedupe([
        ref
        for item in packages
        for ref in _string_list(item.get("evidence_refs"))
    ])
    deferred = [
        f"{item.get('id')}: {item.get('status')} - {item.get('blocker') or 'recorded disposition'}"
        for item in packages
        if item.get("status") in {"deferred", "waived"}
    ]
    content = "\n".join(
        [
            "# Closure Report",
            "",
            "## Intent",
            str(data.get("intent") or "-"),
            "",
            "## Scope",
            _markdown_items(_string_list(data.get("in_scope"))),
            "",
            "## Definition of Done",
            _markdown_items(_string_list(data.get("definition_of_done"))),
            "",
            "## Work Package Results",
            "\n".join(results) if results else "- None",
            "",
            "## Evidence and Artifacts",
            _markdown_items(evidence),
            "",
            "## Deferred or Waived Work",
            _markdown_items(deferred),
            "",
            "## Open Limitations",
            _markdown_items(_string_list(data.get("blockers"))) if data.get("blockers") else "- None recorded",
            "",
            "## Final Verdict",
            "Closure audit passed." if not data.get("blockers") else "Blocked pending listed limitations.",
            "",
            "## Reproduction / Validation Commands",
            "- See evidence_refs and Hermes run_manifest.jsonl where applicable.",
            "",
        ]
    )
    path = task_dir / "closure-report.md"
    path.write_text(content, encoding="utf-8")
    return path


def format_audit_yaml(result: dict[str, Any]) -> str:
    lines = [f"status: {result['status']}", f"mode: {result['mode']}"]
    warnings = _string_list(result.get("warnings"))
    if warnings:
        lines.append("warnings:")
        for warning in warnings:
            lines.append(f"  - {_yaml_scalar(warning)}")
    gaps = result.get("gaps") or []
    if not gaps:
        lines.append("gaps: []")
        return "\n".join(lines)
    lines.append("gaps:")
    for gap in gaps:
        lines.append(f"  - package: {gap.get('package') or 'task'}")
        lines.append(f"    missing: {_yaml_scalar(str(gap.get('missing') or ''))}")
        lines.append(f"    action: {_yaml_scalar(str(gap.get('action') or ''))}")
    return "\n".join(lines)


def _standard_gaps(task_dir: Path) -> list[dict[str, Any]]:
    hermes = task_dir / "hermes"
    run_records = _read_jsonl_values(hermes / "run_manifest.jsonl")
    artifact_records = _read_jsonl_values(hermes / "artifact_ledger.jsonl")
    evidence_records = _read_jsonl_values(hermes / "evidence_ledger.jsonl")
    claim_records = _read_jsonl_values(hermes / "claim_ledger.jsonl")
    compare_records = _read_jsonl_values(hermes / "compare.jsonl")
    gaps: list[dict[str, Any]] = []
    if not run_records or not any(item.get("exit_code") == 0 for item in run_records):
        gaps.append(_gap(None, "successful run manifest", "登记至少一次成功运行"))
    if not artifact_records or not all(_valid_artifact_hash(item.get("hash")) for item in artifact_records):
        gaps.append(_gap(None, "artifact hash", "登记产物路径与 hash"))
    has_metrics = bool(compare_records) or any(isinstance(item.get("metrics"), dict) and item.get("metrics") for item in run_records)
    if not has_metrics:
        gaps.append(_gap(None, "metrics", "在 run manifest 或 compare 中登记指标"))
    if not evidence_records:
        gaps.append(_gap(None, "evidence", "登记可追溯 evidence"))
    if not claim_records:
        gaps.append(_gap(None, "claim limitations", "登记结果适用范围和限制"))
    elif any(not str(item.get("limits") or "").strip() for item in claim_records):
        gaps.append(_gap(None, "claim limitations", "为每个 claim 记录限制"))
    return gaps


def _publication_gaps(task_dir: Path) -> list[dict[str, Any]]:
    hermes = task_dir / "hermes"
    compare_records = _read_jsonl_values(hermes / "compare.jsonl")
    claim_records = _read_jsonl_values(hermes / "claim_ledger.jsonl")
    approval_records = _read_jsonl_values(hermes / "approval_records.jsonl")
    evidence_ids = {
        str(item.get("id")) for item in _read_jsonl_values(hermes / "evidence_ledger.jsonl") if item.get("id")
    }
    claim_ids = {str(item.get("id")) for item in claim_records if item.get("id")}
    gaps: list[dict[str, Any]] = []
    quality_ok = bool(compare_records) and all(
        item.get("passed") is True
        and isinstance(item.get("sample_count"), int)
        and (item.get("variance") is not None or item.get("confidence_interval") is not None)
        and bool(_string_list(item.get("evidence_refs")))
        and all(ref in evidence_ids for ref in _string_list(item.get("evidence_refs")))
        and bool(_string_list(item.get("claim_refs")))
        and all(ref in claim_ids for ref in _string_list(item.get("claim_refs")))
        for item in compare_records
    )
    if not quality_ok:
        gaps.append(_gap(None, "statistical compare quality gate", "补齐通过的 compare、样本数和方差或置信区间"))
    for claim in claim_records:
        claim_id = str(claim.get("id") or "claim")
        refs = _string_list(claim.get("evidence_ids"))
        if not refs or any(ref not in evidence_ids for ref in refs):
            gaps.append(_gap(None, f"claim {claim_id} evidence refs", "补齐有效证据引用"))
        approved = any(
            item.get("claim_id") == claim.get("id")
            and item.get("decision") == "approved"
            and str(item.get("approver") or "").casefold() in {"human", "root", "human/root"}
            for item in approval_records
        )
        if not approved:
            gaps.append(_gap(None, f"claim {claim_id} human approval", "由 human/root 完成 claim disposition"))
    if not claim_records:
        gaps.append(_gap(None, "claim disposition", "登记并处置 publication claim"))
    for filename in ("STATE.md", "CLAIMS.md"):
        if not (task_dir / filename).is_file() and not (hermes / filename).is_file():
            gaps.append(_gap(None, filename, f"更新 {filename}"))
    return gaps


def _block_repair_limit(
    task_dir: Path,
    data: dict[str, Any],
    actor: str,
    audit: dict[str, Any],
    count: int,
    limit: int,
) -> dict[str, Any]:
    blocker = f"repair limit reached ({count}/{limit})"
    data["blockers"] = _dedupe([*_string_list(data.get("blockers")), blocker])
    old_phase = str(data.get("hermes_phase") or "running")
    data["hermes_phase"] = "blocked"
    data["status"] = "in_progress"
    data["next_action"] = "Human review is required before another repair or scope change."
    current_id = data.get("current_work_package")
    if current_id:
        current = package_by_id(data, str(current_id))
        if current.get("status") not in DISPOSED_PACKAGE_STATUSES:
            current["status"] = "blocked"
            current["blocker"] = blocker
    save_task(task_dir, data)
    if old_phase != "blocked":
        append_event(
            task_dir,
            "phase_changed",
            actor=actor,
            old_state=old_phase,
            new_state="blocked",
            reason=blocker,
        )
    write_handoff(task_dir, data, get_repo_root(task_dir))
    return {**audit, "status": "blocked"}


def _prepare_repair_package(
    data: dict[str, Any],
    audit: dict[str, Any],
) -> dict[str, Any] | None:
    """Open only the first incomplete package named by the audit."""
    package_id = next(
        (
            str(gap.get("package"))
            for gap in audit.get("gaps") or []
            if gap.get("package")
        ),
        None,
    )
    if not package_id:
        return None
    package = package_by_id(data, package_id)
    status = str(package.get("status") or "pending")
    if status in DISPOSED_PACKAGE_STATUSES:
        return package
    if status == "blocked":
        package["status"] = "pending"
        package["blocker"] = None
        data["blockers"] = [
            item for item in _string_list(data.get("blockers"))
            if not item.startswith(f"{package_id}:")
        ]
    _refresh_ready_packages(data)
    if package.get("status") == "ready":
        package["status"] = "running"
    if package.get("status") in {"running", "review"}:
        data["current_work_package"] = package_id
    return package


def _reset_incomplete_packages(data: dict[str, Any]) -> None:
    reset_ids: set[str] = set()
    for package in data.get("work_packages") or []:
        if not isinstance(package, dict) or package.get("status") in DISPOSED_PACKAGE_STATUSES:
            continue
        package["status"] = "pending"
        package["blocker"] = None
        reset_ids.add(str(package.get("id") or ""))
    data["current_work_package"] = None
    data["blockers"] = [
        item for item in _string_list(data.get("blockers"))
        if not any(item.startswith(f"{package_id}:") for package_id in reset_ids if package_id)
    ]


def _refresh_ready_packages(data: dict[str, Any]) -> None:
    packages = [item for item in data.get("work_packages") or [] if isinstance(item, dict)]
    status_by_id = {str(item.get("id")): item.get("status") for item in packages}
    for package in packages:
        if package.get("status") not in {"pending", "ready"}:
            continue
        dependencies = _string_list(package.get("depends_on"))
        package["status"] = "ready" if all(
            status_by_id.get(dep) in {"done", "waived"} for dep in dependencies
        ) else "pending"


def _next_package_action(data: dict[str, Any]) -> str:
    for package in data.get("work_packages") or []:
        if package.get("status") == "ready":
            return f"Start {package.get('id')}: {package.get('outcome')}"
    return "Resolve dependencies or run closure.py audit."


def closure_next_action(data: dict[str, Any]) -> str:
    """Return the one valid next action for the authoritative Hermes phase."""
    phase = str(data.get("hermes_phase") or "planning")
    if phase == "planning":
        if research_route(data) == "exploration":
            if not _research_change_fields(data):
                return "Record research changes with closure.py route before validate."
            if data.get("grill_completed") is not True:
                return "Record the completed grill with closure.py grill --complete."
        if not str(data.get("intent") or "").strip():
            return "Set intent with closure.py plan."
        if not _string_list(data.get("definition_of_done")):
            return "Set definition_of_done with closure.py plan."
        if not isinstance(data.get("work_packages"), list) or not data.get("work_packages"):
            return "Add an explicit work package or run closure.py plan to create one safe package."
        return "Run closure.py validate."
    if phase == "ready":
        package_id = next_ready_package_id(data)
        return (
            f"Start {package_id} with closure.py package-start."
            if package_id
            else "Resolve package dependencies before starting work."
        )
    current = data.get("current_work_package")
    if phase == "running":
        if current:
            return f"Complete {current} outcome, then run closure.py package-check."
        package_id = next_ready_package_id(data)
        return (
            f"Start {package_id} with closure.py package-start."
            if package_id
            else "Run closure.py audit."
        )
    if phase == "review":
        if current:
            return f"Record directed validation evidence for {current}, then run closure.py package-done."
        return "Run closure.py audit."
    if phase == "blocked":
        return "Resolve the recorded blocker or record an approved closure amendment."
    if phase == "closed":
        return "Archive the closed Trellis task when ready."
    return "Inspect hermes_phase before continuing."


def _has_dependency_cycle(graph: dict[str, list[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for dependency in graph.get(node, []):
            if dependency in graph and visit(dependency):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)


def _scope_phrase_in_text(phrase: str, text: str) -> bool:
    if re.fullmatch(r"[a-z0-9_.-]+", phrase):
        return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None
    return phrase in text


def _read_change_value(data: dict[str, Any], field: str) -> Any:
    parts = field.split(".")
    if parts[0] == "work_packages" and len(parts) == 3:
        return package_by_id(data, parts[1]).get(parts[2])
    if len(parts) == 1 and parts[0] in AMENDABLE_CLOSURE_FIELDS:
        return data.get(field)
    if parts[:1] == ["constraints"] and len(parts) == 2:
        constraints = data.get("constraints")
        return constraints.get(parts[1]) if isinstance(constraints, dict) else None
    meta = data.get("meta")
    if not isinstance(meta, dict):
        return None
    current: Any = meta.get("research_contract")
    if not isinstance(current, dict):
        return None
    research_parts = _research_field_parts(field)
    for part in research_parts[:-1]:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current.get(research_parts[-1]) if isinstance(current, dict) else None


def _write_change_value(data: dict[str, Any], field: str, value: Any) -> None:
    parts = field.split(".")
    if parts[0] == "work_packages" and len(parts) == 3:
        package = package_by_id(data, parts[1])
        if package.get("status") in DISPOSED_PACKAGE_STATUSES:
            raise ClosureError("repair/amend cannot rewrite a disposed package")
        _validate_package_amend_value(parts[2], value)
        package[parts[2]] = value
        return
    if len(parts) == 1 and parts[0] in AMENDABLE_CLOSURE_FIELDS:
        _validate_closure_amend_value(parts[0], value)
        data[parts[0]] = value
        return
    if parts[:1] == ["constraints"] and len(parts) == 2:
        _validate_constraint_amend_value(parts[1], value)
        constraints = data.setdefault("constraints", {})
        if not isinstance(constraints, dict):
            raise ClosureError("constraints must be an object before amending it")
        constraints[parts[1]] = value
        return
    meta = data.setdefault("meta", {})
    if not isinstance(meta, dict):
        raise ClosureError("task.meta must be an object before amending research fields")
    current = meta.setdefault("research_contract", {})
    if not isinstance(current, dict):
        raise ClosureError("task.meta.research_contract must be an object")
    research_parts = _research_field_parts(field)
    for part in research_parts[:-1]:
        current = current.setdefault(part, {})
        if not isinstance(current, dict):
            raise ClosureError(f"cannot set nested field: {field}")
    current[research_parts[-1]] = value


def _validate_amend_field(data: dict[str, Any], field: str) -> None:
    parts = field.split(".")
    if any(not part for part in parts):
        raise ClosureError("amend field path is invalid")
    if parts[0] == "work_packages":
        if len(parts) != 3 or parts[2] not in AMENDABLE_PACKAGE_FIELDS:
            raise ClosureError("only package title, outcome, done_when, evidence_required, or depends_on may be amended")
        package_by_id(data, parts[1])
        return
    if len(parts) == 1 and field in data and field not in AMENDABLE_CLOSURE_FIELDS:
        raise ClosureError(f"task state field cannot be amended directly: {field}")
    if parts[:1] == ["constraints"]:
        if len(parts) != 2 or parts[1] not in CONSTRAINT_FIELDS:
            raise ClosureError("only constraints.excluded_platforms, constraints.excluded_paths, or constraints.validation_level may be amended")
        return
    if not _research_field_parts(field):
        raise ClosureError("research amend field path is invalid")


def _research_field_parts(field: str) -> list[str]:
    parts = field.split(".")
    if parts[:2] == ["meta", "research_contract"]:
        return parts[2:]
    if parts[:1] == ["research_contract"]:
        return parts[1:]
    return parts


def _validate_closure_amend_value(field: str, value: Any) -> None:
    if field == "closure_mode" and value not in CLOSURE_MODES:
        raise ClosureError("closure_mode must be lean, standard, or publication")
    if field in {"intent"} and not isinstance(value, str):
        raise ClosureError(f"{field} must be a string")
    if field in {"in_scope", "out_of_scope", "definition_of_done", "context_pins"} and not (
        isinstance(value, list) and all(isinstance(item, str) for item in value)
    ):
        raise ClosureError(f"{field} must be an array of strings")
    if field == "context_pins" and len(value) > 3:
        raise ClosureError("context_pins supports at most 3 entries")
    if field == "max_repair_count" and (
        not isinstance(value, int) or isinstance(value, bool) or value < 0
    ):
        raise ClosureError("max_repair_count must be a non-negative integer")


def _validate_package_amend_value(field: str, value: Any) -> None:
    if field in {"title", "outcome"} and not isinstance(value, str):
        raise ClosureError(f"package {field} must be a string")
    if field in {"done_when", "evidence_required", "depends_on"} and not (
        isinstance(value, list) and all(isinstance(item, str) for item in value)
    ):
        raise ClosureError(f"package {field} must be an array of strings")


def _validate_constraint_amend_value(field: str, value: Any) -> None:
    if field in {"excluded_platforms", "excluded_paths"} and not (
        isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise ClosureError(f"constraints.{field} must be an array of non-empty strings")
    if field == "excluded_paths":
        for item in value:
            normalized = item.replace("\\", "/")
            if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized) or ".." in Path(normalized).parts:
                raise ClosureError("constraints.excluded_paths must use repository-relative patterns")
    if field == "validation_level" and value not in VALIDATION_LEVELS:
        raise ClosureError("constraints.validation_level must be targeted, basic, or standard")


def _context_refs(task_dir: Path, data: dict[str, Any], root: Path) -> list[str]:
    refs = _string_list(data.get("context_pins"))
    for filename in ("implement.jsonl", "check.jsonl"):
        for item in _read_jsonl_values(task_dir / filename):
            value = item.get("file")
            if isinstance(value, str) and value.strip():
                refs.append(value.strip())
    refs.extend(_string_list(data.get("relatedFiles")))
    return _dedupe(refs)


def _read_jsonl_values(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    values: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "_example" not in value:
            values.append(value)
    return values


def _valid_artifact_hash(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return re.fullmatch(r"(?:sha256:)?[0-9a-fA-F]{64}", value.strip()) is not None


def _recent_event_reasons(task_dir: Path, types: set[str]) -> list[str]:
    return [
        str(item.get("reason"))
        for item in _read_jsonl_values(task_dir / "hermes" / "task-events.jsonl")[-20:]
        if item.get("event_type") in types and item.get("reason")
    ][-5:]


def _git_changed_files(root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "status", "--short", "--untracked-files=all"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    files: list[str] = []
    for line in result.stdout.splitlines():
        value = line[3:].strip() if len(line) > 3 else ""
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        lowered = value.casefold()
        if value and not any(
            marker in lowered
            for marker in (".env", "credentials", "secret", "token", "api_key")
        ):
            files.append(value)
    return files[:20]


def _gap(package: str | None, missing: str, action: str) -> dict[str, Any]:
    return {"package": package, "missing": missing, "action": action}


def _dedupe_gaps(gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, Any, Any]] = set()
    result: list[dict[str, Any]] = []
    for gap in gaps:
        key = (gap.get("package"), gap.get("missing"), gap.get("action"))
        if key not in seen:
            seen.add(key)
            result.append(gap)
    return result


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, str) and item.strip()]


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _clip(value: str, limit: int) -> str:
    compact = re.sub(r"\s+", " ", value).strip()
    return compact if len(compact) <= limit else compact[: max(0, limit - 3)].rstrip() + "..."


def _compact_list(values: list[str], limit: int, char_limit: int = 180) -> str:
    return _clip("; ".join(values[:limit]), char_limit)


def _markdown_items(values: list[str]) -> str:
    return "\n".join(f"- {item}" for item in values) if values else "- None"


def _yaml_scalar(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)
