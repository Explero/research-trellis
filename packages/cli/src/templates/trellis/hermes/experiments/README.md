# Hermes Experiments

Use this directory for task-scoped experiment setup and run tracking.

Initialize a task copy with:

`python3 ./.trellis/scripts/hermes/experiment.py init --task <task>`

- `experiment.yaml` defines the experiment question, hypothesis, dataset,
  model, metrics, seed, environment, allowed commands, and artifact directory.
- `run_manifest.jsonl` records each run as append-only JSONL with at least:
  command, cwd, env_summary, inputs, outputs, exit_code, started_at, and
  finished_at.

Keep the experiment config readable and keep per-run facts in the manifest.
