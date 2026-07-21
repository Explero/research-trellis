# Hermes Subagent Protocol

Hermes treats subagents as bounded workers, not trusted authorities.

The main agent is the supervisor and state arbiter. It dispatches work, watches
records, decides whether a handoff is acceptable, and asks for human approval
when a gate requires it. A subagent is a bounded worker with an explicit task
card, allowed files, forbidden files, heartbeat interval, timeout, checkpoint,
and record location. `HumanGate` is the point where the main agent stops and
waits for human/root approval instead of inventing a local decision.

## Dispatch

Before starting a worker, create and validate one dispatch with
`python3 ./.trellis/scripts/hermes/dispatch.py create`. The command writes the
dispatch file and its RecordBus `task_card`. Claude Agent calls receive only
the `job_id`; Codex strict work runs through the same CLI.

The validated dispatch defines:

- `job_id`
- `role`
- `profile` (optional; the role default is stored when omitted)
- `worktree_id`
- `allowed_files`
- `forbidden_files`
- `heartbeat_interval`
- `timeout_at`
- `checkpoint`
- `resume_from`
- `record_uri`
- `hermes_revision`
- `work_package`
- no more than three `refs`

The dispatch and task card are the contract for a single worker. Execution
roles bind the current work package. Planner and reviewer task-level work may
use `work_package: null`. A stale revision is rejected before execution.

Explicit task refs and task context pins take priority. The dispatch then adds
only the project background, research plan, or constraints that match the
worker's role/profile and fit within the three-ref limit. For example, a coder
gets project constraints, while an evidence reviewer gets the research plan and
constraints. Add a task-specific spec explicitly when it is more important than
an optional project document.

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
into its own context. Raw Agent/Codex output stays under the gitignored
`.trellis/.runtime/hermes-traces/` directory. Every canonical worker receives
only the validated dispatch body and at most three direct references. Do not
carry over the coder or runner conversation or preload full task history.

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
`worktree_id`. Planning, research, and review roles can run independently when
their task-card write paths do not overlap. If parallel writes are needed, use separate
worktrees or an explicit write lease.
Do not keep two active writers in the same worktree.

A coder result cannot hand off to `review` or `claim_ready` until the worker
records already contain a related `runner:test|build|validation` result and a
related `reviewer:quality|safety` result or checkpoint. Evidence, claim, or
closure review cannot substitute for code-quality review. Checker records do not
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
- `uncertainties` is present and the conclusion is at most 1200 characters
- it contains no complete diff, log stream, search process, secret, or absolute user path

Reject a worker result with a `rejection` record when these conditions are not
met.

Use `python3 ./.trellis/scripts/hermes/dispatch.py apply --task <task>
--job-id <job> --result <file>` before the existing RecordBus validation. The
firewall stores raw output locally, writes only the sanitized result into the
task, and mechanically updates `next_action`. Then use `validate.py --kind
worker` and `guard.py --changed-files` before accepting worker output.

## Completion And Release

One dispatch is one bounded piece of work, not a reusable conversation. Once a
result has been accepted or recorded as failed, blocked, stale, interrupted, or
capacity-blocked, close that subagent immediately. Do not leave it idle, give it
another work package, or reuse its chat context. The next piece of work must use
a new dispatch and a new subagent with its own current revision and minimal
context.

If the result is invalid, request only the permitted rewrite. After the rewrite
limit, record the invalid result, block the relevant job or work package, and
close the subagent.
