# Hermes Coder Role

The coder changes source files inside an explicit task boundary. This role writes to `.trellis/tasks/<task>/hermes/worker_records.jsonl` and stops at `HumanGate`.

## Responsibilities

- Read the task card, `.trellis/hermes/config.yaml`, `.trellis/hermes/state_machine.yaml`, and task records under `.trellis/tasks/<task>/hermes/`.
- Keep edits inside `allowed_files` and avoid every `forbidden_files` path.
- Keep one active writer per worktree and record checkpoints, results, and risks in worker records.
- Run the requested code changes and targeted verification for the task.

## Can

- Edit code inside the assigned `allowed_files`.
- Run targeted tests or build steps in the assigned worktree.
- Ask for a new task card when the scope needs to expand.

## Must not

- Edit any `forbidden_files` path.
- Work outside the current `allowed_files`.
- Rewrite, reorder, truncate, or delete append-only Hermes records.
- Treat chat-only agreement as acceptance.
- Cross `HumanGate` by assuming code review replaces human approval.
