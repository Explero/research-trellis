import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  getAllHermesTemplates,
  getAllScripts,
} from "../../src/templates/trellis/index.js";
import { getSharedHookScripts } from "../../src/templates/shared-hooks/index.js";

const PYTHON = process.platform === "win32" ? "python" : "python3";

interface CommandResult {
  status: number | null;
  stdout: string;
  stderr: string;
}

function writeJson(filePath: string, value: unknown): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf-8");
}

function writeJsonl(filePath: string, values: unknown[]): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(
    filePath,
    `${values.map((value) => JSON.stringify(value)).join("\n")}\n`,
    "utf-8",
  );
}

function baseTask(overrides: Record<string, unknown> = {}) {
  return {
    id: "demo",
    title: "Firewall demo",
    description: "Verify bounded agent context",
    status: "in_progress",
    hermes_revision: 4,
    hermes_phase: "running",
    closure_state: "open",
    closure_mode: "lean",
    intent: "Verify bounded agent context",
    in_scope: ["firewall"],
    out_of_scope: [],
    definition_of_done: ["Firewall behavior is verified"],
    work_packages: [
      {
        id: "WP1",
        title: "Implement firewall",
        outcome: "Firewall behavior exists",
        done_when: ["Firewall behavior is verified"],
        evidence_required: [],
        depends_on: [],
        status: "running",
        evidence_refs: [],
        blocker: null,
      },
    ],
    current_work_package: "WP1",
    next_action: "Implement WP1",
    blockers: [],
    repair_count: 0,
    max_repair_count: 1,
    ...overrides,
  };
}

