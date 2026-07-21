#!/usr/bin/env python3
"""Collect, validate, and summarize Hermes evidence deterministically."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from runtime import (
    ARTIFACT_FILE,
    EVIDENCE_FILE,
    RUN_MANIFEST_FILE,
    has_symlink_component,
    hermes_dir,
    read_jsonl,
    repo_root,
    validate_records,
)


SUMMARY_FILE = "evidence_summary.json"


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def record_index(
    path: Path,
    record_type: str | None,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    records, errors = read_jsonl(path)
    index: dict[str, dict[str, Any]] = {}
    for entry in records:
        value = entry.value
        record_id = value.get("id")
        if (record_type is None or value.get("type") == record_type) and isinstance(record_id, str):
            index[record_id] = value
    return index, errors


def build_summary(root: Path, task: str) -> tuple[dict[str, Any], list[str]]:
    directory = hermes_dir(root, task)
    artifact_path = directory / ARTIFACT_FILE
    evidence_path = directory / EVIDENCE_FILE
    manifest_path = directory / RUN_MANIFEST_FILE
    artifacts, artifact_read_errors = record_index(artifact_path, "artifact")
    evidence, evidence_read_errors = record_index(evidence_path, "evidence")
    manifests, manifest_read_errors = record_index(manifest_path, None)
    errors = [*artifact_read_errors, *evidence_read_errors, *manifest_read_errors]

    dangling_artifacts: list[dict[str, str]] = []
    duplicate_refs: list[dict[str, str]] = []
    missing_fields: list[dict[str, str]] = []
    evidence_rows: list[dict[str, Any]] = []
    referenced_artifacts: set[str] = set()

    for evidence_id in sorted(evidence):
        item = evidence[evidence_id]
        artifact_refs = string_list(item.get("artifact_refs"))
        for artifact_id in sorted(set(artifact_refs)):
            referenced_artifacts.add(artifact_id)
            if artifact_id not in artifacts:
                dangling_artifacts.append({"evidence_id": evidence_id, "artifact_id": artifact_id})
        for artifact_id in sorted({ref for ref in artifact_refs if artifact_refs.count(ref) > 1}):
            duplicate_refs.append({"evidence_id": evidence_id, "artifact_id": artifact_id})
        for field in ("source", "summary", "limits"):
            if not isinstance(item.get(field), str) or not str(item.get(field)).strip():
                missing_fields.append({"record_id": evidence_id, "field": field})
        evidence_rows.append(
            {
                "id": evidence_id,
                "source": item.get("source"),
                "artifact_refs": sorted(set(artifact_refs)),
                "command_refs": sorted(set(string_list(item.get("command_refs")))),
                "limits": item.get("limits"),
            }
        )

    artifact_rows: list[dict[str, Any]] = []
    dangling_runs: list[dict[str, str]] = []
    for artifact_id in sorted(artifacts):
        item = artifacts[artifact_id]
        run_id = item.get("run_id")
        if (
            isinstance(run_id, str)
            and run_id.strip()
            and manifests
            and run_id not in manifests
        ):
            dangling_runs.append({"artifact_id": artifact_id, "run_id": run_id})
        artifact_rows.append(
            {
                "id": artifact_id,
                "path": item.get("path"),
                "hash": item.get("hash"),
                "run_id": run_id,
                "referenced": artifact_id in referenced_artifacts,
            }
        )

    validation_errors = [
        *validate_records(artifact_path, "artifact"),
        *validate_records(evidence_path, "evidence"),
    ]
    if manifest_path.exists():
        validation_errors.extend(validate_records(manifest_path, "run_manifest"))
    validation_errors = list(dict.fromkeys(validation_errors))
    errors.extend(validation_errors)
    summary = {
        "task": task,
        "counts": {
            "artifacts": len(artifacts),
            "evidence": len(evidence),
            "run_manifests": len(manifests),
        },
        "artifacts": artifact_rows,
        "evidence": evidence_rows,
        "validation_errors": validation_errors,
        "gaps": {
            "dangling_artifact_refs": dangling_artifacts,
            "dangling_run_refs": dangling_runs,
            "duplicate_artifact_refs": duplicate_refs,
            "missing_fields": missing_fields,
            "unreferenced_artifacts": sorted(set(artifacts) - referenced_artifacts),
        },
    }
    if dangling_artifacts:
        errors.append("dangling evidence artifact references found")
    if dangling_runs:
        errors.append("dangling artifact run manifest references found")
    if duplicate_refs:
        errors.append("duplicate evidence artifact references found")
    if missing_fields:
        errors.append("evidence records have missing required content")
    return summary, errors


def write_summary(path: Path, value: dict[str, Any]) -> None:
    if has_symlink_component(path):
        raise OSError(f"refusing to write through symlink: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_compact(summary: dict[str, Any]) -> None:
    counts = summary["counts"]
    gaps = summary["gaps"]
    validation_errors = summary.get("validation_errors") or []
    gap_count = sum(len(value) for value in gaps.values()) + len(validation_errors)
    print(f"task: {summary['task']}")
    print(
        "records: "
        f"{counts['evidence']} evidence, {counts['artifacts']} artifacts, "
        f"{counts['run_manifests']} run manifests"
    )
    print(f"gaps: {gap_count}")
    for error in validation_errors:
        print(f"- validation: {error}")
    for name, values in gaps.items():
        if values:
            print(f"- {name}: {json.dumps(values, ensure_ascii=False, separators=(',', ':'))}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deterministically collect, validate, and summarize Hermes evidence."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("collect", "validate", "summary"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--task", required=True)
    args = parser.parse_args()
    root = repo_root()

    try:
        summary, summary_errors = build_summary(root, args.task)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.command == "collect":
        path = hermes_dir(root, args.task) / SUMMARY_FILE
        try:
            write_summary(path, summary)
        except OSError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"wrote {path.relative_to(root)}")
        return 0

    if args.command == "summary":
        print_compact(summary)
        return 0

    errors = list(summary_errors)
    unique_errors = list(dict.fromkeys(errors))
    if unique_errors:
        for error in unique_errors:
            print(error, file=sys.stderr)
        return 1
    print("valid evidence and artifact references")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
