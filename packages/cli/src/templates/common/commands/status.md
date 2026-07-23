# Show Task Status

Show the current Trellis task without changing task, evidence, claim, or archive state.

## Step 1: Resolve the active task

```bash
{{PYTHON_CMD}} ./.trellis/scripts/task.py current --source
```

If there is no active task, report that fact and stop. Do not create a task, start a task, or dispatch a subagent.

## Step 2: Read the smallest authoritative status

For a Hermes closure task, use:

```bash
{{PYTHON_CMD}} ./.trellis/scripts/closure.py status --task <task>
{{PYTHON_CMD}} ./.trellis/scripts/closure.py next --task <task>
```

Report only the task title, phase, current work package, next action, blockers, and whether `HANDOFF.md` exists. Do not load the handoff body, full PRD, reports, or event history unless the user asks for that specific detail.

For a legacy task without closure fields, report its original task status and the available task artifacts. Preserve the original Trellis compatibility path.

## Boundaries

- This command is read-only.
- Do not run plan, validate, package-start, repair, close, finish, or archive.
- Do not turn a runner result into accepted evidence or a completed task.