describe("Agent Context Firewall dispatch CLI", () => {
  let root: string;
  let taskDir: string;

  beforeEach(() => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), "trellis-firewall-"));
    spawnSync("git", ["init", "-q", "-b", "main"], {
      cwd: root,
      encoding: "utf-8",
    });
    taskDir = path.join(root, ".trellis", "tasks", "demo");
    for (const [relativePath, content] of getAllScripts()) {
      const target = path.join(root, ".trellis", "scripts", relativePath);
      fs.mkdirSync(path.dirname(target), { recursive: true });
      fs.writeFileSync(target, content, "utf-8");
    }
    for (const [relativePath, content] of getAllHermesTemplates()) {
      const target = path.join(root, ".trellis", "hermes", relativePath);
      fs.mkdirSync(path.dirname(target), { recursive: true });
      fs.writeFileSync(target, content, "utf-8");
    }
    for (const hook of getSharedHookScripts()) {
      const target = path.join(root, ".claude", "hooks", hook.name);
      fs.mkdirSync(path.dirname(target), { recursive: true });
      fs.writeFileSync(target, hook.content, "utf-8");
    }
    writeJson(path.join(taskDir, "task.json"), baseTask());
    fs.writeFileSync(path.join(taskDir, "prd.md"), "# PRD\n", "utf-8");
    fs.mkdirSync(path.join(root, "src"), { recursive: true });
    fs.writeFileSync(path.join(root, "src", "app.ts"), "export {};\n", "utf-8");
    const sessions = path.join(root, ".trellis", ".runtime", "sessions");
    fs.mkdirSync(sessions, { recursive: true });
    fs.writeFileSync(
      path.join(sessions, "firewall-session.json"),
      `${JSON.stringify({ current_task: ".trellis/tasks/demo" })}\n`,
      "utf-8",
    );
  });

  afterEach(() => {
    fs.rmSync(root, { recursive: true, force: true });
  });

  function run(
    args: string[],
    env: Record<string, string | undefined> = {},
  ): CommandResult {
    const result = spawnSync(
      PYTHON,
      [path.join(root, ".trellis", "scripts", "hermes", "dispatch.py"), ...args],
      {
        cwd: root,
        encoding: "utf-8",
        env: {
          ...process.env,
          TRELLIS_HOOKS_ACTIVE: "1",
          TRELLIS_PLATFORM: "claude",
          ...env,
        },
      },
    );
    return {
      status: result.status,
      stdout: result.stdout.trim(),
      stderr: result.stderr.trim(),
    };
  }

  function create(
    jobId: string,
    role = "coder",
    extra: string[] = [],
  ): CommandResult {
    const args = [
      "create",
      "--task",
      "demo",
      "--job-id",
      jobId,
      "--role",
      role,
      "--objective",
      `Complete ${jobId}`,
      "--ref",
      "prd.md",
    ];
    if (["coder", "runner"].includes(role)) {
      args.push("--work-package", "WP1");
    }
    if (role === "coder") {
      args.push("--allowed-file", "src/**");
    }
    args.push(...extra);
    return run(args);
  }

  function apply(jobId: string, value: Record<string, unknown>): CommandResult {
    return run([
      "apply",
      "--task",
      "demo",
      "--job-id",
      jobId,
      "--result-json",
      JSON.stringify(value),
    ]);
  }

  function validResult(jobId: string, overrides: Record<string, unknown> = {}) {
    const dispatch = JSON.parse(
      fs.readFileSync(
        path.join(taskDir, "hermes", "dispatches", `${jobId}.dispatch.json`),
        "utf-8",
      ),
    ) as Record<string, unknown>;
    return {
      schema: "hermes-result/v1",
      job_id: jobId,
      task_revision: dispatch.task_revision,
      role: dispatch.role,
      profile: dispatch.profile,
      status: "success",
      conclusion: "Bounded work completed.",
      uncertainties: [],
      changed_files: ["src/app.ts"],
      evidence_refs: [],
      artifact_refs: [],
      verification: { status: "not_recorded", run_refs: [] },
      risks: [],
      next_action: "Review the current package.",
      ...overrides,
    };
  }

  function runHook(
    hookName: "inject-subagent-context.py" | "hermes-runtime-guard.py",
    input: Record<string, unknown>,
  ): CommandResult {
    const result = spawnSync(
      PYTHON,
      [path.join(root, ".claude", "hooks", hookName)],
      {
        cwd: root,
        encoding: "utf-8",
        input: JSON.stringify(input),
        env: {
          ...process.env,
          CLAUDE_PROJECT_DIR: root,
          TRELLIS_CONTEXT_ID: "firewall-session",
          TRELLIS_HOOKS_ACTIVE: "1",
          TRELLIS_PLATFORM: "claude",
        },
      },
    );
    return {
      status: result.status,
      stdout: result.stdout.trim(),
      stderr: result.stderr.trim(),
    };
  }

  it("creates a revision-bound canonical dispatch with exact metrics", () => {
    const result = create("job-create");
    expect(result.status).toBe(0);
    const dispatch = JSON.parse(
      fs.readFileSync(
        path.join(taskDir, "hermes", "dispatches", "job-create.dispatch.json"),
        "utf-8",
      ),
    ) as {
      hermes_revision: number;
      refs: string[];
      body: string;
      audit: { metrics: { body_chars: number; ref_count: number } };
    };
    expect(dispatch.hermes_revision).toBe(4);
    expect(dispatch.refs).toEqual([".trellis/tasks/demo/prd.md"]);
    expect(dispatch.body.length).toBeLessThanOrEqual(2000);
    expect(dispatch.audit.metrics.body_chars).toBe(dispatch.body.length);
    expect(dispatch.audit.metrics.ref_count).toBe(1);
  });

  it("permits a coder configuration dispatch only for the current task handoff", () => {
    const result = run([
      "create",
      "--task", "demo",
      "--job-id", "job-handoff",
      "--role", "coder",
      "--profile", "configuration",
      "--objective", "Write the current task handoff.",
      "--ref", "prd.md",
      "--allowed-file", ".trellis/tasks/demo/HANDOFF.md",
    ]);
    expect(result.status, result.stderr).toBe(0);
    const dispatch = JSON.parse(
      fs.readFileSync(
        path.join(taskDir, "hermes", "dispatches", "job-handoff.dispatch.json"),
        "utf-8",
      ),
    ) as { handoff_writer: boolean; work_package: string | null; body: string };
    expect(dispatch.handoff_writer).toBe(true);
    expect(dispatch.work_package).toBeNull();
    expect(dispatch.body).toContain("Handoff writer:");

    const applied = apply("job-handoff", validResult("job-handoff", {
      changed_files: [".trellis/tasks/demo/HANDOFF.md"],
    }));
    expect(applied.status, applied.stderr).toBe(0);
    const handoff = fs.readFileSync(path.join(taskDir, "HANDOFF.md"), "utf-8");
    expect(handoff).toContain("# Task Handoff");
    expect(handoff).toContain("- .trellis/tasks/demo/HANDOFF.md");
  });

  it("reserves the task handoff path for the dedicated handoff dispatch", () => {
    const result = create("job-handoff-escape", "coder", [
      "--allowed-file", ".trellis/tasks/demo/HANDOFF.md",
    ]);
    expect(result.status).toBe(1);
    expect(result.stderr).toContain("handoff_path_reserved");
  });

  it("adds only role-matched project context after explicit task refs", () => {
    const projectDir = path.join(root, ".trellis", "project");
    fs.mkdirSync(projectDir, { recursive: true });
    fs.writeFileSync(path.join(projectDir, "BACKGROUND.md"), "Background\n");
    fs.writeFileSync(path.join(projectDir, "RESEARCH_PLAN.md"), "Plan\n");
    fs.writeFileSync(path.join(projectDir, "CONSTRAINTS.md"), "Constraints\n");
    fs.writeFileSync(path.join(taskDir, "specific-spec.md"), "Spec\n");
    fs.writeFileSync(path.join(taskDir, "evidence.md"), "Evidence\n");

    expect(create("job-project-coder", "coder").status).toBe(0);
    expect(create("job-project-runner", "runner").status).toBe(0);
    expect(
      create("job-project-review", "reviewer", [
        "--profile", "evidence",
        "--work-package", "WP1",
        "--parent-job-id", "job-project-runner",
      ])
        .status,
    ).toBe(0);
    expect(
      create("job-project-manual", "coder", [
        "--ref",
        "specific-spec.md",
        "--ref",
        "evidence.md",
      ]).status,
    ).toBe(0);

    const refsFor = (jobId: string): string[] => (
      JSON.parse(
        fs.readFileSync(
          path.join(taskDir, "hermes", "dispatches", `${jobId}.dispatch.json`),
          "utf-8",
        ),
      ) as { refs: string[] }
    ).refs;
    expect(refsFor("job-project-coder")).toEqual([
      ".trellis/tasks/demo/prd.md",
      ".trellis/project/CONSTRAINTS.md",
    ]);
    expect(refsFor("job-project-runner")).toEqual([
      ".trellis/tasks/demo/prd.md",
      ".trellis/project/RESEARCH_PLAN.md",
      ".trellis/project/CONSTRAINTS.md",
    ]);
    expect(refsFor("job-project-review")).toEqual([
      ".trellis/tasks/demo/prd.md",
      ".trellis/project/RESEARCH_PLAN.md",
      ".trellis/project/CONSTRAINTS.md",
    ]);
    expect(refsFor("job-project-manual")).toEqual([
      ".trellis/tasks/demo/prd.md",
      ".trellis/tasks/demo/specific-spec.md",
      ".trellis/tasks/demo/evidence.md",
    ]);
  });

  it("allows planner and reviewer task-level work without a package", () => {
    expect(create("job-planner", "planner").status).toBe(0);
    expect(
      create("job-review", "reviewer", ["--profile", "closure"]).status,
    ).toBe(0);
    const review = JSON.parse(
      fs.readFileSync(
        path.join(taskDir, "hermes", "dispatches", "job-review.dispatch.json"),
        "utf-8",
      ),
    ) as Record<string, unknown>;
    expect(review.work_package).toBeNull();
    expect(review.blind_review).toBe(true);
  });

  it("rejects missing jobs, stale revisions, and execution without the current package", () => {
    const missing = run(["validate", "--task", "demo", "--job-id", "missing"]);
    expect(missing.status).toBe(1);
    expect(missing.stderr).toContain("missing_dispatch");

    expect(create("job-stale").status).toBe(0);
    const task = JSON.parse(fs.readFileSync(path.join(taskDir, "task.json"), "utf-8"));
    task.hermes_revision = 5;
    writeJson(path.join(taskDir, "task.json"), task);
    const stale = run(["validate", "--task", "demo", "--job-id", "job-stale"]);
    expect(stale.status).toBe(1);
    expect(stale.stderr).toContain("stale_dispatch");

    const missingPackage = run([
      "create",
      "--task",
      "demo",
      "--job-id",
      "job-no-wp",
      "--role",
      "runner",
      "--objective",
      "Run validation",
    ]);
    expect(missingPackage.stderr).toContain("missing_work_package");
  });

  it("rejects excessive, missing, absolute, traversal, and sensitive refs", () => {
    for (const name of ["a.md", "b.md", "c.md", "d.md"]) {
      fs.writeFileSync(path.join(taskDir, name), name, "utf-8");
    }
    const tooMany = run([
      "create", "--task", "demo", "--job-id", "job-refs", "--role", "planner",
      "--objective", "Plan", "--ref", "a.md", "--ref", "b.md", "--ref", "c.md", "--ref", "d.md",
    ]);
    expect(tooMany.stderr).toContain("too_many_refs");
    for (const [job, ref, code] of [
      ["job-missing-ref", "missing.md", "invalid_ref"],
      ["job-abs-ref", path.join(root, "src", "app.ts"), "absolute_user_path"],
      ["job-traversal", "../outside.md", "ref_out_of_bounds"],
    ]) {
      const result = run([
        "create", "--task", "demo", "--job-id", job, "--role", "planner",
        "--objective", "Plan", "--ref", ref,
      ]);
      expect(result.stderr).toContain(code);
    }
    const sensitiveField = ["api", "key"].join("_");
    const syntheticSecret = "a".repeat(16);
    const sensitive = run([
      "create", "--task", "demo", "--job-id", "job-secret", "--role", "planner",
      "--objective", `Use ${sensitiveField}=${syntheticSecret}`,
    ]);
    expect(sensitive.stderr).toContain("sensitive_content");
    if (process.platform !== "win32") {
      const outside = path.join(os.tmpdir(), `trellis-firewall-outside-${Date.now()}.md`);
      fs.writeFileSync(outside, "outside\n", "utf-8");
      fs.symlinkSync(outside, path.join(root, "linked-outside.md"));
      const linked = run([
        "create", "--task", "demo", "--job-id", "job-linked-ref", "--role", "planner",
        "--objective", "Plan", "--ref", "linked-outside.md",
      ]);
      expect(linked.stderr).toContain("ref_out_of_bounds");
      fs.rmSync(outside, { force: true });
    }
  });

  it("applies closure constraints before creating an unrelated platform dispatch", () => {
    writeJson(
      path.join(taskDir, "task.json"),
      baseTask({
        context_pins: ["src/app.ts"],
        constraints: {
          excluded_platforms: ["codex"],
          excluded_paths: ["generated/**"],
          validation_level: "targeted",
        },
      }),
    );
    const excluded = create("job-excluded-platform", "coder", [
      "--platform",
      "codex",
    ]);
    expect(excluded.status).toBe(1);
    expect(excluded.stderr).toContain("excluded_platform");

    const allowed = create("job-constrained-claude");
    expect(allowed.status).toBe(0);
    const dispatch = JSON.parse(
      fs.readFileSync(
        path.join(
          taskDir,
          "hermes",
          "dispatches",
          "job-constrained-claude.dispatch.json",
        ),
        "utf-8",
      ),
    ) as { forbidden_files: string[]; refs: string[] };
    expect(dispatch.refs).toEqual([
      "src/app.ts",
      ".trellis/tasks/demo/prd.md",
    ]);
    expect(dispatch.forbidden_files).toContain("generated/**");
  });

  it("allows publication packet creation with the compact protocol", () => {
    writeJson(path.join(taskDir, "task.json"), baseTask({ closure_mode: "publication" }));
    const result = run(
      [
        "create", "--task", "demo", "--job-id", "job-publication", "--role", "planner",
        "--objective", "Plan publication checks",
      ],
      { TRELLIS_HOOKS: "0", TRELLIS_HOOKS_ACTIVE: "1" },
    );
    expect(result.status).toBe(0);
    expect(result.stderr).toContain("validated dispatch and Result Envelope protocol");
    const execution = run(
      [
        "run", "--task", "demo", "--job-id", "job-publication",
        "--platform", "codex", "--mode", "native",
      ],
      { TRELLIS_HOOKS: "0", TRELLIS_HOOKS_ACTIVE: "1" },
    );
    expect(execution.status).toBe(0);
    expect(execution.stdout).toContain('"status": "advisory"');
  });

  it("rejects invalid JSON, missing uncertainties, long logs, and full diffs", () => {
    expect(create("job-invalid-json").status).toBe(0);
    const invalid = run([
      "apply", "--task", "demo", "--job-id", "job-invalid-json", "--result-json", "not json",
    ]);
    expect(invalid.stderr).toContain("invalid_json");

    expect(create("job-missing-uncertainties").status).toBe(0);
    const missing = validResult("job-missing-uncertainties");
    delete (missing as Record<string, unknown>).uncertainties;
    expect(apply("job-missing-uncertainties", missing).stderr).toContain("missing_result_fields");

    expect(create("job-log").status).toBe(0);
    const logConclusion = Array.from({ length: 7 }, (_, index) => `INFO line ${index}`).join("\n");
    expect(apply("job-log", validResult("job-log", { conclusion: logConclusion })).stderr).toContain("long_log");

    expect(create("job-diff").status).toBe(0);
    expect(apply("job-diff", validResult("job-diff", { conclusion: "diff --git a/a b/a" })).stderr).toContain("full_diff");
  });

  it("blocks only the job/current package after two invalid envelopes", () => {
    expect(create("job-twice").status).toBe(0);
    for (let index = 0; index < 2; index += 1) {
      expect(run([
        "apply", "--task", "demo", "--job-id", "job-twice", "--result-json", "{}",
      ]).status).toBe(1);
    }
    const dispatch = JSON.parse(
      fs.readFileSync(
        path.join(taskDir, "hermes", "dispatches", "job-twice.dispatch.json"),
        "utf-8",
      ),
    ) as Record<string, unknown>;
    const task = JSON.parse(fs.readFileSync(path.join(taskDir, "task.json"), "utf-8"));
    expect(dispatch.status).toBe("blocked");
    expect(task.status).toBe("in_progress");
    expect(task.closure_state).toBe("open");
    expect(task.work_packages[0].status).toBe("blocked");
    expect(task.work_packages[0].dispatch_blockers).toEqual(["job-twice"]);
  });

  it("stores raw output outside the task and returns only a sanitized result", () => {
    expect(create("job-valid").status).toBe(0);
    const result = apply("job-valid", validResult("job-valid"));
    expect(result.status).toBe(0);
    const sanitized = JSON.parse(result.stdout) as {
      audit: { raw_trace_stored: boolean };
    };
    expect(sanitized.audit.raw_trace_stored).toBe(true);
    expect(sanitized).not.toHaveProperty("raw");
    const traceRoot = path.join(root, ".trellis", ".runtime", "hermes-traces");
    const rawFiles = fs.readdirSync(traceRoot, { recursive: true })
      .map(String)
      .filter((name) => name.endsWith("job-valid.raw.jsonl"));
    expect(rawFiles).toHaveLength(1);
    const task = JSON.parse(fs.readFileSync(path.join(taskDir, "task.json"), "utf-8"));
    expect(task.hermes_revision).toBe(5);
    expect(task.status).toBe("in_progress");
  });

  it("redacts github_pat tokens before any rejected result is persisted", () => {
    expect(create("job-github-pat").status).toBe(0);
    const token = `github_pat_${"A".repeat(24)}`;
    const basicCredential = ["QWxhZGRp", "bjpvcGVu", "IHNlc2Ft", "ZQ=="].join("");
    const userPath = "/home/alice/private/research-notes.txt";
    const rejected = apply(
      "job-github-pat",
      validResult("job-github-pat", {
        conclusion: `Do not persist ${token}; Authorization: Basic ${basicCredential}; ${userPath}`,
      }),
    );
    expect(rejected.status).toBe(1);
    expect(rejected.stderr).toContain("sensitive_content");

    const traceRoot = path.join(root, ".trellis", ".runtime", "hermes-traces");
    const traceFile = fs.readdirSync(traceRoot, { recursive: true })
      .map(String)
      .find((name) => name.endsWith("job-github-pat.raw.jsonl"));
    if (!traceFile) {
      throw new Error("expected the rejected result trace to be recorded");
    }
    const trace = fs.readFileSync(path.join(traceRoot, traceFile), "utf-8");
    expect(trace).toContain("[REDACTED]");
    expect(trace).toContain("[REDACTED_PATH]");
    expect(trace).not.toContain(token);
    expect(trace).not.toContain(basicCredential);
    expect(trace).not.toContain(userPath);
    expect(fs.existsSync(
      path.join(taskDir, "hermes", "dispatches", "job-github-pat.result.json"),
    )).toBe(false);
  });

  it("does not accept runner success as evidence and requires an existing run ref", () => {
    expect(create("job-runner", "runner").status).toBe(0);
    writeJsonl(path.join(taskDir, "hermes", "run_manifest.jsonl"), [
      { id: "run-pass", exit_code: 0 },
    ]);
    const withEvidence = apply(
      "job-runner",
      validResult("job-runner", {
        changed_files: [],
        evidence_refs: ["ev-chat"],
        run_refs: ["run-pass"],
      }),
    );
    expect(withEvidence.stderr).toContain("runner_evidence_forbidden");
  });

  it("rejects runner success when the referenced run failed", () => {
    expect(create("job-runner-failed", "runner").status).toBe(0);
    writeJsonl(path.join(taskDir, "hermes", "run_manifest.jsonl"), [
      { id: "run-failed", exit_code: 1, status: "failed" },
    ]);
    const result = apply(
      "job-runner-failed",
      validResult("job-runner-failed", {
        changed_files: [],
        verification: { status: "failed", run_refs: ["run-failed"] },
      }),
    );
    expect(result.stderr).toContain("failed_run_ref");
  });

  it("keeps blind review off worker explanations and rejects chat close authority", () => {
    fs.mkdirSync(path.join(taskDir, "hermes"), { recursive: true });
    fs.writeFileSync(path.join(taskDir, "hermes", "worker_records.jsonl"), "", "utf-8");
    const blind = run([
      "create", "--task", "demo", "--job-id", "job-blind", "--role", "reviewer",
      "--profile", "evidence", "--objective", "Review current evidence", "--ref",
      ".trellis/tasks/demo/hermes/worker_records.jsonl",
    ]);
    expect(blind.stderr).toContain("blind_review_ref");

    expect(create("job-chat-close", "planner").status).toBe(0);
    const closeAttempt = apply(
      "job-chat-close",
      validResult("job-chat-close", {
        changed_files: [],
        closure_state: "closed",
      }),
    );
    expect(closeAttempt.status).toBe(1);
    expect(closeAttempt.stderr).toContain("unknown_result_fields");
    const task = JSON.parse(fs.readFileSync(path.join(taskDir, "task.json"), "utf-8"));
    expect(task.closure_state).toBe("open");
  });

  it("limits evidence and claim reviewers to proposed judgments", () => {
    expect(create("job-judgment-source", "runner").status).toBe(0);
    expect(
      create("job-evidence-judgment", "reviewer", [
        "--profile", "evidence",
        "--work-package", "WP1",
        "--parent-job-id", "job-judgment-source",
      ]).status,
    ).toBe(0);
    const approved = apply(
      "job-evidence-judgment",
      validResult("job-evidence-judgment", {
        changed_files: [],
        review_judgment: { state: "approved", finding: "looks good" },
      }),
    );
    expect(approved.stderr).toContain("review_authority_violation");

    expect(
      create("job-claim-judgment", "reviewer", [
        "--profile", "claim",
        "--work-package", "WP1",
        "--parent-job-id", "job-judgment-source",
      ]).status,
    ).toBe(0);
    const proposed = apply(
      "job-claim-judgment",
      validResult("job-claim-judgment", {
        changed_files: [],
        review_judgment: { state: "proposed", finding: "scope is bounded" },
      }),
    );
    expect(proposed.status, proposed.stderr).toBe(0);
  });

  it("replaces a 50k Claude prompt with the validated canonical dispatch", () => {
    expect(create("job-50k").status).toBe(0);
    const result = runHook("inject-subagent-context.py", {
      cwd: root,
      hook_event_name: "PreToolUse",
      tool_name: "Agent",
      tool_input: {
        subagent_type: "hermes-coder",
        job_id: "job-50k",
        prompt: `UNTRUSTED-${"x".repeat(50_000)}`,
      },
      session_id: "firewall-session",
    });
    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      hookSpecificOutput: { updatedInput: { prompt: string } };
    };
    const prompt = String(payload.hookSpecificOutput.updatedInput.prompt);
    expect(prompt).toContain("job_id: job-50k");
    expect(prompt).not.toContain("UNTRUSTED");
    expect(prompt.length).toBeLessThanOrEqual(2000);
  });

  it("denies Claude Hermes dispatch without a job, with stale state, or in async mode", () => {
    const missing = runHook("inject-subagent-context.py", {
      cwd: root,
      tool_name: "Agent",
      tool_input: { subagent_type: "hermes-coder", prompt: "do work" },
      session_id: "firewall-session",
    });
    expect(JSON.parse(missing.stdout).hookSpecificOutput.permissionDecision).toBe("deny");

    expect(create("job-hook-stale").status).toBe(0);
    const task = JSON.parse(fs.readFileSync(path.join(taskDir, "task.json"), "utf-8"));
    task.hermes_revision += 1;
    writeJson(path.join(taskDir, "task.json"), task);
    const stale = runHook("inject-subagent-context.py", {
      cwd: root,
      tool_name: "Agent",
      tool_input: { subagent_type: "hermes-coder", prompt: "job-hook-stale" },
      session_id: "firewall-session",
    });
    expect(JSON.parse(stale.stdout).hookSpecificOutput.permissionDecisionReason).toContain(
      "dispatch revision does not match",
    );

    writeJson(path.join(taskDir, "task.json"), baseTask());
    expect(create("job-async").status).toBe(0);
    const asyncResult = runHook("inject-subagent-context.py", {
      cwd: root,
      tool_name: "Agent",
      tool_input: {
        subagent_type: "hermes-coder",
        prompt: "job-async",
        run_in_background: true,
      },
      session_id: "firewall-session",
    });
    expect(JSON.parse(asyncResult.stdout).hookSpecificOutput.permissionDecisionReason).toContain(
      "must be synchronous",
    );
  });

  it("bounds SubagentStop rewrites and PostToolUse exposes only sanitized output", () => {
    expect(create("job-hook-result").status).toBe(0);
    const pre = runHook("inject-subagent-context.py", {
      cwd: root,
      tool_name: "Agent",
      tool_input: { subagent_type: "hermes-coder", prompt: "job-hook-result" },
      session_id: "firewall-session",
    });
    expect(pre.status).toBe(0);
    const started = runHook("hermes-runtime-guard.py", {
      cwd: root,
      hook_event_name: "SubagentStart",
      agent_id: "agent-hook-result",
      agent_type: "hermes-coder",
      session_id: "firewall-session",
    });
    expect(started.stdout).toContain("job-hook-result");

    const first = runHook("hermes-runtime-guard.py", {
      cwd: root,
      hook_event_name: "SubagentStop",
      agent_id: "agent-hook-result",
      agent_type: "hermes-coder",
      last_assistant_message: "not-json",
      session_id: "firewall-session",
    });
    expect(JSON.parse(first.stdout).decision).toBe("block");

    const second = runHook("hermes-runtime-guard.py", {
      cwd: root,
      hook_event_name: "SubagentStop",
      agent_id: "agent-hook-result",
      agent_type: "hermes-coder",
      last_assistant_message: "still-not-json",
      session_id: "firewall-session",
    });
    expect(second.stdout).toBe("");

    const post = runHook("hermes-runtime-guard.py", {
      cwd: root,
      hook_event_name: "PostToolUse",
      tool_name: "Agent",
      tool_input: { subagent_type: "hermes-coder", prompt: "job-hook-result" },
      tool_response: {
        status: "completed",
        agentId: "agent-hook-result",
        content: [{ type: "text", text: "still-not-json" }],
      },
      session_id: "firewall-session",
    });
    const output = JSON.parse(post.stdout).hookSpecificOutput.updatedToolOutput as {
      content: { text: string }[];
    };
    expect(output.content[0].text).toContain('"status":"blocked"');
    expect(output.content[0].text).not.toContain("still-not-json");
  });

  it("validates a Claude final result and replaces Agent output with its summary", () => {
    expect(create("job-hook-valid").status).toBe(0);
    runHook("inject-subagent-context.py", {
      cwd: root,
      tool_name: "Agent",
      tool_input: { subagent_type: "hermes-coder", prompt: "job-hook-valid" },
      session_id: "firewall-session",
    });
    const started = runHook("hermes-runtime-guard.py", {
      cwd: root,
      hook_event_name: "SubagentStart",
      agent_id: "agent-hook-valid",
      agent_type: "hermes-coder",
      session_id: "firewall-session",
    });
    expect(started.stdout).toContain("job-hook-valid");
    const raw = JSON.stringify(validResult("job-hook-valid"));
    const stopped = runHook("hermes-runtime-guard.py", {
      cwd: root,
      hook_event_name: "SubagentStop",
      agent_id: "agent-hook-valid",
      agent_type: "hermes-coder",
      last_assistant_message: raw,
      session_id: "firewall-session",
    });
    expect(stopped.stdout).toBe("");
    const post = runHook("hermes-runtime-guard.py", {
      cwd: root,
      hook_event_name: "PostToolUse",
      tool_name: "Agent",
      tool_input: { subagent_type: "hermes-coder", prompt: "job-hook-valid" },
      tool_response: {
        status: "completed",
        agentId: "agent-hook-valid",
        content: [{ type: "text", text: `${raw}\nRAW_SHOULD_NOT_RETURN` }],
      },
      session_id: "firewall-session",
    });
    const output = JSON.parse(post.stdout).hookSpecificOutput.updatedToolOutput as {
      content: { text: string }[];
    };
    expect(output.content[0].text).toContain("Bounded work completed");
    expect(output.content[0].text).not.toContain("RAW_SHOULD_NOT_RETURN");
    expect(output.content[0].text).not.toContain("audit");
  });

  it("binds blind reviewer reads to allowed refs and rejects worker context", () => {
    expect(create("job-review-source", "coder").status).toBe(0);
    expect(
      create("job-review-read", "reviewer", [
        "--profile", "quality",
        "--work-package", "WP1",
        "--parent-job-id", "job-review-source",
      ]).status,
    ).toBe(0);
    runHook("inject-subagent-context.py", {
      cwd: root,
      tool_name: "Agent",
      tool_input: { subagent_type: "hermes-reviewer", prompt: "job-review-read" },
      session_id: "firewall-session",
    });
    runHook("hermes-runtime-guard.py", {
      cwd: root,
      hook_event_name: "SubagentStart",
      agent_id: "agent-review-read",
      agent_type: "hermes-reviewer",
      session_id: "firewall-session",
    });
    const allowed = runHook("hermes-runtime-guard.py", {
      cwd: root,
      hook_event_name: "PreToolUse",
      tool_name: "Read",
      tool_input: { file_path: path.join(taskDir, "prd.md") },
      agent_id: "agent-review-read",
      agent_type: "hermes-reviewer",
      session_id: "firewall-session",
    });
    expect(allowed.stdout).toBe("");
    const denied = runHook("hermes-runtime-guard.py", {
      cwd: root,
      hook_event_name: "PreToolUse",
      tool_name: "Read",
      tool_input: { file_path: path.join(taskDir, "hermes", "worker_records.jsonl") },
      agent_id: "agent-review-read",
      agent_type: "hermes-reviewer",
      session_id: "firewall-session",
    });
    expect(JSON.parse(denied.stdout).hookSpecificOutput.permissionDecision).toBe("deny");
  });

  it("leaves legacy non-Hermes Trellis Agent behavior outside the bridge", () => {
    writeJson(path.join(taskDir, "task.json"), {
      id: "demo",
      title: "Legacy",
      status: "in_progress",
    });
    const result = runHook("inject-subagent-context.py", {
      cwd: root,
      tool_name: "Agent",
      tool_input: { subagent_type: "hermes-evaluator", prompt: "legacy-evidence" },
      session_id: "firewall-session",
    });
    expect(JSON.parse(result.stdout).hookSpecificOutput.permissionDecision).toBe("deny");
    const guard = runHook("hermes-runtime-guard.py", {
      cwd: root,
      hook_event_name: "PreToolUse",
      tool_name: "Write",
      tool_input: { file_path: "src/app.ts" },
      session_id: "firewall-session",
    });
    expect(guard.stdout).toBe("");
  });


  it("supersedes a blocked dispatch and restores the package mechanically", () => {
    expect(create("job-old").status).toBe(0);
    expect(apply("job-old", {}).status).toBe(1);
    expect(apply("job-old", {}).status).toBe(1);
    expect(create("job-replacement").status).toBe(0);
    const superseded = run([
      "supersede", "--task", "demo", "--job-id", "job-old",
      "--replacement-job-id", "job-replacement", "--reason", "replace invalid output",
    ]);
    expect(superseded.status, superseded.stderr).toBe(0);
    const task = JSON.parse(fs.readFileSync(path.join(taskDir, "task.json"), "utf-8"));
    expect(task.work_packages[0].status).toBe("running");
    expect(task.work_packages[0].dispatch_blockers).toEqual([]);
    const oldDispatch = JSON.parse(
      fs.readFileSync(path.join(taskDir, "hermes", "dispatches", "job-old.dispatch.json"), "utf-8"),
    );
    const replacement = JSON.parse(
      fs.readFileSync(path.join(taskDir, "hermes", "dispatches", "job-replacement.dispatch.json"), "utf-8"),
    );
    expect(oldDispatch.status).toBe("superseded");
    expect(replacement.task_revision).toBe(task.hermes_revision);
  });

  it("blocks Stop for unconfirmed results, undisposed packages, and pending close", () => {
    expect(create("job-stop-gate", "planner").status).toBe(0);
    const unconfirmed = runHook("hermes-runtime-guard.py", {
      cwd: root,
      hook_event_name: "Stop",
      session_id: "firewall-session",
    });
    expect(JSON.parse(unconfirmed.stdout).reason).toContain("still unconfirmed");

    expect(
      apply(
        "job-stop-gate",
        validResult("job-stop-gate", { changed_files: [] }),
      ).status,
    ).toBe(0);
    const undisposed = runHook("hermes-runtime-guard.py", {
      cwd: root,
      hook_event_name: "Stop",
      session_id: "firewall-session",
    });
    expect(JSON.parse(undisposed.stdout).reason).toContain("remain undisposed");

    const task = JSON.parse(fs.readFileSync(path.join(taskDir, "task.json"), "utf-8"));
    task.work_packages[0].status = "done";
    task.current_work_package = null;
    task.hermes_phase = "review";
    writeJson(path.join(taskDir, "task.json"), task);
    const pendingClose = runHook("hermes-runtime-guard.py", {
      cwd: root,
      hook_event_name: "Stop",
      session_id: "firewall-session",
    });
    expect(JSON.parse(pendingClose.stdout).reason).toContain("audit/close");
    expect(JSON.parse(fs.readFileSync(path.join(taskDir, "task.json"), "utf-8")).status).toBe(
      "in_progress",
    );
  });
});
