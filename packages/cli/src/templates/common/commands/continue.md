# Continue Current Task

Resume work on the current task — pick up at the right phase/step in `.trellis/workflow.md`.

---

## Step 1: Load Current Context

```bash
{{PYTHON_CMD}} ./.trellis/scripts/get_context.py
```

Confirms: current task, git state, recent commits.

If the active task has Hermes closure fields, immediately load the compact capsule:

```bash
{{PYTHON_CMD}} ./.trellis/scripts/closure.py capsule --task <task>
```

Use the current work package as the execution boundary. Full PRD, reports, events, ledgers, historical tasks, and unrelated specs are read only when needed.

## Step 2: Load the Phase Index

```bash
{{PYTHON_CMD}} ./.trellis/scripts/get_context.py --mode phase
```

Shows the Phase Index (Plan / Execute / Finish) with routing + skill mapping.

## Step 3: Decide Where You Are

`get_context.py` shows the active task's `status` field. First classify the new request as an in-scope continuation, a bounded plan change, or a new task. In-scope detail stays in the current work package and does not regenerate the plan. Route by `status` + artifact presence; this command does not itself approve implementation.

- `status=planning` + no `prd.md` → **1.1** (analyze the task; load `trellis-brainstorm` only if requirements remain unresolved)
- `status=planning` + `prd.md` only → decide whether the task is lightweight or complex. Lightweight can move to **1.4** review; complex returns to **1.1** to add `design.md` + `implement.md`.
- `status=planning` + complex artifacts complete + sub-agent jsonl not curated (only the seed `_example` row) → **1.3**
- `status=planning` + required artifacts complete + required jsonl curated or inline mode → **1.4** (ask for start review; only run `task.py start` after user confirms)
- `status=in_progress` + implementation not started → **2.1**
- `status=in_progress` + implementation done, not yet checked → **2.2**
- `status=in_progress` + check passed → **3.1**
- `status=completed` (rare; usually archived immediately) → archive flow
- `hermes_phase=planning` → plan/validate; `ready` → start the next package; `running` → work only on the current package; `review` → package check or closure audit; `blocked` → follow handoff/human gate; `closed` → finish/archive.

Phase rules (full detail in `.trellis/workflow.md`):

1. Run steps **in order** within a phase — `[required]` steps must not be skipped
2. `[once]` steps are already done if the required output exists. `prd.md` alone can be enough only for lightweight tasks; complex tasks also need `design.md` and `implement.md`.
3. You may go back to an earlier phase if discoveries require it

## Step 4: Load the Specific Step

Once you know which step to resume at:

```bash
{{PYTHON_CMD}} ./.trellis/scripts/get_context.py --mode phase --step <X.X> --platform {{CLI_FLAG}}
```

Follow the loaded instructions. After each `[required]` step completes, move to the next.

---

## Reference

Full workflow and detailed phase steps live in `.trellis/workflow.md`. This command is only an entry point — the canonical guidance is there.
