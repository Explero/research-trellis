# Trellis Brainstorm

## Focused Research Framing Contract

The main agent triggers this skill only when the research question, scope, or
observable completion criteria remain unclear after repository-first analysis.
It is not part of every task. Clear delivery and frozen-protocol execution tasks
go directly to a bounded closure plan.

Resolve only uncertainties that block planning. Ask one high-value question at
a time and include a recommended answer. A researcher may collect missing
sources; a planner may propose framing, but the main agent retains routing and
the user retains research decisions.

## Non-Negotiable Evidence Rule

If a question can be answered by exploring the codebase, explore the codebase instead.

This is mandatory. Before asking the user a question, first check whether the answer is already available in code, tests, configs, docs, existing specs, or task history.

Do not ask the user to confirm facts that the repository can answer. Ask only
for research intent, scope, evidence expectations, preferences, risk tolerance,
or decisions that remain ambiguous after inspection.

---

Use this skill only when Phase 1 analysis finds a real requirement or solution
decision that cannot be resolved from the repository. It is not the default
planning path: every task needs a short main-agent analysis and work-package
split, but clear deterministic work can proceed directly to `closure.py plan`
and `closure.py validate`.

## Preconditions

Use this skill only after task-creation consent has been given and the user is ready to enter Trellis planning.

If no task exists yet, create one:

```bash
TASK_DIR=$({{PYTHON_CMD}} ./.trellis/scripts/task.py create "<short task title>" --slug <slug>)
```

Use a concise title from the user's request. Use a slug without a date prefix. `task.py create` adds the `MM-DD-` directory prefix automatically.

`task.py create` creates the default `prd.md`. Update that file with the current understanding before asking follow-up questions.

## Planning Flow

1. Capture the user's request and initial known facts in `prd.md`.
2. Inspect available evidence before asking questions:
   - code, tests, fixtures, and configs
   - README files, docs, existing specs, and domain notes
   - related Trellis tasks, research files, and session history when present
3. Separate what you found into:
   - confirmed facts
   - product intent still needed from the user
   - scope or risk decisions still needed from the user
   - likely out-of-scope items
4. Ask the single highest-value remaining question.
5. Include your recommended answer with the question.
6. After each user answer, update `prd.md` before continuing.
7. Do not enter `trellis-grill-me` only because a task is legacy or complex. Use it when a material solution, architecture, research-design, or scope decision remains unresolved after repository inspection, and tighten only that decision one question at a time with a recommendation.
8. For a Lean Research Closure task, always record the final intent, scope, definition of done, route, and work packages. When these are clear, run `closure.py plan` and `closure.py validate` directly. For an exploration route, keep the required grill focused on the changed research decision rather than turning it into a general interview.
9. Before implementation starts on the Claude Code path, record the development strategy decisions in the task documents: development mode, branch vs worktree, default flow vs TDD, and the task-level review-gate selection. Ask these in a single `A.` / `B.` / `C.` style option block. New tasks must stamp that strategy block with `Review-gate contract: explicit-selection-v1`. Lightweight tasks may keep that record in `prd.md`; complex tasks should keep it in `implement.md` together with the enabled/disabled review gates and the preserved execution order for any enabled Claude review gates: `trellis-spec-review` → `trellis-code-review` → `trellis-code-architecture-review`. The selectable review gates are `trellis-spec-review`, `trellis-code-review`, `trellis-code-architecture-review`, `trellis-improve-codebase-architecture`, and `trellis-merge-review`. While the choice is still open, `Optional review gates status: pending` is allowed; before `task.py start`, replace it with `Optional review gates status: configured` plus explicit `Enabled optional review gates:` and `Disabled optional review gates:` lists. If the user leaves all optional gates off, still record all five in the disabled list; `trellis-check` stays fixed outside this set. Only tasks that entirely lack `Review-gate contract: explicit-selection-v1` count as legacy tasks and preserve the old behavior; if the marker exists but the configured enabled/disabled lists are missing, planning is incomplete and the task must not start. `trellis-improve-codebase-architecture` deep-review requires `trellis-code-architecture-review`, so do not record or accept the deep-review gate without that prerequisite. If the strategy is `subagent + worktree`, pin `./.trellis/trellis-worktrees/<task-dir-name>`. If the strategy is TDD, record `trellis-tdd` as the reference flow. Also record whether to run pre-development architecture guidance in that same strategy block. If guidance is enabled, record `架构审查：enabled`, dispatch `trellis-improve-codebase-architecture` with `架构审查模式: guidance` before `task.py start`, and append its output to `design.md`, but do NOT implicitly enable `trellis-improve-codebase-architecture` deep-review; that gate still requires explicit selection in the task-level review-gate set.
10. For complex tasks, create or update `design.md` and `implement.md` after the required clarification is complete. A Lean closure task needs them only when its scope actually requires them.
11. For a Hermes closure task, copy the final intent, scope boundaries, and acceptance criteria into `task.json` through `closure.py plan`. Keep 1-4 observable-result work packages by default; commands and file operations belong in `done_when`, not separate packages. Run `closure.py validate` before `task.py start`.

Do not invent a project-specific product/spec hierarchy. If the repository already has product, domain, or spec docs, use them. If it does not, proceed with the evidence that exists.

## Question Rules

Ask only one question per message.

Each question must include:

- the decision needed
- why the answer matters
- your recommended answer
- the trade-off if the user chooses differently

Do not ask process questions such as whether to search, inspect files, or continue brainstorming. Do the evidence work directly. Ask the user only when the remaining issue is a product decision, preference, scope boundary, or risk tolerance choice.

## Artifact Rules

`prd.md` records requirements and acceptance:

- goal and user value
- confirmed facts
- requirements
- acceptance criteria
- out of scope
- open questions that still block planning

`design.md` records technical design for complex tasks:

- architecture and boundaries
- data flow and contracts
- compatibility and migration notes
- important trade-offs
- operational or rollback considerations

`implement.md` records execution planning for complex tasks:

- development strategy decisions
- review-gate selection and enabled-gate order
- ordered implementation checklist
- validation commands
- risky files or rollback points
- follow-up checks before `task.py start`

Lightweight tasks may have only `prd.md`. Complex tasks must have `prd.md`, `design.md`, and `implement.md` before `task.py start`.

`implement.md` is not a replacement for `implement.jsonl`. Use JSONL files only for manifest-style spec and research references when the task needs them.

## Quality Bar

Before declaring planning ready:

- `prd.md` contains testable acceptance criteria.
- Repository-answerable questions have already been answered through inspection.
- Remaining open questions are genuinely about user intent or scope.
- Complex tasks have `design.md` and `implement.md`.
- The user has reviewed the final planning artifacts or explicitly approved proceeding.
- The closure plan has an intent, definition of done, and 1-4 appropriately sized work packages; 5 or more only carries a task-split warning.
- `closure.py validate` passes before `task.py start` for new Hermes tasks.

Do not start implementation until the user approves or asks for implementation.
