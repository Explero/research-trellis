"""Runtime capability and heartbeat checks for the Agent Context Firewall."""

from __future__ import annotations

import json
import os
import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io import write_json_atomic


SUPPORTED_PLATFORMS = {"claude", "codex"}
FIREWALL_HEARTBEAT_TTL_SECONDS = 15 * 60


def hooks_disabled() -> bool:
    return (
        os.environ.get("TRELLIS_HOOKS") == "0"
        or os.environ.get("TRELLIS_DISABLE_HOOKS") == "1"
    )


def heartbeat_root(repo_root: Path) -> Path:
    return repo_root / ".trellis" / ".runtime" / "context-firewall"


def record_firewall_heartbeat(
    repo_root: Path,
    platform: str,
    mechanism: str,
    *,
    task_id: str | None = None,
    job_id: str | None = None,
    session_id: str | None = None,
) -> bool:
    if platform not in SUPPORTED_PLATFORMS or mechanism not in {"hooks", "strict"}:
        return False
    if mechanism == "hooks" and hooks_disabled():
        return False
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = {
        "platform": platform,
        "mechanism": mechanism,
        "task_id": task_id,
        "job_id": job_id,
        "session_id": session_id,
        "timestamp": timestamp,
        "pid": os.getpid(),
        "nonce": secrets.token_hex(12),
    }
    payload["signature"] = _sign_heartbeat(repo_root, payload)
    identity = hashlib.sha256(
        f"{platform}:{mechanism}:{task_id or '-'}:{job_id or '-'}:{session_id or '-'}".encode()
    ).hexdigest()[:20]
    return write_json_atomic(
        heartbeat_root(repo_root) / f"{platform}-{mechanism}-{identity}.json",
        payload,
    )


def firewall_health(
    repo_root: Path,
    *,
    platform: str | None = None,
    mechanism: str | None = None,
    task_id: str | None = None,
    job_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    active: list[dict[str, str]] = []
    disabled = hooks_disabled()
    required_platform = platform
    required_mechanism = mechanism
    for path in heartbeat_root(repo_root).glob("*.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            timestamp = _parse_timestamp(value.get("timestamp"))
        except (OSError, json.JSONDecodeError, AttributeError):
            continue
        record_platform = value.get("platform")
        record_mechanism = value.get("mechanism")
        if record_platform not in SUPPORTED_PLATFORMS or record_mechanism not in {"hooks", "strict"}:
            continue
        age = (now - timestamp).total_seconds() if timestamp is not None else None
        if timestamp is None or age is None or age < -5 or age > _heartbeat_ttl():
            continue
        if record_mechanism == "hooks" and disabled:
            continue
        if not _verify_heartbeat(repo_root, value):
            continue
        if required_platform is not None and record_platform != required_platform:
            continue
        if required_mechanism is not None and record_mechanism != required_mechanism:
            continue
        if task_id is not None and value.get("task_id") != task_id:
            continue
        if job_id is not None and value.get("job_id") != job_id:
            continue
        if session_id is not None and value.get("session_id") != session_id:
            continue
        active.append({
            "platform": str(record_platform),
            "mechanism": str(record_mechanism),
            "task_id": str(value.get("task_id") or ""),
            "job_id": str(value.get("job_id") or ""),
        })

    deduped = [
        dict(pair)
        for pair in {
            (item["platform"], item["mechanism"], item["task_id"], item["job_id"]): item
            for item in active
        }.values()
    ]
    return {
        "hooks_disabled": disabled,
        "active": sorted(deduped, key=lambda item: (item["platform"], item["mechanism"])),
        "hard_gate": bool(deduped),
        "advisory_signals": {
            "hooks_env": os.environ.get("TRELLIS_HOOKS_ACTIVE") == "1",
            "codex_strict_env": os.environ.get("TRELLIS_CODEX_STRICT") == "1",
        },
    }


def closure_mode_gate(
    repo_root: Path,
    mode: str,
    *,
    platform: str | None = None,
    mechanism: str | None = None,
    task_id: str | None = None,
    job_id: str | None = None,
    session_id: str | None = None,
) -> tuple[list[str], list[str]]:
    health = firewall_health(
        repo_root,
        platform=platform,
        mechanism=mechanism,
        task_id=task_id,
        job_id=job_id,
        session_id=session_id,
    )
    active = health["active"]
    if mode == "lean":
        if not active:
            return [], [
                "Lean context firewall is advisory because no fresh hook or strict heartbeat is active."
            ]
        return [], []
    if active:
        return [], []
    if mode == "publication":
        return [
            "publication requires an active Claude hook or Codex strict context-firewall heartbeat"
        ], []
    return [
        "standard requires an active hook heartbeat or Codex strict execution"
    ], []


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _heartbeat_ttl() -> int:
    raw = os.environ.get("TRELLIS_CONTEXT_FIREWALL_HEARTBEAT_TTL", "")
    try:
        parsed = int(raw)
    except ValueError:
        return FIREWALL_HEARTBEAT_TTL_SECONDS
    return parsed if parsed > 0 else FIREWALL_HEARTBEAT_TTL_SECONDS


def _heartbeat_key_path(repo_root: Path) -> Path:
    return heartbeat_root(repo_root) / ".heartbeat.key"


def _heartbeat_key(repo_root: Path) -> bytes:
    path = _heartbeat_key_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        return path.read_bytes()
    except FileNotFoundError:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags, 0o600)
        except FileExistsError:
            return path.read_bytes()
        value = secrets.token_bytes(32)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        return value


def _heartbeat_message(value: dict[str, Any]) -> bytes:
    unsigned = {key: item for key, item in value.items() if key != "signature"}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sign_heartbeat(repo_root: Path, value: dict[str, Any]) -> str:
    return hmac.new(_heartbeat_key(repo_root), _heartbeat_message(value), hashlib.sha256).hexdigest()


def _verify_heartbeat(repo_root: Path, value: dict[str, Any]) -> bool:
    signature = value.get("signature")
    if not isinstance(signature, str):
        return False
    try:
        expected = _sign_heartbeat(repo_root, value)
    except OSError:
        return False
    return hmac.compare_digest(signature, expected)
