import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

const TEMPLATE_SCRIPTS = path.resolve(
  __dirname,
  "../../src/templates/trellis/scripts",
);

function taskCard(
  role: string,
  options: { profile?: string; objective?: string; jobId?: string } = {},
) {
  return {
    type: "task_card",
    id: `tc-${options.jobId ?? role}`,
    timestamp: "2026-07-16T00:00:00Z",
    job_id: options.jobId ?? `job-${role}`,
    role,
    ...(options.profile ? { profile: options.profile } : {}),
    ...(options.objective ? { objective: options.objective } : {}),
    worktree_id: "main",
    status: "queued",
    allowed_files: ["src/**"],
    forbidden_files: [".env"],
    heartbeat_interval: "5m",
    timeout_at: "2099-01-01T00:00:00Z",
    checkpoint: "not-started",
    resume_from: "task_card",
    record_uri: ".trellis/tasks/01-role-test/hermes/worker_records.jsonl",
    evidence_refs: [],
    risk_flags: [],
  };
}

function writeJsonl(file: string, records: unknown[]): void {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, records.map((record) => JSON.stringify(record)).join("\n") + "\n");
}

describe("Hermes canonical roles and profiles", () => {
  let root: string;
  let taskDir: string;

  beforeEach(() => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), "research-trellis-roles-"));
    fs.mkdirSync(path.join(root, ".trellis", "tasks", "01-role-test", "hermes"), {
      recursive: true,
    });
    fs.cpSync(TEMPLATE_SCRIPTS, path.join(root, ".trellis", "scripts"), {
      recursive: true,
    });
    taskDir = path.join(root, ".trellis", "tasks", "01-role-test");
    fs.writeFileSync(
      path.join(taskDir, "task.json"),
      JSON.stringify({ id: "01-role-test", status: "in_progress" }) + "\n",
    );
  });

  afterEach(() => {
    fs.rmSync(root, { recursive: true, force: true });
  });

  function run(script: string, args: string[]) {
    return spawnSync(
      "python3",
      [path.join(root, ".trellis", "scripts", "hermes", script), ...args],
      { cwd: root, encoding: "utf-8" },
    );
  }

  function append(card: ReturnType<typeof taskCard>) {
    return run("record.py", [
      "append",
      "--task",
      "01-role-test",
      "--record-type",
      "worker",
      "--json",
      JSON.stringify(card),
    ]);
  }

  it("writes only canonical roles and supplies each safe default profile", () => {
    const defaults = {
      planner: "task_planning",
      researcher: "codebase",
      coder: "implementation",
      runner: "validation",
      reviewer: "quality",
    };
    for (const [index, [role, profile]] of Object.entries(defaults).entries()) {
      const result = append(taskCard(role, { jobId: `job-${index}-${role}` }));
      expect(result.status, result.stderr).toBe(0);
      const records = fs
        .readFileSync(path.join(taskDir, "hermes", "worker_records.jsonl"), "utf-8")
        .trim()
        .split("\n")
        .map((line) => JSON.parse(line));
      expect(records.at(-1)).toMatchObject({ role, profile });
    }
  });

  it("accepts every declared role/profile pair and rejects invalid combinations", () => {
    const profiles: Record<string, string[]> = {
      planner: ["research_design", "task_planning", "root_cause", "method_selection"],
      researcher: ["literature", "codebase", "external_docs", "prior_art"],
      coder: ["implementation", "tests", "configuration", "repair"],
      runner: ["experiment", "test", "build", "validation"],
      reviewer: ["quality", "evidence", "claim", "safety", "closure", "statistics"],
    };
    let index = 0;
    for (const [role, roleProfiles] of Object.entries(profiles)) {
      for (const profile of roleProfiles) {
        const result = append(taskCard(role, { profile, jobId: `job-${index++}` }));
        expect(result.status, `${role}:${profile} ${result.stderr}`).toBe(0);
      }
    }
    const invalid = append(taskCard("coder", { profile: "statistics", jobId: "bad" }));
    expect(invalid.status).toBe(2);
    expect(invalid.stderr).toContain("invalid profile 'statistics' for role 'coder'");
  });

  it("normalizes legacy role names without rewriting historical files", () => {
    const cases = [
      ["scientist", "planner", "research_design", ""],
      ["builder", "coder", "implementation", ""],
      ["literature", "researcher", "literature", ""],
      ["research/scout", "researcher", "external_docs", "查官方 API 文档"],
      ["evaluator", "reviewer", "evidence", ""],
      ["claim-reviewer", "reviewer", "claim", ""],
      ["analyst", "reviewer", "statistics", "检查方差和置信区间"],
      ["analyst", "reviewer", "statistics", ""],
    ];
    for (const [index, [legacy, role, profile, objective]] of cases.entries()) {
      const result = append(
        taskCard(legacy, {
          objective,
          ...(index === cases.length - 1 ? { profile: "statistics" } : {}),
          jobId: `legacy-${index}`,
        }),
      );
      expect(result.status, result.stderr).toBe(0);
      expect(result.stderr).toContain("deprecated Hermes role");
      const latestLine = fs
        .readFileSync(path.join(taskDir, "hermes", "worker_records.jsonl"), "utf-8")
        .trim()
        .split("\n")
        .at(-1);
      expect(latestLine).toBeDefined();
      const latest = JSON.parse(latestLine ?? "{}");
      expect(latest).toMatchObject({ role, profile });
    }

    const legacyPath = path.join(taskDir, "hermes", "worker_records.jsonl");
    writeJsonl(legacyPath, [taskCard("analyst", { jobId: "historical" })]);
    const validate = run("validate.py", ["--task", "01-role-test", "--kind", "worker"]);
    expect(validate.status, validate.stderr).toBe(0);
    expect(validate.stderr).toContain("safe default planner:root_cause");
    expect(JSON.parse(fs.readFileSync(legacyPath, "utf-8")).role).toBe("analyst");
  });

  it("rejects evidence-curator for new dispatch but reads historical records", () => {
    const rejected = append(taskCard("evidence-curator"));
    expect(rejected.status).toBe(2);
    expect(rejected.stderr).toContain("tool-only");

    writeJsonl(path.join(taskDir, "hermes", "worker_records.jsonl"), [taskCard("evidence-curator")]);
    const validate = run("validate.py", ["--task", "01-role-test", "--kind", "worker"]);
    expect(validate.status, validate.stderr).toBe(0);
    expect(validate.stderr).toContain("deterministic evidence command");
  });

  it("does not let evidence review replace independent code-quality review", () => {
    const checkpoint = (jobId: string) => ({
      type: "checkpoint",
      id: `cp-${jobId}`,
      timestamp: "2026-07-16T00:01:00Z",
      job_id: jobId,
      checkpoint: "checked",
      resume_from: "complete",
      evidence_refs: [],
      open_items: [],
    });
    const result = (jobId: string, status = "done", handoff = "done") => ({
      type: "result",
      id: `result-${jobId}`,
      timestamp: "2026-07-16T00:02:00Z",
      job_id: jobId,
      status,
      summary: "complete",
      changed_files: [],
      evidence_refs: [],
      risk_flags: [],
      handoff,
    });
    const coder = taskCard("coder", { jobId: "coder" });
    const runner = { ...taskCard("runner", { profile: "test", jobId: "runner" }), parent_job_id: "coder" };
    const reviewer = {
      ...taskCard("reviewer", { profile: "evidence", jobId: "reviewer" }),
      parent_job_id: "coder",
    };
    const records = [
      coder,
      runner,
      checkpoint("runner"),
      result("runner"),
      reviewer,
      checkpoint("reviewer"),
      result("reviewer"),
      checkpoint("coder"),
      result("coder", "review", "review"),
    ];
    const workerPath = path.join(taskDir, "hermes", "worker_records.jsonl");
    writeJsonl(workerPath, records);
    const rejected = run("validate.py", ["--task", "01-role-test", "--kind", "worker"]);
    expect(rejected.status).toBe(1);
    expect(rejected.stderr).toContain("requires reviewer result or checkpoint");

    reviewer.profile = "quality";
    writeJsonl(workerPath, records);
    const accepted = run("validate.py", ["--task", "01-role-test", "--kind", "worker"]);
    expect(accepted.status, accepted.stderr).toBe(0);
  });

  it("collects and validates evidence deterministically", () => {
    const content = "accuracy=0.91\n";
    fs.mkdirSync(path.join(root, "artifacts"), { recursive: true });
    fs.writeFileSync(path.join(root, "artifacts", "metrics.txt"), content);
    const hash = `sha256:${createHash("sha256").update(content).digest("hex")}`;
    writeJsonl(path.join(taskDir, "hermes", "artifact_ledger.jsonl"), [
      {
        type: "artifact",
        id: "artifact-1",
        path: "artifacts/metrics.txt",
        hash,
        run_id: "run-1",
        command_ref: "command-1",
        summary: "metrics output",
      },
    ]);
    writeJsonl(path.join(taskDir, "hermes", "evidence_ledger.jsonl"), [
      {
        type: "evidence",
        id: "evidence-1",
        timestamp: "2026-07-16T00:00:00Z",
        source: "artifacts/metrics.txt",
        summary: "accuracy is 0.91",
        limits: "single fixture",
        artifact_refs: ["artifact-1"],
        command_refs: ["command-1"],
      },
    ]);

    const validate = run("evidence.py", ["validate", "--task", "01-role-test"]);
    expect(validate.status, validate.stderr).toBe(0);
    const collect = run("evidence.py", ["collect", "--task", "01-role-test"]);
    expect(collect.status, collect.stderr).toBe(0);
    const summary = JSON.parse(
      fs.readFileSync(path.join(taskDir, "hermes", "evidence_summary.json"), "utf-8"),
    );
    expect(summary.counts).toEqual({ artifacts: 1, evidence: 1, run_manifests: 0 });
    expect(summary.gaps.dangling_artifact_refs).toEqual([]);
    expect(summary.validation_errors).toEqual([]);
  });
});
