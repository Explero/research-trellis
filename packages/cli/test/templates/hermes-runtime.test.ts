import { describe, expect, it, beforeEach, afterEach } from "vitest";
import { createHash } from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";

import { getAllScripts } from "../../src/templates/trellis/index.js";

function writeScripts(root: string): void {
  const scriptsRoot = path.join(root, ".trellis", "scripts");
  for (const [relativePath, content] of getAllScripts()) {
    const target = path.join(scriptsRoot, ...relativePath.split("/"));
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, content, "utf-8");
  }
}

function writeJson(filePath: string, value: unknown): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(value, null, 2), "utf-8");
}

function runHermes(
  root: string,
  script:
    | "record.py"
    | "validate.py"
    | "guard.py"
    | "jobs.py"
    | "heartbeat.py"
    | "experiment.py"
    | "runner.py"
    | "report.py"
    | "service.py",
  args: string[],
  options: { env?: Record<string, string | undefined> } = {},
): { status: number | null; stdout: string; stderr: string } {
  const result = spawnSync(
    "python3",
    [path.join(root, ".trellis", "scripts", "hermes", script), ...args],
    {
      cwd: root,
      encoding: "utf-8",
      env: options.env,
    },
  );
  return {
    status: result.status,
    stdout: result.stdout.trim(),
    stderr: result.stderr.trim(),
  };
}

function writeJsonl(filePath: string, records: Record<string, unknown>[]): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(
    filePath,
    records.map((record) => JSON.stringify(record)).join("\n") + "\n",
    "utf-8",
  );
}

function writeExperimentConfig(taskDir: string): void {
  fs.writeFileSync(
    path.join(taskDir, "hermes", "experiment.yaml"),
    [
      'question: "Does the command produce the expected output?"',
      'hypothesis: "The command is deterministic."',
      'dataset: "unit fixture"',
      'model: "test runner"',
      "metrics:",
      '  - "exit_code"',
      "seed: 1",
      "environment:",
      '  os: "ubuntu-24.04"',
      '  shell: "bash"',
      "allowed_commands:",
      '  - "python3"',
      'artifact_dir: ".trellis/tasks/01-test/hermes/runs"',
      "",
    ].join("\n"),
    "utf-8",
  );
}

function writeExperimentConfigWithAllowedCommands(
  taskDir: string,
  allowedCommands: string[],
): void {
  fs.writeFileSync(
    path.join(taskDir, "hermes", "experiment.yaml"),
    [
      'question: "Does the command produce the expected output?"',
      'hypothesis: "The command is deterministic."',
      'dataset: "unit fixture"',
      'model: "test runner"',
      "metrics:",
      '  - "exit_code"',
      "seed: 1",
      "environment:",
      '  os: "ubuntu-24.04"',
      '  shell: "bash"',
      "allowed_commands:",
      ...allowedCommands.map((command) => `  - "${command}"`),
      'artifact_dir: ".trellis/tasks/01-test/hermes/runs"',
      "",
    ].join("\n"),
    "utf-8",
  );
}


function sha256Text(value: string): string {
  return `sha256:${createHash("sha256").update(value).digest("hex")}`;
}

function writeRunnerCard(taskDir: string, jobId: string): void {
  writeJsonl(path.join(taskDir, "hermes", "worker_records.jsonl"), [
    {
      type: "task_card",
      id: `tc-${jobId}`,
      timestamp: "2026-06-29T00:00:00Z",
      job_id: jobId,
      role: "runner",
      worktree_id: "main",
      status: "queued",
      allowed_files: ["**"],
      forbidden_files: [],
      heartbeat_interval: "1s",
      timeout_at: "2099-01-01T00:00:00Z",
      checkpoint: "not-started",
      resume_from: "task_card",
      record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
      evidence_refs: [],
      risk_flags: [],
    },
  ]);
}

function markDataExploration(taskDir: string): void {
  writeJson(path.join(taskDir, "task.json"), {
    id: "01-test",
    status: "in_progress",
    research_route: "exploration",
    research_change_fields: ["dataset"],
  });
}

function appendDataPreflight(
  taskDir: string,
  hash: string,
  checksContent: string,
): { manifestPath: string; checksPath: string } {
  const manifestPath = "data/input-manifest.json";
  const checksPath = "data/checks.yaml";
  const root = path.resolve(taskDir, "../../../");
  fs.mkdirSync(path.join(root, "data"), { recursive: true });
  fs.writeFileSync(path.join(root, manifestPath), '{"rows":2}\n', "utf-8");
  fs.writeFileSync(path.join(root, checksPath), checksContent, "utf-8");
  fs.appendFileSync(
    path.join(taskDir, "hermes", "experiment.yaml"),
    [
      "data_preflight:",
      '  source: "fixture"',
      '  version: "v1"',
      `  input_manifest: "${manifestPath}"`,
      `  hash: "${hash}"`,
      `  checks_ref: "${checksPath}"`,
      "",
    ].join("\n"),
    "utf-8",
  );
  return { manifestPath, checksPath };
}

