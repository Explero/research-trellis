# Hermes Records

Per-task records should live in `.trellis/tasks/<task>/hermes/`.

Global `.trellis/hermes/records/` is only for schema notes and conventions shared by tasks. It should not hold task-specific evidence, claims, approvals, run outputs, or review results.

Recommended per-task files:

- `evidence_ledger.jsonl`
- `claim_ledger.jsonl`
- `provenance_ledger.jsonl`
- `audit_ledger.jsonl`
- `plan_change_log.jsonl`
- `approval_records.jsonl`
- `state_transition_log.jsonl`
- `worker_records.jsonl`
- `service_queue.jsonl`
- `experiment.yaml`
- `run_manifest.jsonl`
- `compare.jsonl`
- `report.md`

Worker handoffs, task cards, heartbeats, checkpoints, results, risks, and
rejections all go through `worker_records.jsonl`.

`experiment.yaml` holds the question, hypothesis, dataset, model, metrics, seed,
environment, allowed commands, and artifact directory for a task-scoped
experiment. `run_manifest.jsonl` records each execution step as append-only run
metadata with command, cwd, env_summary, inputs, outputs, exit_code, started_at,
and finished_at.

`compare.jsonl` records baseline versus new-method comparisons with thresholds,
directions, evidence refs, and claim refs. `report.md` summarizes the task as a
reviewable research report and must keep conclusions at `claim_ready` until
human/root approval is recorded.

`plan_change_log.jsonl` records append-only changes to research plans, PRDs,
contracts, and experiment configs. Each record should name the changed plan ref,
summarize the change, explain the reason, record who requested it, and keep a
decision state of `proposed`, `accepted`, `rejected`, or `superseded`.

`provenance_ledger.jsonl` records dataset, model, code, environment, and
artifact refs with hash, version, or source metadata. `audit_ledger.jsonl`
records security gate, approval boundary, external write boundary, and secret
redaction events. `service_queue.jsonl` is a local queue slice for enqueue,
status, cancel, and retry records; it is not a daemon or remote service.

Every JSONL file is append-only by convention. If a record is wrong, append a
correction that references the earlier record id. Do not edit the old line in
place. JSONL here is not tamper-proof storage; use external controls if an
immutable audit log is required.
