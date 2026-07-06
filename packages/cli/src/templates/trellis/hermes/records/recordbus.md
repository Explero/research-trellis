# Hermes RecordBus

RecordBus is the only trusted communication channel between agents.

Chat messages can hint at work, but they are not facts. A task is not complete
until the relevant record exists under `.trellis/tasks/<task>/hermes/`.
This is deployment candidate hardening, not a production-ready platform. JSONL
records are not tamper-proof storage, and Hermes is not an OS sandbox.

## Role And Task Card Guide

Use task cards to assign one bounded worker at a time. The supported worker
roles for task cards are `coder`, `runner`, `evaluator`, `reviewer`, and
`literature`.

- `coder` changes source files inside `allowed_files`.
- `runner` executes commands or tests and reports structured output.
- `evaluator` compares outputs against the requested evidence standard.
- `reviewer` checks diffs, records, and task scope before handoff.
- `literature` gathers outside sources and citations for the task.

Every task card should point at `.trellis/tasks/<task>/hermes/worker_records.jsonl`
and should carry both `allowed_files` and `forbidden_files`. RecordBus records
do not replace `HumanGate`; they only describe the worker boundary and the
task-card handoff that needs to be reviewed.

## Location

Task records live under:

```text
.trellis/tasks/<task>/hermes/
```

Global `.trellis/hermes/records/` files only define conventions. They do not
store task-specific evidence, claims, approvals, worker logs, or review results.

## Rules

- Append records as JSONL: one JSON object per line.
- Do not rewrite, reorder, truncate, or silently delete records.
- If a record is wrong, append a later correction record that references it.
- Long logs and long diffs stay in files; records should link to them.
- Main agents should consume structured summaries, evidence indexes, risk flags,
  and decision requests instead of raw exploration history.
- Evidence records may include `artifact_refs` and `command_refs` for traceable
  provenance. If `artifact_refs` are present, every id must resolve in
  `.trellis/tasks/<task>/hermes/artifact_ledger.jsonl`.
- Provenance records go to `provenance_ledger.jsonl` and should include
  dataset, model, code, env, and artifact refs with hash, version, or source
  metadata.
- Audit records go to `audit_ledger.jsonl` for security gates, external write
  boundaries, secret redaction, sandbox gate decisions, and approval boundary
  events.
- Plan change records go to `plan_change_log.jsonl` when a PRD, contract,
  experiment config, or other research plan changes. Append a new record instead
  of rewriting the old plan trail.
- The local service queue goes to `service_queue.jsonl`; it supports enqueue,
  status, cancel, and retry records without a daemon.
- Worker validation enforces one unfinished active writer per worktree. Active
  writers are `coder` and `runner`; checker roles such as `reviewer`,
  `evaluator`, and `literature` do not count as active writers.
- A `coder` result whose `status` or `handoff` enters `review` or `claim_ready`
  must already have a related `runner` result and a related `reviewer` result
  or checkpoint in `worker_records.jsonl`.
- Metric, split, and baseline changes belong behind HumanGate. Record the
  rationale in task notes and do not encode a human approval UI here.

Experiment work should keep its source config in `experiment.yaml` and append
execution details to `run_manifest.jsonl` so the run stays traceable without
mixing it into chat history. Each manifest entry should include command, cwd,
env_summary, inputs, outputs, exit_code, started_at, and finished_at.
`allowed_commands` is a command allowlist, not a strong command sandbox. If
`python3` is allowed, arbitrary Python code can still be executed by that
command. Use exact command patterns and external OS-level isolation for stronger
controls.
Runner-managed commands should write stdout and stderr logs under the task
Hermes directory and include those log paths in the manifest. Failed commands
must keep the original exit code and append a rejection that points to the
captured stderr.

Evaluation work should aggregate run manifests into reviewable summaries,
append method comparisons to `compare.jsonl`, and generate a task-level
`report.md`. The report is evidence packaging only: core conclusions must link
back to claim ids and evidence ids, and the status stays `claim_ready` until a
human/root approval record exists. `claim-review` checks whether claims are
supported by evidence; it must not write approval records or move claims to
`approved`. `approval-gate` only checks an existing `human/root` approval
record for a claim; it does not create or simulate approval.
Use `quality-gate` to fail closed when a compare record failed, lacks evidence
refs, lacks claim refs, or omits a simple statistic field such as sample_count,
variance, or confidence_interval.

## Runtime Commands

Hermes runtime scripts live under `.trellis/scripts/hermes/`.

