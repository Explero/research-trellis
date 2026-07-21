#!/usr/bin/env python3
"""Trellis per-turn breadcrumb hook (UserPromptSubmit / BeforeAgent equivalent).

Runs on every user prompt. Resolves the active task through Trellis'
session-aware active task resolver and emits a short <workflow-state>
block reminding the main AI what task is active and its expected flow.

The emitted ``hookEventName`` field is platform-aware: most hosts expect
``UserPromptSubmit`` (Claude Code naming, also accepted by Cursor / Qoder /
CodeBuddy / Droid / Codex / Copilot wiring), but Gemini CLI 0.40.x renamed
its per-turn event to ``BeforeAgent`` and its schema validator rejects the
legacy name. ``_detect_platform`` picks the right value at runtime.
Breadcrumb text is pulled exclusively from workflow.md
[workflow-state:STATUS] tag blocks — workflow.md is the single source of
truth. There are no fallback dicts in this script: when workflow.md is
missing or a tag is absent, the breadcrumb degrades to a generic
"Refer to workflow.md for current step." line so users see (and fix)
the broken state instead of the hook silently masking it.

Shared across all hook-capable platforms (Claude, Cursor, Codex, Qoder,
CodeBuddy, Droid, Gemini, Copilot). Kiro is not wired (no per-turn
hook entry point). Written to each platform's hooks directory via
writeSharedHooks() at init time.

Silent exit 0 cases (no output):
  - No .trellis/ directory found (not a Trellis project)
  - task.json malformed or missing status
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Force UTF-8 on stdin/stdout/stderr on Windows. Default codepage there is
# cp936 / cp1252 / etc. — non-ASCII content (Chinese task names, prd snippets)
# both in stdin (hook payload from host CLI) and stdout (our emitted blocks)
# raises UnicodeDecodeError / UnicodeEncodeError. Equivalent to `python -X utf8`
# but applied per-stream so we don't depend on host CLI's command wiring.
if sys.platform.startswith("win"):
    import io as _io
    for _stream_name in ("stdin", "stdout", "stderr"):
        _stream = getattr(sys, _stream_name, None)
        if _stream is None:
            continue
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
            except Exception:
                pass
        elif hasattr(_stream, "detach"):
            try:
                setattr(sys, _stream_name, _io.TextIOWrapper(_stream.detach(), encoding="utf-8", errors="replace"))
            except Exception:
                pass
from typing import Optional


# Bootstrap notice for Codex while the session has no active task. Codex does not
# get the full SessionStart overview; this short reminder points the main session
# at the start skill once and leaves the per-turn state block compact.
CODEX_NO_TASK_BOOTSTRAP_NOTICE = """<trellis-bootstrap>
If you have not already loaded Trellis context this session, read the `trellis-start` skill once.
</trellis-bootstrap>"""

PROJECT_CONTEXT_REFS = (
    ("Project background", "BACKGROUND.md", "project origin and objective"),
    ("Research plan", "RESEARCH_PLAN.md", "research approach and evidence limits"),
    ("Project constraints", "CONSTRAINTS.md", "fixed boundaries and approvals"),
)

_HANDOFF_REVISION_RE = re.compile(r"<!--\s*hermes-handoff-revision:\s*(\d+)\s*-->")


def _build_project_context_index(root: Path) -> str:
    """List main-agent project inputs without loading the documents themselves."""
    project_dir = root / ".trellis" / "project"
    lines = [
        "<project-context-index>",
        "Main-agent planning input. Read a relevant document on demand before accepting or splitting a request; do not pass its full content to subagents by default.",
    ]
    for title, filename, purpose in PROJECT_CONTEXT_REFS:
        state = "available" if (project_dir / filename).is_file() else "missing"
        lines.append(
            f"- {title}: .trellis/project/{filename} [{state}] - {purpose}."
        )
    lines.append("</project-context-index>")
    return "\n".join(lines)


def _build_codex_hermes_boot_guard_notice(root: Path) -> str:
    guard_path = root / ".trellis" / "hermes" / "HERMES_MAIN_AGENT_BOOT_GUARD.md"
    if not guard_path.is_file():
        return ""
    return """<main-agent-boot-guard>
