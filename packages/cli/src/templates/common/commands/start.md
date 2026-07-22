# Start Session

Initialize a Trellis-managed development session. This platform has no session-start hook, so manually load the equivalent compact context by following these steps.

---

## Step 1: Current state
Identity, git status, current task, active tasks, journal location.

```bash
{{PYTHON_CMD}} ./.trellis/scripts/get_context.py
```

If this output includes a line beginning `Research Trellis update available:`, copy the full line verbatim when summarizing session context. Do not shorten operational command hints.

## Step 2: Workflow overview
Compact Phase Index, request triage rules, planning artifact contract, and the step-detail command.

```bash
{{PYTHON_CMD}} ./.trellis/scripts/get_context.py --mode phase
```

Full guide in `.trellis/workflow.md` (read on demand).

## Step 3: Guideline indexes
Discover packages + spec layers, then read each relevant index file.

```bash
{{PYTHON_CMD}} ./.trellis/scripts/get_context.py --mode packages
cat .trellis/spec/guides/index.md
cat .trellis/spec/<package>/<layer>/index.md   # for each relevant layer
```

Index files list the specific guideline docs to read when you actually start coding.

## Step 4: Decide next action
From Step 1 you know the current task and status. Check the task directory:

For a Hermes closure task, run `{{PYTHON_CMD}} ./.trellis/scripts/closure.py capsule --task <task>` first. Use only the current package and its related references; load full PRD, reports, event history, ledgers, old tasks, and unrelated specs on demand.

- **Active task status `planning` + no `prd.md`** → Phase 1.1. Analyze intent, scope, completion criteria, research route, and a 1-4 package candidate split. Load `trellis-brainstorm` only if requirements remain unresolved after reading relevant project evidence.
- **Active task status `planning` + `prd.md` exists** → stay in Phase 1. Read the Task Capsule, keep existing work packages for an in-scope continuation, and use `closure.py amend` for a real plan change. `trellis-grill-me` is optional and only applies to an unresolved material research or scope decision; task complexity alone never makes it mandatory. Lightweight tasks can be PRD-only, while code-heavy complex tasks add `design.md` and `implement.md` with their development strategy and explicitly selected review gates before `task.py start`.
- **Active task status `in_progress`** → Phase 2 step 2.1. Load the step detail:
  ```bash
  {{PYTHON_CMD}} ./.trellis/scripts/get_context.py --mode phase --step 2.1 --platform {{CLI_FLAG}}
  ```
- **Hermes phase `review`** → run `closure.py audit`; use `closure.py repair` only for listed gaps and within the configured limit.
- **Hermes phase `blocked`** → read the capsule and `HANDOFF.md`; do not widen scope or bypass human approval.
- **Hermes phase `closed`** → the task may be finished or archived; this does not imply claim approval.
- **No active task** → analyze every actionable request first, then ask whether this turn should create a Trellis task. If the user says no, skip Trellis for this session.

---

## Skill routing (quick reference)

| User intent | Skill |
|---|---|
| Research question, scope, or done criteria remain unclear | `trellis-brainstorm` |
| Material research-contract decision remains unresolved | `trellis-grill-me` |
| Current work package requires code | coder uses `trellis-before-dev` |
| Code work is complete | runner verifies; reviewer uses `trellis-check` |
| Repeated technical failure, not a negative research result | planner uses `trellis-break-loop` |
| Reviewed durable knowledge exists near closure | coder configuration uses `trellis-update-spec` |

Full rules + anti-rationalization table in `.trellis/workflow.md`.