- Append worker records with `python3 ./.trellis/scripts/hermes/record.py append --task <task> --record-type worker --json '<json>'`.
- Validate worker records with `python3 ./.trellis/scripts/hermes/validate.py --task <task> --kind worker`.
- Check worker file permissions with `python3 ./.trellis/scripts/hermes/guard.py --task <task> --job-id <job> --changed-files <comma-separated-files>`.
- Write a heartbeat once with `python3 ./.trellis/scripts/hermes/heartbeat.py beat --task <task> --job-id <job> --checkpoint <checkpoint> --summary <summary>`.
- Keep writing heartbeats during long work with `python3 ./.trellis/scripts/hermes/heartbeat.py watch --task <task> --job-id <job> --checkpoint <checkpoint> --summary <summary> --interval 5m`.
- Check timeouts with `python3 ./.trellis/scripts/hermes/jobs.py check --task <task>`.
- Show the latest resume point with `python3 ./.trellis/scripts/hermes/jobs.py resume --task <task> --job-id <job>`.
- Run a command with heartbeats and a manifest with `python3 ./.trellis/scripts/hermes/runner.py run --task <task> --job-id <job> --checkpoint <checkpoint> --summary <summary> -- <command>`.
- Recheck a recorded run with `python3 ./.trellis/scripts/hermes/runner.py replay --task <task> --run-id <run>`.
- Validate run manifests with `python3 ./.trellis/scripts/hermes/validate.py --task <task> --kind run_manifest`.
- Validate provenance records with `python3 ./.trellis/scripts/hermes/validate.py --task <task> --kind provenance`.
- Validate audit records with `python3 ./.trellis/scripts/hermes/validate.py --task <task> --kind audit`.
- Append plan change records with `python3 ./.trellis/scripts/hermes/record.py append --task <task> --record-type plan_change --json '<json>'`.
- Validate plan change records with `python3 ./.trellis/scripts/hermes/validate.py --task <task> --kind plan_change`.
- Aggregate run manifests with `python3 ./.trellis/scripts/hermes/report.py aggregate --task <task> --output .trellis/tasks/<task>/hermes/aggregate.json`.
- Append a compare record with `python3 ./.trellis/scripts/hermes/report.py compare --task <task> --metric <metric> --baseline <value> --new <value> --threshold <value> --direction higher_is_better`.
- Generate a task report with `python3 ./.trellis/scripts/hermes/report.py report --task <task> --question <text> --method <text> --data <text> --metrics <text> --limitations <text> --risks <text>`.
- Review claim support with `python3 ./.trellis/scripts/hermes/report.py claim-review --task <task> --claim-id <claim>`.
- Check an existing human approval with `python3 ./.trellis/scripts/hermes/report.py approval-gate --task <task> --claim-id <claim>`.
- Run the local quality gate with `python3 ./.trellis/scripts/hermes/report.py quality-gate --task <task>`.
- Enqueue local service work with `python3 ./.trellis/scripts/hermes/service.py enqueue --task <task> --job-id <job> --command "<command>"`.
- Inspect local service queue status with `python3 ./.trellis/scripts/hermes/service.py status --task <task>`.
- Cancel queued local service work with `python3 ./.trellis/scripts/hermes/service.py cancel --task <task> --job-id <job> --reason "<reason>"`.

## Minimum Record Types

### task_card

Append a `task_card` record when dispatching a worker.

```json
{"type":"task_card","id":"tc-YYYYMMDD-HHMMSS-slug","timestamp":"YYYY-MM-DDTHH:MM:SSZ","job_id":"job-YYYYMMDD-HHMMSS-slug","role":"coder|runner|evaluator|reviewer|literature","worktree_id":"main|worktree-name","status":"queued","allowed_files":["path/**"],"forbidden_files":["path/**"],"heartbeat_interval":"5m","timeout_at":"YYYY-MM-DDTHH:MM:SSZ","checkpoint":"not-started","resume_from":"task_card","record_uri":".trellis/tasks/<task>/hermes/worker_records.jsonl","evidence_refs":[],"risk_flags":[]}
```

### heartbeat

Append a `heartbeat` record while a long-running worker is still active.

```json
{"type":"heartbeat","id":"hb-YYYYMMDD-HHMMSS-slug","timestamp":"YYYY-MM-DDTHH:MM:SSZ","job_id":"job-YYYYMMDD-HHMMSS-slug","status":"running","checkpoint":"files-read","summary":"short structured progress note","next_check_at":"YYYY-MM-DDTHH:MM:SSZ"}
```

### checkpoint

Append a `checkpoint` record when the worker reaches a resumable point.

```json
{"type":"checkpoint","id":"cp-YYYYMMDD-HHMMSS-slug","timestamp":"YYYY-MM-DDTHH:MM:SSZ","job_id":"job-YYYYMMDD-HHMMSS-slug","checkpoint":"tests-added","resume_from":"rerun targeted test and continue implementation","evidence_refs":["ev-..."],"open_items":["short remaining item"]}
```

### evidence

Append evidence records with command and artifact traceability.

```json
{"type":"evidence","id":"ev-YYYYMMDD-HHMMSS-slug","timestamp":"YYYY-MM-DDTHH:MM:SSZ","source":"command output","summary":"what was observed","limits":"short scope note","artifact_refs":["ar-..."],"command_refs":["cmd-..."]}
```

