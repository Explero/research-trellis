import { describe, expect, it } from "vitest";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  scriptsInit,
  commonInit,
  commonPaths,
  commonDeveloper,
  commonGitContext,
  commonTaskQueue,
  commonTaskUtils,
  commonActiveTask,
  commonCliAdapter,
  commonWorktreeSync,
  getDeveloperScript,
  initDeveloperScript,
  taskScript,
  getContextScript,
  addSessionScript,
  workflowMdTemplate,
  gitignoreTemplate,
  getAllScripts,
  getAllHermesTemplates,
} from "../../src/templates/trellis/index.js";

function cliRoot(): string {
  if (fs.existsSync(path.join(process.cwd(), "src", "templates"))) {
    return process.cwd();
  }
  return path.join(process.cwd(), "packages", "cli");
}

function readTemplateFile(relativePath: string): string {
  return fs.readFileSync(
    path.join(cliRoot(), "src", "templates", ...relativePath.split("/")),
    "utf-8",
  );
}

function templateDir(relativePath: string): string {
  return path.join(cliRoot(), "src", "templates", ...relativePath.split("/"));
}

function writeProjectFile(root: string, relativePath: string, content: string): void {
  const target = path.join(root, ...relativePath.split("/"));
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, content, "utf-8");
}

function writeTaskRuntime(root: string, options: { omitHermesExperiment?: boolean } = {}): void {
  for (const [relativePath, content] of getAllScripts()) {
    if (options.omitHermesExperiment && relativePath === "hermes/experiment.py") {
      continue;
    }
    writeProjectFile(root, `.trellis/scripts/${relativePath}`, content);
  }
  writeProjectFile(
    root,
    ".trellis/.developer",
    "name=test-dev\ninitialized_at=2026-07-01T00:00:00\n",
  );
  writeProjectFile(root, ".trellis/workflow.md", "# Workflow\n");
}

function runTask(root: string, args: string[]) {
  return spawnSync(
    "python3",
    [path.join(root, ".trellis", "scripts", "task.py"), ...args],
    {
      cwd: root,
      encoding: "utf-8",
    },
  );
}

function findTaskDir(root: string, slug: string): string {
  const tasksRoot = path.join(root, ".trellis", "tasks");
  const match = fs
    .readdirSync(tasksRoot)
    .find((entry) => entry.endsWith(`-${slug}`) || entry === slug);
  if (!match) {
    throw new Error(`task directory not found for slug ${slug}`);
  }
  return path.join(tasksRoot, match);
}

// =============================================================================
// Template Constants — module-level string exports
// =============================================================================

