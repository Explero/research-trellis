# Write Task Handoff

Write a concise handoff for the active Hermes closure task before a pause, session switch, context compaction, or explicit user handoff request.

## Step 1: Resolve the active task

```bash
{{PYTHON_CMD}} ./.trellis/scripts/task.py current --source
```

If there is no active task, report that fact and stop.

## Step 2: Dispatch the handoff writer

The main agent must not run the write command. Create a validated
`coder:configuration` dispatch with no work package, only this allowed file:

```text
.trellis/tasks/<task>/HANDOFF.md
```

The worker receives the current `task.json` and runs
`closure.py handoff --task <task>`. It returns a normal Result Envelope. After
that result is confirmed, the deterministic closure code rewrites the handoff
with the new task revision.

Read the sanitized worker result, then report the generated `HANDOFF.md` path,
current phase, current work package, blockers, and next action. Keep the chat
response short; the file is the durable checkpoint.

For a legacy task without closure fields, do not invent a Hermes handoff. Report that the task uses the original compatibility flow and identify the current task artifacts instead.

## Boundaries

- Writing a handoff does not complete, close, archive, approve, or amend the task.
- Do not load full chat history or unrelated task files to create the handoff.
- The dedicated handoff writer is the one exception: it may only write the
  current task's `HANDOFF.md` and must not change task state or other files.