### artifact

Append artifact records for files or outputs that evidence points to.

```json
{"type":"artifact","id":"ar-YYYYMMDD-HHMMSS-slug","path":"reports/output.txt","hash":"sha256:...","run_id":"run-YYYYMMDD-HHMMSS-slug","command_ref":"cmd-...","summary":"artifact description"}
```

### provenance

Append a `provenance` record to lock the refs used by an experiment.

```json
{"type":"provenance","id":"pv-YYYYMMDD-HHMMSS-slug","timestamp":"YYYY-MM-DDTHH:MM:SSZ","dataset":{"ref":"dataset-id","hash":"sha256:...","source":"fixture"},"model":{"ref":"model-id","version":"1.0.0","source":"local"},"code":{"ref":"git:abc123","hash":"sha256:...","source":"repo"},"env":{"ref":"ubuntu-24.04","version":"python-3.12","source":"runner"},"artifact":{"ref":"ar-...","hash":"sha256:...","source":"artifact_ledger"}}
```

### audit

Append an `audit` record when a security or approval boundary is checked.

```json
{"type":"audit","id":"au-YYYYMMDD-HHMMSS-slug","timestamp":"YYYY-MM-DDTHH:MM:SSZ","event":"security_gate|external_write_boundary|secret_redaction|sandbox_gate|approval_boundary","actor":"runner.py","boundary":"allowed_commands","decision":"blocked","summary":"short reason"}
```

### plan_change

Append a `plan_change` record when a research plan, PRD, contract, or
experiment config changes.

```json
{"type":"plan_change","id":"pc-YYYYMMDD-HHMMSS-slug","timestamp":"YYYY-MM-DDTHH:MM:SSZ","plan_ref":"prd.md","change_summary":"what changed","reason":"why it changed","requested_by":"human/root|agent-id","decision_state":"proposed|accepted|rejected|superseded","evidence_refs":["ev-..."],"supersedes":["pc-..."]}
```

### result

Append a `result` record when the worker completes the authorized task.

```json
{"type":"result","id":"rs-YYYYMMDD-HHMMSS-slug","timestamp":"YYYY-MM-DDTHH:MM:SSZ","job_id":"job-YYYYMMDD-HHMMSS-slug","status":"done","summary":"what changed","changed_files":["path/file"],"evidence_refs":["ev-..."],"risk_flags":[],"handoff":"structured next step or review request"}
```

### stalled

Append a `stalled` record when a timeout checker detects a missed heartbeat or
expired task card. Keep the latest checkpoint and resume point in the record.

```json
{"type":"stalled","id":"st-YYYYMMDD-HHMMSS-timeout","timestamp":"YYYY-MM-DDTHH:MM:SSZ","job_id":"job-YYYYMMDD-HHMMSS-slug","reason":"timeout|heartbeat_timeout","checkpoint":"tests-running","resume_from":"rerun tests from checkpoint","required_fix":"resume from rerun tests from checkpoint"}
```

### risk

Append a `risk` record when uncertainty may affect acceptance.

```json
{"type":"risk","id":"rk-YYYYMMDD-HHMMSS-slug","timestamp":"YYYY-MM-DDTHH:MM:SSZ","job_id":"job-YYYYMMDD-HHMMSS-slug","severity":"low|medium|high","summary":"risk statement","evidence_refs":["ev-..."],"proposed_mitigation":"bounded mitigation or human decision needed"}
```

### rejection

Append a `rejection` record when a result is refused or a transition is blocked.

```json
{"type":"rejection","id":"rj-YYYYMMDD-HHMMSS-slug","timestamp":"YYYY-MM-DDTHH:MM:SSZ","job_id":"job-YYYYMMDD-HHMMSS-slug","rejected_record_id":"rs-...","reason":"missing evidence|missing checkpoint|unauthorized files|scope mismatch|human gate required","required_fix":"specific record or change needed before retry"}
```

### compare

Append a `compare` record when comparing a baseline with a new method.

```json
{"type":"compare","id":"cmp-YYYYMMDD-HHMMSS-metric","timestamp":"YYYY-MM-DDTHH:MM:SSZ","metric":"accuracy","direction":"higher_is_better","threshold":0.05,"baseline":0.7,"new":0.76,"delta":0.06,"passed":true,"evidence_refs":["ev-..."],"claim_refs":["cl-..."],"conclusion_state":"claim_ready"}
```

`compare` records must keep metric, split, and baseline definitions stable. If
those definitions need to change, stop at HumanGate before recording the new
comparison.

### report.md

Generate `report.md` only after claims and evidence are present. The report must
include problem, method, data, metrics, results, limitations, risks, and
conclusion status. Each core conclusion should include `claim:` and `evidence:`
links so a reviewer can trace it back to append-only records.
