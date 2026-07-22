# Hermes Base Contract

- Read the Task Capsule before any larger task artifact.
- Treat `task.json` and append-only Hermes records as state; chat statements do not change state.
- Stay inside task-card file and command permissions.
- `Edit` and `Write` actions are checked against `allowed_files` before they run; this is a file-boundary check, not process isolation.
- `Bash` uses a small role and command allowlist plus later record and closure checks. It is not a sandbox or protection against a malicious process.
- Load only the current assignment and at most three direct references by default.
- Cite concrete records, artifacts, commands, or sources in the required output.
- Stop and report a blocker for high-risk research changes or missing human approval.
- Never turn one run into a durable claim or project rule without the required review.
- Keep the result compact and append records instead of rewriting history.
