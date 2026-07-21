"""Canonical Hermes roles, profiles, and legacy role normalization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CANONICAL_ROLES = ("planner", "researcher", "coder", "runner", "reviewer")

ROLE_PROFILES: dict[str, tuple[str, ...]] = {
    "planner": (
        "research_design",
        "task_planning",
        "root_cause",
        "method_selection",
    ),
    "researcher": ("literature", "codebase", "external_docs", "prior_art"),
    "coder": ("implementation", "tests", "configuration", "repair"),
    "runner": ("experiment", "test", "build", "validation"),
    "reviewer": ("quality", "evidence", "claim", "safety", "closure", "statistics"),
}

DEFAULT_PROFILES = {
    "planner": "task_planning",
    "researcher": "codebase",
    "coder": "implementation",
    "runner": "validation",
    "reviewer": "quality",
}

ROLE_SUMMARIES = {
    "planner": "Design and plan bounded work; propose changes without approving high-risk research changes.",
    "researcher": "Find and summarize code, literature, prior art, or official documentation; do not mutate implementation or state.",
    "coder": "Modify code, tests, and configuration inside the task-card boundary; do not approve claims or close tasks.",
    "runner": "Execute experiments, tests, builds, and validation; register commands and artifacts without changing core code.",
    "reviewer": "Independently review quality, evidence, claims, safety, statistics, or closure; never alter source results.",
}

PROFILE_SUMMARIES = {
    ("planner", "research_design"): "Define the question, hypothesis, experiment design, evidence standard, limits, and claim boundary.",
    ("planner", "task_planning"): "Define intent, scope, completion criteria, 1-4 outcome-based work packages, next action, and blockers.",
    ("planner", "root_cause"): "Explain the failure, testable causes, minimum diagnostics, and bounded repair options.",
    ("planner", "method_selection"): "Compare methods against data, resources, verification criteria, and risk.",
    ("researcher", "literature"): "Collect papers, DOI and citation details, conclusions, evidence type, and citation limits.",
    ("researcher", "codebase"): "Locate relevant files, call paths, existing tests, and repository conventions.",
    ("researcher", "external_docs"): "Use official documentation to identify APIs, version differences, and external constraints.",
    ("researcher", "prior_art"): "Find comparable projects and existing mechanisms, including their applicability limits.",
    ("coder", "implementation"): "Implement the assigned observable outcome within allowed files.",
    ("coder", "tests"): "Add or repair focused automated coverage for the assigned behavior.",
    ("coder", "configuration"): "Change bounded configuration and keep generated templates consistent.",
    ("coder", "repair"): "Apply only the defects or audit gaps explicitly assigned for repair.",
    ("runner", "experiment"): "Execute the declared experiment and record its manifest and artifacts.",
    ("runner", "test"): "Run the requested tests and register exact commands and outcomes.",
    ("runner", "build"): "Build the requested packages and register exact commands and outcomes.",
    ("runner", "validation"): "Run bounded validation or environment checks and register the result.",
    ("reviewer", "quality"): "Review correctness, maintainability, tests, regressions, and task scope.",
    ("reviewer", "evidence"): "Judge whether evidence references and artifacts satisfy done_when and claim support.",
    ("reviewer", "claim"): "Review claim wording, scope, evidence, limitations, and approval prerequisites.",
    ("reviewer", "safety"): "Review permission boundaries, sensitive data, destructive actions, and security risk.",
    ("reviewer", "closure"): "Review completion criteria, package disposition, blockers, repair count, and close gates.",
    ("reviewer", "statistics"): "Review sample count, variance, intervals, seeds, splits, effect size, and comparison fairness.",
}

LEGACY_ROLE_ALIASES = {
    "scientist": ("planner", "research_design"),
    "builder": ("coder", "implementation"),
    "literature": ("researcher", "literature"),
    "evaluator": ("reviewer", "evidence"),
    "claim-reviewer": ("reviewer", "claim"),
    "claim_reviewer": ("reviewer", "claim"),
}

CODE_REVIEW_PROFILES = {"quality", "safety"}
CODE_RUNNER_PROFILES = {"test", "build", "validation"}
ACTIVE_WRITER_ROLES = {"coder", "runner"}


class RoleProfileError(ValueError):
    """Raised when a task card requests an invalid role/profile contract."""


@dataclass(frozen=True)
class RoleProfile:
    role: str | None
    profile: str | None
    warnings: tuple[str, ...] = ()
    dispatchable: bool = True


def normalize_role_profile(
    role: Any,
    profile: Any = None,
    *,
    context: str = "",
    for_write: bool = False,
) -> RoleProfile:
    if not isinstance(role, str) or not role.strip():
        raise RoleProfileError("task_card role must be a non-empty string")
    normalized_role = role.strip().casefold().replace(" ", "-")
    normalized_profile = _normalize_profile(profile)

    if normalized_role == "evidence-curator":
        message = (
            "deprecated role evidence-curator is tool-only; use the deterministic "
            "evidence command and reviewer:evidence for judgment"
        )
        if for_write:
            raise RoleProfileError(message)
        return RoleProfile(None, None, (message,), dispatchable=False)

    warning: str | None = None
    if normalized_role in CANONICAL_ROLES:
        canonical_role = normalized_role
        canonical_profile = normalized_profile or DEFAULT_PROFILES[canonical_role]
    elif normalized_role in {"research/scout", "research-scout", "research_scout"}:
        canonical_role = "researcher"
        canonical_profile = normalized_profile or _research_profile(context)
        warning = _legacy_warning(role, canonical_role, canonical_profile)
    elif normalized_role == "analyst":
        canonical_role, inferred = _analyst_profile(context, normalized_profile)
        canonical_profile = normalized_profile or inferred
        warning = _legacy_warning(role, canonical_role, canonical_profile)
        if not context.strip() and normalized_profile is None:
            warning += "; context was ambiguous, using safe default planner:root_cause"
    elif normalized_role in LEGACY_ROLE_ALIASES:
        canonical_role, default_profile = LEGACY_ROLE_ALIASES[normalized_role]
        canonical_profile = normalized_profile or default_profile
        warning = _legacy_warning(role, canonical_role, canonical_profile)
    else:
        allowed = ", ".join(CANONICAL_ROLES)
        raise RoleProfileError(f"unknown Hermes role {role!r}; expected one of: {allowed}")

    validate_role_profile(canonical_role, canonical_profile)
    warnings = (warning,) if warning else ()
    return RoleProfile(canonical_role, canonical_profile, warnings)


def normalize_task_card(
    card: dict[str, Any],
    *,
    for_write: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    context = " ".join(
        str(card.get(field) or "")
        for field in ("objective", "summary")
    )
    normalized = normalize_role_profile(
        card.get("role"),
        card.get("profile"),
        context=context,
        for_write=for_write,
    )
    if not normalized.dispatchable:
        return dict(card), list(normalized.warnings)
    result = dict(card)
    result["role"] = normalized.role
    result["profile"] = normalized.profile
    return result, list(normalized.warnings)


def validate_role_profile(role: str, profile: str) -> None:
    if role not in ROLE_PROFILES:
        allowed = ", ".join(CANONICAL_ROLES)
        raise RoleProfileError(f"unknown Hermes role {role!r}; expected one of: {allowed}")
    if profile not in ROLE_PROFILES[role]:
        allowed = ", ".join(ROLE_PROFILES[role])
        raise RoleProfileError(
            f"invalid profile {profile!r} for role {role!r}; expected one of: {allowed}"
        )


def role_summary(role: str) -> str:
    return ROLE_SUMMARIES[role]


def profile_summary(role: str, profile: str) -> str:
    validate_role_profile(role, profile)
    return PROFILE_SUMMARIES[(role, profile)]


def _normalize_profile(profile: Any) -> str | None:
    if profile is None or profile == "":
        return None
    if not isinstance(profile, str):
        raise RoleProfileError("task_card profile must be a string when supplied")
    return profile.strip().casefold().replace("-", "_").replace(" ", "_")


def _legacy_warning(old_role: Any, role: str, profile: str) -> str:
    return f"deprecated Hermes role {old_role!r}; normalized to {role}:{profile}"


def _research_profile(context: str) -> str:
    text = context.casefold()
    if _contains_any(text, ("paper", "doi", "citation", "literature", "论文", "文献", "引用")):
        return "literature"
    if _contains_any(text, ("official", "api", "documentation", "external docs", "官方", "外部文档")):
        return "external_docs"
    return "codebase"


def _analyst_profile(
    context: str,
    explicit_profile: str | None = None,
) -> tuple[str, str]:
    if explicit_profile in ROLE_PROFILES["planner"]:
        return "planner", explicit_profile
    if explicit_profile in ROLE_PROFILES["reviewer"]:
        return "reviewer", explicit_profile
    text = context.casefold()
    if _contains_any(text, ("statistics", "variance", "confidence interval", "effect size", "统计", "方差", "置信区间")):
        return "reviewer", "statistics"
    if _contains_any(text, ("evidence", "可信", "证据", "artifact", "claim support")):
        return "reviewer", "evidence"
    if _contains_any(text, ("result quality", "quality of result", "结果质量", "结果是否")):
        return "reviewer", "quality"
    if _contains_any(text, ("method", "tradeoff", "方案权衡", "方法选择")):
        return "planner", "method_selection"
    return "planner", "root_cause"


def _contains_any(text: str, candidates: tuple[str, ...]) -> bool:
    return any(candidate in text for candidate in candidates)
