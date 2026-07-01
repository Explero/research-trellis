# Hermes Ledgers

This global directory is kept for Hermes ledger schema notes and shared conventions. It is not the default place for task evidence, claim, approval, or artifact data.

Do not seed empty `.jsonl` files here. Empty ledgers are hard to distinguish from missing or unused records in template tests and in real projects, so this directory is preserved with `.gitkeep`.

Task-specific append-only ledgers should live under `.trellis/tasks/<task>/hermes/`:

- `evidence_ledger.jsonl`: observations, citations, commands, outputs, and measurements.
- `claim_ledger.jsonl`: proposed claims linked to evidence record ids.
- `artifact_ledger.jsonl`: artifact id, path, hash, run id, command ref, and summary.
- `approval_records.jsonl`: human/root approval records for claims.
- `state_transition_log.jsonl`: requested and accepted state transitions.

Append-only means new facts are added as new JSON lines. Do not rewrite, reorder, truncate, or delete previous lines; append a correction record instead.

Any change to metric, split, or baseline definitions belongs behind HumanGate and should be recorded in the task notes before it reaches approval.
