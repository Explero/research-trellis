#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

from runtime import (
    JsonlRecord,
    append_record,
    compare_path,
    make_record_id,
    now_utc,
    parse_timestamp,
    read_jsonl,
    record_path,
    repo_root,
    report_path,
    run_manifest_path,
    validate_compare_records,
    validate_records,
    validate_run_manifest_records,
)


def number_arg(value: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not a number: {value}") from exc


def relative_to_root(root: Path, path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_output_path(root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve(strict=False)


def resolve_task_hermes_output_path(root: Path, task: str, value: str) -> Path:
    hermes_root = report_path(root, task).parent.resolve(strict=False)
    candidate = Path(value)
    if candidate.is_absolute():
        resolved = candidate.resolve(strict=False)
    else:
        repo_relative = (root / candidate).resolve(strict=False)
        try:
            repo_relative.relative_to(hermes_root)
            resolved = repo_relative
        except ValueError:
            resolved = (hermes_root / candidate).resolve(strict=False)
    try:
        resolved.relative_to(hermes_root)
    except ValueError as exc:
        raise ValueError("output must stay inside task Hermes directory") from exc
    return resolved


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def numeric_summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "variance": None,
            "min": None,
            "max": None,
        }
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return {
        "count": len(values),
        "mean": mean,
        "variance": variance,
        "min": min(values),
        "max": max(values),
    }


def duration_seconds(record: dict[str, Any]) -> float | None:
    started = parse_timestamp(record.get("started_at"))
    finished = parse_timestamp(record.get("finished_at"))
    if started is None or finished is None:
        return None
    return max(0.0, (finished - started).total_seconds())


def output_count(record: dict[str, Any]) -> int:
    outputs = record.get("outputs")
    if isinstance(outputs, list):
        return len(outputs)
    return 0


def collect_output_hashes(records: list[dict[str, Any]]) -> list[str]:
    hashes: list[str] = []
    for record in records:
        outputs = record.get("outputs")
        if not isinstance(outputs, list):
            continue
        for output in outputs:
            if isinstance(output, dict) and isinstance(output.get("hash"), str):
                hashes.append(output["hash"])
    return hashes


def collect_metric_values(records: list[dict[str, Any]]) -> dict[str, list[float]]:
    values: dict[str, list[float]] = {}
    for record in records:
        metrics = record.get("metrics")
        if not isinstance(metrics, dict):
            continue
        for key, value in metrics.items():
            if isinstance(key, str) and isinstance(value, (int, float)) and not isinstance(value, bool):
                if math.isfinite(float(value)):
                    values.setdefault(key, []).append(float(value))
    return values


def aggregate_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    durations = [
        value
        for value in (duration_seconds(record) for record in records)
        if value is not None
    ]
    output_counts = [float(output_count(record)) for record in records]
    failures = [
        record
        for record in records
        if isinstance(record.get("exit_code"), int) and record.get("exit_code") != 0
    ]
    exceptions = [
        {"run_id": str(record.get("id", "")), "error": str(record.get("error"))}
        for record in records
        if record.get("error")
    ]
    metric_values = collect_metric_values(records)
    metrics = {
        metric: numeric_summary(values)
        for metric, values in sorted(metric_values.items())
    }
    return {
        "type": "aggregate",
        "generated_at": now_utc(),
        "run_count": len(records),
        "failure_count": len(failures),
        "exceptions": exceptions,
        "duration_seconds": numeric_summary(durations),
        "outputs_count": numeric_summary(output_counts),
        "metrics": metrics,
        "run_ids": [
            record["id"]
            for record in records
            if isinstance(record.get("id"), str)
        ],
        "output_hashes": collect_output_hashes(records),
        "conclusion_state": "claim_ready",
    }


def aggregate_command(args: argparse.Namespace) -> int:
    root = repo_root()
    task = args.task
    try:
        manifest_path = run_manifest_path(root, task)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    entries, errors = read_jsonl(manifest_path)
    errors.extend(validate_run_manifest_records(manifest_path, entries))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    aggregate = aggregate_records([entry.value for entry in entries])
    if args.output:
        try:
            output_path = resolve_task_hermes_output_path(root, task, args.output)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    else:
        output_path = manifest_path.parent / "aggregate.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"aggregate written to {relative_to_root(root, output_path)}")
    return 0


def passed_compare(direction: str, baseline: float, new: float, threshold: float) -> bool:
    if direction == "higher_is_better":
        return (new - baseline) >= threshold
    if direction == "lower_is_better":
        return (baseline - new) >= threshold
    raise ValueError(f"unknown direction: {direction}")


def compare_record(args: argparse.Namespace) -> dict[str, Any]:
    delta = args.new - args.baseline
    return {
        "type": "compare",
        "id": make_record_id("cmp", args.metric),
        "timestamp": now_utc(),
        "metric": args.metric,
        "direction": args.direction,
        "threshold": args.threshold,
        "baseline": args.baseline,
        "new": args.new,
        "delta": delta,
        "passed": passed_compare(args.direction, args.baseline, args.new, args.threshold),
        "evidence_refs": args.evidence_ref or [],
        "claim_refs": args.claim_ref or [],
        "conclusion_state": "claim_ready",
    }


def compare_command(args: argparse.Namespace) -> int:
    if args.threshold < 0:
        print("threshold must be non-negative", file=sys.stderr)
        return 2
    root = repo_root()
    task = args.task
    try:
        path = compare_path(root, task)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    record = compare_record(args)
    errors = validate_compare_records([JsonlRecord(1, record)])
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2

    try:
        append_record(path, record)
    except OSError as exc:
        print(f"cannot append compare record: {exc}", file=sys.stderr)
        return 1
    print(json_dump(record))
    return 0


def records_by_id(path: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    entries, errors = read_jsonl(path)
    by_id: dict[str, dict[str, Any]] = {}
    for entry in entries:
        record_id = entry.value.get("id")
        if isinstance(record_id, str):
            by_id[record_id] = entry.value
    return by_id, errors


def review_claims(task: str, claim_id: str | None = None) -> tuple[dict[str, Any], list[str]]:
    root = repo_root()
    try:
        claim_path = record_path(root, task, "claim")
        evidence_path = record_path(root, task, "evidence")
    except ValueError as exc:
        return {}, [str(exc)]

    claims, claim_errors = records_by_id(claim_path)
    evidence, evidence_errors = records_by_id(evidence_path)
    errors = claim_errors + evidence_errors
    selected = [
        claim
        for claim in claims.values()
        if claim.get("type") == "claim" and (claim_id is None or claim.get("id") == claim_id)
    ]
    if claim_id is not None and not selected:
        errors.append(f"missing claim_id {claim_id}")

    reviews: list[dict[str, Any]] = []
    for claim in selected:
        evidence_ids = claim.get("evidence_ids")
        if not isinstance(evidence_ids, list):
            evidence_ids = []
        missing = [
            evidence_id
            for evidence_id in evidence_ids
            if not isinstance(evidence_id, str) or evidence_id not in evidence
        ]
        reviews.append(
            {
                "claim_id": claim.get("id"),
                "state": claim.get("state"),
                "supported": bool(evidence_ids) and not missing,
                "evidence_ids": [
                    evidence_id
                    for evidence_id in evidence_ids
                    if isinstance(evidence_id, str)
                ],
                "missing_evidence_ids": missing,
                "scope": claim.get("scope"),
                "limits": claim.get("limits"),
            }
        )

    return {
        "type": "claim_review",
        "generated_at": now_utc(),
        "supported": bool(reviews) and all(review["supported"] for review in reviews),
        "claims": reviews,
        "approval_written": False,
        "conclusion_state": "claim_ready",
    }, errors


def claim_review_command(args: argparse.Namespace) -> int:
    result, errors = review_claims(args.task, args.claim_id)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(json_dump(result))
    return 0 if result["supported"] else 1


def quality_gate_command(args: argparse.Namespace) -> int:
    root = repo_root()
    task = args.task
    try:
        cmp_path = compare_path(root, task)
        evidence_path = record_path(root, task, "evidence")
        claim_path = record_path(root, task, "claim")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    compares, errors = load_compare_records(cmp_path)
    evidence_errors = validate_records(evidence_path, "evidence")
    claim_errors = validate_records(claim_path, "claim")
    evidence_records, evidence_load_errors = records_by_id(evidence_path)
    claim_records, claim_load_errors = records_by_id(claim_path)
    errors.extend(evidence_errors)
    errors.extend(claim_errors)
    errors.extend(evidence_load_errors)
    errors.extend(claim_load_errors)
    if not compares:
        errors.append("quality gate requires at least one compare record")
    for record in compares:
        compare_id = str(record.get("id", "unknown"))
        if record.get("passed") is not True:
            errors.append(f"compare {compare_id} failed")
        evidence_refs = record.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs:
            errors.append(f"compare {compare_id} missing evidence_refs")
        else:
            for evidence_ref in evidence_refs:
                if isinstance(evidence_ref, str) and evidence_ref not in evidence_records:
                    errors.append(
                        f"compare {compare_id} references missing evidence_id {evidence_ref}"
                    )
        claim_refs = record.get("claim_refs")
        if not isinstance(claim_refs, list) or not claim_refs:
            errors.append(f"compare {compare_id} missing claim_refs")
        else:
            for claim_ref in claim_refs:
                if isinstance(claim_ref, str) and claim_ref not in claim_records:
                    errors.append(
                        f"compare {compare_id} references missing claim_id {claim_ref}"
                    )
        if "sample_count" not in record and "variance" not in record and "confidence_interval" not in record:
            errors.append(
                f"compare {compare_id} missing sample_count, variance, or confidence_interval"
            )
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(json_dump({"status": "passed", "compare_count": len(compares)}))
    return 0


def approval_gate_command(args: argparse.Namespace) -> int:
    root = repo_root()
    try:
        approval_path = record_path(root, args.task, "approval")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    errors = validate_records(approval_path, "approval")
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        if not approval_path.exists():
            print(
                f"claim {args.claim_id} requires human/root approval in approval_records.jsonl",
                file=sys.stderr,
            )
        return 1

    approval_entries, approval_errors = read_jsonl(approval_path)
    if approval_errors:
        for error in approval_errors:
            print(error, file=sys.stderr)
        return 1

    for entry in approval_entries:
        approval = entry.value
        if (
            approval.get("type") == "human_approval"
            and approval.get("claim_id") == args.claim_id
            and approval.get("approver") == "human/root"
            and approval.get("decision") == "approved"
        ):
            print(json_dump({"status": "approved", "claim_id": args.claim_id}))
            return 0

    print(
        f"claim {args.claim_id} requires human/root approval in approval_records.jsonl",
        file=sys.stderr,
    )
    return 1


def load_compare_records(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    entries, errors = read_jsonl(path)
    errors.extend(validate_compare_records(entries))
    return [entry.value for entry in entries if entry.value.get("type") == "compare"], errors


def bullet_or_none(items: list[str]) -> str:
    if not items:
        return "- None recorded.\n"
    return "".join(f"- {item}\n" for item in items)


def report_markdown(
    args: argparse.Namespace,
    claims: dict[str, dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
    compares: list[dict[str, Any]],
    claim_review: dict[str, Any],
) -> str:
    lines: list[str] = [
        "# Hermes Evaluation Report",
        "",
        "## Problem",
        args.question,
        "",
        "## Method",
        args.method,
        "",
        "## Data",
        args.data,
        "",
        "## Metrics",
        args.metrics,
        "",
        "## Results",
    ]

    if compares:
        for record in compares:
            compare_id = record.get("id")
            lines.append(
                "- compare: {compare_id}; metric: {metric}; baseline: {baseline}; new: {new}; "
                "delta: {delta}; threshold: {threshold}; passed: {passed}; evidence: {evidence}; claim: {claim}".format(
                    compare_id=compare_id,
                    metric=record.get("metric"),
                    baseline=record.get("baseline"),
                    new=record.get("new"),
                    delta=record.get("delta"),
                    threshold=record.get("threshold"),
                    passed=record.get("passed"),
                    evidence=", ".join(record.get("evidence_refs", [])),
                    claim=", ".join(record.get("claim_refs", [])),
                )
            )
    else:
        lines.append("- No compare records found.")

    lines.extend(["", "## Core Conclusions"])
    core_lines: list[str] = []
    for claim in claims.values():
        if claim.get("type") != "claim":
            continue
        evidence_ids = [
            evidence_id
            for evidence_id in claim.get("evidence_ids", [])
            if isinstance(evidence_id, str)
        ] if isinstance(claim.get("evidence_ids"), list) else []
        core_lines.append(
            "claim: {claim_id}; state: {state}; evidence: {evidence_ids}; text: {text}".format(
                claim_id=claim.get("id"),
                state=claim.get("state"),
                evidence_ids=", ".join(evidence_ids) or "missing",
                text=claim.get("text"),
            )
        )
    lines.append(bullet_or_none(core_lines).rstrip("\n"))

    lines.extend(["", "## Evidence Index"])
    evidence_lines = [
        "evidence: {evidence_id}; source: {source}; summary: {summary}; limits: {limits}".format(
            evidence_id=record.get("id"),
            source=record.get("source"),
            summary=record.get("summary"),
            limits=record.get("limits"),
        )
        for record in evidence.values()
        if record.get("type") == "evidence"
    ]
    lines.append(bullet_or_none(evidence_lines).rstrip("\n"))

    lines.extend(
        [
            "",
            "## Limitations",
            args.limitations,
            "",
            "## Risks",
            args.risks,
            "",
            "## Conclusion Status",
            "- conclusion_state: claim_ready",
            "- human/root approval required before any approved claim.",
            f"- claim_review_supported: {claim_review.get('supported')}",
        ]
    )
    return "\n".join(lines) + "\n"


def report_command(args: argparse.Namespace) -> int:
    root = repo_root()
    task = args.task
    try:
        claim_path = record_path(root, task, "claim")
        evidence_path = record_path(root, task, "evidence")
        cmp_path = compare_path(root, task)
        out_path = (
            report_path(root, task)
            if args.output is None
            else resolve_task_hermes_output_path(root, task, args.output)
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    claims, claim_errors = records_by_id(claim_path)
    evidence, evidence_errors = records_by_id(evidence_path)
    compares, compare_errors = load_compare_records(cmp_path)
    claim_review, review_errors = review_claims(args.task)
    errors = claim_errors + evidence_errors + compare_errors + review_errors
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    markdown = report_markdown(args, claims, evidence, compares, claim_review)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")
    print(f"report written to {relative_to_root(root, out_path)}")
    return 0


def add_aggregate_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("aggregate")
    parser.add_argument("--task", required=True)
    parser.add_argument("--output")


def add_compare_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("compare")
    parser.add_argument("--task", required=True)
    parser.add_argument("--metric", required=True)
    parser.add_argument("--baseline", required=True, type=number_arg)
    parser.add_argument("--new", required=True, type=number_arg)
    parser.add_argument("--threshold", required=True, type=number_arg)
    parser.add_argument(
        "--direction",
        required=True,
        choices=["higher_is_better", "lower_is_better"],
    )
    parser.add_argument("--evidence-ref", action="append")
    parser.add_argument("--claim-ref", action="append")


def add_report_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("report")
    parser.add_argument("--task", required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--method", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--metrics", required=True)
    parser.add_argument("--limitations", required=True)
    parser.add_argument("--risks", required=True)
    parser.add_argument("--output")


def add_claim_review_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("claim-review")
    parser.add_argument("--task", required=True)
    parser.add_argument("--claim-id")


def add_quality_gate_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("quality-gate")
    parser.add_argument("--task", required=True)


def add_approval_gate_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("approval-gate")
    parser.add_argument("--task", required=True)
    parser.add_argument("--claim-id", required=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate, compare, and report Hermes research results.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_aggregate_parser(subparsers)
    add_compare_parser(subparsers)
    add_report_parser(subparsers)
    add_claim_review_parser(subparsers)
    add_quality_gate_parser(subparsers)
    add_approval_gate_parser(subparsers)

    args = parser.parse_args()
    if args.command == "aggregate":
        return aggregate_command(args)
    if args.command == "compare":
        return compare_command(args)
    if args.command == "report":
        return report_command(args)
    if args.command == "claim-review":
        return claim_review_command(args)
    if args.command == "quality-gate":
        return quality_gate_command(args)
    if args.command == "approval-gate":
        return approval_gate_command(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