describe("trellis template constants", () => {
  const allTemplates = {
    scriptsInit,
    commonInit,
    commonPaths,
    commonDeveloper,
    commonGitContext,
    commonTaskQueue,
    commonTaskUtils,
    commonActiveTask,
    commonCliAdapter,
    commonWorktreeSync,
    getDeveloperScript,
    initDeveloperScript,
    taskScript,
    getContextScript,
    addSessionScript,
    workflowMdTemplate,
    gitignoreTemplate,
  };

  function inProgressBreadcrumb(): string {
    const inProgressMatch =
      /\[workflow-state:in_progress\]([\s\S]*?)\[\/workflow-state:in_progress\]/.exec(
        workflowMdTemplate,
      );
    if (!inProgressMatch) {
      throw new Error("in_progress breadcrumb block must exist in workflow.md");
    }
    return inProgressMatch[1];
  }

  function workflowStateBreadcrumb(status: string): string {
    const match = new RegExp(
      `\\[workflow-state:${status}\\]([\\s\\S]*?)\\[/workflow-state:${status}\\]`,
    ).exec(workflowMdTemplate);
    if (!match) {
      throw new Error(`${status} breadcrumb block must exist in workflow.md`);
    }
    return match[1];
  }

  function stepSection(step: string): string {
    const pattern = new RegExp(
      `#### ${step.replace(".", "\\.")}[^\\n]*\\n([\\s\\S]*?)(?=\\n#### |\\n### |$)`,
    );
    const match = pattern.exec(workflowMdTemplate);
    if (!match) {
      throw new Error(`workflow.md step ${step} must exist`);
    }
    return match[1];
  }

  it("all templates are non-empty strings", () => {
    for (const [name, content] of Object.entries(allTemplates)) {
      expect(content.length, `${name} should be non-empty`).toBeGreaterThan(0);
    }
  });

  it("Python scripts contain valid Python syntax indicators", () => {
    // scriptsInit (__init__.py) only has docstrings, so use scripts with actual code
    const pyScripts = [
      commonInit,
      commonPaths,
      commonActiveTask,
      getDeveloperScript,
      taskScript,
    ];
    for (const script of pyScripts) {
      expect(
        script.includes("import") ||
          script.includes("def ") ||
          script.includes("class ") ||
          script.includes("#"),
      ).toBe(true);
    }
  });

  it("scriptsInit is a Python docstring module", () => {
    expect(scriptsInit).toContain('"""');
  });

  it("workflowMdTemplate is markdown", () => {
    expect(workflowMdTemplate).toContain("#");
  });

  it("marketplace native workflow mirror matches the bundled workflow", () => {
    const repoRoot = fs.existsSync(path.join(process.cwd(), "marketplace"))
      ? process.cwd()
      : path.resolve(process.cwd(), "../..");
    const marketplaceNative = fs.readFileSync(
      path.join(repoRoot, "marketplace/workflows/native/workflow.md"),
      "utf-8",
    );
    expect(marketplaceNative).toBe(workflowMdTemplate);
  });

  it("marketplace TDD workflow planning breadcrumbs include behavior gates", () => {
    const repoRoot = fs.existsSync(path.join(process.cwd(), "marketplace"))
      ? process.cwd()
      : path.resolve(process.cwd(), "../..");
    const tddWorkflow = fs.readFileSync(
      path.join(repoRoot, "marketplace/workflows/tdd/workflow.md"),
      "utf-8",
    );
    const planning =
      /\[workflow-state:planning\]([\s\S]*?)\[\/workflow-state:planning\]/.exec(
        tddWorkflow,
      )?.[1];
    const planningInline =
      /\[workflow-state:planning-inline\]([\s\S]*?)\[\/workflow-state:planning-inline\]/.exec(
        tddWorkflow,
      )?.[1];

    for (const block of [planning, planningInline]) {
      expect(block).toContain("observable behavior slices");
      expect(block).toContain("public interface under test");
      expect(block).toContain("mock boundaries");
    }
  });

  it("[issue-225] workflow.md in_progress breadcrumb has class-2 sub-agent dispatch protocol", () => {
    // The in_progress breadcrumb instructs the main agent to prefix
    // dispatch prompts with "Active task: <path>" on class-2 platforms.
    // Without this line, codex/copilot/gemini/qoder sub-agents cannot
    // find the active task (no PreToolUse hook to inject context).
    const block = inProgressBreadcrumb();
    expect(block).toContain("Active task:");
    expect(block.toLowerCase()).toContain("class-2");
    expect(block).toMatch(/codex|copilot|gemini|qoder/);
  });

  it("[issue-237] workflow.md in_progress breadcrumb self-exempts implement/check sub-agents", () => {
    // The in_progress breadcrumb may be injected into sub-agent turns on some
    // hosts, so its main-session dispatch guidance must not recursively apply
    // to a sub-agent that is already doing the requested work.
    const block = inProgressBreadcrumb();
    expect(block).toContain("Main-session default");
    expect(block).toContain("Sub-agent self-exemption");
    expect(block).toContain("already running as `trellis-implement`");
    expect(block).toContain("do NOT spawn another `trellis-implement`");
    expect(block).toContain("already running as `trellis-check`");
    expect(block).toContain("do NOT spawn another `trellis-check`");
    expect(block).toContain("main session only");
  });

  it("workflow.md in_progress breadcrumb records optional review gates and final verification reachability", () => {
    const block = inProgressBreadcrumb();
    expect(block).toContain("optional review gates");
    expect(block).toContain("trellis-merge-review");
    expect(block).toContain("Review-gate contract: explicit-selection-v1");
    expect(block).toContain("Optional review gates status: configured");
    expect(block).toContain("trellis-check");
    expect(block).toContain("merge if needed");
    expect(block).toContain("build/test");
    expect(block).toContain("trellis-code-architecture-review");
    expect(block).toContain("does not by itself enable or block deep-review");
  });

  it("[issue-237] workflow.md Phase 2 dispatch steps require prompt recursion guards", () => {
    expect(workflowMdTemplate).toContain("**Dispatch prompt guard**");
    expect(workflowMdTemplate).toContain(
      "already the `trellis-implement` sub-agent",
    );
    expect(workflowMdTemplate).toContain(
      "not spawn another `trellis-implement` / `trellis-check`",
    );
    expect(workflowMdTemplate).toContain(
      "already the `trellis-check` sub-agent",
    );
    expect(workflowMdTemplate).toContain(
      "not spawn another `trellis-check` / `trellis-implement`",
    );
    expect(workflowMdTemplate).toContain(
      "`trellis-implement` carries `permissionMode: acceptEdits`",
    );
    expect(workflowMdTemplate).toContain(
      "host-constrained mode such as `auto`",
    );
  });

  it("workflow.md documents parent child task tree responsibilities", () => {
    expect(workflowMdTemplate).toContain("### Parent / Child Task Trees");
    expect(workflowMdTemplate).toContain(
      "several independently verifiable deliverables",
    );
    expect(workflowMdTemplate).toContain(
      "Parent/child structure is not a dependency system",
    );
    expect(workflowMdTemplate).toContain("--parent <parent-dir>");
    expect(workflowMdTemplate).toContain(
      "task.py add-subtask <parent> <child>",
    );
    expect(workflowMdTemplate).toContain(
      "start the child that owns the next independently verifiable deliverable",
    );
  });

  it("workflow.md step 1.1 includes parent child split guidance", () => {
    const step = stepSection("1.1");
    expect(step).toContain("When considering a parent/child split");
    expect(step).toContain("Parent tasks own source requirements");
    expect(step).toContain("Child tasks own actual deliverables");
    expect(step).toContain("Parent/child structure is not a dependency system");
    expect(step).toContain("Do not start the parent unless");
    expect(step).toContain("A.` / `B.` / `C.`");
    expect(step).toContain("task-local review-gate 选择");
    expect(step).toContain("Review-gate contract: explicit-selection-v1");
    expect(step).toContain("Optional review gates status: pending");
    expect(step).toContain("Optional review gates status: configured");
    expect(step).toContain("legacy task");
    expect(step).toContain("trellis-check");
    expect(step).toContain("pre-development architecture guidance");
    expect(step).toContain("trellis-code-architecture-review");
    expect(step).toContain(
      "不会隐式开启 `trellis-improve-codebase-architecture` deep-review",
    );
  });

  it("workflow.md planning breadcrumb keeps requirement clarification before strategy decisions on Claude Code path", () => {
    const planning = workflowStateBreadcrumb("planning");
    expect(planning).toContain("trellis-grill-me");
    expect(planning).toContain("development strategy decision");
    expect(planning).toContain(
      "`trellis-grill-me` is a required planning gate",
    );
    expect(planning).toContain("Before `trellis-grill-me` is complete");
    expect(planning).toContain("do not enter development strategy decisions");
    expect(planning).toContain(
      "do not create or complete `design.md` / `implement.md`",
    );
    expect(planning).toContain("do not run `task.py start`");
    expect(planning).toContain(
      "Do not enter development strategy decisions until `prd.md` has been tightened",
    );
  });

  it("workflow.md planning breadcrumb records Claude Code development strategy decisions before start", () => {
    const planning = workflowStateBreadcrumb("planning");
    expect(planning).toContain("development mode");
    expect(planning).toContain("branch vs worktree");
    expect(planning).toContain("./.trellis/trellis-worktrees/<task-dir-name>");
    expect(planning).toContain("trellis-tdd");
    expect(planning).toContain("A.` / `B.` / `C.`");
    expect(planning).toContain("trellis-merge-review");
    expect(planning).toContain("Review-gate contract: explicit-selection-v1");
    expect(planning).toContain("Optional review gates status: pending");
    expect(planning).toContain("Optional review gates status: configured");
    expect(planning).toContain("Enabled optional review gates:");
    expect(planning).toContain("Disabled optional review gates:");
    expect(planning).toContain("pre-development architecture guidance");
    expect(planning).toContain("trellis-code-architecture-review");
    expect(planning).toContain(
      "do NOT implicitly enable `trellis-improve-codebase-architecture` deep-review",
    );
  });

  it("workflow.md step 2.2 explains selected review gates and preserved order", () => {
    const step = stepSection("2.2");
    expect(step).toContain("按任务策略运行显式选中的 review gate");
    expect(step).toContain("trellis-spec-review");
    expect(step).toContain("trellis-code-review");
    expect(step).toContain("trellis-code-architecture-review");
    expect(step).toContain("trellis-improve-codebase-architecture");
    expect(step).toContain("trellis-merge-review");
    expect(step).toContain("Review-gate contract: explicit-selection-v1");
    expect(step).toContain("Optional review gates status: configured");
    expect(step).toContain("legacy task");
    expect(step).toContain("任务策略无效");
    expect(step).toContain(
      "Do not advance to the next gate until the previous gate passes",
    );
    expect(step).toContain(
      "the main agent fixes the blocking issues and re-runs the same gate",
    );
    expect(step).toContain("more than 3 times in a row");
    expect(step).toContain("ask whether to skip the current review gate");
  });

  it("gitignoreTemplate contains ignore patterns", () => {
    expect(gitignoreTemplate).toContain(".developer");
    expect(gitignoreTemplate).toContain("trellis-worktrees/");
    expect(gitignoreTemplate).toContain("__pycache__");
  });

  it("Hermes templates provide research config, state machine, roles, and record conventions", () => {
    const config = readTemplateFile("trellis/hermes/config.yaml");
    const stateMachine = readTemplateFile("trellis/hermes/state_machine.yaml");
    const recordsReadme = readTemplateFile("trellis/hermes/records/README.md");
    const recordBus = readTemplateFile("trellis/hermes/records/recordbus.md");
    const subagentProtocol = readTemplateFile(
      "trellis/hermes/records/subagent_protocol.md",
    );
    const reportTemplate = readTemplateFile("trellis/hermes/reports/report.md");
    const ledgersReadme = readTemplateFile("trellis/hermes/ledgers/README.md");
    const metricsSchema = readTemplateFile("trellis/hermes/metrics/metrics_schema.yaml");
    const roleFiles = [
      "scientist.md",
      "coder.md",
      "runner.md",
      "evaluator.md",
      "reviewer.md",
      "literature.md",
      "evidence-curator.md",
      "claim-reviewer.md",
    ];

    expect(config).toContain("hermes_version");
    expect(config).toContain('records_dir: ".trellis/tasks/{task}/hermes"');
    expect(config).toContain(
      'state_machine_file: ".trellis/hermes/state_machine.yaml"',
    );
    expect(config).toContain("artifact_ledger");
    expect(config).toContain("provenance_ledger");
    expect(config).toContain("audit_ledger");
    expect(config).toContain("service_queue");
    expect(config).toContain("metrics_schema");
    expect(config).toContain("approval_records");
    expect(config).toContain('experiment: ".trellis/tasks/{task}/hermes/experiment.yaml"');
    expect(config).toContain('run_manifest: ".trellis/tasks/{task}/hermes/run_manifest.jsonl"');
    expect(config).toContain("sandbox:");
    expect(config).toContain('mode: "none"');
    expect(config).toContain("required: false");
    expect(config).toContain("heartbeat_beat");
    expect(config).toContain("heartbeat_watch");
    expect(config).toContain("runner_run");
    expect(config).toContain("runner_replay");
    expect(config).toContain("validate_run_manifest");
    expect(config).toContain("compare_records");
    expect(config).toContain("aggregate");
    expect(config).toContain("claim_review");
    expect(config).toContain("quality_gate");
    expect(config).toContain("service_enqueue");
    expect(config).toContain("service_cancel");
    expect(config).toContain("append-only");
    expect(config).toContain("deployment candidate hardening");
    expect(config).toContain("not an OS sandbox");
    expect(config).not.toContain("claim_allowed");

    for (const state of [
      "planning",
      "running",
      "review",
      "claim_ready",
      "approved",
    ]) {
      expect(stateMachine).toContain(state);
    }
    expect(stateMachine).toContain(
      "planning -> running -> review -> claim_ready -> approved",
    );
    expect(stateMachine).toContain("human approval record");

    for (const roleFile of roleFiles) {
      const role = readTemplateFile(`trellis/hermes/roles/${roleFile}`);
      expect(role).toContain("Responsibilities");
      expect(role).toContain("Must not");
      expect(role).toContain("worker_records.jsonl");
      expect(role).toContain("HumanGate");
    }

    const ledgerFiles = fs.readdirSync(templateDir("trellis/hermes/ledgers"));
    expect(ledgerFiles).toContain(".gitkeep");
    expect(ledgerFiles.filter((file) => file.endsWith(".jsonl"))).toEqual([]);
    expect(ledgersReadme).toContain("append-only");
    expect(ledgersReadme).toContain("evidence");
    expect(ledgersReadme).toContain("claim");
    expect(ledgersReadme).toContain("approval");
    expect(ledgersReadme).toContain("artifact");
    expect(ledgersReadme).toContain("HumanGate");

    expect(metricsSchema).toContain("metrics:");
    expect(metricsSchema).toContain("name:");
    expect(metricsSchema).toContain("direction:");
    expect(metricsSchema).toContain("unit:");
    expect(metricsSchema).toContain("aggregation:");
    expect(metricsSchema).toContain("split:");
    expect(metricsSchema).toContain("baseline:");
    expect(metricsSchema).toContain("baseline_version:");
    expect(metricsSchema).toContain("split_version:");
    expect(metricsSchema).toContain("HumanGate");

    expect(recordsReadme).toContain(".trellis/tasks/<task>/hermes/");
    expect(recordsReadme).toContain("Global");
    expect(recordsReadme).toContain("schema");
    expect(recordsReadme).toContain("conventions");
    expect(recordsReadme).toContain("worker_records.jsonl");
    expect(recordsReadme).toContain("provenance_ledger.jsonl");
    expect(recordsReadme).toContain("audit_ledger.jsonl");
    expect(recordsReadme).toContain("service_queue.jsonl");
    expect(recordsReadme).toContain("experiment.yaml");
    expect(recordsReadme).toContain("run_manifest.jsonl");
    expect(recordsReadme).toContain("JSONL");
    expect(recordsReadme).toContain("not tamper-proof");
    expect(recordsReadme).not.toContain("reviews/");
    expect(recordsReadme).not.toContain("subagent_records/");

    expect(recordBus).toContain("RecordBus");
    expect(recordBus).toContain("task_card");
    expect(recordBus).toContain("allowed_files");
    expect(recordBus).toContain("forbidden_files");
    expect(recordBus).toContain("heartbeat");
    expect(recordBus).toContain("checkpoint");
    expect(recordBus).toContain("result");
    expect(recordBus).toContain("risk");
    expect(recordBus).toContain("rejection");
    expect(recordBus).toContain("artifact_refs");
    expect(recordBus).toContain("command_refs");
    expect(recordBus).toContain("compare");
    expect(recordBus).toContain("claim-review");
    expect(recordBus).toContain("quality-gate");
    expect(recordBus).toContain("provenance");
    expect(recordBus).toContain("audit");
    expect(recordBus).toContain("service queue");
    expect(recordBus).toContain("not an OS sandbox");
    expect(recordBus).toContain("report.md");
    expect(recordBus).toContain("HumanGate");

    expect(reportTemplate).toContain("## Problem");
    expect(reportTemplate).toContain("## Method");
    expect(reportTemplate).toContain("## Data");
    expect(reportTemplate).toContain("## Metrics");
    expect(reportTemplate).toContain("## Results");
    expect(reportTemplate).toContain("## Core Conclusions");
    expect(reportTemplate).toContain("claim:");
    expect(reportTemplate).toContain("evidence:");
    expect(reportTemplate).toContain("claim_ready");

    const evaluator = readTemplateFile("trellis/hermes/roles/evaluator.md");
    expect(evaluator).toContain("Must not modify source files");
    expect(evaluator).toContain("Must not modify metrics, split, or baseline");
    const reviewer = readTemplateFile("trellis/hermes/roles/reviewer.md");
    expect(reviewer).toContain("only read the current diff, records, evidence");
    expect(reviewer).toContain("Must not inherit coder long conversation");

    expect(subagentProtocol).toContain("main agent");
    expect(subagentProtocol).toContain("supervisor");
    expect(subagentProtocol).toContain("bounded worker");
    expect(subagentProtocol).toContain("HumanGate");
    expect(subagentProtocol).toContain("allowed_files");
    expect(subagentProtocol).toContain("forbidden_files");
    expect(subagentProtocol).toContain("stalled");
    expect(subagentProtocol).toContain("resume_from");
    expect(subagentProtocol).toContain("one active writer");
  });

  it("getAllHermesTemplates exposes files needed by init and update", () => {
    const templateRoot = templateDir("trellis/hermes");
    const templateKeys = [
      "config.yaml",
      "state_machine.yaml",
      "roles/scientist.md",
      "roles/coder.md",
      "roles/runner.md",
      "roles/evaluator.md",
      "roles/reviewer.md",
      "roles/literature.md",
      "roles/evidence-curator.md",
      "roles/claim-reviewer.md",
      "records/README.md",
      "records/recordbus.md",
      "records/subagent_protocol.md",
      "reports/report.md",
      "ledgers/README.md",
      "ledgers/.gitkeep",
      "metrics/metrics_schema.yaml",
      "experiments/README.md",
      "experiments/experiment.yaml",
    ];

    for (const key of templateKeys) {
      expect(fs.existsSync(path.join(templateRoot, ...key.split("/")))).toBe(true);
    }

    const templates = getAllHermesTemplates();
    expect(templates.get("config.yaml")).toContain("append-only-records");
    expect(templates.get("state_machine.yaml")).toContain("claim_ready");
    expect(templates.get("metrics/metrics_schema.yaml")).toContain("HumanGate");
    expect(templates.get("reports/report.md")).toContain("Core Conclusions");
  });
});

