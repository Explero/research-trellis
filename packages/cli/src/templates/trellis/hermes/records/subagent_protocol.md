# Hermes Subagent Protocol

Hermes treats subagents as bounded workers, not trusted authorities.

The main agent is the supervisor and state arbiter. It dispatches work, watches
records, decides whether a handoff is acceptable, and asks for human approval
when a gate requires it. A subagent is a bounded worker with an explicit task
card, allowed files, forbidden files, heartbeat interval, timeout, checkpoint,
and record location. `HumanGate` is the point where the main agent stops and
waits for human/root approval instead of inventing a local decision.

## Dispatch

Before starting a worker, append a `task_card` record through RecordBus. The
task card should define:

- `job_id`
- `role`
- `worktree_id`
- `allowed_files`
- `forbidden_files`
- `heartbeat_interval`
- `timeout_at`
- `checkpoint`
- `resume_from`
- `record_uri`

The `task_card` is the contract for a single worker. If there is no task card,
there is no accepted worker result.

The worker must not expand its own authority. If the task needs more scope, it
records a risk or asks for a new task card.

## Waiting

The main agent should not idle while a long task runs. During waiting windows,
it should do independent supervision work:

- check prerequisite evidence
- prepare the acceptance checklist
- prepare the failure or retry plan
- update the state board
- inspect non-overlapping files or tests

The main agent should not pull long logs, long diffs, or raw exploration history
into its own context. It should read structured records and evidence indexes.
When dispatching `reviewer` or `evaluator`, give them the task card, evidence
refs, changed-file summary, and the exact check to perform. Do not carry over
the coder or runner long conversation into a checker turn.

## Heartbeat And Timeout

Workers append `heartbeat` records while running. Each heartbeat should include
the current checkpoint and the next expected check time.

Use `python3 ./.trellis/scripts/hermes/heartbeat.py beat --task <task>
--job-id <job> --checkpoint <checkpoint> --summary <summary>` to write one
heartbeat, or `python3 ./.trellis/scripts/hermes/heartbeat.py watch --task
<task> --job-id <job> --checkpoint <checkpoint> --summary <summary>
--interval 5m` to keep writing heartbeats during long work.

If a heartbeat is missing, mark the job as `stalled` by appending a record. Do
not keep waiting silently.

If `timeout_at` is reached, stop waiting on the old run. Resume from the latest
`checkpoint` and `resume_from`, or dispatch a replacement worker with a new
task card that references the stalled job.

Use `python3 ./.trellis/scripts/hermes/jobs.py check --task <task>` to detect
timed-out jobs and append rejection records with the latest `resume_from`.

## Checkpoint And Resume

Every meaningful checkpoint must be independently useful. It should explain:

- what has already happened
- where the work can resume
- which evidence or files support the current state
- which risks or open items remain

Interrupted tasks resume from records, not from chat history.

## Maker And Checker

Use maker/checker separation:

- the maker writes or runs the authorized work
- the checker reviews task cards, records, diffs, test output, and evidence
- checker summaries do not replace human approval when HumanGate is required

By default, one worktree has one active writer. `validate.py --kind worker`
fails when multiple unfinished `coder` or `runner` task cards share the same
`worktree_id`. Read-only checker roles such as `reviewer`, `evaluator`, and
`literature` can run in parallel. If parallel writes are needed, use separate
worktrees or an explicit write lease.
Do not keep two active writers in the same worktree.

A coder result cannot hand off to `review` or `claim_ready` until the worker
records already contain a related `runner` result and a related `reviewer`
result or checkpoint. Checker records can support the handoff, but they do not
replace `human/root` approval when HumanGate is required.

## Acceptance

Accept a worker result only when:

- a `result` record exists
- required heartbeat and checkpoint records exist for long work
- evidence references are traceable
- changed files stay within `allowed_files`
- no forbidden file was changed
- risks are recorded instead of hidden in prose
- the result is still inside the task card boundary and below `HumanGate`

Reject a worker result with a `rejection` record when these conditions are not
met.

Use `python3 ./.trellis/scripts/hermes/validate.py --task <task> --kind worker`
and `python3 ./.trellis/scripts/hermes/guard.py --task <task> --job-id <job>
--changed-files <files>` before accepting worker output.
