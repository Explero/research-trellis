#!/usr/bin/env python3
"""Create, validate, inspect, run, and apply Hermes firewall dispatches."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common.closure import ClosureError, resolve_closure_task
from common.dispatch import (
    DispatchError,
    accept_result_text,
    create_dispatch,
    dispatch_path,
    list_dispatches,
    load_dispatch,
    load_sanitized_result,
    prepare_dispatch_for_agent,
    result_json_schema,
    run_codex_strict,
    sanitized_summary,
    supersede_dispatch,
    validate_dispatch,
    validate_result_envelope,
)
from common.firewall import firewall_health


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hermes Agent Context Firewall dispatch CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create")
    _task_arg(create)
    create.add_argument("--job-id")
    create.add_argument("--role", required=True)
    create.add_argument("--profile")
    create.add_argument("--work-package")
    create.add_argument("--objective", required=True)
    create.add_argument("--ref", action="append", default=[])
    create.add_argument("--allowed-file", action="append", default=[])
    create.add_argument("--forbidden-file", action="append", default=[])
    create.add_argument("--risk-flag", action="append", default=[])
    create.add_argument("--worktree-id", default="main")
    create.add_argument("--heartbeat-interval", default="5m")
    create.add_argument("--timeout-at")
    create.add_argument("--human-gate")
    create.add_argument("--platform", choices=["auto", "claude", "codex"], default="auto")
    create.add_argument("--not-blind", action="store_true")

    validate = subparsers.add_parser("validate")
    _task_arg(validate)
    validate.add_argument("--job-id", required=True)
    validate.add_argument("--result")
    validate.add_argument("--result-json")

    show = subparsers.add_parser("show")
    _task_arg(show)
    show.add_argument("--job-id", required=True)
    show.add_argument("--result", action="store_true")
    show.add_argument("--prompt", action="store_true")

    run = subparsers.add_parser("run")
    _task_arg(run)
    run.add_argument("--job-id", required=True)
    run.add_argument("--platform", choices=["claude", "codex"], required=True)
    run.add_argument("--mode", choices=["native", "strict"], default="native")
    run.add_argument("--codex-bin", default="codex")

    apply = subparsers.add_parser("apply")
    _task_arg(apply)
    apply.add_argument("--job-id", required=True)
    apply.add_argument("--result")
    apply.add_argument("--result-json")

    listing = subparsers.add_parser("list")
    _task_arg(listing)

    status = subparsers.add_parser("status")
    _task_arg(status)
    status.add_argument("--job-id")

    supersede = subparsers.add_parser("supersede")
    _task_arg(supersede)
    supersede.add_argument("--job-id", required=True)
    supersede.add_argument("--replacement-job-id")
    supersede.add_argument("--reason", required=True)

    schema = subparsers.add_parser("schema")
    schema.add_argument("--output")
    return parser


def _task_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task")


def _result_text(args: argparse.Namespace) -> str:
    if args.result_json:
        return args.result_json
    if args.result:
        return Path(args.result).read_text(encoding="utf-8")
    return sys.stdin.read()


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "schema":
        schema = result_json_schema()
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            _print(schema)
        return 0

    try:
        task_dir, task, root = resolve_closure_task(args.task)
        if args.command == "create":
            spec = {
                "job_id": args.job_id,
                "role": args.role,
                "profile": args.profile,
                "work_package": args.work_package,
                "objective": args.objective,
                "refs": args.ref,
                "allowed_files": args.allowed_file,
                "forbidden_files": args.forbidden_file,
                "risk_flags": args.risk_flag,
                "worktree_id": args.worktree_id,
                "heartbeat_interval": args.heartbeat_interval,
                "timeout_at": args.timeout_at,
                "human_gate": args.human_gate,
                "platform": args.platform,
                "blind_review": not args.not_blind,
            }
            dispatch, warnings = create_dispatch(task_dir, task, spec, root)
            for warning in warnings:
                print(f"warning: {warning}", file=sys.stderr)
            _print({"job_id": dispatch["job_id"], "status": dispatch["status"], "path": str(dispatch_path(task_dir, dispatch["job_id"]).relative_to(root)), "audit": dispatch["audit"]})
            return 0
        if args.command == "validate":
            dispatch = load_dispatch(task_dir, args.job_id)
            validate_dispatch(task_dir, task, dispatch, root)
            if args.result or args.result_json:
                validate_result_envelope(task_dir, task, dispatch, _result_text(args), root)
            _print({"job_id": args.job_id, "status": "valid"})
            return 0
        if args.command == "show":
            if args.result:
                stored_result = load_sanitized_result(task_dir, args.job_id)
                if stored_result is None:
                    raise DispatchError("missing_result", "sanitized result does not exist")
                _print(stored_result)
            else:
                dispatch = load_dispatch(task_dir, args.job_id)
                print(dispatch["body"] if args.prompt else json.dumps(dispatch, ensure_ascii=False, indent=2))
            return 0
        if args.command == "run":
            if args.platform == "codex" and args.mode == "strict":
                result, warnings = run_codex_strict(task_dir, task, root, args.job_id, codex_bin=args.codex_bin)
                for warning in warnings:
                    print(f"warning: {warning}", file=sys.stderr)
                if result is None:
                    dispatch = load_dispatch(task_dir, args.job_id)
                    _print({"job_id": args.job_id, "status": "advisory", "prompt": dispatch["body"]})
                else:
                    _print(sanitized_summary(task_dir, args.job_id))
                return 0
            dispatch = prepare_dispatch_for_agent(
                task_dir,
                task,
                root,
                args.job_id,
                platform=args.platform,
                hook_active=False,
            )
            _print({"job_id": args.job_id, "status": "advisory", "prompt": dispatch["body"]})
            return 0
        if args.command == "apply":
            result = accept_result_text(task_dir, task, root, args.job_id, _result_text(args))
            _print(result)
            return 0
        if args.command == "list":
            _print({"dispatches": list_dispatches(task_dir)})
            return 0
        if args.command == "status":
            value: dict[str, Any] = {"firewall": firewall_health(root)}
            if args.job_id:
                value["dispatch"] = load_dispatch(task_dir, args.job_id)
                value["summary"] = sanitized_summary(task_dir, args.job_id)
            else:
                value["dispatches"] = list_dispatches(task_dir)
            _print(value)
            return 0
        if args.command == "supersede":
            dispatch = supersede_dispatch(
                task_dir,
                task,
                root,
                args.job_id,
                reason=args.reason,
                replacement_job_id=args.replacement_job_id,
            )
            _print({
                "job_id": args.job_id,
                "status": dispatch["status"],
                "replacement_job_id": dispatch.get("replacement_job_id"),
            })
            return 0
    except (DispatchError, ClosureError, OSError) as exc:
        code = exc.code if isinstance(exc, DispatchError) else "operation_failed"
        details = exc.details if isinstance(exc, DispatchError) else []
        print(json.dumps({"error": code, "message": str(exc), "details": details}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