// =============================================================================
// task.py Hermes lifecycle integration
// =============================================================================

describe("task.py Hermes lifecycle", () => {
  it("initializes a task-scoped Hermes experiment after create", () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "trellis-task-hermes-"));
    try {
      writeTaskRuntime(root);

      const result = runTask(root, [
        "create",
        "Hermes task",
        "--slug",
        "hermes-task",
        "--assignee",
        "test-dev",
      ]);

      expect(result.status, result.stderr).toBe(0);
      const taskDir = findTaskDir(root, "hermes-task");
      const taskName = path.basename(taskDir);
      const experimentPath = path.join(taskDir, "hermes", "experiment.yaml");
      const runManifestPath = path.join(taskDir, "hermes", "run_manifest.jsonl");
      const workerRecordsPath = path.join(taskDir, "hermes", "worker_records.jsonl");

      expect(fs.existsSync(experimentPath)).toBe(true);
      expect(fs.existsSync(runManifestPath)).toBe(true);
      expect(fs.existsSync(workerRecordsPath)).toBe(true);
      expect(fs.readFileSync(workerRecordsPath, "utf-8")).toBe("");
      expect(fs.readFileSync(experimentPath, "utf-8")).toContain(
        `artifact_dir: ".trellis/tasks/${taskName}/hermes/runs"`,
      );
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });

  it("keeps task create working when the Hermes experiment script is absent", () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "trellis-task-hermes-"));
    try {
      writeTaskRuntime(root, { omitHermesExperiment: true });

      const result = runTask(root, [
        "create",
        "Plain task",
        "--slug",
        "plain-task",
        "--assignee",
        "test-dev",
      ]);

      expect(result.status, result.stderr).toBe(0);
      expect(fs.existsSync(findTaskDir(root, "plain-task"))).toBe(true);
      expect(result.stderr).not.toContain("Hermes");
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });

  it("initializes missing Hermes experiment files before task start for legacy tasks", () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "trellis-task-hermes-"));
    try {
      writeTaskRuntime(root);
      const taskDir = path.join(root, ".trellis", "tasks", "01-legacy-task");
      writeProjectFile(
        root,
        ".trellis/tasks/01-legacy-task/task.json",
        JSON.stringify(
          {
            title: "Legacy Task",
            status: "planning",
            package: null,
          },
          null,
          2,
        ),
      );

      const result = spawnSync(
        "python3",
        [
          path.join(root, ".trellis", "scripts", "task.py"),
          "start",
          ".trellis/tasks/01-legacy-task",
        ],
        {
          cwd: root,
          encoding: "utf-8",
          env: { ...process.env, TRELLIS_CONTEXT_ID: "test-session" },
        },
      );

      expect(result.status, result.stderr).toBe(0);
      expect(fs.existsSync(path.join(taskDir, "hermes", "experiment.yaml"))).toBe(true);
      expect(fs.existsSync(path.join(taskDir, "hermes", "run_manifest.jsonl"))).toBe(true);
      expect(fs.existsSync(path.join(taskDir, "hermes", "worker_records.jsonl"))).toBe(true);
      const taskJson = JSON.parse(
        fs.readFileSync(path.join(taskDir, "task.json"), "utf-8"),
      ) as { status: string };
      expect(taskJson.status).toBe("in_progress");
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });

  it("blocks task start when Hermes experiment validation fails", () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "trellis-task-hermes-"));
    try {
      writeTaskRuntime(root);
      const taskDir = path.join(root, ".trellis", "tasks", "01-bad-hermes");
      writeProjectFile(
        root,
        ".trellis/tasks/01-bad-hermes/task.json",
        JSON.stringify(
          {
            title: "Bad Hermes",
            status: "planning",
            package: null,
          },
          null,
          2,
        ),
      );
      fs.mkdirSync(path.join(taskDir, "hermes"), { recursive: true });
      fs.writeFileSync(
        path.join(taskDir, "hermes", "experiment.yaml"),
        [
          'question: ""',
          'hypothesis: "test"',
          'dataset: "fixture"',
          'model: "runner"',
          "metrics:",
          '  - "exit_code"',
          "seed: 1",
          "environment:",
          '  os: "ubuntu-24.04"',
          "allowed_commands:",
          '  - "python3"',
          'artifact_dir: ".trellis/tasks/01-bad-hermes/hermes/runs"',
          "",
        ].join("\n"),
        "utf-8",
      );

      const result = runTask(root, ["start", ".trellis/tasks/01-bad-hermes"]);

      expect(result.status).toBe(1);
      expect(result.stderr).toContain("Hermes experiment validation failed");
      expect(result.stderr).toContain("question must be a non-empty string");
      const taskJson = JSON.parse(
        fs.readFileSync(path.join(taskDir, "task.json"), "utf-8"),
      ) as { status: string };
      expect(taskJson.status).toBe("planning");
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });
});