describe("Hermes runtime scripts", () => {
  let tmpDir: string;
  let taskDir: string;

  function writeQualityGateLedgers(): void {
    const artifactContent = "accuracy=0.76\n";
    fs.mkdirSync(path.join(tmpDir, "reports"), { recursive: true });
    fs.writeFileSync(
      path.join(tmpDir, "reports", "accuracy.txt"),
      artifactContent,
      "utf-8",
    );
    writeJsonl(path.join(taskDir, "hermes", "artifact_ledger.jsonl"), [
      {
        type: "artifact",
        id: "ar-20260629-000000-demo",
        path: "reports/accuracy.txt",
        hash: sha256Text(artifactContent),
        run_id: "run-20260629-000000-demo",
        command_ref: "cmd-20260629-000000-demo",
        summary: "captured accuracy output",
      },
    ]);
    writeJsonl(path.join(taskDir, "hermes", "evidence_ledger.jsonl"), [
      {
        type: "evidence",
        id: "ev-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        source: "reports/accuracy.txt",
        summary: "accuracy output is 0.76",
        limits: "unit-test fixture",
        artifact_refs: ["ar-20260629-000000-demo"],
        command_refs: ["cmd-20260629-000000-demo"],
      },
    ]);
    writeJsonl(path.join(taskDir, "hermes", "claim_ledger.jsonl"), [
      {
        type: "claim",
        id: "cl-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:01Z",
        text: "accuracy improved from 0.70 to 0.76",
        evidence_ids: ["ev-20260629-000000-demo"],
        scope: "unit-test fixture",
        limits: "single deterministic sample",
        state: "claim_ready",
      },
    ]);
  }

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "research-trellis-runtime-"));
    fs.mkdirSync(path.join(tmpDir, ".trellis", "tasks", "01-test", "hermes"), {
      recursive: true,
    });
    writeScripts(tmpDir);
    taskDir = path.join(tmpDir, ".trellis", "tasks", "01-test");
    writeJson(path.join(taskDir, "task.json"), {
      id: "01-test",
      status: "in_progress",
    });
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("appends and validates worker records as JSONL", () => {
    const taskCard = {
      type: "task_card",
      id: "tc-20260629-000000-demo",
      timestamp: "2026-06-29T00:00:00Z",
      job_id: "job-demo",
      role: "coder",
      worktree_id: "main",
      status: "queued",
      allowed_files: ["src/**"],
      forbidden_files: [".env"],
      heartbeat_interval: "5m",
      timeout_at: "2099-01-01T00:00:00Z",
      checkpoint: "not-started",
      resume_from: "task_card",
      record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
      evidence_refs: [],
      risk_flags: [],
    };

    const append = runHermes(tmpDir, "record.py", [
      "append",
      "--task",
      "01-test",
      "--record-type",
      "worker",
      "--json",
      JSON.stringify(taskCard),
    ]);

    expect(append.status).toBe(0);
    expect(append.stdout).toContain("appended");

    const records = fs
      .readFileSync(
        path.join(taskDir, "hermes", "worker_records.jsonl"),
        "utf-8",
      )
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line) as Record<string, unknown>);

    expect(records).toHaveLength(1);
    expect(records[0].type).toBe("task_card");

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "worker",
    ]);
    expect(validate.status).toBe(0);
    expect(validate.stdout).toContain("valid");
  });

  it("appends and validates artifact ledger records as JSONL", () => {
    const artifactContent = "captured runtime output";
    fs.mkdirSync(path.join(tmpDir, "reports"), { recursive: true });
    fs.writeFileSync(
      path.join(tmpDir, "reports", "runtime-output.txt"),
      artifactContent,
      "utf-8",
    );
    const artifactRecord = {
      type: "artifact",
      id: "ar-20260629-000000-demo",
      path: "reports/runtime-output.txt",
      hash: sha256Text(artifactContent),
      run_id: "run-demo",
      command_ref: "cmd-demo",
      summary: "captured runtime output",
    };

    const append = runHermes(tmpDir, "record.py", [
      "append",
      "--task",
      "01-test",
      "--record-type",
      "artifact",
      "--json",
      JSON.stringify(artifactRecord),
    ]);

    expect(append.status).toBe(0);
    expect(append.stdout).toContain("appended");

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "artifact",
    ]);

    expect(validate.status).toBe(0);
    expect(validate.stdout).toContain("valid");
  });

  it("appends and validates plan change records as JSONL", () => {
    const planChange = {
      type: "plan_change",
      id: "pc-20260706-000000-demo",
      timestamp: "2026-07-06T00:00:00Z",
      plan_ref: "prd.md",
      change_summary: "Narrow evaluation to one dataset split.",
      reason: "Initial scope was too broad for the task budget.",
      requested_by: "human/root",
      decision_state: "accepted",
      evidence_refs: [],
      supersedes: [],
    };

    const append = runHermes(tmpDir, "record.py", [
      "append",
      "--task",
      "01-test",
      "--record-type",
      "plan_change",
      "--json",
      JSON.stringify(planChange),
    ]);

    expect(append.status).toBe(0);
    expect(append.stdout).toContain("appended");

    const records = fs
      .readFileSync(
        path.join(taskDir, "hermes", "plan_change_log.jsonl"),
        "utf-8",
      )
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line) as Record<string, unknown>);

    expect(records).toHaveLength(1);
    expect(records[0].type).toBe("plan_change");

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "plan_change",
    ]);

    expect(validate.status).toBe(0);
    expect(validate.stdout).toContain("valid");
  });

  it("rejects plan change records with invalid decision_state", () => {
    writeJsonl(path.join(taskDir, "hermes", "plan_change_log.jsonl"), [
      {
        type: "plan_change",
        id: "pc-20260706-000000-demo",
        timestamp: "2026-07-06T00:00:00Z",
        plan_ref: "prd.md",
        change_summary: "Narrow evaluation to one dataset split.",
        reason: "Initial scope was too broad for the task budget.",
        requested_by: "human/root",
        decision_state: "approved",
        evidence_refs: [],
        supersedes: [],
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "plan_change",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("decision_state must be one of");
  });

  it("rejects non-plan-change records in the plan change log", () => {
    writeJsonl(path.join(taskDir, "hermes", "plan_change_log.jsonl"), [
      {
        type: "claim",
        id: "cl-20260706-000000-demo",
        timestamp: "2026-07-06T00:00:00Z",
        text: "The plan changed.",
        evidence_ids: [],
        scope: "unit test",
        limits: "none",
        state: "draft",
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "plan_change",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("expected plan_change record");
  });

  it("rejects plan change records with missing required fields", () => {
    writeJsonl(path.join(taskDir, "hermes", "plan_change_log.jsonl"), [
      {
        type: "plan_change",
        id: "pc-20260706-000000-demo",
        timestamp: "2026-07-06T00:00:00Z",
        plan_ref: "prd.md",
        change_summary: "Narrow evaluation to one dataset split.",
        requested_by: "human/root",
        decision_state: "accepted",
        evidence_refs: [],
        supersedes: [],
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "plan_change",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("missing required fields: reason");
  });

  it("rejects plan change records with an empty plan_ref", () => {
    writeJsonl(path.join(taskDir, "hermes", "plan_change_log.jsonl"), [
      {
        type: "plan_change",
        id: "pc-20260706-000000-demo",
        timestamp: "2026-07-06T00:00:00Z",
        plan_ref: "   ",
        change_summary: "Narrow evaluation to one dataset split.",
        reason: "Initial scope was too broad for the task budget.",
        requested_by: "human/root",
        decision_state: "accepted",
        evidence_refs: [],
        supersedes: [],
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "plan_change",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain(
      "plan_change plan_ref must be a non-empty string",
    );
  });

  it("rejects plan change records with non-string reference arrays", () => {
    writeJsonl(path.join(taskDir, "hermes", "plan_change_log.jsonl"), [
      {
        type: "plan_change",
        id: "pc-20260706-000000-demo",
        timestamp: "2026-07-06T00:00:00Z",
        plan_ref: "prd.md",
        change_summary: "Narrow evaluation to one dataset split.",
        reason: "Initial scope was too broad for the task budget.",
        requested_by: "human/root",
        decision_state: "accepted",
        evidence_refs: ["ev-demo", 123],
        supersedes: [false],
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "plan_change",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain(
      "evidence_refs must contain only non-empty strings",
    );
    expect(validate.stderr).toContain(
      "supersedes must contain only non-empty strings",
    );
  });

  it("rejects artifact ledger records when the artifact file is missing", () => {
    writeJsonl(path.join(taskDir, "hermes", "artifact_ledger.jsonl"), [
      {
        type: "artifact",
        id: "ar-20260629-000000-demo",
        path: "reports/missing-output.txt",
        hash: "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        run_id: "run-demo",
        command_ref: "cmd-demo",
        summary: "captured runtime output",
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "artifact",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("artifact path is not readable");
  });

  it("rejects artifact ledger records when the hash format is invalid", () => {
    fs.mkdirSync(path.join(tmpDir, "reports"), { recursive: true });
    fs.writeFileSync(path.join(tmpDir, "reports", "bad-hash.txt"), "output", "utf-8");
    writeJsonl(path.join(taskDir, "hermes", "artifact_ledger.jsonl"), [
      {
        type: "artifact",
        id: "ar-20260629-000000-demo",
        path: "reports/bad-hash.txt",
        hash: "sha256:not-a-real-hash",
        run_id: "run-demo",
        command_ref: "cmd-demo",
        summary: "captured runtime output",
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "artifact",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("artifact hash is invalid");
  });

  it("rejects artifact ledger records when the sha256 does not match", () => {
    fs.mkdirSync(path.join(tmpDir, "reports"), { recursive: true });
    fs.writeFileSync(path.join(tmpDir, "reports", "mismatch.txt"), "actual", "utf-8");
    writeJsonl(path.join(taskDir, "hermes", "artifact_ledger.jsonl"), [
      {
        type: "artifact",
        id: "ar-20260629-000000-demo",
        path: "reports/mismatch.txt",
        hash: sha256Text("expected"),
        run_id: "run-demo",
        command_ref: "cmd-demo",
        summary: "captured runtime output",
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "artifact",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("artifact hash mismatch");
  });

  it("validates evidence records with artifact_refs and command_refs", () => {
    const artifactContent = "captured runtime output";
    fs.mkdirSync(path.join(tmpDir, "reports"), { recursive: true });
    fs.writeFileSync(
      path.join(tmpDir, "reports", "runtime-output.txt"),
      artifactContent,
      "utf-8",
    );
    fs.writeFileSync(
      path.join(taskDir, "hermes", "artifact_ledger.jsonl"),
      `${JSON.stringify({
        type: "artifact",
        id: "ar-20260629-000000-demo",
        path: "reports/runtime-output.txt",
        hash: sha256Text(artifactContent),
        run_id: "run-demo",
        command_ref: "cmd-demo",
        summary: "captured runtime output",
      })}\n`,
    );
    fs.writeFileSync(
      path.join(taskDir, "hermes", "evidence_ledger.jsonl"),
      `${JSON.stringify({
        type: "evidence",
        id: "ev-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        source: "runtime output",
        summary: "captured output",
        limits: "unit test only",
        artifact_refs: ["ar-20260629-000000-demo"],
        command_refs: ["cmd-demo"],
      })}\n`,
    );

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "evidence",
    ]);

    expect(validate.status).toBe(0);
    expect(validate.stdout).toContain("valid");
  });

  it("initializes task-scoped experiment and run manifest skeleton paths", () => {
    const init = runHermes(tmpDir, "experiment.py", [
      "init",
      "--task",
      "01-test",
    ]);

    expect(init.status).toBe(0);
    expect(init.stdout).toContain(".trellis/tasks/01-test/hermes/experiment.yaml");
    expect(init.stdout).toContain(".trellis/tasks/01-test/hermes/run_manifest.jsonl");
    expect(init.stdout).toContain(".trellis/tasks/01-test/hermes/worker_records.jsonl");
    expect(fs.existsSync(path.join(taskDir, "hermes", "experiment.yaml"))).toBe(true);
    expect(fs.existsSync(path.join(taskDir, "hermes", "run_manifest.jsonl"))).toBe(true);
    expect(fs.readFileSync(
      path.join(taskDir, "hermes", "worker_records.jsonl"),
      "utf-8",
    )).toBe("");
  });

  it("keeps ordinary experiment validation free of data_preflight", () => {
    writeExperimentConfig(taskDir);

    const validate = runHermes(tmpDir, "experiment.py", [
      "validate",
      "--task",
      "01-test",
    ]);

    expect(validate.status).toBe(0);
  });

  it("blocks a data-changing exploration before runner command execution when data_preflight is missing", () => {
    markDataExploration(taskDir);
    writeExperimentConfig(taskDir);
    writeRunnerCard(taskDir, "job-data-preflight-missing");

    const run = runHermes(tmpDir, "runner.py", [
      "run",
      "--task",
      "01-test",
      "--job-id",
      "job-data-preflight-missing",
      "--checkpoint",
      "data-preflight",
      "--summary",
      "validate data before execution",
      "--",
      "python3",
      "-c",
      "import pathlib; pathlib.Path('should-not-run.txt').write_text('bad')",
    ]);

    expect(run.status).toBe(1);
    expect(run.stderr).toContain("data_preflight is required");
    expect(fs.existsSync(path.join(tmpDir, "should-not-run.txt"))).toBe(false);
    expect(fs.existsSync(path.join(taskDir, "hermes", "run_manifest.jsonl"))).toBe(false);
  });

  it("rejects a data_preflight hash that does not match its input manifest", () => {
    markDataExploration(taskDir);
    writeExperimentConfig(taskDir);
    appendDataPreflight(
      taskDir,
      `sha256:${"0".repeat(64)}`,
      "schema: checked\nmissing: checked\nduplicates: checked\nsplit_leakage: not_applicable\n",
    );

    const validate = runHermes(tmpDir, "experiment.py", [
      "validate",
      "--task",
      "01-test",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("data_preflight hash mismatch");
  });

  it("rejects data_preflight checks with a missing required check", () => {
    markDataExploration(taskDir);
    writeExperimentConfig(taskDir);
    const manifestContent = '{"rows":2}\n';
    appendDataPreflight(
      taskDir,
      sha256Text(manifestContent),
      "schema: checked\nmissing: checked\nduplicates: checked\n",
    );

    const validate = runHermes(tmpDir, "experiment.py", [
      "validate",
      "--task",
      "01-test",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("split_leakage must be checked or not_applicable");
  });

  it("accepts valid data_preflight and records its files as runner inputs", () => {
    markDataExploration(taskDir);
    writeExperimentConfig(taskDir);
    const manifestContent = '{"rows":2}\n';
    const refs = appendDataPreflight(
      taskDir,
      sha256Text(manifestContent),
      "schema: checked\nmissing: checked\nduplicates: checked\nsplit_leakage: not_applicable\n",
    );
    writeRunnerCard(taskDir, "job-data-preflight-valid");

    const run = runHermes(tmpDir, "runner.py", [
      "run",
      "--task",
      "01-test",
      "--job-id",
      "job-data-preflight-valid",
      "--checkpoint",
      "data-preflight",
      "--summary",
      "run with validated data",
      "--input",
      refs.manifestPath,
      "--input",
      refs.checksPath,
      "--output",
      "data-run.txt",
      "--",
      "python3",
      "-c",
      "import pathlib; pathlib.Path('data/input-manifest.json').write_text('{\"rows\":99}\\n'); pathlib.Path('data-run.txt').write_text('ok')",
    ]);

    expect(run.status).toBe(0);
    const manifest = fs
      .readFileSync(path.join(taskDir, "hermes", "run_manifest.jsonl"), "utf-8")
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line) as Record<string, unknown>);
    expect(manifest).toHaveLength(1);
    expect(manifest[0].inputs).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ path: refs.manifestPath, hash: sha256Text(manifestContent) }),
        expect.objectContaining({ path: refs.checksPath }),
      ]),
    );
    expect(sha256Text(fs.readFileSync(path.join(tmpDir, refs.manifestPath), "utf-8"))).not.toBe(
      sha256Text(manifestContent),
    );
  });

  it("rejects worker results when there is no task_card", () => {
    fs.writeFileSync(
      path.join(taskDir, "hermes", "worker_records.jsonl"),
      `${JSON.stringify({
        type: "result",
        id: "rs-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-missing-card",
        status: "done",
        summary: "changed files",
        changed_files: ["src/app.ts"],
        evidence_refs: [],
        risk_flags: [],
        handoff: "review",
      })}\n`,
    );

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "worker",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("missing task_card");
  });

  it("rejects file changes outside allowed_files and inside forbidden_files", () => {
    const workerRecords = [
      {
        type: "task_card",
        id: "tc-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-demo",
        role: "coder",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: [".env", "secrets/**"],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
      {
        type: "result",
        id: "rs-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-demo",
        status: "done",
        summary: "changed files",
        changed_files: ["src/app.ts", "docs/readme.md", ".env"],
        evidence_refs: [],
        risk_flags: [],
        handoff: "review",
      },
    ];
    fs.writeFileSync(
      path.join(taskDir, "hermes", "worker_records.jsonl"),
      workerRecords.map((record) => JSON.stringify(record)).join("\n") + "\n",
    );

    const guard = runHermes(tmpDir, "guard.py", [
      "--task",
      "01-test",
      "--job-id",
      "job-demo",
      "--changed-files",
      "src/app.ts,docs/readme.md,.env",
    ]);

    expect(guard.status).toBe(1);
    expect(guard.stderr).toContain("outside allowed_files");
    expect(guard.stderr).toContain("forbidden_files");
  });

  it("rejects duplicate task_card records for one job_id", () => {
    const workerRecords = [
      {
        type: "task_card",
        id: "tc-20260629-000000-narrow",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-duplicate",
        role: "coder",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
      {
        type: "task_card",
        id: "tc-20260629-000100-wide",
        timestamp: "2026-06-29T00:01:00Z",
        job_id: "job-duplicate",
        role: "coder",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
      {
        type: "result",
        id: "rs-20260629-000200-demo",
        timestamp: "2026-06-29T00:02:00Z",
        job_id: "job-duplicate",
        status: "done",
        summary: "changed docs",
        changed_files: ["docs/readme.md"],
        evidence_refs: [],
        risk_flags: [],
        handoff: "review",
      },
    ];
    fs.writeFileSync(
      path.join(taskDir, "hermes", "worker_records.jsonl"),
      workerRecords.map((record) => JSON.stringify(record)).join("\n") + "\n",
    );

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "worker",
    ]);
    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("duplicate task_card");
  });

  it("rejects multiple unfinished active writer task cards in the same worktree", () => {
    writeJsonl(path.join(taskDir, "hermes", "worker_records.jsonl"), [
      {
        type: "task_card",
        id: "tc-20260629-000000-coder",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-coder",
        role: "coder",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
      {
        type: "task_card",
        id: "tc-20260629-000100-coder",
        timestamp: "2026-06-29T00:01:00Z",
        job_id: "job-coder-two",
        role: "coder",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["docs/**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
      {
        type: "task_card",
        id: "tc-20260629-000200-reviewer",
        timestamp: "2026-06-29T00:02:00Z",
        job_id: "job-reviewer",
        role: "reviewer",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "worker",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("multiple active writers in worktree main");
  });

  it("accepts unfinished checker task cards alongside one active writer", () => {
    writeJsonl(path.join(taskDir, "hermes", "worker_records.jsonl"), [
      {
        type: "task_card",
        id: "tc-20260629-000000-coder",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-coder",
        role: "coder",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
      {
        type: "task_card",
        id: "tc-20260629-000100-reviewer",
        timestamp: "2026-06-29T00:01:00Z",
        job_id: "job-reviewer",
        role: "reviewer",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
      {
        type: "task_card",
        id: "tc-20260629-000200-evaluator",
        timestamp: "2026-06-29T00:02:00Z",
        job_id: "job-evaluator",
        role: "evaluator",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
      {
        type: "task_card",
        id: "tc-20260629-000300-literature",
        timestamp: "2026-06-29T00:03:00Z",
        job_id: "job-literature",
        role: "literature",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "worker",
    ]);

    expect(validate.status).toBe(0);
    expect(validate.stdout).toContain("valid");
  });

  it("rejects coder review handoff before runner and reviewer results exist", () => {
    writeJsonl(path.join(taskDir, "hermes", "worker_records.jsonl"), [
      {
        type: "task_card",
        id: "tc-20260629-000000-coder",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-coder",
        role: "coder",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
      {
        type: "checkpoint",
        id: "cp-20260629-000100-coder",
        timestamp: "2026-06-29T00:01:00Z",
        job_id: "job-coder",
        checkpoint: "implementation-done",
        resume_from: "review diff",
        evidence_refs: [],
        open_items: [],
      },
      {
        type: "result",
        id: "rs-20260629-000200-coder",
        timestamp: "2026-06-29T00:02:00Z",
        job_id: "job-coder",
        status: "done",
        summary: "changed files",
        changed_files: ["src/app.ts"],
        evidence_refs: [],
        risk_flags: [],
        handoff: "review",
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "worker",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("coder review handoff requires runner result");
    expect(validate.stderr).toContain("coder review handoff requires reviewer");
  });

  it("accepts a configuration handoff without inventing code test records", () => {
    writeJsonl(path.join(taskDir, "hermes", "worker_records.jsonl"), [
      {
        type: "task_card",
        id: "tc-20260629-000000-config",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-config",
        role: "coder",
        profile: "configuration",
        worktree_id: "main",
        status: "queued",
        allowed_files: [".trellis/tasks/01-test/HANDOFF.md"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
      {
        type: "checkpoint",
        id: "cp-20260629-000100-config",
        timestamp: "2026-06-29T00:01:00Z",
        job_id: "job-config",
        checkpoint: "handoff-written",
        resume_from: "return result",
        evidence_refs: [],
        open_items: [],
      },
      {
        type: "result",
        id: "rs-20260629-000200-config",
        timestamp: "2026-06-29T00:02:00Z",
        job_id: "job-config",
        status: "done",
        summary: "wrote task handoff",
        changed_files: [".trellis/tasks/01-test/HANDOFF.md"],
        evidence_refs: [],
        risk_flags: [],
        handoff: "review",
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "worker",
    ]);

    expect(validate.status).toBe(0);
    expect(validate.stdout).toContain("valid");
  });

  it("rejects coder review handoff when runner has no result record", () => {
    writeJsonl(path.join(taskDir, "hermes", "worker_records.jsonl"), [
      {
        type: "task_card",
        id: "tc-20260629-000000-coder",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-coder",
        role: "coder",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
      {
        type: "task_card",
        id: "tc-20260629-000100-runner",
        timestamp: "2026-06-29T00:01:00Z",
        job_id: "job-runner",
        role: "runner",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
        parent_job_id: "job-coder",
      },
      {
        type: "checkpoint",
        id: "cp-20260629-000200-runner",
        timestamp: "2026-06-29T00:02:00Z",
        job_id: "job-runner",
        checkpoint: "tests-started",
        resume_from: "finish tests",
        evidence_refs: [],
        open_items: [],
      },
      {
        type: "task_card",
        id: "tc-20260629-000300-reviewer",
        timestamp: "2026-06-29T00:03:00Z",
        job_id: "job-reviewer",
        role: "reviewer",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
        parent_job_id: "job-coder",
      },
      {
        type: "checkpoint",
        id: "cp-20260629-000400-reviewer",
        timestamp: "2026-06-29T00:04:00Z",
        job_id: "job-reviewer",
        checkpoint: "diff-reviewed",
        resume_from: "accept handoff",
        evidence_refs: [],
        open_items: [],
      },
      {
        type: "checkpoint",
        id: "cp-20260629-000500-coder",
        timestamp: "2026-06-29T00:05:00Z",
        job_id: "job-coder",
        checkpoint: "implementation-done",
        resume_from: "review diff",
        evidence_refs: [],
        open_items: [],
      },
      {
        type: "result",
        id: "rs-20260629-000600-coder",
        timestamp: "2026-06-29T00:06:00Z",
        job_id: "job-coder",
        status: "done",
        summary: "changed files",
        changed_files: ["src/app.ts"],
        evidence_refs: [],
        risk_flags: [],
        handoff: "review",
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "worker",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("coder review handoff requires runner result");
    expect(validate.stderr).not.toContain("coder review handoff requires reviewer");
  });

  it("accepts coder review handoff after runner and reviewer results exist", () => {
    writeJsonl(path.join(taskDir, "hermes", "worker_records.jsonl"), [
      {
        type: "task_card",
        id: "tc-20260629-000000-coder",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-coder",
        role: "coder",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
      {
        type: "task_card",
        id: "tc-20260629-000100-runner",
        timestamp: "2026-06-29T00:01:00Z",
        job_id: "job-runner",
        role: "runner",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
        parent_job_id: "job-coder",
      },
      {
        type: "checkpoint",
        id: "cp-20260629-000200-runner",
        timestamp: "2026-06-29T00:02:00Z",
        job_id: "job-runner",
        checkpoint: "tests-run",
        resume_from: "inspect test output",
        evidence_refs: [],
        open_items: [],
      },
      {
        type: "result",
        id: "rs-20260629-000300-runner",
        timestamp: "2026-06-29T00:03:00Z",
        job_id: "job-runner",
        status: "done",
        summary: "tests passed",
        changed_files: [],
        evidence_refs: [],
        risk_flags: [],
        handoff: "reviewer",
      },
      {
        type: "task_card",
        id: "tc-20260629-000400-reviewer",
        timestamp: "2026-06-29T00:04:00Z",
        job_id: "job-reviewer",
        role: "reviewer",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
        parent_job_id: "job-coder",
      },
      {
        type: "checkpoint",
        id: "cp-20260629-000500-reviewer",
        timestamp: "2026-06-29T00:05:00Z",
        job_id: "job-reviewer",
        checkpoint: "diff-reviewed",
        resume_from: "accept handoff",
        evidence_refs: [],
        open_items: [],
      },
      {
        type: "result",
        id: "rs-20260629-000600-reviewer",
        timestamp: "2026-06-29T00:06:00Z",
        job_id: "job-reviewer",
        status: "done",
        summary: "review passed",
        changed_files: [],
        evidence_refs: [],
        risk_flags: [],
        handoff: "claim_ready",
      },
      {
        type: "checkpoint",
        id: "cp-20260629-000700-coder",
        timestamp: "2026-06-29T00:07:00Z",
        job_id: "job-coder",
        checkpoint: "implementation-done",
        resume_from: "review diff",
        evidence_refs: [],
        open_items: [],
      },
      {
        type: "result",
        id: "rs-20260629-000800-coder",
        timestamp: "2026-06-29T00:08:00Z",
        job_id: "job-coder",
        status: "done",
        summary: "changed files",
        changed_files: ["src/app.ts"],
        evidence_refs: [],
        risk_flags: [],
        handoff: "review",
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "worker",
    ]);

    expect(validate.status).toBe(0);
    expect(validate.stdout).toContain("valid");
  });

  it("jobs check rejects duplicate task_card records before timeout handling", () => {
    const workerRecords = [
      {
        type: "task_card",
        id: "tc-20260629-000000-narrow",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-duplicate-check",
        role: "coder",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2026-06-29T00:05:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
      {
        type: "task_card",
        id: "tc-20260629-000100-wide",
        timestamp: "2026-06-29T00:01:00Z",
        job_id: "job-duplicate-check",
        role: "coder",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2026-06-29T00:05:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
    ];
    const recordsPath = path.join(taskDir, "hermes", "worker_records.jsonl");
    fs.writeFileSync(
      recordsPath,
      workerRecords.map((record) => JSON.stringify(record)).join("\n") + "\n",
    );

    const check = runHermes(tmpDir, "jobs.py", [
      "check",
      "--task",
      "01-test",
      "--now",
      "2026-06-29T00:10:00Z",
    ]);

    expect(check.status).toBe(1);
    expect(check.stderr).toContain("duplicate task_card");
    const records = fs.readFileSync(recordsPath, "utf-8");
    expect(records).not.toContain('"type":"rejection"');
  });

  it("marks timed-out jobs as stalled and records resume_from", () => {
    const workerRecords = [
      {
        type: "task_card",
        id: "tc-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-timeout",
        role: "coder",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2026-06-29T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
      {
        type: "checkpoint",
        id: "cp-20260629-000100-demo",
        timestamp: "2026-06-29T00:01:00Z",
        job_id: "job-timeout",
        checkpoint: "tests-added",
        resume_from: "rerun targeted tests",
        evidence_refs: [],
        open_items: ["finish implementation"],
      },
    ];
    fs.writeFileSync(
      path.join(taskDir, "hermes", "worker_records.jsonl"),
      workerRecords.map((record) => JSON.stringify(record)).join("\n") + "\n",
    );

    const check = runHermes(tmpDir, "jobs.py", [
      "check",
      "--task",
      "01-test",
      "--now",
      "2026-06-29T00:10:00Z",
    ]);

    expect(check.status).toBe(1);
    expect(check.stderr).toContain("stalled");

    const content = fs.readFileSync(
      path.join(taskDir, "hermes", "worker_records.jsonl"),
      "utf-8",
    );
    expect(content).toContain('"type":"rejection"');
    expect(content).toContain('"reason":"timeout"');
    expect(content).toContain(
      '"required_fix":"resume from rerun targeted tests"',
    );
  });

  it("marks jobs as stalled when heartbeat next_check_at is missed", () => {
    const workerRecords = [
      {
        type: "task_card",
        id: "tc-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-heartbeat-timeout",
        role: "coder",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
      {
        type: "heartbeat",
        id: "hb-20260629-000100-demo",
        timestamp: "2026-06-29T00:01:00Z",
        job_id: "job-heartbeat-timeout",
        status: "running",
        checkpoint: "files-read",
        summary: "still running",
        next_check_at: "2026-06-29T00:06:00Z",
      },
    ];
    fs.writeFileSync(
      path.join(taskDir, "hermes", "worker_records.jsonl"),
      workerRecords.map((record) => JSON.stringify(record)).join("\n") + "\n",
    );

    const check = runHermes(tmpDir, "jobs.py", [
      "check",
      "--task",
      "01-test",
      "--now",
      "2026-06-29T00:10:00Z",
    ]);

    expect(check.status).toBe(1);
    expect(check.stderr).toContain("stalled");
    const content = fs.readFileSync(
      path.join(taskDir, "hermes", "worker_records.jsonl"),
      "utf-8",
    );
    expect(content).toContain('"reason":"heartbeat_timeout"');
  });

  it("jobs check rejects heartbeat records with invalid next_check_at", () => {
    const workerRecords = [
      {
        type: "task_card",
        id: "tc-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-invalid-heartbeat",
        role: "coder",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
      {
        type: "heartbeat",
        id: "hb-20260629-000100-demo",
        timestamp: "2026-06-29T00:01:00Z",
        job_id: "job-invalid-heartbeat",
        status: "running",
        checkpoint: "files-read",
        summary: "still running",
        next_check_at: "not-a-time",
      },
    ];
    fs.writeFileSync(
      path.join(taskDir, "hermes", "worker_records.jsonl"),
      workerRecords.map((record) => JSON.stringify(record)).join("\n") + "\n",
    );

    const check = runHermes(tmpDir, "jobs.py", [
      "check",
      "--task",
      "01-test",
      "--now",
      "2026-06-29T00:10:00Z",
    ]);

    expect(check.status).toBe(1);
    expect(check.stderr).toContain("invalid heartbeat next_check_at");
  });

  it("writes heartbeat records for long-running jobs", () => {
    const workerRecords = [
      {
        type: "task_card",
        id: "tc-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-heartbeat",
        role: "coder",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
    ];
    fs.writeFileSync(
      path.join(taskDir, "hermes", "worker_records.jsonl"),
      workerRecords.map((record) => JSON.stringify(record)).join("\n") + "\n",
    );

    const beat = runHermes(tmpDir, "heartbeat.py", [
      "beat",
      "--task",
      "01-test",
      "--job-id",
      "job-heartbeat",
      "--checkpoint",
      "files-read",
      "--summary",
      "read runtime files",
      "--now",
      "2026-06-29T00:00:00Z",
    ]);

    expect(beat.status).toBe(0);
    expect(beat.stdout).toContain("heartbeat");

    const records = fs
      .readFileSync(
        path.join(taskDir, "hermes", "worker_records.jsonl"),
        "utf-8",
      )
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line) as Record<string, unknown>);

    expect(records).toHaveLength(2);
    expect(records[1]).toMatchObject({
      type: "heartbeat",
      job_id: "job-heartbeat",
      timestamp: "2026-06-29T00:00:00Z",
      status: "running",
      checkpoint: "files-read",
      summary: "read runtime files",
      next_check_at: "2026-06-29T00:05:00Z",
    });

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "worker",
    ]);
    expect(validate.status).toBe(0);
  });

  it("rejects heartbeat records with invalid timestamps", () => {
    const workerRecords = [
      {
        type: "task_card",
        id: "tc-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-bad-heartbeat",
        role: "coder",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
    ];
    fs.writeFileSync(
      path.join(taskDir, "hermes", "worker_records.jsonl"),
      workerRecords.map((record) => JSON.stringify(record)).join("\n") + "\n",
    );

    const beat = runHermes(tmpDir, "heartbeat.py", [
      "beat",
      "--task",
      "01-test",
      "--job-id",
      "job-bad-heartbeat",
      "--checkpoint",
      "files-read",
      "--summary",
      "bad timestamp",
      "--now",
      "not-a-time",
    ]);

    expect(beat.status).toBe(2);
    expect(beat.stderr).toContain("invalid --now timestamp");
  });

  it("can run the heartbeat watcher for a bounded count", () => {
    const workerRecords = [
      {
        type: "task_card",
        id: "tc-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-watch",
        role: "coder",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: [],
        heartbeat_interval: "30s",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
    ];
    fs.writeFileSync(
      path.join(taskDir, "hermes", "worker_records.jsonl"),
      workerRecords.map((record) => JSON.stringify(record)).join("\n") + "\n",
    );

    const watch = runHermes(tmpDir, "heartbeat.py", [
      "watch",
      "--task",
      "01-test",
      "--job-id",
      "job-watch",
      "--checkpoint",
      "tests-running",
      "--summary",
      "running tests",
      "--count",
      "1",
      "--now",
      "2026-06-29T00:00:00Z",
    ]);

    expect(watch.status).toBe(0);

    const records = fs
      .readFileSync(
        path.join(taskDir, "hermes", "worker_records.jsonl"),
        "utf-8",
      )
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line) as Record<string, unknown>);

    expect(records).toHaveLength(2);
    expect(records[1]).toMatchObject({
      type: "heartbeat",
      job_id: "job-watch",
      next_check_at: "2026-06-29T00:00:30Z",
    });
  });

  it("runner uses local execution for legacy sandbox configs and records a replayable manifest", () => {
    const workerRecords = [
      {
        type: "task_card",
        id: "tc-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-runner",
        role: "runner",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["**"],
        forbidden_files: [],
        heartbeat_interval: "1s",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
    ];
    fs.writeFileSync(
      path.join(taskDir, "hermes", "worker_records.jsonl"),
      workerRecords.map((record) => JSON.stringify(record)).join("\n") + "\n",
    );
    writeExperimentConfig(taskDir);
    fs.appendFileSync(
      path.join(taskDir, "hermes", "experiment.yaml"),
      'sandbox:\n  mode: "container"\n  required: true\n',
      "utf-8",
    );

    const run = runHermes(tmpDir, "runner.py", [
      "run",
      "--task",
      "01-test",
      "--job-id",
      "job-runner",
      "--checkpoint",
      "command-running",
      "--summary",
      "run long command",
      "--resume-from",
      "rerun command from run_manifest",
      "--heartbeat-interval",
      "1s",
      "--output",
      "runner-output.txt",
      "--",
      "python3",
      "-c",
      "import pathlib, time; time.sleep(1.15); pathlib.Path('runner-output.txt').write_text('done', encoding='utf-8')",
    ]);

    expect(run.status).toBe(0);
    expect(run.stdout).toContain("run manifest appended");

    const workerRows = fs
      .readFileSync(
        path.join(taskDir, "hermes", "worker_records.jsonl"),
        "utf-8",
      )
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line) as Record<string, unknown>);
    expect(workerRows.filter((record) => record.type === "heartbeat").length).toBeGreaterThanOrEqual(2);
    expect(workerRows[1]).toMatchObject({
      type: "checkpoint",
      checkpoint: "command-running",
      resume_from: "rerun command from run_manifest",
    });
    expect(workerRows.find((record) => record.type === "checkpoint")).toMatchObject({
      checkpoint: "command-running",
      resume_from: "rerun command from run_manifest",
    });
    expect(workerRows.find((record) => record.type === "result")).toMatchObject({
      status: "done",
      job_id: "job-runner",
    });

    const manifestRows = fs
      .readFileSync(path.join(taskDir, "hermes", "run_manifest.jsonl"), "utf-8")
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line) as Record<string, unknown>);
    expect(manifestRows).toHaveLength(1);
    expect(manifestRows[0]).toMatchObject({
      job_id: "job-runner",
      exit_code: 0,
      checkpoint: "command-running",
    });
    expect(manifestRows[0].command).toEqual(
      expect.arrayContaining(["python3", "-c"]),
    );

    const validateManifest = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "run_manifest",
    ]);
    expect(validateManifest.status).toBe(0);

    const replay = runHermes(tmpDir, "runner.py", [
      "replay",
      "--task",
      "01-test",
      "--run-id",
      String(manifestRows[0].id),
    ]);
    expect(replay.status).toBe(0);
    expect(replay.stdout).toContain("replayable");
  });

  it("runner run rejects missing task experiment config before writing run_manifest", () => {
    const workerRecords = [
      {
        type: "task_card",
        id: "tc-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-runner-no-experiment",
        role: "runner",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["**"],
        forbidden_files: [],
        heartbeat_interval: "1s",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
    ];
    fs.writeFileSync(
      path.join(taskDir, "hermes", "worker_records.jsonl"),
      workerRecords.map((record) => JSON.stringify(record)).join("\n") + "\n",
    );

    const run = runHermes(tmpDir, "runner.py", [
      "run",
      "--task",
      "01-test",
      "--job-id",
      "job-runner-no-experiment",
      "--checkpoint",
      "command-running",
      "--summary",
      "run command without experiment config",
      "--",
      "python3",
      "-c",
      "import pathlib; pathlib.Path('should-not-run.txt').write_text('bad', encoding='utf-8')",
    ]);

    expect(run.status).toBe(1);
    expect(run.stderr).toContain("missing experiment.yaml");
    expect(
      fs.existsSync(path.join(taskDir, "hermes", "run_manifest.jsonl")),
    ).toBe(false);
    expect(fs.existsSync(path.join(tmpDir, "should-not-run.txt"))).toBe(false);
  });

  it("runner run rejects commands missing from experiment allowed_commands", () => {
    const workerRecords = [
      {
        type: "task_card",
        id: "tc-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-runner-disallowed-command",
        role: "runner",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["**"],
        forbidden_files: [],
        heartbeat_interval: "1s",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
    ];
    fs.writeFileSync(
      path.join(taskDir, "hermes", "worker_records.jsonl"),
      workerRecords.map((record) => JSON.stringify(record)).join("\n") + "\n",
    );
    writeExperimentConfigWithAllowedCommands(taskDir, ["python3"]);

    const run = runHermes(tmpDir, "runner.py", [
      "run",
      "--task",
      "01-test",
      "--job-id",
      "job-runner-disallowed-command",
      "--checkpoint",
      "command-running",
      "--summary",
      "run disallowed command",
      "--",
      "node",
      "-e",
      "require('fs').writeFileSync('should-not-run.txt', 'bad')",
    ]);

    expect(run.status).toBe(1);
    expect(run.stderr).toContain("not allowed by experiment allowed_commands");
    expect(
      fs.existsSync(path.join(taskDir, "hermes", "run_manifest.jsonl")),
    ).toBe(false);
    expect(fs.existsSync(path.join(tmpDir, "should-not-run.txt"))).toBe(false);
  });

  it("runner run rejects cwd escaping the repository", () => {
    const outsideDir = fs.mkdtempSync(path.join(os.tmpdir(), "trellis-runner-outside-"));
    const workerRecords = [
      {
        type: "task_card",
        id: "tc-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-runner-cwd-escape",
        role: "runner",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["**"],
        forbidden_files: [],
        heartbeat_interval: "1s",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
    ];
    fs.writeFileSync(
      path.join(taskDir, "hermes", "worker_records.jsonl"),
      workerRecords.map((record) => JSON.stringify(record)).join("\n") + "\n",
    );
    writeExperimentConfig(taskDir);

    try {
      const run = runHermes(tmpDir, "runner.py", [
        "run",
        "--task",
        "01-test",
        "--job-id",
        "job-runner-cwd-escape",
        "--checkpoint",
        "command-running",
        "--summary",
        "run outside cwd",
        "--cwd",
        path.relative(tmpDir, outsideDir),
        "--",
        "python3",
        "-c",
        "print('should not run')",
      ]);

      expect(run.status).toBe(2);
      expect(run.stderr).toContain("cwd must stay inside repository");
      expect(
        fs.existsSync(path.join(taskDir, "hermes", "run_manifest.jsonl")),
      ).toBe(false);
    } finally {
      fs.rmSync(outsideDir, { recursive: true, force: true });
    }
  });

  it("runner run rejects inputs and outputs escaping repository bounds", () => {
    const workerRecords = [
      {
        type: "task_card",
        id: "tc-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-runner-output-escape",
        role: "runner",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["**"],
        forbidden_files: [],
        heartbeat_interval: "1s",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
    ];
    fs.writeFileSync(
      path.join(taskDir, "hermes", "worker_records.jsonl"),
      workerRecords.map((record) => JSON.stringify(record)).join("\n") + "\n",
    );
    writeExperimentConfig(taskDir);

    const run = runHermes(tmpDir, "runner.py", [
      "run",
      "--task",
      "01-test",
      "--job-id",
      "job-runner-output-escape",
      "--checkpoint",
      "command-running",
      "--summary",
      "run with escaping output",
      "--output",
      "../escape.txt",
      "--",
      "python3",
      "-c",
      "print('should not run')",
    ]);

    expect(run.status).toBe(2);
    expect(run.stderr).toContain("output path must stay inside repository");
    expect(
      fs.existsSync(path.join(taskDir, "hermes", "run_manifest.jsonl")),
    ).toBe(false);
  });

  it("runner inherits the project runtime environment without recording it", () => {
    const workerRecords = [
      {
        type: "task_card",
        id: "tc-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-runner-env",
        role: "runner",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["**"],
        forbidden_files: [],
        heartbeat_interval: "1s",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
    ];
    fs.writeFileSync(
      path.join(taskDir, "hermes", "worker_records.jsonl"),
      workerRecords.map((record) => JSON.stringify(record)).join("\n") + "\n",
    );
    writeExperimentConfig(taskDir);

    const result = spawnSync(
      "python3",
      [
        path.join(tmpDir, ".trellis", "scripts", "hermes", "runner.py"),
        "run",
        "--task",
        "01-test",
        "--job-id",
        "job-runner-env",
        "--checkpoint",
        "command-running",
        "--summary",
        "run env check",
        "--output",
        "env-output.txt",
        "--",
        "python3",
        "-c",
        "import os, pathlib; pathlib.Path('env-output.txt').write_text(os.environ.get('AWS_SECRET_ACCESS_KEY', 'missing'), encoding='utf-8')",
      ],
      {
        cwd: tmpDir,
        encoding: "utf-8",
        env: {
          ...process.env,
          AWS_SECRET_ACCESS_KEY: "test-secret-value",
        },
      },
    );

    expect(result.status).toBe(0);
    expect(
      fs.readFileSync(path.join(tmpDir, "env-output.txt"), "utf-8"),
    ).toBe("test-secret-value");
    const manifest = fs.readFileSync(
      path.join(taskDir, "hermes", "run_manifest.jsonl"),
      "utf-8",
    );
    expect(manifest).not.toContain("AWS_SECRET_ACCESS_KEY");
    expect(manifest).not.toContain("test-secret-value");
  });


  it("runner replay passes when output hashes match", () => {
    const output = "stable output";
    fs.writeFileSync(path.join(tmpDir, "replay-output.txt"), output, "utf-8");
    writeJsonl(path.join(taskDir, "hermes", "run_manifest.jsonl"), [
      {
        id: "run-replay-ok",
        job_id: "job-replay-ok",
        command: ["python3", "-c", "print('ok')"],
        cwd: ".",
        env_summary: { python: "3.x" },
        inputs: [],
        outputs: [
          {
            path: "replay-output.txt",
            kind: "artifact",
            hash: sha256Text(output),
          },
        ],
        exit_code: 0,
        started_at: "2026-06-29T00:00:00Z",
        finished_at: "2026-06-29T00:00:01Z",
      },
    ]);

    const replay = runHermes(tmpDir, "runner.py", [
      "replay",
      "--task",
      "01-test",
      "--run-id",
      "run-replay-ok",
    ]);

    expect(replay.status).toBe(0);
    expect(replay.stdout).toContain("replayable");
  });

  it("runner replay fails when output file content drifts", () => {
    const originalOutput = "original output";
    fs.writeFileSync(path.join(tmpDir, "drift-output.txt"), originalOutput, "utf-8");
    writeJsonl(path.join(taskDir, "hermes", "run_manifest.jsonl"), [
      {
        id: "run-replay-drift",
        job_id: "job-replay-drift",
        command: ["python3", "-c", "print('ok')"],
        cwd: ".",
        env_summary: { python: "3.x" },
        inputs: [],
        outputs: [
          {
            path: "drift-output.txt",
            kind: "artifact",
            hash: sha256Text(originalOutput),
          },
        ],
        exit_code: 0,
        started_at: "2026-06-29T00:00:00Z",
        finished_at: "2026-06-29T00:00:01Z",
      },
    ]);
    fs.writeFileSync(path.join(tmpDir, "drift-output.txt"), "changed output", "utf-8");

    const replay = runHermes(tmpDir, "runner.py", [
      "replay",
      "--task",
      "01-test",
      "--run-id",
      "run-replay-drift",
    ]);

    expect(replay.status).toBe(1);
    expect(replay.stderr).toContain("hash mismatch");
  });

  it("runner replay fails when an output file is missing", () => {
    writeJsonl(path.join(taskDir, "hermes", "run_manifest.jsonl"), [
      {
        id: "run-replay-missing",
        job_id: "job-replay-missing",
        command: ["python3", "-c", "print('ok')"],
        cwd: ".",
        env_summary: { python: "3.x" },
        inputs: [],
        outputs: [
          {
            path: "missing-replay-output.txt",
            kind: "artifact",
            hash: "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          },
        ],
        exit_code: 0,
        started_at: "2026-06-29T00:00:00Z",
        finished_at: "2026-06-29T00:00:01Z",
      },
    ]);

    const replay = runHermes(tmpDir, "runner.py", [
      "replay",
      "--task",
      "01-test",
      "--run-id",
      "run-replay-missing",
    ]);

    expect(replay.status).toBe(1);
    expect(replay.stderr).toContain("output path is not readable");
  });

  it("runner replay fails when an output hash is missing", () => {
    fs.writeFileSync(path.join(tmpDir, "missing-hash-output.txt"), "output", "utf-8");
    writeJsonl(path.join(taskDir, "hermes", "run_manifest.jsonl"), [
      {
        id: "run-replay-missing-hash",
        job_id: "job-replay-missing-hash",
        command: ["python3", "-c", "print('ok')"],
        cwd: ".",
        env_summary: { python: "3.x" },
        inputs: [],
        outputs: [
          {
            path: "missing-hash-output.txt",
            kind: "artifact",
          },
        ],
        exit_code: 0,
        started_at: "2026-06-29T00:00:00Z",
        finished_at: "2026-06-29T00:00:01Z",
      },
    ]);

    const replay = runHermes(tmpDir, "runner.py", [
      "replay",
      "--task",
      "01-test",
      "--run-id",
      "run-replay-missing-hash",
    ]);

    expect(replay.status).toBe(1);
    expect(replay.stderr).toContain("output hash is required");
  });

  it("runner replay fails when an output hash is invalid", () => {
    fs.writeFileSync(path.join(tmpDir, "invalid-hash-output.txt"), "output", "utf-8");
    writeJsonl(path.join(taskDir, "hermes", "run_manifest.jsonl"), [
      {
        id: "run-replay-invalid-hash",
        job_id: "job-replay-invalid-hash",
        command: ["python3", "-c", "print('ok')"],
        cwd: ".",
        env_summary: { python: "3.x" },
        inputs: [],
        outputs: [
          {
            path: "invalid-hash-output.txt",
            kind: "artifact",
            hash: "sha256:zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz",
          },
        ],
        exit_code: 0,
        started_at: "2026-06-29T00:00:00Z",
        finished_at: "2026-06-29T00:00:01Z",
      },
    ]);

    const replay = runHermes(tmpDir, "runner.py", [
      "replay",
      "--task",
      "01-test",
      "--run-id",
      "run-replay-invalid-hash",
    ]);

    expect(replay.status).toBe(1);
    expect(replay.stderr).toContain("output hash is invalid");
  });

  it("runner returns command failure and writes rejection with log paths", () => {
    const workerRecords = [
      {
        type: "task_card",
        id: "tc-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-runner-fail",
        role: "runner",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["**"],
        forbidden_files: [],
        heartbeat_interval: "1s",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
    ];
    fs.writeFileSync(
      path.join(taskDir, "hermes", "worker_records.jsonl"),
      workerRecords.map((record) => JSON.stringify(record)).join("\n") + "\n",
    );
    writeExperimentConfig(taskDir);

    const run = runHermes(tmpDir, "runner.py", [
      "run",
      "--task",
      "01-test",
      "--job-id",
      "job-runner-fail",
      "--checkpoint",
      "command-started",
      "--summary",
      "run failing command",
      "--resume-from",
      "inspect stderr and retry",
      "--",
      "python3",
      "-c",
      "import sys; print('boom', file=sys.stderr); sys.exit(7)",
    ]);

    expect(run.status).toBe(7);

    const manifestRows = fs
      .readFileSync(path.join(taskDir, "hermes", "run_manifest.jsonl"), "utf-8")
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line) as Record<string, unknown>);
    expect(manifestRows[0]).toMatchObject({
      job_id: "job-runner-fail",
      exit_code: 7,
    });

    const workerRows = fs
      .readFileSync(
        path.join(taskDir, "hermes", "worker_records.jsonl"),
        "utf-8",
      )
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line) as Record<string, unknown>);
    expect(workerRows.find((record) => record.type === "rejection")).toMatchObject({
      job_id: "job-runner-fail",
      reason: "runner_command_failed",
    });
    expect(JSON.stringify(workerRows)).toContain("stderr.log");
  });

  it("runner records launch failures without losing logs", () => {
    const workerRecords = [
      {
        type: "task_card",
        id: "tc-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-runner-missing-command",
        role: "runner",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["**"],
        forbidden_files: [],
        heartbeat_interval: "1s",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
    ];
    fs.writeFileSync(
      path.join(taskDir, "hermes", "worker_records.jsonl"),
      workerRecords.map((record) => JSON.stringify(record)).join("\n") + "\n",
    );
    writeExperimentConfigWithAllowedCommands(taskDir, [
      "missing-hermes-command-for-test",
    ]);

    const run = runHermes(tmpDir, "runner.py", [
      "run",
      "--task",
      "01-test",
      "--job-id",
      "job-runner-missing-command",
      "--checkpoint",
      "command-started",
      "--summary",
      "run missing command",
      "--resume-from",
      "install command or fix PATH",
      "--",
      "missing-hermes-command-for-test",
    ]);

    expect(run.status).toBe(127);

    const manifestRows = fs
      .readFileSync(path.join(taskDir, "hermes", "run_manifest.jsonl"), "utf-8")
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line) as Record<string, unknown>);
    expect(manifestRows[0]).toMatchObject({
      job_id: "job-runner-missing-command",
      exit_code: 127,
    });

    const workerRows = fs
      .readFileSync(
        path.join(taskDir, "hermes", "worker_records.jsonl"),
        "utf-8",
      )
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line) as Record<string, unknown>);
    expect(workerRows.find((record) => record.type === "rejection")).toMatchObject({
      job_id: "job-runner-missing-command",
      reason: "runner_command_failed",
    });

    const stderrOutput = fs.readFileSync(
      path.join(
        tmpDir,
        String((manifestRows[0].outputs as { path: string }[]).find((entry) =>
          entry.path.endsWith("stderr.log"),
        )?.path),
      ),
      "utf-8",
    );
    expect(stderrOutput).toContain("cannot start command");
  });

  it("jobs resume reports the latest checkpoint resume point", () => {
    const workerRecords = [
      {
        type: "task_card",
        id: "tc-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-resume",
        role: "coder",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
      {
        type: "checkpoint",
        id: "cp-20260629-000100-demo",
        timestamp: "2026-06-29T00:01:00Z",
        job_id: "job-resume",
        checkpoint: "files-read",
        resume_from: "continue after reading files",
        evidence_refs: [],
        open_items: [],
      },
      {
        type: "checkpoint",
        id: "cp-20260629-000200-demo",
        timestamp: "2026-06-29T00:02:00Z",
        job_id: "job-resume",
        checkpoint: "tests-added",
        resume_from: "rerun targeted tests",
        evidence_refs: [],
        open_items: ["finish implementation"],
      },
    ];
    fs.writeFileSync(
      path.join(taskDir, "hermes", "worker_records.jsonl"),
      workerRecords.map((record) => JSON.stringify(record)).join("\n") + "\n",
    );

    const resume = runHermes(tmpDir, "jobs.py", [
      "resume",
      "--task",
      "01-test",
      "--job-id",
      "job-resume",
    ]);

    expect(resume.status).toBe(0);
    expect(JSON.parse(resume.stdout)).toMatchObject({
      job_id: "job-resume",
      checkpoint: "tests-added",
      resume_from: "rerun targeted tests",
      source: "checkpoint",
    });
  });

  it("jobs check appends stalled records with the latest resume point", () => {
    const workerRecords = [
      {
        type: "task_card",
        id: "tc-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-stalled",
        role: "coder",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2026-06-29T00:10:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: ".trellis/tasks/01-test/hermes/worker_records.jsonl",
        evidence_refs: [],
        risk_flags: [],
      },
      {
        type: "checkpoint",
        id: "cp-20260629-000500-demo",
        timestamp: "2026-06-29T00:05:00Z",
        job_id: "job-stalled",
        checkpoint: "tests-running",
        resume_from: "rerun tests from checkpoint",
        evidence_refs: [],
        open_items: [],
      },
    ];
    fs.writeFileSync(
      path.join(taskDir, "hermes", "worker_records.jsonl"),
      workerRecords.map((record) => JSON.stringify(record)).join("\n") + "\n",
    );

    const check = runHermes(tmpDir, "jobs.py", [
      "check",
      "--task",
      "01-test",
      "--now",
      "2026-06-29T00:11:00Z",
    ]);

    expect(check.status).toBe(1);

    const workerRows = fs
      .readFileSync(
        path.join(taskDir, "hermes", "worker_records.jsonl"),
        "utf-8",
      )
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line) as Record<string, unknown>);
    expect(workerRows.find((record) => record.type === "stalled")).toMatchObject({
      job_id: "job-stalled",
      reason: "timeout",
      checkpoint: "tests-running",
      resume_from: "rerun tests from checkpoint",
    });
  });

  it("validate rejects run manifests with missing output paths", () => {
    fs.writeFileSync(
      path.join(taskDir, "hermes", "run_manifest.jsonl"),
      `${JSON.stringify({
        id: "run-20260629-000000-demo",
        job_id: "job-manifest",
        command: ["python3", "-c", "print('ok')"],
        cwd: ".",
        env_summary: { python: "3.x" },
        inputs: [],
        outputs: [{ path: "missing-output.txt", kind: "artifact" }],
        exit_code: 0,
        started_at: "2026-06-29T00:00:00Z",
        finished_at: "2026-06-29T00:00:01Z",
      })}\n`,
    );

    const validateManifest = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "run_manifest",
    ]);

    expect(validateManifest.status).toBe(1);
    expect(validateManifest.stderr).toContain("output path is not readable");
  });

  it("aggregates run manifests with failures, durations, outputs, and metric variance", () => {
    fs.writeFileSync(path.join(tmpDir, "run-a.txt"), "a", "utf-8");
    fs.writeFileSync(path.join(tmpDir, "run-b.txt"), "b", "utf-8");
    writeJsonl(path.join(taskDir, "hermes", "run_manifest.jsonl"), [
      {
        id: "run-a",
        job_id: "job-a",
        command: ["python3", "-c", "print('a')"],
        cwd: ".",
        env_summary: { python: "3.x" },
        inputs: [],
        outputs: [
          { path: "run-a.txt", kind: "artifact", hash: "sha256:aaa" },
        ],
        exit_code: 0,
        started_at: "2026-06-29T00:00:00Z",
        finished_at: "2026-06-29T00:00:02Z",
        metrics: { accuracy: 0.8, loss: 0.4 },
      },
      {
        id: "run-b",
        job_id: "job-b",
        command: ["python3", "-c", "print('b')"],
        cwd: ".",
        env_summary: { python: "3.x" },
        inputs: [],
        outputs: [
          { path: "run-b.txt", kind: "artifact", hash: "sha256:bbb" },
        ],
        exit_code: 1,
        started_at: "2026-06-29T00:00:00Z",
        finished_at: "2026-06-29T00:00:04Z",
        error: "measurement failed",
        metrics: { accuracy: 0.6, loss: 0.7 },
      },
    ]);

    const aggregate = runHermes(tmpDir, "report.py", [
      "aggregate",
      "--task",
      "01-test",
      "--output",
      ".trellis/tasks/01-test/hermes/aggregate.json",
    ]);

    expect(aggregate.status).toBe(0);
    expect(aggregate.stdout).toContain("aggregate written");

    interface AggregateReport {
      run_count: number;
      failure_count: number;
      exceptions: { run_id: string; error: string }[];
      duration_seconds: { mean: number; variance: number };
      outputs_count: { mean: number };
      metrics: {
        accuracy: { mean: number; variance: number };
      };
      output_hashes: string[];
    }

    const result = JSON.parse(
      fs.readFileSync(
        path.join(taskDir, "hermes", "aggregate.json"),
        "utf-8",
      ),
    ) as AggregateReport;
    expect(result.run_count).toBe(2);
    expect(result.failure_count).toBe(1);
    expect(result.exceptions).toEqual([
      { run_id: "run-b", error: "measurement failed" },
    ]);
    expect(result.duration_seconds.mean).toBe(3);
    expect(result.duration_seconds.variance).toBe(1);
    expect(result.outputs_count.mean).toBe(1);
    expect(result.metrics.accuracy.mean).toBe(0.7);
    expect(result.metrics.accuracy.variance).toBeCloseTo(0.01);
    expect(result.output_hashes).toEqual(["sha256:aaa", "sha256:bbb"]);
  });

  it("report aggregate rejects output paths outside task Hermes directory", () => {
    fs.writeFileSync(path.join(taskDir, "hermes", "run_manifest.jsonl"), "", "utf-8");

    const aggregate = runHermes(tmpDir, "report.py", [
      "aggregate",
      "--task",
      "01-test",
      "--output",
      "../aggregate.json",
    ]);

    expect(aggregate.status).toBe(2);
    expect(aggregate.stderr).toContain("output must stay inside task Hermes directory");
  });

  it("compares baseline and new metrics and validates compare records", () => {
    const compare = runHermes(tmpDir, "report.py", [
      "compare",
      "--task",
      "01-test",
      "--metric",
      "accuracy",
      "--baseline",
      "0.70",
      "--new",
      "0.76",
      "--threshold",
      "0.05",
      "--direction",
      "higher_is_better",
      "--evidence-ref",
      "ev-20260629-000000-demo",
      "--claim-ref",
      "cl-20260629-000000-demo",
    ]);

    expect(compare.status).toBe(0);
    const stdout = JSON.parse(compare.stdout) as Record<string, unknown>;
    expect(stdout.passed).toBe(true);

    const records = fs
      .readFileSync(path.join(taskDir, "hermes", "compare.jsonl"), "utf-8")
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line) as Record<string, unknown>);
    expect(records).toHaveLength(1);
    expect(records[0]).toMatchObject({
      type: "compare",
      metric: "accuracy",
      direction: "higher_is_better",
      threshold: 0.05,
      baseline: 0.7,
      new: 0.76,
      passed: true,
      evidence_refs: ["ev-20260629-000000-demo"],
      claim_refs: ["cl-20260629-000000-demo"],
      conclusion_state: "claim_ready",
    });

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "compare",
    ]);
    expect(validate.status).toBe(0);
  });

  it("validates provenance ledger records with dataset, model, code, env, and artifact refs", () => {
    writeJsonl(path.join(taskDir, "hermes", "provenance_ledger.jsonl"), [
      {
        type: "provenance",
        id: "pv-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        dataset: { ref: "dataset-fixture", hash: "sha256:aaa", source: "unit" },
        model: { ref: "model-fixture", version: "1.0.0", source: "unit" },
        code: { ref: "git:abc123", hash: "sha256:bbb", source: "repo" },
        env: { ref: "ubuntu-24.04", version: "python-3", source: "runner" },
        artifact: { ref: "ar-20260629-000000-demo", hash: "sha256:ccc", source: "artifact_ledger" },
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "provenance",
    ]);

    expect(validate.status).toBe(0);
    expect(validate.stdout).toContain("valid");
  });

  it("rejects provenance records missing required refs", () => {
    writeJsonl(path.join(taskDir, "hermes", "provenance_ledger.jsonl"), [
      {
        type: "provenance",
        id: "pv-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        dataset: { ref: "dataset-fixture" },
        model: { version: "1.0.0" },
        code: { ref: "git:abc123" },
        env: { ref: "ubuntu-24.04" },
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "provenance",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("model.ref is required");
    expect(validate.stderr).toContain("artifact must be a mapping");
  });

  it("validates audit security records", () => {
    writeJsonl(path.join(taskDir, "hermes", "audit_ledger.jsonl"), [
      {
        type: "audit",
        id: "au-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        event: "security_gate",
        actor: "runner.py",
        boundary: "allowed_commands",
        decision: "blocked",
        summary: "command rejected by allowed_commands",
      },
      {
        type: "audit",
        id: "au-20260629-000100-demo",
        timestamp: "2026-06-29T00:01:00Z",
        event: "secret_redaction",
        actor: "runner.py",
        boundary: "run_manifest",
        decision: "redacted",
        summary: "secret env name redacted",
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "audit",
    ]);

    expect(validate.status).toBe(0);
  });

  it("rejects audit records without a supported security event", () => {
    writeJsonl(path.join(taskDir, "hermes", "audit_ledger.jsonl"), [
      {
        type: "audit",
        id: "au-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        event: "chat_note",
        actor: "runner.py",
        boundary: "allowed_commands",
        decision: "blocked",
        summary: "not a security audit event",
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "audit",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("audit event must be one of");
  });

  it("service queue supports enqueue, status, and cancel", () => {
    const enqueue = runHermes(tmpDir, "service.py", [
      "enqueue",
      "--task",
      "01-test",
      "--job-id",
      "svc-job",
      "--command",
      "python3 -m pytest",
    ]);
    expect(enqueue.status).toBe(0);
    expect(JSON.parse(enqueue.stdout)).toMatchObject({
      status: "queued",
      job_id: "svc-job",
    });

    const statusBeforeCancel = runHermes(tmpDir, "service.py", [
      "status",
      "--task",
      "01-test",
    ]);
    expect(statusBeforeCancel.status).toBe(0);
    expect(JSON.parse(statusBeforeCancel.stdout).jobs).toEqual([
      expect.objectContaining({ job_id: "svc-job", status: "queued" }),
    ]);

    const cancel = runHermes(tmpDir, "service.py", [
      "cancel",
      "--task",
      "01-test",
      "--job-id",
      "svc-job",
      "--reason",
      "no longer needed",
    ]);
    expect(cancel.status).toBe(0);
    expect(JSON.parse(cancel.stdout)).toMatchObject({
      status: "cancelled",
      job_id: "svc-job",
    });

    const rows = fs
      .readFileSync(path.join(taskDir, "hermes", "service_queue.jsonl"), "utf-8")
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line) as Record<string, unknown>);
    expect(rows.map((row) => row.type)).toEqual(["service_enqueue", "service_cancel"]);
  });

  it("service queue rejects enqueue when max_active would be exceeded", () => {
    const first = runHermes(tmpDir, "service.py", [
      "enqueue",
      "--task",
      "01-test",
      "--job-id",
      "svc-active-one",
      "--command",
      "python3 -m pytest",
      "--max-active",
      "1",
    ]);
    expect(first.status).toBe(0);

    const second = runHermes(tmpDir, "service.py", [
      "enqueue",
      "--task",
      "01-test",
      "--job-id",
      "svc-active-two",
      "--command",
      "python3 -m pytest",
      "--max-active",
      "1",
    ]);
    expect(second.status).toBe(1);
    expect(second.stderr).toContain("max_active exceeded");
  });

  it("quality gate fails failed compare records and missing evidence", () => {
    writeJsonl(path.join(taskDir, "hermes", "compare.jsonl"), [
      {
        type: "compare",
        id: "cmp-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        metric: "accuracy",
        direction: "higher_is_better",
        threshold: 0.05,
        baseline: 0.7,
        new: 0.71,
        delta: 0.01,
        passed: false,
        evidence_refs: [],
        claim_refs: ["cl-20260629-000000-demo"],
        conclusion_state: "claim_ready",
      },
    ]);

    const gate = runHermes(tmpDir, "report.py", [
      "quality-gate",
      "--task",
      "01-test",
    ]);

    expect(gate.status).toBe(1);
    expect(gate.stderr).toContain("compare cmp-20260629-000000-demo failed");
    expect(gate.stderr).toContain("missing evidence_refs");
  });

  it("quality gate passes compare records with evidence and statistic fields", () => {
    writeQualityGateLedgers();
    writeJsonl(path.join(taskDir, "hermes", "compare.jsonl"), [
      {
        type: "compare",
        id: "cmp-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        metric: "accuracy",
        direction: "higher_is_better",
        threshold: 0.05,
        baseline: 0.7,
        new: 0.76,
        delta: 0.06,
        passed: true,
        evidence_refs: ["ev-20260629-000000-demo"],
        claim_refs: ["cl-20260629-000000-demo"],
        conclusion_state: "claim_ready",
        sample_count: 12,
        variance: 0.01,
      },
    ]);

    const gate = runHermes(tmpDir, "report.py", [
      "quality-gate",
      "--task",
      "01-test",
    ]);

    expect(gate.status).toBe(0);
    expect(JSON.parse(gate.stdout)).toMatchObject({
      status: "passed",
      compare_count: 1,
    });
  });

  it.each([
    {
      field: "evidence_refs",
      missingId: "ev-20260629-000001-missing",
      expected: "references missing evidence_id ev-20260629-000001-missing",
    },
    {
      field: "claim_refs",
      missingId: "cl-20260629-000001-missing",
      expected: "references missing claim_id cl-20260629-000001-missing",
    },
  ])("quality gate rejects a missing ledger id in $field", ({ field, missingId, expected }) => {
    writeQualityGateLedgers();
    const compare: Record<string, unknown> = {
      type: "compare",
      id: "cmp-20260629-000001-missing-ref",
      timestamp: "2026-06-29T00:00:02Z",
      metric: "accuracy",
      direction: "higher_is_better",
      threshold: 0.05,
      baseline: 0.7,
      new: 0.76,
      delta: 0.06,
      passed: true,
      evidence_refs: ["ev-20260629-000000-demo"],
      claim_refs: ["cl-20260629-000000-demo"],
      conclusion_state: "claim_ready",
      sample_count: 12,
    };
    compare[field] = [missingId];
    writeJsonl(path.join(taskDir, "hermes", "compare.jsonl"), [compare]);

    const gate = runHermes(tmpDir, "report.py", [
      "quality-gate",
      "--task",
      "01-test",
    ]);

    expect(gate.status).toBe(1);
    expect(gate.stderr).toContain(expected);
  });

  it("rejects metric split baseline changes without HumanGate approval", () => {
    fs.writeFileSync(
      path.join(taskDir, "hermes", "metrics_schema.yaml"),
      [
        "metrics:",
        '  - name: "accuracy"',
        '    direction: "higher_is_better"',
        '    unit: "ratio"',
        '    aggregation: "mean"',
        '    split: "validation"',
        '    baseline: "0.70"',
        "change_records:",
        '  - id: "chg-20260629-000000-metric"',
        '    field: "metric"',
        '    summary: "rename primary metric"',
        '  - id: "chg-20260629-000100-split"',
        '    field: "split"',
        '    summary: "switch evaluation split"',
        '  - id: "chg-20260629-000200-baseline"',
        '    field: "baseline"',
        '    summary: "raise baseline"',
        "",
      ].join("\n"),
      "utf-8",
    );

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "metrics_schema",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("HumanGate approval required");
  });

  it("rejects metric split baseline changes with only HumanGate evidence text", () => {
    fs.writeFileSync(
      path.join(taskDir, "hermes", "metrics_schema.yaml"),
      [
        "metrics:",
        '  - name: "accuracy"',
        '    direction: "higher_is_better"',
        '    unit: "ratio"',
        '    aggregation: "mean"',
        '    split: "validation"',
        '    baseline: "0.70"',
        "change_records:",
        '  - id: "chg-20260629-000000-baseline"',
        '    field: "baseline"',
        '    summary: "raise baseline"',
        "",
      ].join("\n"),
      "utf-8",
    );
    writeJsonl(path.join(taskDir, "hermes", "evidence_ledger.jsonl"), [
      {
        type: "evidence",
        id: "ev-20260629-000000-human-gate",
        timestamp: "2026-06-29T00:00:00Z",
        source: "HumanGate",
        summary:
          "HumanGate approved chg-20260629-000000-baseline by human/root",
        limits: "evidence text must not replace approval_records",
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "metrics_schema",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("HumanGate approval required");
  });

  it("rejects metric split baseline changes when approval omits change id and evidence text contains it", () => {
    fs.writeFileSync(
      path.join(taskDir, "hermes", "metrics_schema.yaml"),
      [
        "metrics:",
        '  - name: "accuracy"',
        '    direction: "higher_is_better"',
        '    unit: "ratio"',
        '    aggregation: "mean"',
        '    split: "validation"',
        '    baseline: "0.70"',
        "change_records:",
        '  - id: "chg-20260629-000000-baseline"',
        '    field: "baseline"',
        '    summary: "raise baseline"',
        "",
      ].join("\n"),
      "utf-8",
    );
    writeJsonl(path.join(taskDir, "hermes", "evidence_ledger.jsonl"), [
      {
        type: "evidence",
        id: "ev-20260629-000000-human-gate",
        timestamp: "2026-06-29T00:00:00Z",
        source: "HumanGate",
        summary:
          "HumanGate approved chg-20260629-000000-baseline by human/root",
        limits: "evidence text must not replace structured approval change ids",
      },
    ]);
    writeJsonl(path.join(taskDir, "hermes", "claim_ledger.jsonl"), [
      {
        type: "claim",
        id: "cl-20260629-000000-human-gate",
        timestamp: "2026-06-29T00:00:00Z",
        text: "HumanGate approval references evidence for the metric schema baseline change",
        evidence_ids: ["ev-20260629-000000-human-gate"],
        scope: "metrics_schema_change",
        limits: "task scoped",
        state: "claim_ready",
      },
    ]);
    writeJsonl(path.join(taskDir, "hermes", "approval_records.jsonl"), [
      {
        type: "human_approval",
        id: "ap-20260629-000000-human-gate",
        timestamp: "2026-06-29T00:01:00Z",
        claim_id: "cl-20260629-000000-human-gate",
        approver: "human/root",
        decision: "approved",
        notes: "approved metric schema baseline change",
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "metrics_schema",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("HumanGate approval required");
  });

  it("accepts metric split baseline changes with human root approval", () => {
    fs.writeFileSync(
      path.join(taskDir, "hermes", "metrics_schema.yaml"),
      [
        "metrics:",
        '  - name: "accuracy"',
        '    direction: "higher_is_better"',
        '    unit: "ratio"',
        '    aggregation: "mean"',
        '    split: "validation"',
        '    baseline: "0.70"',
        "change_records:",
        '  - id: "chg-20260629-000000-baseline"',
        '    field: "baseline"',
        '    summary: "raise baseline"',
        "",
      ].join("\n"),
      "utf-8",
    );
    writeJsonl(path.join(taskDir, "hermes", "evidence_ledger.jsonl"), [
      {
        type: "evidence",
        id: "ev-20260629-000000-human-gate",
        timestamp: "2026-06-29T00:00:00Z",
        source: "HumanGate",
        summary: "human reviewed baseline change",
        limits: "approval evidence only",
      },
    ]);
    writeJsonl(path.join(taskDir, "hermes", "claim_ledger.jsonl"), [
      {
        type: "claim",
        id: "cl-20260629-000000-human-gate",
        timestamp: "2026-06-29T00:00:00Z",
        text: "HumanGate approves metric schema baseline change chg-20260629-000000-baseline",
        evidence_ids: ["ev-20260629-000000-human-gate"],
        scope: "metrics_schema_change",
        limits: "task scoped",
        state: "claim_ready",
      },
    ]);
    writeJsonl(path.join(taskDir, "hermes", "approval_records.jsonl"), [
      {
        type: "human_approval",
        id: "ap-20260629-000000-human-gate",
        timestamp: "2026-06-29T00:01:00Z",
        claim_id: "cl-20260629-000000-human-gate",
        approver: "human/root",
        decision: "approved",
        notes: "approve metric schema baseline change",
        change_id: "chg-20260629-000000-baseline",
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "metrics_schema",
    ]);

    expect(validate.status).toBe(0);
    expect(validate.stdout).toContain("valid");
  });

  it("rejects metric split baseline approval records when decision is not approved", () => {
    fs.writeFileSync(
      path.join(taskDir, "hermes", "metrics_schema.yaml"),
      [
        "metrics:",
        '  - name: "accuracy"',
        '    direction: "higher_is_better"',
        '    unit: "ratio"',
        '    aggregation: "mean"',
        '    split: "validation"',
        '    baseline: "0.70"',
        "change_records:",
        '  - id: "chg-20260629-000000-baseline"',
        '    field: "baseline"',
        '    summary: "raise baseline"',
        "",
      ].join("\n"),
      "utf-8",
    );
    writeJsonl(path.join(taskDir, "hermes", "evidence_ledger.jsonl"), [
      {
        type: "evidence",
        id: "ev-20260629-000000-human-gate",
        timestamp: "2026-06-29T00:00:00Z",
        source: "HumanGate",
        summary:
          "HumanGate approved chg-20260629-000000-baseline by human/root",
        limits: "evidence text must not replace an approved decision",
      },
    ]);
    writeJsonl(path.join(taskDir, "hermes", "claim_ledger.jsonl"), [
      {
        type: "claim",
        id: "cl-20260629-000000-human-gate",
        timestamp: "2026-06-29T00:00:00Z",
        text: "metric schema baseline change chg-20260629-000000-baseline",
        evidence_ids: ["ev-20260629-000000-human-gate"],
        scope: "metrics_schema_change",
        limits: "task scoped",
        state: "claim_ready",
      },
    ]);
    writeJsonl(path.join(taskDir, "hermes", "approval_records.jsonl"), [
      {
        type: "human_approval",
        id: "ap-20260629-000000-human-gate",
        timestamp: "2026-06-29T00:01:00Z",
        claim_id: "cl-20260629-000000-human-gate",
        approver: "human/root",
        decision: "needs_changes",
        notes: "not approved chg-20260629-000000-baseline",
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "metrics_schema",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("HumanGate approval required");
  });

  it("rejects metric split baseline approval records when approver is not human root", () => {
    fs.writeFileSync(
      path.join(taskDir, "hermes", "metrics_schema.yaml"),
      [
        "metrics:",
        '  - name: "accuracy"',
        '    direction: "higher_is_better"',
        '    unit: "ratio"',
        '    aggregation: "mean"',
        '    split: "validation"',
        '    baseline: "0.70"',
        "change_records:",
        '  - id: "chg-20260629-000000-baseline"',
        '    field: "baseline"',
        '    summary: "raise baseline"',
        "",
      ].join("\n"),
      "utf-8",
    );
    writeJsonl(path.join(taskDir, "hermes", "evidence_ledger.jsonl"), [
      {
        type: "evidence",
        id: "ev-20260629-000000-human-gate",
        timestamp: "2026-06-29T00:00:00Z",
        source: "HumanGate",
        summary:
          "HumanGate approved chg-20260629-000000-baseline by human/root",
        limits: "evidence text must not replace human/root approver",
      },
    ]);
    writeJsonl(path.join(taskDir, "hermes", "claim_ledger.jsonl"), [
      {
        type: "claim",
        id: "cl-20260629-000000-human-gate",
        timestamp: "2026-06-29T00:00:00Z",
        text: "metric schema baseline change chg-20260629-000000-baseline",
        evidence_ids: ["ev-20260629-000000-human-gate"],
        scope: "metrics_schema_change",
        limits: "task scoped",
        state: "claim_ready",
      },
    ]);
    writeJsonl(path.join(taskDir, "hermes", "approval_records.jsonl"), [
      {
        type: "human_approval",
        id: "ap-20260629-000000-human-gate",
        timestamp: "2026-06-29T00:01:00Z",
        claim_id: "cl-20260629-000000-human-gate",
        approver: "agent/reviewer",
        decision: "approved",
        notes: "approve chg-20260629-000000-baseline",
      },
    ]);

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "metrics_schema",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("HumanGate approval required");
  });

  it("reviews claim support without writing human approval", () => {
    writeJsonl(path.join(taskDir, "hermes", "evidence_ledger.jsonl"), [
      {
        type: "evidence",
        id: "ev-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        source: "test output",
        summary: "accuracy improved",
        limits: "unit fixture only",
      },
    ]);
    writeJsonl(path.join(taskDir, "hermes", "claim_ledger.jsonl"), [
      {
        type: "claim",
        id: "cl-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        text: "new method improves accuracy",
        evidence_ids: ["ev-20260629-000000-demo"],
        scope: "unit fixture",
        limits: "not a full benchmark",
        state: "claim_ready",
      },
    ]);

    const review = runHermes(tmpDir, "report.py", [
      "claim-review",
      "--task",
      "01-test",
      "--claim-id",
      "cl-20260629-000000-demo",
    ]);

    expect(review.status).toBe(0);
    interface ClaimReviewResult {
      supported: boolean;
      claims: {
        claim_id: string;
        supported: boolean;
        evidence_ids: string[];
      }[];
    }

    const result = JSON.parse(review.stdout) as ClaimReviewResult;
    expect(result.supported).toBe(true);
    expect(result.claims[0]).toMatchObject({
      claim_id: "cl-20260629-000000-demo",
      supported: true,
      evidence_ids: ["ev-20260629-000000-demo"],
    });
    expect(
      fs.existsSync(path.join(taskDir, "hermes", "approval_records.jsonl")),
    ).toBe(false);
  });

  it("approval-gate fails without a matching human root approval", () => {
    writeJsonl(path.join(taskDir, "hermes", "evidence_ledger.jsonl"), [
      {
        type: "evidence",
        id: "ev-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        source: "test output",
        summary: "accuracy improved",
        limits: "unit fixture only",
      },
    ]);
    writeJsonl(path.join(taskDir, "hermes", "claim_ledger.jsonl"), [
      {
        type: "claim",
        id: "cl-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        text: "new method improves accuracy",
        evidence_ids: ["ev-20260629-000000-demo"],
        scope: "unit fixture",
        limits: "not a full benchmark",
        state: "claim_ready",
      },
    ]);

    const gate = runHermes(tmpDir, "report.py", [
      "approval-gate",
      "--task",
      "01-test",
      "--claim-id",
      "cl-20260629-000000-demo",
    ]);

    expect(gate.status).toBe(1);
    expect(gate.stderr).toContain("human/root approval");
  });

  it("approval-gate fails when approval belongs to a different claim", () => {
    writeJsonl(path.join(taskDir, "hermes", "evidence_ledger.jsonl"), [
      {
        type: "evidence",
        id: "ev-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        source: "test output",
        summary: "accuracy improved",
        limits: "unit fixture only",
      },
    ]);
    writeJsonl(path.join(taskDir, "hermes", "claim_ledger.jsonl"), [
      {
        type: "claim",
        id: "cl-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        text: "new method improves accuracy",
        evidence_ids: ["ev-20260629-000000-demo"],
        scope: "unit fixture",
        limits: "not a full benchmark",
        state: "claim_ready",
      },
      {
        type: "claim",
        id: "cl-20260629-000000-other",
        timestamp: "2026-06-29T00:02:00Z",
        text: "other claim",
        evidence_ids: ["ev-20260629-000000-demo"],
        scope: "unit fixture",
        limits: "not a full benchmark",
        state: "claim_ready",
      },
    ]);
    writeJsonl(path.join(taskDir, "hermes", "approval_records.jsonl"), [
      {
        type: "human_approval",
        id: "ap-20260629-000000-other",
        timestamp: "2026-06-29T00:03:00Z",
        claim_id: "cl-20260629-000000-other",
        approver: "human/root",
        decision: "approved",
        notes: "approve different claim",
      },
    ]);

    const gate = runHermes(tmpDir, "report.py", [
      "approval-gate",
      "--task",
      "01-test",
      "--claim-id",
      "cl-20260629-000000-demo",
    ]);

    expect(gate.status).toBe(1);
    expect(gate.stderr).toContain("human/root approval");
  });

  it("approval-gate accepts an existing human root approved claim", () => {
    writeJsonl(path.join(taskDir, "hermes", "evidence_ledger.jsonl"), [
      {
        type: "evidence",
        id: "ev-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        source: "test output",
        summary: "accuracy improved",
        limits: "unit fixture only",
      },
    ]);
    writeJsonl(path.join(taskDir, "hermes", "claim_ledger.jsonl"), [
      {
        type: "claim",
        id: "cl-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        text: "new method improves accuracy",
        evidence_ids: ["ev-20260629-000000-demo"],
        scope: "unit fixture",
        limits: "not a full benchmark",
        state: "claim_ready",
      },
    ]);
    writeJsonl(path.join(taskDir, "hermes", "approval_records.jsonl"), [
      {
        type: "human_approval",
        id: "ap-20260629-000000-demo",
        timestamp: "2026-06-29T00:01:00Z",
        claim_id: "cl-20260629-000000-demo",
        approver: "human/root",
        decision: "approved",
        notes: "approve",
      },
    ]);

    const gate = runHermes(tmpDir, "report.py", [
      "approval-gate",
      "--task",
      "01-test",
      "--claim-id",
      "cl-20260629-000000-demo",
    ]);

    expect(gate.status).toBe(0);
    expect(JSON.parse(gate.stdout)).toEqual({
      status: "approved",
      claim_id: "cl-20260629-000000-demo",
    });
  });

  it("generates a claim-ready report with claim and evidence back links", () => {
    writeJsonl(path.join(taskDir, "hermes", "evidence_ledger.jsonl"), [
      {
        type: "evidence",
        id: "ev-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        source: "compare.jsonl",
        summary: "accuracy improved by 0.06",
        limits: "unit fixture only",
      },
    ]);
    writeJsonl(path.join(taskDir, "hermes", "claim_ledger.jsonl"), [
      {
        type: "claim",
        id: "cl-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        text: "new method improves accuracy over baseline",
        evidence_ids: ["ev-20260629-000000-demo"],
        scope: "unit fixture",
        limits: "not a full benchmark",
        state: "claim_ready",
      },
    ]);
    writeJsonl(path.join(taskDir, "hermes", "compare.jsonl"), [
      {
        type: "compare",
        id: "cmp-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        metric: "accuracy",
        direction: "higher_is_better",
        threshold: 0.05,
        baseline: 0.7,
        new: 0.76,
        delta: 0.06,
        passed: true,
        evidence_refs: ["ev-20260629-000000-demo"],
        claim_refs: ["cl-20260629-000000-demo"],
        conclusion_state: "claim_ready",
      },
    ]);

    const report = runHermes(tmpDir, "report.py", [
      "report",
      "--task",
      "01-test",
      "--question",
      "Does the new method improve accuracy?",
      "--method",
      "Compare a baseline and candidate metric.",
      "--data",
      "Unit fixture records.",
      "--metrics",
      "accuracy",
      "--limitations",
      "Unit fixture only.",
      "--risks",
      "Human approval remains required.",
    ]);

    expect(report.status).toBe(0);
    expect(report.stdout).toContain("report written");

    const content = fs.readFileSync(
      path.join(taskDir, "hermes", "report.md"),
      "utf-8",
    );
    for (const heading of [
      "## Problem",
      "## Method",
      "## Data",
      "## Metrics",
      "## Results",
      "## Core Conclusions",
      "## Limitations",
      "## Risks",
      "## Conclusion Status",
    ]) {
      expect(content).toContain(heading);
    }
    expect(content).toContain("cl-20260629-000000-demo");
    expect(content).toContain("ev-20260629-000000-demo");
    expect(content).toContain("cmp-20260629-000000-demo");
    expect(content).toContain("claim_ready");
    expect(content).toContain("human/root approval required");
  });

  it("report command rejects absolute output paths outside task Hermes directory", () => {
    writeJsonl(path.join(taskDir, "hermes", "evidence_ledger.jsonl"), [
      {
        type: "evidence",
        id: "ev-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        source: "compare.jsonl",
        summary: "accuracy improved by 0.06",
        limits: "unit fixture only",
      },
    ]);
    writeJsonl(path.join(taskDir, "hermes", "claim_ledger.jsonl"), [
      {
        type: "claim",
        id: "cl-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        text: "new method improves accuracy over baseline",
        evidence_ids: ["ev-20260629-000000-demo"],
        scope: "unit fixture",
        limits: "not a full benchmark",
        state: "claim_ready",
      },
    ]);

    const report = runHermes(tmpDir, "report.py", [
      "report",
      "--task",
      "01-test",
      "--question",
      "Does the new method improve accuracy?",
      "--method",
      "Compare a baseline and candidate metric.",
      "--data",
      "Unit fixture records.",
      "--metrics",
      "accuracy",
      "--limitations",
      "Unit fixture only.",
      "--risks",
      "Human approval remains required.",
      "--output",
      path.join(os.tmpdir(), "trellis-report-escape.md"),
    ]);

    expect(report.status).toBe(2);
    expect(report.stderr).toContain("output must stay inside task Hermes directory");
  });

  it("rejects claim_ready records without evidence ids", () => {
    fs.writeFileSync(
      path.join(taskDir, "hermes", "claim_ledger.jsonl"),
      `${JSON.stringify({
        type: "claim",
        id: "cl-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        text: "implementation is complete",
        evidence_ids: [],
        scope: "runtime",
        limits: "unit test only",
        state: "claim_ready",
      })}\n`,
    );

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "claim",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("claim_ready requires evidence_ids");
  });

  it("rejects approval records for claims that are not claim_ready", () => {
    fs.writeFileSync(
      path.join(taskDir, "hermes", "claim_ledger.jsonl"),
      `${JSON.stringify({
        type: "claim",
        id: "cl-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        text: "implementation is complete",
        evidence_ids: ["ev-20260629-000000-demo"],
        scope: "runtime",
        limits: "unit test only",
        state: "draft",
      })}\n`,
    );
    fs.writeFileSync(
      path.join(taskDir, "hermes", "approval_records.jsonl"),
      `${JSON.stringify({
        type: "human_approval",
        id: "ap-20260629-000000-demo",
        timestamp: "2026-06-29T00:01:00Z",
        claim_id: "cl-20260629-000000-demo",
        approver: "human/root",
        decision: "approved",
        notes: "approve",
      })}\n`,
    );

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "approval",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("approval requires claim_ready");
  });

  it("rejects approval records without human root approval decision", () => {
    fs.writeFileSync(
      path.join(taskDir, "hermes", "evidence_ledger.jsonl"),
      `${JSON.stringify({
        type: "evidence",
        id: "ev-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        source: "test output",
        summary: "tests passed",
        limits: "unit test only",
      })}\n`,
    );
    fs.writeFileSync(
      path.join(taskDir, "hermes", "claim_ledger.jsonl"),
      `${JSON.stringify({
        type: "claim",
        id: "cl-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        text: "implementation is complete",
        evidence_ids: ["ev-20260629-000000-demo"],
        scope: "runtime",
        limits: "unit test only",
        state: "claim_ready",
      })}\n`,
    );
    fs.writeFileSync(
      path.join(taskDir, "hermes", "approval_records.jsonl"),
      `${JSON.stringify({
        type: "human_approval",
        id: "ap-20260629-000000-demo",
        timestamp: "2026-06-29T00:01:00Z",
        claim_id: "cl-20260629-000000-demo",
        approver: "agent/reviewer",
        decision: "approved",
        notes: "approve",
      })}\n${JSON.stringify({
        type: "human_approval",
        id: "ap-20260629-000100-demo",
        timestamp: "2026-06-29T00:02:00Z",
        claim_id: "cl-20260629-000000-demo",
        approver: "human/root",
        decision: "needs_changes",
        notes: "not approved",
      })}\n`,
    );

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "approval",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("approval approver must be human/root");
    expect(validate.stderr).toContain("approval decision must be approved");
  });

  it("rejects approvals when the approved claim evidence is missing", () => {
    fs.writeFileSync(
      path.join(taskDir, "hermes", "claim_ledger.jsonl"),
      `${JSON.stringify({
        type: "claim",
        id: "cl-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        text: "implementation is complete",
        evidence_ids: ["ev-20260629-000000-demo"],
        scope: "runtime",
        limits: "unit test only",
        state: "claim_ready",
      })}\n`,
    );
    fs.writeFileSync(
      path.join(taskDir, "hermes", "approval_records.jsonl"),
      `${JSON.stringify({
        type: "human_approval",
        id: "ap-20260629-000000-demo",
        timestamp: "2026-06-29T00:01:00Z",
        claim_id: "cl-20260629-000000-demo",
        approver: "human/root",
        decision: "approved",
        notes: "approve",
      })}\n`,
    );

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "approval",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("approval claim missing evidence ids");
  });

  it("rejects evidence records that reference missing artifacts", () => {
    fs.writeFileSync(
      path.join(taskDir, "hermes", "evidence_ledger.jsonl"),
      `${JSON.stringify({
        type: "evidence",
        id: "ev-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        source: "runtime output",
        summary: "captured output",
        limits: "unit test only",
        artifact_refs: ["ar-20260629-000000-demo"],
        command_refs: ["cmd-demo"],
      })}\n`,
    );

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "evidence",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("missing artifact ids");
  });

  it("rejects approvals when referenced evidence artifacts are incomplete", () => {
    fs.writeFileSync(
      path.join(taskDir, "hermes", "evidence_ledger.jsonl"),
      `${JSON.stringify({
        type: "evidence",
        id: "ev-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        source: "runtime output",
        summary: "captured output",
        limits: "unit test only",
        artifact_refs: ["ar-20260629-000000-demo"],
        command_refs: ["cmd-demo"],
      })}\n`,
    );
    fs.writeFileSync(
      path.join(taskDir, "hermes", "artifact_ledger.jsonl"),
      `${JSON.stringify({
        type: "artifact",
        id: "ar-20260629-000000-demo",
        path: "",
        hash: "",
        run_id: "run-demo",
        command_ref: "cmd-demo",
        summary: "captured runtime output",
      })}\n`,
    );
    fs.writeFileSync(
      path.join(taskDir, "hermes", "claim_ledger.jsonl"),
      `${JSON.stringify({
        type: "claim",
        id: "cl-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        text: "implementation is complete",
        evidence_ids: ["ev-20260629-000000-demo"],
        scope: "runtime",
        limits: "unit test only",
        state: "claim_ready",
      })}\n`,
    );
    fs.writeFileSync(
      path.join(taskDir, "hermes", "approval_records.jsonl"),
      `${JSON.stringify({
        type: "human_approval",
        id: "ap-20260629-000000-demo",
        timestamp: "2026-06-29T00:01:00Z",
        claim_id: "cl-20260629-000000-demo",
        approver: "human/root",
        decision: "approved",
        notes: "approve",
      })}\n`,
    );

    const validate = runHermes(tmpDir, "validate.py", [
      "--task",
      "01-test",
      "--kind",
      "approval",
    ]);

    expect(validate.status).toBe(1);
    expect(validate.stderr).toContain("artifact path must be a non-empty string");
    expect(validate.stderr).toContain("artifact hash must be a non-empty string");
  });
});
