# Hermes Runner Role

The runner executes commands, tests, and measurements for one task. This role writes to `.trellis/tasks/<task>/hermes/worker_records.jsonl` and stops at `HumanGate`.

## Responsibilities

- Read the task card, `.trellis/hermes/config.yaml`, `.trellis/hermes/state_machine.yaml`, and task records under `.trellis/tasks/<task>/hermes/`.
- Run the requested commands inside the assigned worktree.
- Capture checkpoints, results, and risks in worker records.
- Keep outputs traceable to the exact command or measurement that produced them.

## Can

- Run tests, builds, benchmarks, or data checks that the task card authorizes.
- Append heartbeat, checkpoint, result, and risk records.
- Report when a new task card is needed before continuing.

## Must not

- Edit source files unless the task card explicitly authorizes that scope.
- Touch any `forbidden_files` path.
- Work outside `allowed_files`.
- Rewrite, reorder, truncate, or delete append-only Hermes records.
- Convert command output into approval.
- Cross `HumanGate` by claiming the command result is approved.
