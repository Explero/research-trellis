---
name: hermes-research
description: "Use for Hermes research tasks that need append-only evidence, claim, approval, or state-transition records under .trellis/tasks/<task>/hermes/."
---

# Hermes Research

Use this skill when a task asks for Hermes research discipline, evidence ledgers, claim review, human approval records, or state-machine-aware research progress.

## Read First

1. Resolve the active task from the prompt or `python3 ./.trellis/scripts/task.py current --source`.
2. Read `.trellis/hermes/config.yaml`.
3. Read `.trellis/hermes/state_machine.yaml`.
4. Read `.trellis/hermes/records/recordbus.md`.
5. Read `.trellis/hermes/records/subagent_protocol.md`.
6. Read the relevant role file from `.trellis/hermes/roles/`.
7. Read existing task records under `.trellis/tasks/<task>/hermes/`.
8. Read task artifacts such as `prd.md`, `design.md`, `implement.md`, and `check.jsonl` when present.

## Role Selection

Choose the worker role from the task shape before dispatching:

- `scientist` for framing the question, evidence standard, and claim scope
- `coder` for source edits inside `allowed_files`
- `runner` for commands, tests, benchmarks, and measurements
- `evaluator` for result checks against a stated standard
- `reviewer` for diff and record review before handoff
- `literature` for papers, citations, and source trail work

Do not dispatch a subagent without a task card. A result without a task card is
not accepted, even if the text looks useful.

## Record Location

Task records live under `.trellis/tasks/<task>/hermes/`.

Recommended append-only files:

- `evidence_ledger.jsonl`
- `claim_ledger.jsonl`
- `plan_change_log.jsonl`
- `approval_records.jsonl`
- `state_transition_log.jsonl`
- `worker_records.jsonl`

Create the task `hermes/` directory if it is missing. Do not create or rely on global empty `.jsonl` templates.

## RecordBus

Use `.trellis/hermes/records/recordbus.md` as the source of truth for agent handoff records. RecordBus is the trusted channel; chat-only summaries are not facts.

For worker coordination, append task cards, heartbeats, checkpoints, results, risks, and rejections to `worker_records.jsonl`.
Every task card should include `allowed_files`, `forbidden_files`, `record_uri`,
and a clear `HumanGate` boundary. `worker_records.jsonl` is the acceptance trail
for worker dispatch, not a chat-side summary.

The main agent should not receive long logs or long diffs in chat. Keep raw outputs in files and pass only structured summaries, evidence refs, risk flags, and decision requests.

Runtime helpers are available under `.trellis/scripts/hermes/`:

- `python3 ./.trellis/scripts/hermes/record.py append --task <task> --record-type worker --json '<json>'`
- `python3 ./.trellis/scripts/hermes/validate.py --task <task> --kind worker`
- `python3 ./.trellis/scripts/hermes/record.py append --task <task> --record-type plan_change --json '<json>'`
- `python3 ./.trellis/scripts/hermes/validate.py --task <task> --kind plan_change`
- `python3 ./.trellis/scripts/hermes/guard.py --task <task> --job-id <job> --changed-files <files>`
- `python3 ./.trellis/scripts/hermes/heartbeat.py beat --task <task> --job-id <job> --checkpoint <checkpoint> --summary <summary>`
- `python3 ./.trellis/scripts/hermes/heartbeat.py watch --task <task> --job-id <job> --checkpoint <checkpoint> --summary <summary> --interval 5m`
- `python3 ./.trellis/scripts/hermes/jobs.py check --task <task>`

## Subagent Protocol

Use `.trellis/hermes/records/subagent_protocol.md` for long-running worker behavior.

Long-running subagents must leave heartbeat and checkpoint records. If heartbeat records stop arriving, the main agent should mark the job stalled and resume from the latest checkpoint or dispatch a replacement worker.

Maker and checker roles are separate. A checker reviews records, diffs, test output, and evidence; it does not replace human approval when HumanGate is required.
Reviewers and evaluators should get task-card context, evidence refs, and the
exact check to perform, not the coder or runner long chat.

## Append Worker Records

Append one JSON object per line to `worker_records.jsonl`.

Task card:

```json
{"type":"task_card","id":"tc-YYYYMMDD-HHMMSS-slug","timestamp":"YYYY-MM-DDTHH:MM:SSZ","job_id":"job-YYYYMMDD-HHMMSS-slug","role":"coder","worktree_id":"main","status":"queued","allowed_files":["path/**"],"forbidden_files":["path/**"],"heartbeat_interval":"5m","timeout_at":"YYYY-MM-DDTHH:MM:SSZ","checkpoint":"not-started","resume_from":"task_card","record_uri":".trellis/tasks/<task>/hermes/worker_records.jsonl","evidence_refs":[],"risk_flags":[]}
```

