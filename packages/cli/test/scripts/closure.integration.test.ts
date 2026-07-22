import { execFileSync, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
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
  hermes_revision: number;
  research_route?: string;
  research_change_fields?: string[];
  grill_completed?: boolean;
  decision_ref?: string | null;
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
    hermes_revision: 0,
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
    {
      cwd: root,
      encoding: "utf-8",
      env: {
        ...process.env,
        TRELLIS_HOOKS_ACTIVE: "1",
        TRELLIS_PLATFORM: "claude",
      },
    },
  );
}

function runTask(root: string, ...args: string[]) {
  return spawnSync(PYTHON, [".trellis/scripts/task.py", ...args], {
    cwd: root,
    encoding: "utf-8",
    env: { ...process.env, TRELLIS_CONTEXT_ID: "closure-test-session" },
  });
}

function recordHookHeartbeat(root: string, taskId = "demo"): void {
  const result = spawnSync(
    PYTHON,
    [
      "-c",
      "import sys; from pathlib import Path; sys.path.insert(0, '.trellis/scripts'); from common.firewall import record_firewall_heartbeat; raise SystemExit(0 if record_firewall_heartbeat(Path('.').resolve(), 'claude', 'hooks', task_id=sys.argv[1], session_id='test-session') else 1)",
      taskId,
    ],
    { cwd: root, encoding: "utf-8" },
  );
  expect(result.status, result.stderr).toBe(0);
}

function runDispatch(root: string, ...args: string[]) {
  return spawnSync(
    PYTHON,
    [".trellis/scripts/hermes/dispatch.py", ...args, "--task", "demo"],
    {
      cwd: root,
      encoding: "utf-8",
      env: {
        ...process.env,
        TRELLIS_HOOKS_ACTIVE: "1",
        TRELLIS_PLATFORM: "claude",
      },
    },
  );
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

function stableValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stableValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, stableValue(item)]),
    );
  }
  return value;
}

function resultSha256(value: Record<string, unknown>): string {
  const payload = Object.fromEntries(
    Object.entries(value).filter(([key]) => key !== "audit"),
  );
  return `sha256:${createHash("sha256")
    .update(JSON.stringify(stableValue(payload)), "utf8")
    .digest("hex")}`;
}

function plan(root: string, doneWhen: string[], extra: string[] = []) {
  const args = ["plan", "--intent", "Produce a verified result"];
  for (const item of doneWhen) args.push("--done-when", item);
  args.push(...extra);
  return run(root, ...args);
}

function writeDecisionRecord(
  taskDir: string,
  filename = "design.md",
  marker = "DECISION_BODY_MUST_NOT_BE_IN_CAPSULE",
): string {
  fs.writeFileSync(
    path.join(taskDir, filename),
    [
      "# Research Decision",
      "",
      "## Decision",
      marker,
      "",
      "## Rationale",
      "The choice follows the current research objective.",
      "",
      "## Evidence",
      "Repository evidence supports this bounded choice.",
      "",
      "## Alternatives",
      "Keep the previous protocol.",
      "",
      "## Failure Conditions",
      "Conflicting evidence or a failed critical assumption.",
      "",
    ].join("\n"),
    "utf-8",
  );
  return filename;
}

function planTwoExplicitPackages(root: string) {
  return plan(root, ["Result A", "Result B"], [
    "--package",
    "Prepare result A::Result A::Result A",
    "--package",
    "Prepare result B::Result B::Result B",
  ]);
}

function materializeEvidence(root: string, label: string): string {
  const safeName = label.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "") || "result";
  const relativePath = `artifacts/${safeName}.txt`;
  const absolutePath = path.join(root, relativePath);
  fs.mkdirSync(path.dirname(absolutePath), { recursive: true });
  fs.writeFileSync(absolutePath, `validation evidence: ${label}\n`, "utf-8");
  return relativePath;
}

