#!/usr/bin/env python3
"""Lean Research Closure CLI for one Trellis task and 1-4 work packages."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from common.closure import (
    CLOSURE_MODES,
    ClosureError,
    actor_name,
    amend_plan,
    audit_closure,
    block_package,
    build_capsule,
    check_package,
    close_task,
    complete_package,
    format_audit_yaml,
    is_closure_task,
    package_by_id,
    plan_closure,
    repair_closure,
    resolve_closure_task,
    start_package,
    validate_and_ready,
    write_handoff,
)


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task", help="Task name/path; defaults to active task")
    parser.add_argument("--actor", help="Actor written to task-events.jsonl")


def package_spec(value: str) -> dict[str, Any]:
    """Parse TITLE::OUTCOME::DONE[|DONE]::EVIDENCE[|EVIDENCE]."""
    parts = value.split("::")
    if len(parts) < 3:
        raise argparse.ArgumentTypeError(
            "package must be TITLE::OUTCOME::DONE_WHEN[|DONE_WHEN]"
        )
    return {
        "title": parts[0].strip(),
        "outcome": parts[1].strip(),
        "done_when": _pipe_values(parts[2]),
        "evidence_required": _pipe_values(parts[3]) if len(parts) > 3 else [],
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Plan, execute, audit, and close a lean research task.",
    )
    subparsers = root.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="Create a lean closure plan")
    add_common(plan)
    plan.add_argument("--intent")
    plan.add_argument("--in-scope", action="append", default=None)
    plan.add_argument("--out-of-scope", action="append", default=None)
    plan.add_argument("--done-when", action="append", default=None)
    plan.add_argument("--package", action="append", type=package_spec, default=None)
    plan.add_argument("--mode", choices=sorted(CLOSURE_MODES))

    validate = subparsers.add_parser("validate", help="Validate plan and enter ready")
    add_common(validate)

    status = subparsers.add_parser("status", help="Show compact closure status")
    add_common(status)
    status.add_argument("--json", action="store_true")

    next_command = subparsers.add_parser("next", help="Show the bounded next action")
    add_common(next_command)

    capsule = subparsers.add_parser("capsule", help="Print compact task context")
    add_common(capsule)

    package_start = subparsers.add_parser("package-start", help="Start a ready package")
    add_common(package_start)
    package_start.add_argument("--package-id")
    package_start.add_argument("--reason", default="")

    package_check = subparsers.add_parser("package-check", help="Move running package to review")
    add_common(package_check)
    package_check.add_argument("--package-id")

    package_done = subparsers.add_parser("package-done", help="Dispose a reviewed package")
    add_common(package_done)
    package_done.add_argument("--package-id")
    package_done.add_argument("--evidence", action="append", default=[])
    package_done.add_argument("--disposition", choices=["done", "deferred", "waived"], default="done")
    package_done.add_argument("--reason", default="")

    package_block = subparsers.add_parser("package-block", help="Block the current package")
    add_common(package_block)
    package_block.add_argument("--package-id")
    package_block.add_argument("--reason", required=True)

    amend = subparsers.add_parser("amend", help="Record and apply a bounded plan change")
    add_common(amend)
    amend.add_argument("--field", required=True)
    amend.add_argument("--value", required=True, help="JSON value or plain string")
    amend.add_argument("--reason", required=True)
    amend.add_argument("--affected-package", action="append", default=[])
    amend.add_argument("--approved-by", help="Required for high-risk research contract changes")

    audit = subparsers.add_parser("audit", help="Audit closure without making a new plan")
    add_common(audit)
    audit.add_argument("--json", action="store_true")
    audit.add_argument("--no-report", action="store_true")

    repair = subparsers.add_parser("repair", help="Run one bounded audit-gap repair round")
    add_common(repair)
    repair.add_argument("--json", action="store_true")

    handoff = subparsers.add_parser("handoff", help="Write a conditional HANDOFF.md")
    add_common(handoff)

    close = subparsers.add_parser("close", help="Audit and close the task")
    add_common(close)
    close.add_argument("--json", action="store_true")

    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        task_dir, data, repo_root = resolve_closure_task(args.task)
        actor = actor_name(repo_root, args.actor)
        if not is_closure_task(data) and args.command != "plan":
            if args.command in {"status", "next", "capsule"}:
                print("Compatibility mode: legacy non-Hermes task; run closure.py plan to opt in.")
                return 0
            raise ClosureError("legacy non-Hermes task; run closure.py plan before closure commands")
        if args.command == "plan":
            warnings = plan_closure(
                task_dir,
                data,
                intent=args.intent,
                in_scope=args.in_scope,
                out_of_scope=args.out_of_scope,
                definition_of_done=args.done_when,
                packages=args.package,
                mode=args.mode,
            )
            print(f"planned {len(data.get('work_packages') or [])} work package(s)")
            for warning in warnings:
                print(f"warning: {warning}", file=sys.stderr)
            return 0
        if args.command == "validate":
            errors, warnings = validate_and_ready(task_dir, data, actor=actor)
            for warning in warnings:
                print(f"warning: {warning}", file=sys.stderr)
            if errors:
                for error in errors:
                    print(f"error: {error}", file=sys.stderr)
                return 1
            print("valid closure plan; phase=ready")
            return 0
        if args.command == "status":
            if args.json:
                print(json.dumps(_status_record(data), ensure_ascii=False, indent=2))
            else:
                print(build_capsule(task_dir, data, repo_root))
            return 0
        if args.command == "next":
            print(data.get("next_action") or "Run closure.py plan or validate.")
            return 0
        if args.command == "capsule":
            print(build_capsule(task_dir, data, repo_root))
            return 0
        if args.command == "package-start":
            package = start_package(
                task_dir,
                data,
                args.package_id,
                actor=actor,
                reason=args.reason,
            )
            print(f"started {package['id']}: {package['outcome']}")
            return 0
        if args.command == "package-check":
            package = check_package(task_dir, data, args.package_id, actor=actor)
            print(f"review {package['id']}: validate done_when and evidence")
            return 0
        if args.command == "package-done":
            package = complete_package(
                task_dir,
                data,
                args.package_id,
                actor=actor,
                evidence_refs=args.evidence,
                disposition=args.disposition,
                reason=args.reason,
            )
            print(f"{package['id']} -> {package['status']}")
            return 0
        if args.command == "package-block":
            package = block_package(
                task_dir,
                data,
                args.package_id,
                actor=actor,
                reason=args.reason,
            )
            print(f"blocked {package['id']}: {package['blocker']}")
            return 0
        if args.command == "amend":
            result = amend_plan(
                task_dir,
                data,
                field=args.field,
                new_value=_json_or_text(args.value),
                reason=args.reason,
                actor=actor,
                affected_packages=args.affected_package,
                approved_by=args.approved_by,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "audit":
            result = audit_closure(task_dir, data, write_report=not args.no_report)
            _print_audit(result, args.json)
            return 0 if result["status"] == "all_met" else 1
        if args.command == "repair":
            result = repair_closure(task_dir, data, actor=actor)
            _print_audit(result, args.json)
            return 0 if result["status"] == "all_met" else 1
        if args.command == "handoff":
            path = write_handoff(task_dir, data, repo_root)
            print(path.relative_to(repo_root).as_posix())
            return 0
        if args.command == "close":
            result = close_task(task_dir, data, actor=actor)
            _print_audit(result, args.json)
            return 0 if result["status"] == "all_met" else 1
        return 2
    except ClosureError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _pipe_values(value: str) -> list[str]:
    return [item.strip() for item in value.split("|") if item.strip()]


def _json_or_text(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _status_record(data: dict[str, Any]) -> dict[str, Any]:
    current = data.get("current_work_package")
    current_package = package_by_id(data, str(current)) if current else None
    return {
        "task_status": data.get("status"),
        "hermes_phase": data.get("hermes_phase"),
        "closure_state": data.get("closure_state"),
        "closure_mode": data.get("closure_mode"),
        "current_work_package": current_package,
        "next_action": data.get("next_action"),
        "blockers": data.get("blockers") or [],
        "repair_count": data.get("repair_count", 0),
        "max_repair_count": data.get("max_repair_count", 1),
    }


def _print_audit(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_audit_yaml(result))


if __name__ == "__main__":
    raise SystemExit(main())