Hermes main-agent mode: coordinate state, route bounded work through validated dispatches, require sanitized Result Envelopes, and stop at human/PI gates. Full rules: .trellis/hermes/HERMES_MAIN_AGENT_BOOT_GUARD.md. Formal Claude/Codex context policy: validated_dispatch_only.
</main-agent-boot-guard>"""


# ---------------------------------------------------------------------------
# CWD-robust Trellis root discovery (fixes hook-path-robustness for this hook)
# ---------------------------------------------------------------------------

def find_trellis_root(start: Path) -> Optional[Path]:
    """Walk up from start to find directory containing .trellis/.

    Handles CWD drift: subdirectory launches, monorepo packages, etc.
    Returns None if no .trellis/ found (silent no-op).
    """
    cur = start.resolve()
    while cur != cur.parent:
        if (cur / ".trellis").is_dir():
            return cur
        cur = cur.parent
    return None


# ---------------------------------------------------------------------------
# Active task discovery
# ---------------------------------------------------------------------------

def _detect_platform(input_data: dict) -> str | None:
    if isinstance(input_data.get("cursor_version"), str):
        return "cursor"
    env_map = {
        "CLAUDE_PROJECT_DIR": "claude",
        "CURSOR_PROJECT_DIR": "cursor",
        "CODEBUDDY_PROJECT_DIR": "codebuddy",
        "FACTORY_PROJECT_DIR": "droid",
        "GEMINI_PROJECT_DIR": "gemini",
        "QODER_PROJECT_DIR": "qoder",
        "KIRO_PROJECT_DIR": "kiro",
        "COPILOT_PROJECT_DIR": "copilot",
    }
    for env_name, platform in env_map.items():
        if os.environ.get(env_name):
            return platform
    script_parts = set(Path(sys.argv[0]).parts)
    if ".claude" in script_parts:
        return "claude"
    if ".cursor" in script_parts:
        return "cursor"
    if ".codex" in script_parts:
        return "codex"
    if ".gemini" in script_parts:
        return "gemini"
    if ".qoder" in script_parts:
        return "qoder"
    if ".codebuddy" in script_parts:
        return "codebuddy"
    if ".factory" in script_parts:
        return "droid"
    if ".kiro" in script_parts:
        return "kiro"
    return None


def _resolve_active_task(root: Path, input_data: dict):
    scripts_dir = root / ".trellis" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from common.active_task import resolve_active_task  # type: ignore[import-not-found]

    return resolve_active_task(root, input_data, platform=_detect_platform(input_data))


def get_active_task(root: Path, input_data: dict) -> Optional[tuple[str, str, str]]:
    """Return (task_id, status, source) from the current active task."""
    active = _resolve_active_task(root, input_data)
    if not active.task_path:
        return None

    task_dir = Path(active.task_path)
    if not task_dir.is_absolute():
        task_dir = root / task_dir
    if active.stale:
        return task_dir.name, f"stale_{active.source_type}", active.source

    task_json = task_dir / "task.json"
    if not task_json.is_file():
        return None
    try:
        data = json.loads(task_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    task_id = data.get("id") or task_dir.name
    status = data.get("status", "")
    if not isinstance(status, str) or not status:
        return None
    return task_id, status, active.source


def get_task_capsule(root: Path, input_data: dict) -> str | None:
    """Build the compact Hermes capsule for the active closure task."""
    active = _resolve_active_task(root, input_data)
    if not active.task_path or active.stale:
        return None
    task_dir = Path(active.task_path)
    if not task_dir.is_absolute():
        task_dir = root / task_dir
    try:
        task = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    scripts_dir = root / ".trellis" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from common.closure import build_capsule, is_closure_task  # type: ignore[import-not-found]
    except Exception:
        return None
    if not isinstance(task, dict) or not is_closure_task(task):
        return None
    return build_capsule(task_dir, task, root)


def _build_task_resume_notice(
    root: Path,
    task_dir: Path,
    data: dict,
    *,
    task_id: str,
    phase: str,
    next_action: str,
    handoff_notice: str | None,
) -> str:
    """Point the main agent at durable task state on every active-task turn."""
    def compact(value: object, limit: int) -> str:
        text = " ".join(str(value or "-").split())
        return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."

    try:
        task_ref = task_dir.relative_to(root).as_posix()
    except ValueError:
        task_ref = ".trellis/tasks/" + task_dir.name
    task_label = compact(task_id, 72)
    phase_label = compact(phase, 32)
    current_package = compact(data.get("current_work_package"), 48)
    action = compact(next_action, 180)
    lines = [
        "<task-resume>",
        f"Active task: {task_label}; phase={phase_label}; current package={current_package}; next={action}",
        f"Before planning, dispatching, or continuing work, read {task_ref}/task.json.",
    ]
    if handoff_notice:
        lines.append(handoff_notice)
    lines.append(
        "Read only the directly relevant referenced file for this request; do not preload project context, full task history, or unrelated artifacts."
    )
    lines.append("</task-resume>")
    return "\n".join(lines)


def _handoff_state(task_dir: Path, revision: object) -> tuple[str, str | None]:
    """Return a fresh handoff marker or a compact stale/missing explanation."""
    handoff = task_dir / "HANDOFF.md"
    if not handoff.is_file():
        return "missing", "No current HANDOFF.md exists; use the Task Capsule and task state."
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        return "invalid-task-revision", "Ignore HANDOFF.md until task.json has a valid Hermes revision."
    try:
        prefix = handoff.read_text(encoding="utf-8", errors="replace")[:512]
        marker = _HANDOFF_REVISION_RE.search(prefix)
        stamp = handoff.stat().st_mtime_ns
    except OSError:
        return "unreadable", "HANDOFF.md could not be read; use task.json as the source of truth."
    if marker is None or int(marker.group(1)) != revision:
        return f"stale:{marker.group(1) if marker else 'legacy'}:{stamp}", "HANDOFF.md is stale for this task revision; do not rely on it. Regenerate it before a handoff."
    return f"fresh:{revision}:{stamp}", None


def _context_reset_requested(input_data: dict) -> bool:
    """Recognize compact/clear markers supplied by hook-capable hosts."""
    for key in ("source", "event", "event_type", "reason", "session_start_source"):
        value = input_data.get(key)
        if isinstance(value, str) and value.casefold() in {
            "compact",
            "compaction",
            "context_compacted",
            "clear",
        }:
            return True
    return False


def _closure_turn_context(root: Path, input_data: dict) -> tuple[str, str | None, str] | None:
    """Return closure-specific, revision-aware per-turn context."""
    active = _resolve_active_task(root, input_data)
    if not active.task_path or active.stale:
        return None
    task_dir = Path(active.task_path)
    if not task_dir.is_absolute():
        task_dir = root / task_dir
    try:
        data = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    scripts_dir = root / ".trellis" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from common.closure import (  # type: ignore[import-not-found]
            build_capsule,
            closure_next_action,
            is_closure_task,
            research_route_rule,
            research_route_summary,
        )
    except Exception:
        return None
    if not isinstance(data, dict) or not is_closure_task(data):
        return None
    task_id = str(data.get("id") or task_dir.name)
    revision = data.get("hermes_revision", 0)
    phase = str(data.get("hermes_phase") or "planning")
    next_action = closure_next_action(data)
    route_summary = research_route_summary(data)
    route_rule = research_route_rule(data)
    key = getattr(active, "context_key", None)
    anchor_path = root / ".trellis" / ".runtime" / "sessions" / f"{key}.json" if isinstance(key, str) and key else None
    anchor: dict = {}
    if anchor_path and anchor_path.is_file():
        try:
            anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            anchor = {}
    previous = anchor.get("closure_context_anchor") if isinstance(anchor, dict) else None
    context_reset = _context_reset_requested(input_data)
    if context_reset:
        previous = None
    handoff_marker, handoff_problem = _handoff_state(task_dir, revision)
    seen_handoff_marker = previous.get("handoff_marker") if isinstance(previous, dict) else None
    if handoff_marker == seen_handoff_marker:
        handoff_notice = None
    elif handoff_problem:
        handoff_notice = handoff_problem
    else:
        try:
            handoff_ref = task_dir.relative_to(root).as_posix()
        except ValueError:
            handoff_ref = ".trellis/tasks/" + task_dir.name
        handoff_notice = f"Read {handoff_ref}/HANDOFF.md once before continuing; it matches the current task revision."
    resume_notice = _build_task_resume_notice(
        root,
        task_dir,
        data,
        task_id=task_id,
        phase=phase,
        next_action=next_action,
        handoff_notice=handoff_notice,
    )
    current = {
        "task": task_id,
        "revision": revision,
        "phase": phase,
        "next_action": next_action,
        "route": route_summary,
        "handoff_marker": handoff_marker,
    }
    if anchor_path:
        try:
            anchor_path.parent.mkdir(parents=True, exist_ok=True)
            anchor["closure_context_anchor"] = current
            anchor_path.write_text(json.dumps(anchor, ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError:
            pass
    force_capsule = context_reset or (
        handoff_marker.startswith("fresh:") and handoff_marker != seen_handoff_marker
    )
    if (
        isinstance(previous, dict)
        and previous.get("task") == task_id
        and previous.get("revision") == revision
        and not force_capsule
    ):
        return (
            f"<workflow-state>\nHermes closure task: {task_id}; anchor revision {revision} remains active.\n{route_summary}\nRoute rule: {route_rule}\n</workflow-state>",
            None,
            resume_notice,
        )
    if isinstance(previous, dict) and previous.get("task") == task_id:
        changes = [f"Hermes closure update: {task_id}; revision {previous.get('revision')} -> {revision}."]
        for field, label in (("phase", "Phase"), ("next_action", "Next")):
            if previous.get(field) != current[field]:
                changes.append(f"{label}: {current[field]}")
        if previous.get("route") != current["route"]:
            changes.append(route_summary)
        changes.append("Route rule: " + route_rule)
        return (
            "<workflow-state>\n" + "\n".join(changes) + "\n</workflow-state>",
            build_capsule(task_dir, data, root),
            resume_notice,
        )
    return (
        f"<workflow-state>\nHermes closure task: {task_id}; phase={phase}.\n{route_summary}\nRoute rule: {route_rule}\nNext: {next_action}\n</workflow-state>",
        build_capsule(task_dir, data, root),
        resume_notice,
    )
# ---------------------------------------------------------------------------
# Breadcrumb loading: parse workflow.md, fall back to hardcoded defaults
# ---------------------------------------------------------------------------

# Supports STATUS values with letters, digits, underscores, hyphens
# (so "in-review" / "blocked-by-team" work alongside "in_progress").
_TAG_RE = re.compile(
    r"\[workflow-state:([A-Za-z0-9_-]+)\]\s*\n(.*?)\n\s*\[/workflow-state:\1\]",
    re.DOTALL,
)

def load_breadcrumbs(root: Path) -> dict[str, str]:
    """Parse workflow.md for [workflow-state:STATUS] blocks.

    Returns {status: body_text}. workflow.md is the single source of
    truth — there are no fallback dicts in this script. Missing tags
    (or a missing/unreadable workflow.md) fall back to a generic line
    in build_breadcrumb so users see the broken state and fix
    workflow.md, rather than the hook silently masking the issue.
    """
    workflow = root / ".trellis" / "workflow.md"
    if not workflow.is_file():
        return {}
    try:
        content = workflow.read_text(encoding="utf-8")
    except OSError:
        return {}

    result: dict[str, str] = {}
    for match in _TAG_RE.finditer(content):
        status = match.group(1)
        body = match.group(2).strip()
        if body:
            result[status] = body
    return result


def _read_trellis_config(root: Path) -> dict:
    """Load .trellis/config.yaml via the bundled trellis_config helper.

    The helper lives in .trellis/scripts/common; the hook lives outside the
    scripts tree, so we extend sys.path before importing.
    """
    scripts_dir = root / ".trellis" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from common.trellis_config import read_trellis_config  # type: ignore[import-not-found]
    except Exception:
        return {}
    try:
        return read_trellis_config(root)
    except Exception:
        return {}


def _codex_mode_banner(config: dict) -> str:
    """Emit a `<codex-mode>` banner for the additionalContext payload.

    Reads `codex.dispatch_mode` from .trellis/config.yaml; defaults to
    `sub-agent` when missing or invalid so Codex matches the same
    coordinator-only dispatch contract enforced by Hermes PreToolUse.
    Inline remains an explicit routing mode for installations where the
    Hermes runtime guard is not active; it does not bypass PreToolUse. The banner makes the active
    mode explicit to Codex AI per turn, complementing the workflow-state
    body which is per-status. Mode tells AI which dispatch protocol to
    follow; workflow-state tells AI what step it's at.
    """
    mode = "sub-agent"
    if isinstance(config, dict):
        codex_cfg = config.get("codex")
        if isinstance(codex_cfg, dict):
            cfg_mode = codex_cfg.get("dispatch_mode")
            if cfg_mode in ("inline", "sub-agent"):
                mode = cfg_mode
    if mode == "sub-agent":
        meaning = (
            "sub-agent: implement/check work defaults to Trellis sub-agents; "
            "the main session still coordinates, clarifies, updates specs, commits, and finishes."
        )
    else:
        meaning = (
            "inline: the main session implements/checks directly; "
            "do not dispatch implement/check sub-agents."
        )
    return f"<codex-mode>{meaning}</codex-mode>"


def resolve_breadcrumb_key(
    status: str, platform: str | None, config: dict
) -> str:
    """Pick the breadcrumb tag key based on Codex dispatch_mode.

    Codex defaults to ``sub-agent`` so the main session stays read-only and
    the dispatch protocol matches Hermes PreToolUse gate expectations. Users
    can opt into ``codex.dispatch_mode: inline`` in ``.trellis/config.yaml``
    to use the parallel ``<status>`` tag → ``<status>-inline`` flip when
    the Hermes runtime guard is not active. Invalid or missing values fall
    back to sub-agent.

    Non-codex platforms return the plain status unchanged.
    """
    if platform == "codex":
        mode = "sub-agent"
        if isinstance(config, dict):
            codex_cfg = config.get("codex")
            if isinstance(codex_cfg, dict):
                cfg_mode = codex_cfg.get("dispatch_mode")
                if cfg_mode in ("inline", "sub-agent"):
                    mode = cfg_mode
        return f"{status}-inline" if mode == "inline" else status
    return status


def build_breadcrumb(
    task_id: Optional[str],
    status: str,
    templates: dict[str, str],
    source: str | None = None,
    breadcrumb_key: str | None = None,
) -> str:
    """Build the <workflow-state>...</workflow-state> block.

    - Known status (tag present in workflow.md) → detailed template body
    - Unknown status (no tag, or workflow.md missing) → generic
      "Refer to workflow.md for current step." line
    - `no_task` pseudo-status (task_id is None) → header omits task info
    """
    lookup_key = breadcrumb_key or status
    body = templates.get(lookup_key)
    if body is None and lookup_key != status:
        body = templates.get(status)
    if body is None:
        body = "Refer to workflow.md for current step."
    header = f"Status: {status}" if task_id is None else f"Task: {task_id} ({status})"
    return f"<workflow-state>\n{header}\n{body}\n</workflow-state>"


def build_closure_breadcrumb(task_id: str, status: str) -> str:
    return (
        "<workflow-state>\n"
        f"Task: {task_id} ({status})\n"
        "Hermes closure: use only the Task Capsule and its next action. "
        "Plan/validate before start; execute only the current package; audit in review; "
        "use bounded repair for listed gaps; close before archive. Load full artifacts on demand.\n"
        "</workflow-state>"
    )


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

def _read_trellis_switch_enabled() -> bool:
    try:
        cwd = Path.cwd()
        while cwd != cwd.parent:
            trellis_dir = cwd / ".trellis"
            if trellis_dir.is_dir():
                dev_file = trellis_dir / ".developer"
                if dev_file.is_file():
                    for line in dev_file.read_text(encoding="utf-8").splitlines():
                        if line.startswith("name="):
                            name = line.split("=", 1)[1].strip()
                            switch = trellis_dir / "workspace" / name / "trellis-switch.json"
                            if switch.is_file():
                                return json.loads(switch.read_text(encoding="utf-8")).get("enabled", True)
                return True
            cwd = cwd.parent
    except Exception:
        pass
    return True


def main() -> int:
    if os.environ.get("TRELLIS_HOOKS") == "0" or os.environ.get("TRELLIS_DISABLE_HOOKS") == "1":
        return 0

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        data = {}

    platform = _detect_platform(data)
    if platform == "claude" and not _read_trellis_switch_enabled():
        return 0

    cwd_str = data.get("cwd") or os.getcwd()
    cwd = Path(cwd_str)

    root = find_trellis_root(cwd)
    if root is None:
        return 0  # not a Trellis project

    templates = load_breadcrumbs(root)
    config = _read_trellis_config(root)
    platform = _detect_platform(data)
    closure_context = _closure_turn_context(root, data)
    task = get_active_task(root, data)
    capsule = None
    resume_notice = None
    if closure_context is not None:
        breadcrumb, capsule, resume_notice = closure_context
    elif task is None:
        # No active task — still emit a breadcrumb nudging AI toward
        # trellis-brainstorm + task.py create when user describes real work.
        no_task_key = resolve_breadcrumb_key("no_task", platform, config)
        breadcrumb = build_breadcrumb(
            None, "no_task", templates, breadcrumb_key=no_task_key
        )
    else:
        task_id, status, source = task
        status_key = resolve_breadcrumb_key(status, platform, config)
        source_for_breadcrumb = None if platform == "codex" else source
        breadcrumb = build_breadcrumb(
            task_id, status, templates, source_for_breadcrumb, breadcrumb_key=status_key
        )
        if capsule:
            breadcrumb = build_closure_breadcrumb(task_id, status)
    if platform == "codex":
        parts: list[str] = []
        boot_guard_notice = _build_codex_hermes_boot_guard_notice(root)
        if boot_guard_notice:
            parts.append(boot_guard_notice)
        parts.append(_build_project_context_index(root))
        if task is None:
            parts.append(CODEX_NO_TASK_BOOTSTRAP_NOTICE)
        parts.append(_codex_mode_banner(config))
        parts.append(breadcrumb)
        if resume_notice:
            parts.append(resume_notice)
        if capsule:
            parts.append(f"<task-capsule>\n{capsule}\n</task-capsule>")
        breadcrumb = "\n\n".join(parts)
    else:
        if resume_notice:
            breadcrumb = f"{breadcrumb}\n\n{resume_notice}"
        if capsule:
            breadcrumb = f"{breadcrumb}\n\n<task-capsule>\n{capsule}\n</task-capsule>"

    # Gemini CLI 0.40.x rejects "UserPromptSubmit" — its per-turn event is
    # named "BeforeAgent". Other platforms (Claude/Cursor/Qoder/CodeBuddy/
    # Droid/Codex/Copilot) accept the original Claude-style name.
    hook_event_name = (
        "BeforeAgent" if platform == "gemini" else "UserPromptSubmit"
    )

    output = {
        "hookSpecificOutput": {
            "hookEventName": hook_event_name,
            "additionalContext": breadcrumb,
        }
    }
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