function completeCurrent(root: string, evidence = "test-pass"): void {
  const evidenceRef = materializeEvidence(root, evidence);
  expect(run(root, "package-start").status).toBe(0);
  expect(run(root, "package-check").status).toBe(0);
  expect(run(root, "package-done", "--evidence", evidenceRef).status).toBe(0);
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

  it("requires a completed grill before an exploration task validates", () => {
    expect(
      plan(root, ["Research result is verified"], [
        "--route",
        "exploration",
        "--research-change",
        "model_architecture",
      ]).status,
    ).toBe(0);
    const before = readTask(taskDir);
    expect(before.research_route).toBe("exploration");
    expect(before.research_change_fields).toEqual(["model_architecture"]);
    expect(before.grill_completed).toBe(false);
    const blocked = run(root, "validate");
    expect(blocked.status).toBe(1);
    expect(blocked.stderr).toContain("completed grill");

    const missingDecision = run(root, "grill", "--complete");
    expect(missingDecision.status).not.toBe(0);
    expect(missingDecision.stderr).toContain("--decision-ref");

    const decisionRef = writeDecisionRecord(taskDir);
    expect(
      run(root, "grill", "--complete", "--decision-ref", decisionRef).status,
    ).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    const capsule = run(root, "capsule");
    expect(capsule.stdout).toContain("Route: exploration");
    expect(capsule.stdout).toContain("Research changes: model_architecture");
    expect(capsule.stdout).toContain("Grill: complete");
    expect(capsule.stdout).toContain("Decision ref: design.md");
    expect(capsule.stdout).not.toContain("DECISION_BODY_MUST_NOT_BE_IN_CAPSULE");
    const events = fs
      .readFileSync(path.join(taskDir, "hermes", "task-events.jsonl"), "utf-8")
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line) as Record<string, unknown>);
    expect(events.find((event) => event.event_type === "grill_completed")).toMatchObject({
      decision_ref: "design.md",
    });
  });

  it("keeps legacy completed grills without decision_ref compatible with a warning", () => {
    writeTask(taskDir, baseTask({
      intent: "Preserve a legacy exploration task",
      definition_of_done: ["Legacy result is verified"],
      research_route: "exploration",
      research_change_fields: ["dataset"],
      grill_completed: true,
      work_packages: [
        {
          id: "WP1",
          title: "Legacy result",
          outcome: "Legacy result is verified",
          done_when: ["Legacy result is verified"],
          evidence_required: [],
          depends_on: [],
          status: "pending",
          evidence_refs: [],
          blocker: null,
        },
      ],
    }));

    const result = run(root, "validate");
    expect(result.status).toBe(0);
    expect(result.stderr).toContain("legacy completed grill has no decision_ref");
  });

  it("automatically routes recorded research changes to exploration", () => {
    expect(
      plan(root, ["Research result is verified"], [
        "--research-change",
        "dataset",
      ]).status,
    ).toBe(0);
    expect(readTask(taskDir).research_route).toBe("exploration");
    expect(run(root, "validate").status).toBe(1);

    const conflict = run(root, "route", "--route", "delivery");
    expect(conflict.status).toBe(1);
    expect(conflict.stderr).toContain("require the exploration route");
  });

  it("rejects an explicit delivery route with research protocol changes", () => {
    const result = plan(root, ["Research result is verified"], [
      "--route",
      "delivery",
      "--research-change",
      "dataset",
    ]);
    expect(result.status).toBe(1);
    expect(result.stderr).toContain("require the exploration route");
    expect(readTask(taskDir).research_route).toBeUndefined();
  });

  it("allows a deterministic delivery task to validate without a grill", () => {
    expect(
      plan(root, ["Delivery is verified"], ["--route", "delivery"]).status,
    ).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    expect(readTask(taskDir).research_route).toBe("delivery");
  });

  it("keeps older Hermes closure tasks compatible with the delivery default", () => {
    writeTask(taskDir, baseTask({
      intent: "Preserve an existing closure task",
      definition_of_done: ["Existing result is verified"],
      work_packages: [
        {
          id: "WP1",
          title: "Existing result",
          outcome: "Existing result is verified",
          done_when: ["Existing result is verified"],
          evidence_required: [],
          depends_on: [],
          status: "pending",
          evidence_refs: [],
          blocker: null,
        },
      ],
    }));
    expect(run(root, "validate").status).toBe(0);
    const task = readTask(taskDir);
    expect(task.research_route).toBe("delivery");
    expect(task.grill_completed).toBe(false);
  });

  it("increments hermes_revision on every Closure semantic write", () => {
    expect(readTask(taskDir).hermes_revision).toBe(0);
    expect(plan(root, ["CLI prints a verified result"]).status).toBe(0);
    expect(readTask(taskDir).hermes_revision).toBe(1);
    expect(run(root, "validate").status).toBe(0);
    expect(readTask(taskDir).hermes_revision).toBe(2);
    expect(run(root, "package-start").status).toBe(0);
    expect(readTask(taskDir).hermes_revision).toBe(3);
    expect(run(root, "package-check").status).toBe(0);
    expect(readTask(taskDir).hermes_revision).toBe(4);
    const evidence = materializeEvidence(root, "revision");
    expect(run(root, "package-done", "--evidence", evidence).status).toBe(0);
    expect(readTask(taskDir).hermes_revision).toBe(5);
  });

  it("rejects a stale task writer with compare-and-swap semantics", () => {
    const script = [
      "import copy, sys",
      "from pathlib import Path",
      "sys.path.insert(0, str(Path(sys.argv[1]).resolve()))",
      "from common.closure import ClosureError, save_task",
      "from common.io import read_json",
      "task_dir = Path(sys.argv[2])",
      "first = read_json(task_dir / 'task.json')",
      "second = copy.deepcopy(first)",
      "save_task(task_dir, first)",
      "try:",
      "    save_task(task_dir, second)",
      "except ClosureError as exc:",
      "    raise SystemExit(0 if 'stale task revision' in str(exc) else 2)",
      "raise SystemExit(1)",
    ].join("\n");
    const result = spawnSync(
      PYTHON,
      ["-c", script, path.join(root, ".trellis", "scripts"), taskDir],
      { cwd: root, encoding: "utf-8" },
    );
    expect(result.status, result.stderr).toBe(0);
  });

  it("plans explicit work packages from implementation units", () => {
    fs.writeFileSync(
      path.join(taskDir, "implement.md"),
      [
        "# Implementation",
        "",
        "## Work Packages",
        "### WP1: Prepare dataset",
        "Outcome: Dataset is prepared",
        "Done when: Dataset is prepared",
        "### WP2: Evaluate model",
        "Outcome: Model is evaluated",
        "Done when: Model is evaluated",
        "### WP3: Review report",
        "Outcome: Report is reviewed",
        "Done when: Report is reviewed",
        "",
      ].join("\n"),
    );
    expect(
      plan(root, [
        "Dataset is prepared",
        "Model is evaluated",
        "Report is reviewed",
      ]).status,
    ).toBe(0);
    expect(readTask(taskDir).work_packages).toHaveLength(3);
  });

  it("uses one safe package when implementation units are absent", () => {
    const result = plan(root, ["Dataset is prepared", "Model is evaluated"]);
    expect(result.status).toBe(0);
    expect(result.stderr).toContain("one safe work package");
    expect(readTask(taskDir).work_packages).toHaveLength(1);
  });

  it("keeps context pins first in the compact capsule", () => {
    expect(
      plan(root, ["Artifact exists"], ["--context-pin", ".trellis/spec/guides/index.md"])
        .status,
    ).toBe(0);
    const capsule = run(root, "capsule");
    expect(capsule.status).toBe(0);
    expect(capsule.stdout).toContain("Refs: .trellis/spec/guides/index.md");
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

  it("rejects unresolvable evidence refs and catches forged refs during audit", () => {
    expect(plan(root, ["Artifact exists"]).status).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    expect(run(root, "package-start").status).toBe(0);
    expect(run(root, "package-check").status).toBe(0);
    const rejected = run(root, "package-done", "--evidence", "test:pass");
    expect(rejected.status).toBe(1);
    expect(rejected.stderr).toContain("existing repository files or evidence ledger ids");

    const task = readTask(taskDir) as TestTask & {
      work_packages: (TestWorkPackage & { evidence_refs: string[] })[];
    };
    task.work_packages[0].status = "done";
    task.work_packages[0].evidence_refs = ["forged:reference"];
    task.current_work_package = null;
    task.hermes_phase = "review";
    writeTask(taskDir, task);
    const audit = run(root, "audit", "--no-report");
    expect(audit.status).toBe(1);
    expect(audit.stdout).toContain("invalid evidence refs");
  });

  it("does not dispose another package while one is current", () => {
    expect(planTwoExplicitPackages(root).status).toBe(0);
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
    expect(planTwoExplicitPackages(root).status).toBe(0);
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
    expect(planTwoExplicitPackages(root).status).toBe(0);
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

  it("refuses close while a dispatch result is still unconfirmed", () => {
    expect(plan(root, ["Result A"]).status).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    completeCurrent(root);
    expect(
      runDispatch(
        root,
        "create",
        "--job-id",
        "job-unconfirmed",
        "--role",
        "reviewer",
        "--profile",
        "closure",
        "--objective",
        "Review closure readiness",
      ).status,
    ).toBe(0);
    const result = run(root, "close");
    expect(result.status).toBe(1);
    expect(result.stdout).toContain("unconfirmed dispatch job-unconfirmed");
    expect(readTask(taskDir).closure_state).toBe("open");
  });

  it("refuses archive before closure", () => {
    expect(plan(root, ["Result A"]).status).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    const result = runTask(root, "archive", "demo", "--no-commit");
    expect(result.status).toBe(1);
    expect(result.stderr).toContain("closure task is not closed");
    expect(fs.existsSync(taskDir)).toBe(true);
  });

  it("updates a handoff before an open task session finishes", () => {
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

  it("writes handoffs from validated task results only", () => {
    expect(plan(root, ["Result A"]).status).toBe(0);
    fs.mkdirSync(path.join(taskDir, "hermes", "dispatches"), { recursive: true });
    fs.mkdirSync(path.join(root, "src"), { recursive: true });
    fs.writeFileSync(path.join(root, "src", "owned.ts"), "export {};\n");
    fs.writeFileSync(path.join(root, "src", "forged.ts"), "export {};\n");
    fs.writeFileSync(path.join(root, "unrelated.txt"), "other task change\n");
    const task = readTask(taskDir);
    writeTask(taskDir, { ...task, confirmed_dispatches: ["job-1"] });
    const confirmedResult = {
      job_id: "job-1",
      task_revision: task.hermes_revision,
      status: "success",
      confirmed: true,
      changed_files: ["src/owned.ts"],
    };
    fs.writeFileSync(
      path.join(taskDir, "hermes", "dispatches", "job-1.dispatch.json"),
      `${JSON.stringify({
        job_id: "job-1",
        hermes_revision: task.hermes_revision,
        confirmed_revision: task.hermes_revision,
        result_sha256: resultSha256(confirmedResult),
        status: "confirmed",
      })}\n`,
    );
    fs.writeFileSync(
      path.join(taskDir, "hermes", "dispatches", "job-1.result.json"),
      `${JSON.stringify({ ...confirmedResult, changed_files: ["src/forged.ts"] })}\n`,
    );
    fs.writeFileSync(
      path.join(taskDir, "hermes", "dispatches", "forged.result.json"),
      `${JSON.stringify({
        job_id: "forged",
        status: "success",
        confirmed: true,
        changed_files: ["src/forged.ts"],
      })}\n`,
    );

    expect(run(root, "handoff").status).toBe(0);
    const handoff = fs.readFileSync(path.join(taskDir, "HANDOFF.md"), "utf-8");
    expect(handoff).toContain("# Task Handoff");
    expect(handoff).not.toContain("- src/owned.ts");
    expect(handoff).not.toContain("src/forged.ts");
    expect(handoff).not.toContain("unrelated.txt");
    expect(handoff).toContain("job-1: confirmed result integrity check failed");
  });


  it("derives next action from current closure state instead of stale task text", () => {
    expect(plan(root, ["Result A"]).status).toBe(0);
    const task = readTask(taskDir);
    writeTask(taskDir, { ...task, next_action: "obsolete action" });
    const result = run(root, "next");
    expect(result.status).toBe(0);
    expect(result.stdout).toContain("Run closure.py validate.");
    expect(result.stdout).not.toContain("obsolete action");

    const status = run(root, "status", "--json");
    expect(status.status).toBe(0);
    expect(JSON.parse(status.stdout).next_action).toContain("Run closure.py validate.");
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

  it("warns when lean closure runs without a context hook", () => {
    expect(plan(root, ["Result A"]).status).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    const result = spawnSync(
      PYTHON,
      [".trellis/scripts/closure.py", "audit", "--task", "demo", "--no-report"],
      {
        cwd: root,
        encoding: "utf-8",
        env: { ...process.env, TRELLIS_HOOKS: "0" },
      },
    );
    expect(result.stdout).toContain("warnings:");
    expect(result.stdout).toContain("validated dispatch");
  });

  it("repairs only the first gap and preserves completed packages", () => {
    expect(planTwoExplicitPackages(root).status).toBe(0);
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
    expect(planTwoExplicitPackages(root).status).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    completeCurrent(root, "test:a");
    expect(run(root, "audit", "--no-report").status).toBe(1);
    expect(run(root, "repair").status).toBe(1);
    expect(run(root, "package-check").status).toBe(0);
    expect(run(root, "package-done", "--evidence", materializeEvidence(root, "test-b")).status).toBe(0);
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
    expect(task.research_route).toBe("exploration");
    expect(task.research_change_fields).toEqual(["dataset"]);
    expect(task.grill_completed).toBe(false);
    expect(run(root, "validate").status).toBe(1);
    const decisionRef = writeDecisionRecord(taskDir);
    expect(
      run(root, "grill", "--complete", "--decision-ref", decisionRef).status,
    ).toBe(0);
    expect(run(root, "validate").status).toBe(0);
  });

  it("preserves the completed decision until a research amendment is applied", () => {
    expect(
      plan(root, ["Research result is verified"], [
        "--route",
        "exploration",
        "--research-change",
        "dataset",
      ]).status,
    ).toBe(0);
    const decisionRef = writeDecisionRecord(taskDir);
    expect(
      run(root, "grill", "--complete", "--decision-ref", decisionRef).status,
    ).toBe(0);
    expect(run(root, "validate").status).toBe(0);

    const taskWithInvalidNestedTarget = readTask(taskDir);
    taskWithInvalidNestedTarget.meta.research_contract = { dataset: "dataset-v1" };
    writeTask(taskDir, taskWithInvalidNestedTarget);

    const denied = run(
      root,
      "amend",
      "--field",
      "split",
      "--value",
      "split-v2",
      "--reason",
      "unapproved split change",
    );
    expect(denied.status).toBe(1);
    expect(readTask(taskDir)).toMatchObject({
      decision_ref: decisionRef,
      grill_completed: true,
    });

    const invalid = run(
      root,
      "amend",
      "--field",
      "dataset.version",
      "--value",
      "v2",
      "--reason",
      "invalid nested dataset change",
      "--approved-by",
      "human/root",
    );
    expect(invalid.status).toBe(1);
    expect(readTask(taskDir)).toMatchObject({
      decision_ref: decisionRef,
      grill_completed: true,
    });

    const approved = run(
      root,
      "amend",
      "--field",
      "split",
      "--value",
      "split-v2",
      "--reason",
      "approved split change",
      "--approved-by",
      "human/root",
    );
    expect(approved.status).toBe(0);
    expect(readTask(taskDir)).toMatchObject({
      decision_ref: null,
      grill_completed: false,
    });
  });

  it("treats functional model architecture changes as high risk", () => {
    expect(plan(root, ["Result A"]).status).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    const denied = run(
      root,
      "amend",
      "--field",
      "model_architecture",
      "--value",
      "new functional encoder",
      "--reason",
      "new model behavior",
    );
    expect(denied.status).toBe(1);
    expect(denied.stderr).toContain(
      "high-risk change model_architecture requires --approved-by human/root",
    );
    expect(readTask(taskDir).hermes_phase).toBe("blocked");
  });

  it("blocks an approved model architecture amendment and requires a new exploration task", () => {
    expect(plan(root, ["Result A"]).status).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    const result = run(
      root,
      "amend",
      "--field",
      "model_architecture",
      "--value",
      "new functional encoder",
      "--reason",
      "new model behavior",
      "--approved-by",
      "human/root",
    );
    expect(result.status).toBe(1);
    expect(result.stderr).toContain("independent exploration task");
    const task = readTask(taskDir);
    expect(task.hermes_phase).toBe("blocked");
    expect(task.status).toBe("in_progress");
    expect(task.research_route).toBe("exploration");
    expect(task.research_change_fields).toEqual(["model_architecture"]);
    expect(task.grill_completed).toBe(false);
    expect(
      (task.meta.research_contract as Record<string, unknown> | undefined)
        ?.model_architecture,
    ).toBeUndefined();
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

  it("refuses archive when closure fields are forged without a close event", () => {
    expect(plan(root, ["Lean result verified"]).status).toBe(0);
    const evidence = materializeEvidence(root, "forged-archive");
    const forged = readTask(taskDir) as TestTask & {
      work_packages: (TestWorkPackage & { evidence_refs: string[] })[];
    };
    forged.status = "completed";
    forged.hermes_phase = "closed";
    forged.closure_state = "closed";
    forged.current_work_package = null;
    forged.work_packages[0].status = "done";
    forged.work_packages[0].evidence_refs = [evidence];
    writeTask(taskDir, forged);

    const archive = runTask(root, "archive", "demo", "--no-commit");
    expect(archive.status).toBe(1);
    expect(archive.stderr).toContain("task_closed event is missing");
    expect(fs.existsSync(taskDir)).toBe(true);
  });

  it("rolls back task state when recording the close event fails", () => {
    expect(plan(root, ["Lean result verified"]).status).toBe(0);
    expect(run(root, "validate").status).toBe(0);
    completeCurrent(root, "pnpm test:pass");

    const beforeClose = readTask(taskDir);
    const eventPath = path.join(taskDir, "hermes", "task-events.jsonl");
    fs.rmSync(eventPath);
    fs.mkdirSync(eventPath);

    const result = run(root, "close");
    expect(result.status).toBe(1);
    expect(result.stderr).toContain("failed to read task event log");

    const afterFailure = readTask(taskDir);
    expect(afterFailure.status).toBe(beforeClose.status);
    expect(afterFailure.hermes_phase).toBe(beforeClose.hermes_phase);
    expect(afterFailure.closure_state).toBe(beforeClose.closure_state);
    expect(afterFailure.current_work_package).toBe(beforeClose.current_work_package);
    expect(afterFailure.hermes_revision).toBe(beforeClose.hermes_revision);
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
    recordHookHeartbeat(root);
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