Heartbeat:

```json
{"type":"heartbeat","id":"hb-YYYYMMDD-HHMMSS-slug","timestamp":"YYYY-MM-DDTHH:MM:SSZ","job_id":"job-YYYYMMDD-HHMMSS-slug","status":"running","checkpoint":"files-read","summary":"short structured progress note","next_check_at":"YYYY-MM-DDTHH:MM:SSZ"}
```

Checkpoint:

```json
{"type":"checkpoint","id":"cp-YYYYMMDD-HHMMSS-slug","timestamp":"YYYY-MM-DDTHH:MM:SSZ","job_id":"job-YYYYMMDD-HHMMSS-slug","checkpoint":"tests-added","resume_from":"rerun targeted test and continue implementation","evidence_refs":["ev-..."],"open_items":["short remaining item"]}
```

Result:

```json
{"type":"result","id":"rs-YYYYMMDD-HHMMSS-slug","timestamp":"YYYY-MM-DDTHH:MM:SSZ","job_id":"job-YYYYMMDD-HHMMSS-slug","status":"done","summary":"what changed","changed_files":["path/file"],"evidence_refs":["ev-..."],"risk_flags":[],"handoff":"structured next step or review request"}
```

Risk:

```json
{"type":"risk","id":"rk-YYYYMMDD-HHMMSS-slug","timestamp":"YYYY-MM-DDTHH:MM:SSZ","job_id":"job-YYYYMMDD-HHMMSS-slug","severity":"low|medium|high","summary":"risk statement","evidence_refs":["ev-..."],"proposed_mitigation":"bounded mitigation or human decision needed"}
```

Rejection:

```json
{"type":"rejection","id":"rj-YYYYMMDD-HHMMSS-slug","timestamp":"YYYY-MM-DDTHH:MM:SSZ","job_id":"job-YYYYMMDD-HHMMSS-slug","rejected_record_id":"rs-...","reason":"missing evidence|missing checkpoint|unauthorized files|scope mismatch|human gate required","required_fix":"specific record or change needed before retry"}
```

## Append Evidence Records

Append one JSON object per line to `evidence_ledger.jsonl`.

Minimum fields:

```json
{"type":"evidence","id":"ev-YYYYMMDD-HHMMSS-slug","timestamp":"YYYY-MM-DDTHH:MM:SSZ","source":"path, command, output, citation, or measurement","summary":"what was observed","limits":"known uncertainty or scope"}
```

## Append Claim Records

Append one JSON object per line to `claim_ledger.jsonl`.

Minimum fields:

```json
{"type":"claim","id":"cl-YYYYMMDD-HHMMSS-slug","timestamp":"YYYY-MM-DDTHH:MM:SSZ","text":"claim wording","evidence_ids":["ev-..."],"scope":"where this claim applies","limits":"what it does not prove","state":"claim_ready"}
```

Claims without evidence ids are drafts, not claim-ready records.

## Append Plan Change Records

Append one JSON object per line to `plan_change_log.jsonl` whenever a research
plan, PRD, contract, or experiment config changes. Do not rewrite prior plan
records.

Minimum fields:

```json
{"type":"plan_change","id":"pc-YYYYMMDD-HHMMSS-slug","timestamp":"YYYY-MM-DDTHH:MM:SSZ","plan_ref":"prd.md","change_summary":"what changed","reason":"why it changed","requested_by":"human/root|agent-id","decision_state":"proposed|accepted|rejected|superseded","evidence_refs":[],"supersedes":[]}
```

## Append Approval Records

Approval is append-only. Do not use a boolean flag for claim approval.

Only the human/root authority can approve a claim. When approval is provided, append one JSON object per line to `approval_records.jsonl`.

Minimum fields:

```json
{"type":"human_approval","id":"ap-YYYYMMDD-HHMMSS-slug","timestamp":"YYYY-MM-DDTHH:MM:SSZ","claim_id":"cl-...","approver":"human/root","decision":"approved","notes":"approval scope or conditions"}
```

The `claim_ready -> approved` transition requires this human approval record.

## State Transitions

Use `.trellis/hermes/state_machine.yaml` as the source of truth. The MVP flow is:

```text
planning -> running -> review -> claim_ready -> approved
```

Append state-transition observations to `state_transition_log.jsonl`. If a transition was requested but requirements were missing, append a rejected transition record instead of editing history.

## Do Not

- Do not rewrite, reorder, truncate, or delete Hermes records.
- Do not treat chat-only text as evidence.
- Do not claim approval without a human approval record.
- Do not skip the review state before marking a claim ready.
