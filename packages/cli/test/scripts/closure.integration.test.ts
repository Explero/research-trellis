import { execFileSync, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

const PYTHON = process.platform === "win32" ? "python" : "python3";
const TEMPLATE_SCRIPTS = path.resolve(
  import.meta.dirname,
  "../../src/templates/trellis/scripts",
);

interface TestWorkPackage {
  id: string;
  status: string;
  done_when: string[];
  [key: string]: unknown;
}

interface TestTask {
  status: string;
  hermes_phase: string;
  closure_state: string;
  work_packages: TestWorkPackage[];
  current_work_package: string | null;
  repair_count: number;
  max_repair_count: number;
  blockers: string[];
  meta: { research_contract?: { dataset?: string } };
}

function hasPython(): boolean {
  try {
    execFileSync(PYTHON, ["--version"], { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

function baseTask(overrides: Record<string, unknown> = {}) {
  return {
    id: "demo",
    name: "demo",
    title: "Demo research task",
    description: "Produce a verified research result",
    status: "planning",
    priority: "P2",
    createdAt: "2026-07-15",
    assignee: "tester",
    creator: "tester",
    subtasks: [],
    children: [],
    relatedFiles: [],
    meta: {},
    hermes_phase: "planning",
    closure_state: "open",
    closure_mode: "lean",
    intent: "",
    in_scope: [],
    out_of_scope: [],
    definition_of_done: [],
    work_packages: [],
    current_work_package: null,
    next_action: null,
    blockers: [],
    repair_count: 0,
    max_repair_count: 1,
    ...overrides,
  };
}

function setupRepo(root: string, task = baseTask()): string {
  const scripts = path.join(root, ".trellis", "scripts");
  const taskDir = path.join(root, ".trellis", "tasks", "demo");
  fs.mkdirSync(scripts, { recursive: true });
  fs.cpSync(TEMPLATE_SCRIPTS, scripts, { recursive: true });
  fs.mkdirSync(taskDir, { recursive: true });
  fs.writeFileSync(
    path.join(root, ".trellis", "config.yaml"),
    "session_auto_commit: false\n",
  );
  fs.writeFileSync(path.join(root, ".trellis", ".developer"), "name=tester\n");
  fs.writeFileSync(
    path.join(taskDir, "task.json"),
    `${JSON.stringify(task, null, 2)}\n`,
  );
  return taskDir;
}

function run(root: string, ...args: string[]) {
  return spawnSync(
    PYTHON,
    [".trellis/scripts/closure.py", ...args, "--task", "demo"],
    { cwd: root, encoding: "utf-8" },
  );
}

function runTask(root: string, ...args: string[]) {
  return spawnSync(PYTHON, [".trellis/scripts/task.py", ...args], {
    cwd: root,
    encoding: "utf-8",
    env: { ...process.env, TRELLIS_CONTEXT_ID: "closure-test-session" },
  });
}

function readTask(taskDir: string): TestTask {
  return JSON.parse(
    fs.readFileSync(path.join(taskDir, "task.json"), "utf-8"),
  ) as TestTask;
}

function writeTask(taskDir: string, value: Record<string, unknown>): void {
  fs.writeFileSync(
    path.join(taskDir, "task.json"),
    `${JSON.stringify(value, null, 2)}\n`,
  );
}

function plan(root: string, doneWhen: string[], extra: string[] = []) {
  const args = ["plan", "--intent", "Produce a verified result"];
  for (const item of doneWhen) args.push("--done-when", item);
  args.push(...extra);
  return run(root, ...args);
}

function completeCurrent(root: string, evidence = "test:pass"): void {
  expect(run(root, "package-start").status).toBe(0);
  expect(run(root, "package-check").status).toBe(0);
  expect(run(root, "package-done", "--evidence", evidence).status).toBe(0);
}

function appendJsonl(
  taskDir: string,
  filename: string,
  records: unknown[],
): void {
  const hermes = path.join(taskDir, "hermes");
  fs.mkdirSync(hermes, { recursive: true });
  fs.writeFileSync(
    path.join(hermes, filename),
    `${records.map((item) => JSON.stringify(item)).join("\n")}\n`,
  );
}

describe.skipIf(!hasPython())("Lean Research Closure CLI", () => {
  let root: string;
  let taskDir: string;

  beforeEach(() => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), "trellis-closure-"));
    taskDir = setupRepo(root);
  });

  afterEach(() => {
    fs.rmSync(root, { recursive: true, force: true });
  });

  it("plans one package for a simple task", () => {
    expect(plan(root, ["CLI prints a verified result"]).status).toBe(0);
    expect(readTask(taskDir).work_packages).toHaveLength(1);
  });

  it("plans two to four packages for ordinary observable outcomes", () => {
    expect(
      plan(root, [
        "Dataset is prepared",
        "Model is evaluated",
        "Report is reviewed",
      ]).status,
    ).toBe(0);
    expect(readTask(taskDir).work_packages).toHaveLength(3);
  });

  it("keeps command and file microsteps inside done_when", () => {
    expect(
      plan(root, [
        "CLI produces the requested artifact",
        "读取文件",
        "运行命令",
      ]).status,
    ).toBe(0);
    const packages = readTask(taskDir).work_packages;
    expect(packages).toHaveLength(1);
    expect(packages[0].done_when).toEqual([
      "CLI produces the requested artifact",
      "读取文件",
      "运行命令",
    ]);
  });

  it("keeps tests and build checks as package validation", () => {
    expect(
      plan(root, ["CLI artifact exists", "Unit tests pass", "Build passes"])
        .status,
    ).toBe(0);
    const packages = readTask(taskDir).work_packages;
    expect(packages).toHaveLength(1);
    expect(packages[0].done_when).toEqual([
      "CLI artifact exists",
      "Unit tests pass",
      "Build passes",
    ]);
  });

  it("warns instead of auto-splitting five explicit packages", () => {
    const packages = Array.from({ length: 5 }, (_, index) => [
      "--package",
      `Result ${index + 1}::Observable result ${index + 1}::Result ${index + 1} verified`,
    ]).flat();
    const result = plan(root, [], packages);
    expect(result.status).toBe(0);
    expect(result.stderr).toContain("consider multiple Trellis tasks");
    expect(readTask(taskDir).work_packages).toHaveLength(5);
  });

  it("rejects validation without definition_of_done", () => {
    expect(run(root, "plan", "--intent", "Intent only").status).toBe(0);
    const result = run(root, "validate");
    expect(result.status).toBe(1);
    expect(result.stderr).toContain("definition_of_done is required");
  });

  it("detects dependency cycles", () => {
    const task = baseTask({
      intent: "Cycle test",
      definition_of_done: ["A and B complete"],
      work_packages: [
        {
          id: "WP1",
          title: "A",
          outcome: "A complete",
          done_when: ["A complete"],
          evidence_required: [],
          depends_on: ["WP2"],
          status: "pending",
          evidence_refs: [],
          blocker: null,
        },
        {
          id: "WP2",
          title: "B",
          outcome: "B complete",
          done_when: ["B complete"],
          evidence_required: [],
          depends_on: ["WP1"],
          status: "pending",
          evidence_refs: [],
          blocker: null,
        },
      ],
    });
    writeTask(taskDir, task);
    const result = run(root, "validate");
    expect(result.status).toBe(1);
    expect(result.stderr).toContain("dependencies contain a cycle");
  });

  it("keeps the capsule compact and focused on the current package", () => {
    const longScope = `Scope ${"x".repeat(400)}`;
    expect(
      plan(root, ["Artifact exists"], ["--in-scope", longScope]).status,
    ).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    expect(run(root, "package-start").status).toBe(0);
    const result = run(root, "capsule");
    expect(result.status).toBe(0);
    expect(result.stdout.trim().length).toBeLessThanOrEqual(1000);
    expect(result.stdout).toContain("Current: WP1");
    expect(result.stdout).toContain("Done when:");
  });

  it("does not complete a package without validation evidence", () => {
    expect(plan(root, ["Artifact exists"]).status).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    expect(run(root, "package-start").status).toBe(0);
    expect(run(root, "package-check").status).toBe(0);
    const result = run(root, "package-done");
    expect(result.status).toBe(1);
    expect(result.stderr).toContain("requires validation evidence");
  });

  it("does not dispose another package while one is current", () => {
    expect(plan(root, ["Result A", "Result B"]).status).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    expect(run(root, "package-start").status).toBe(0);
    const result = run(
      root,
      "package-done",
      "--package-id",
      "WP2",
      "--disposition",
      "deferred",
      "--reason",
      "not needed",
    );
    expect(result.status).toBe(1);
    expect(result.stderr).toContain("WP1 is still the current work package");
  });

  it("starts the next package after completing the previous package", () => {
    expect(plan(root, ["Result A", "Result B"]).status).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    completeCurrent(root, "test:a");

    const between = readTask(taskDir);
    expect(between.hermes_phase).toBe("running");
    expect(between.current_work_package).toBeNull();
    expect(between.work_packages[1].status).toBe("ready");

    expect(run(root, "package-start").status).toBe(0);
    const after = readTask(taskDir);
    expect(after.current_work_package).toBe("WP2");
    expect(after.work_packages[1].status).toBe("running");
    expect(after.repair_count).toBe(0);
  });

  it("refuses close while part of the plan is unfinished", () => {
    expect(plan(root, ["Result A", "Result B"]).status).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    completeCurrent(root);
    const result = run(root, "close");
    expect(result.status).toBe(1);
    expect(result.stdout).toContain("package: WP2");
    const task = readTask(taskDir);
    expect(task.status).toBe("in_progress");
    expect(task.hermes_phase).toBe("running");
    expect(task.closure_state).toBe("open");
    expect(fs.existsSync(path.join(taskDir, "closure-report.md"))).toBe(false);
    const events = fs.readFileSync(
      path.join(taskDir, "hermes", "task-events.jsonl"),
      "utf-8",
    );
    expect(events).not.toContain('"event_type":"task_closed"');
  });

  it("refuses archive before closure", () => {
    expect(plan(root, ["Result A"]).status).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    const result = runTask(root, "archive", "demo", "--no-commit");
    expect(result.status).toBe(1);
    expect(result.stderr).toContain("closure task is not closed");
    expect(fs.existsSync(taskDir)).toBe(true);
  });

  it("writes a handoff when an open task session is finished", () => {
    expect(plan(root, ["Result A"]).status).toBe(0);
    const sessions = path.join(root, ".trellis", ".runtime", "sessions");
    fs.mkdirSync(sessions, { recursive: true });
    fs.writeFileSync(
      path.join(sessions, "closure-test-session.json"),
      `${JSON.stringify({ current_task: ".trellis/tasks/demo" })}\n`,
    );
    const result = runTask(root, "finish");
    expect(result.status).toBe(0);
    expect(result.stdout).toContain("Handoff updated");
    expect(fs.existsSync(path.join(taskDir, "HANDOFF.md"))).toBe(true);
  });

  it("prints a compact actionable audit gap", () => {
    expect(plan(root, ["Result A"]).status).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    const result = run(root, "audit", "--no-report");
    expect(result.status).toBe(1);
    expect(result.stdout).toContain("gaps:");
    expect(result.stdout).toContain("package: WP1");
    expect(result.stdout).toContain("action:");
    expect(result.stdout.length).toBeLessThan(800);
  });

  it("repairs only the first gap and preserves completed packages", () => {
    expect(plan(root, ["Result A", "Result B"]).status).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    completeCurrent(root, "test:a");
    const before = structuredClone(readTask(taskDir).work_packages[0]);
    const repair = run(root, "repair");
    expect(repair.status).toBe(1);
    const task = readTask(taskDir);
    expect(task.work_packages[0]).toEqual(before);
    expect(task.work_packages[1].status).toBe("running");
    expect(task.repair_count).toBe(1);
    expect(task.hermes_phase).toBe("running");
  });

  it("runs audit gap, one repair, and final close end to end", () => {
    expect(plan(root, ["Result A", "Result B"]).status).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    completeCurrent(root, "test:a");
    expect(run(root, "audit", "--no-report").status).toBe(1);
    expect(run(root, "repair").status).toBe(1);
    expect(run(root, "package-check").status).toBe(0);
    expect(run(root, "package-done", "--evidence", "test:b").status).toBe(0);
    expect(run(root, "audit").status).toBe(0);
    expect(run(root, "close").status).toBe(0);
    expect(readTask(taskDir).closure_state).toBe("closed");
  });

  it("blocks a second lean repair attempt after the limit", () => {
    expect(plan(root, ["Result A"]).status).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    expect(run(root, "repair").status).toBe(1);
    const second = run(root, "repair");
    expect(second.status).toBe(1);
    expect(readTask(taskDir).hermes_phase).toBe("blocked");
    expect(fs.existsSync(path.join(taskDir, "HANDOFF.md"))).toBe(true);
  });

  it("requires human approval to extend a repair limit", () => {
    expect(plan(root, ["Result A"]).status).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    expect(run(root, "repair").status).toBe(1);
    expect(run(root, "repair").status).toBe(1);
    expect(
      run(
        root,
        "amend",
        "--field",
        "max_repair_count",
        "--value",
        "2",
        "--reason",
        "one reviewed retry",
      ).status,
    ).toBe(1);
    expect(
      run(
        root,
        "amend",
        "--field",
        "max_repair_count",
        "--value",
        "2",
        "--reason",
        "one reviewed retry",
        "--approved-by",
        "human/root",
      ).status,
    ).toBe(0);
    const task = readTask(taskDir);
    expect(task.max_repair_count).toBe(2);
    expect(task.hermes_phase).toBe("planning");
    expect(task.current_work_package).toBeNull();
    expect(task.work_packages[0].status).toBe("pending");
    expect(task.blockers).toEqual([]);
    expect(run(root, "validate").status).toBe(0);
  });

  it("requires explicit human approval for high-risk amendments", () => {
    expect(plan(root, ["Result A"]).status).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    const denied = run(
      root,
      "amend",
      "--field",
      "dataset",
      "--value",
      "dataset-v2",
      "--reason",
      "new source",
    );
    expect(denied.status).toBe(1);
    expect(readTask(taskDir).meta.research_contract?.dataset).toBeUndefined();
    expect(readTask(taskDir).hermes_phase).toBe("blocked");

    const approved = run(
      root,
      "amend",
      "--field",
      "dataset",
      "--value",
      "dataset-v2",
      "--reason",
      "approved source",
      "--approved-by",
      "human/root",
    );
    expect(approved.status).toBe(0);
    const task = readTask(taskDir);
    expect(task.meta.research_contract.dataset).toBe("dataset-v2");
    expect(task.hermes_phase).toBe("planning");
    expect(task.blockers).toEqual([]);
  });

  it("does not allow amend to bypass task state commands", () => {
    expect(plan(root, ["Result A"]).status).toBe(0);
    const result = run(
      root,
      "amend",
      "--field",
      "hermes_phase",
      "--value",
      "closed",
      "--reason",
      "bypass close",
    );
    expect(result.status).toBe(1);
    expect(result.stderr).toContain("cannot be amended directly");
    expect(readTask(taskDir).hermes_phase).toBe("planning");
  });

  it("closes a valid lean task and then allows archive", () => {
    expect(plan(root, ["Lean result verified"]).status).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    completeCurrent(root, "pnpm test:pass");
    expect(run(root, "close").status).toBe(0);
    const task = readTask(taskDir);
    expect(task.status).toBe("completed");
    expect(task.hermes_phase).toBe("closed");
    expect(task.closure_state).toBe("closed");
    expect(fs.existsSync(path.join(taskDir, "closure-report.md"))).toBe(true);
    const events = fs.readFileSync(
      path.join(taskDir, "hermes", "task-events.jsonl"),
      "utf-8",
    );
    expect(events).toContain('"event_type":"package_started"');
    expect(events).toContain('"event_type":"package_completed"');
    expect(events).toContain('"event_type":"task_closed"');
    expect(runTask(root, "archive", "demo", "--no-commit").status).toBe(0);
    const archiveMonth = new Date().toISOString().slice(0, 7);
    expect(
      fs.existsSync(
        path.join(root, ".trellis", "tasks", "archive", archiveMonth, "demo"),
      ),
    ).toBe(true);
  });

  it("closes standard mode when run, artifact, metrics, and evidence exist", () => {
    expect(
      plan(root, ["Standard result verified"], ["--mode", "standard"]).status,
    ).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    completeCurrent(root, "ev-standard");
    appendJsonl(taskDir, "run_manifest.jsonl", [
      { id: "run-standard", exit_code: 0, metrics: { rmse: 0.2 } },
    ]);
    appendJsonl(taskDir, "artifact_ledger.jsonl", [
      { id: "ar-standard", hash: `sha256:${"b".repeat(64)}` },
    ]);
    appendJsonl(taskDir, "evidence_ledger.jsonl", [{ id: "ev-standard" }]);
    appendJsonl(taskDir, "claim_ledger.jsonl", [
      { id: "cl-standard", limits: "fixed fixture only" },
    ]);
    expect(run(root, "close").status).toBe(0);
    expect(readTask(taskDir).closure_state).toBe("closed");
  });

  it("rejects publication close without claim approval", () => {
    expect(
      plan(root, ["Publication result verified"], ["--mode", "publication"])
        .status,
    ).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    completeCurrent(root, "ev-1");
    appendJsonl(taskDir, "run_manifest.jsonl", [{ id: "run-1", exit_code: 0 }]);
    appendJsonl(taskDir, "artifact_ledger.jsonl", [
      { id: "ar-1", hash: `sha256:${"a".repeat(64)}` },
    ]);
    appendJsonl(taskDir, "evidence_ledger.jsonl", [{ id: "ev-1" }]);
    appendJsonl(taskDir, "claim_ledger.jsonl", [
      { id: "cl-1", evidence_ids: ["ev-1"], limits: "single dataset" },
    ]);
    appendJsonl(taskDir, "compare.jsonl", [
      {
        id: "cmp-1",
        passed: true,
        sample_count: 3,
        variance: 0.01,
        evidence_refs: ["ev-1"],
        claim_refs: ["cl-1"],
      },
    ]);
    fs.writeFileSync(path.join(taskDir, "STATE.md"), "# State\n");
    fs.writeFileSync(path.join(taskDir, "CLAIMS.md"), "# Claims\n");

    const result = run(root, "close");
    expect(result.status).toBe(1);
    expect(result.stdout).toContain("claim cl-1 human approval");
    expect(readTask(taskDir).closure_state).toBe("open");
  });

  it("keeps legacy non-Hermes archive behavior", () => {
    const legacyRoot = fs.mkdtempSync(
      path.join(os.tmpdir(), "trellis-legacy-"),
    );
    try {
      setupRepo(legacyRoot, {
        id: "demo",
        name: "demo",
        title: "Legacy task",
        status: "in_progress",
        priority: "P2",
        createdAt: "2026-07-15",
        assignee: "tester",
        creator: "tester",
        subtasks: [],
        children: [],
        relatedFiles: [],
        meta: {},
      });
      const result = runTask(legacyRoot, "archive", "demo", "--no-commit");
      expect(result.status).toBe(0);
      expect(result.stderr).toContain("Compatibility mode");
    } finally {
      fs.rmSync(legacyRoot, { recursive: true, force: true });
    }
  });
});