// =============================================================================
// getAllScripts — pure function assembling pre-loaded strings
// =============================================================================

describe("getAllScripts", () => {
  it("returns a Map", () => {
    const scripts = getAllScripts();
    expect(scripts).toBeInstanceOf(Map);
  });

  it("contains expected script entries", () => {
    const scripts = getAllScripts();
    expect(scripts.has("__init__.py")).toBe(true);
    expect(scripts.has("common/__init__.py")).toBe(true);
    expect(scripts.has("common/paths.py")).toBe(true);
    expect(scripts.has("common/active_task.py")).toBe(true);
    expect(scripts.has("common/worktree_sync.py")).toBe(true);
    expect(scripts.has("hermes/__init__.py")).toBe(true);
    expect(scripts.has("hermes/runtime.py")).toBe(true);
    expect(scripts.has("hermes/record.py")).toBe(true);
    expect(scripts.has("hermes/validate.py")).toBe(true);
    expect(scripts.has("hermes/guard.py")).toBe(true);
    expect(scripts.has("hermes/jobs.py")).toBe(true);
    expect(scripts.has("hermes/heartbeat.py")).toBe(true);
    expect(scripts.has("hermes/experiment.py")).toBe(true);
    expect(scripts.has("hermes/runner.py")).toBe(true);
    expect(scripts.has("hermes/report.py")).toBe(true);
    expect(scripts.has("hermes/service.py")).toBe(true);
    expect(scripts.has("task.py")).toBe(true);
    expect(scripts.has("get_developer.py")).toBe(true);
  });

  it("does not include Python cache artifacts in script entries", () => {
    const scripts = getAllScripts();
    for (const key of scripts.keys()) {
      expect(key).not.toContain("__pycache__");
      expect(key.endsWith(".pyc")).toBe(false);
    }
  });

  it("has at least one entry", () => {
    const scripts = getAllScripts();
    expect(scripts.size).toBeGreaterThan(0);
  });

  it("all values are non-empty strings", () => {
    const scripts = getAllScripts();
    for (const [key, value] of scripts) {
      expect(value.length, `${key} should be non-empty`).toBeGreaterThan(0);
    }
  });

  it("values match the exported constants", () => {
    const scripts = getAllScripts();
    expect(scripts.get("__init__.py")).toBe(scriptsInit);
    expect(scripts.get("common/__init__.py")).toBe(commonInit);
    expect(scripts.get("task.py")).toBe(taskScript);
  });

  it("does not contain multi_agent entries", () => {
    const scripts = getAllScripts();
    for (const [key] of scripts) {
      expect(key, `${key} should not be a multi_agent script`).not.toContain(
        "multi_agent",
      );
    }
  });
});
