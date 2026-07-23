import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { execFileSync, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  SHARED_HOOKS_BY_PLATFORM,
  getSharedHookScripts,
  getSharedHookScriptsForPlatform,
  type SharedHookPlatform,
} from "../../src/templates/shared-hooks/index.js";

const ALL_HOOK_FILES = [
  "session-start.py",
  "inject-shell-session-context.py",
  "inject-workflow-state.py",
  "inject-subagent-context.py",
  "hermes-runtime-guard.py",
] as const;

const TEMPLATE_SCRIPTS = path.resolve(
  __dirname,
  "../../src/templates/trellis/scripts",
);
const PYTHON = process.platform === "win32" ? "python" : "python3";

function hasPython(): boolean {
  try {
    execFileSync(PYTHON, ["--version"], { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

function writeTaskArtifacts(
  repoRoot: string,
  taskName: string,
  prd: string,
  implementPlan = "# implement\n",
): void {
  const taskDir = path.join(repoRoot, ".trellis", "tasks", taskName);
  fs.mkdirSync(path.join(taskDir, "research"), { recursive: true });
  fs.writeFileSync(
    path.join(taskDir, "task.json"),
    JSON.stringify({
      id: taskName,
      name: taskName,
      title: taskName,
      status: "in_progress",
      priority: "P2",
      createdAt: "2026-06-04",
      assignee: "test",
      creator: "test",
      subtasks: [],
      children: [],
      relatedFiles: [],
      meta: {},
    }) + "\n",
  );
  fs.writeFileSync(path.join(taskDir, "prd.md"), prd);
  fs.writeFileSync(path.join(taskDir, "design.md"), "# design\n");
  fs.writeFileSync(path.join(taskDir, "implement.md"), implementPlan);
  fs.writeFileSync(
    path.join(taskDir, "implement.jsonl"),
    '{"file":".trellis/spec/guides/index.md","reason":"test"}\n',
  );
  fs.writeFileSync(
    path.join(taskDir, "check.jsonl"),
    '{"file":".trellis/spec/guides/index.md","reason":"test"}\n',
  );
  fs.writeFileSync(path.join(taskDir, "research", "note.md"), "research\n");
}

function setupMainRepo(
  repoRoot: string,
  taskName: string,
  prd: string,
  implementPlan?: string,
): void {
  fs.mkdirSync(repoRoot, { recursive: true });
  spawnSync("git", ["init", "-q", "-b", "main"], {
    cwd: repoRoot,
    encoding: "utf-8",
  });
  fs.mkdirSync(path.join(repoRoot, ".trellis"), { recursive: true });
  fs.cpSync(TEMPLATE_SCRIPTS, path.join(repoRoot, ".trellis", "scripts"), {
    recursive: true,
  });
  fs.mkdirSync(path.join(repoRoot, ".trellis", "spec", "guides"), {
    recursive: true,
  });
  fs.writeFileSync(
    path.join(repoRoot, ".trellis", "workflow.md"),
    "# Workflow\n",
  );
  fs.writeFileSync(
    path.join(repoRoot, ".trellis", "config.yaml"),
    "session_auto_commit: false\n",
  );
  fs.writeFileSync(
    path.join(repoRoot, ".trellis", ".gitignore"),
    ".runtime/\n",
  );
  fs.writeFileSync(
    path.join(repoRoot, ".trellis", "spec", "guides", "index.md"),
    "# Guides\n",
  );
  writeTaskArtifacts(repoRoot, taskName, prd, implementPlan);
}

function setSessionActiveTask(
  repoRoot: string,
  taskName: string,
  contextId = "test-session",
): string {
  const sessionsDir = path.join(repoRoot, ".trellis", ".runtime", "sessions");
  fs.mkdirSync(sessionsDir, { recursive: true });
  fs.writeFileSync(
    path.join(sessionsDir, `${contextId}.json`),
    JSON.stringify({ current_task: `.trellis/tasks/${taskName}` }) + "\n",
  );
  return contextId;
}

function setupManagedWorktreeRepo(
  worktreeRoot: string,
  taskName: string,
  prd: string,
  implementPlan = "# implement\n",
): void {
  fs.mkdirSync(worktreeRoot, { recursive: true });
  spawnSync("git", ["init", "-q", "-b", "main"], {
    cwd: worktreeRoot,
    encoding: "utf-8",
  });
  fs.mkdirSync(path.join(worktreeRoot, ".trellis"), { recursive: true });
  fs.cpSync(TEMPLATE_SCRIPTS, path.join(worktreeRoot, ".trellis", "scripts"), {
    recursive: true,
  });
  fs.mkdirSync(path.join(worktreeRoot, ".trellis", "spec", "guides"), {
    recursive: true,
  });
  fs.writeFileSync(
    path.join(worktreeRoot, ".trellis", "workflow.md"),
    "# Workflow\n",
  );
  fs.writeFileSync(
    path.join(worktreeRoot, ".trellis", "config.yaml"),
    "session_auto_commit: false\n",
  );
  fs.writeFileSync(
    path.join(worktreeRoot, ".trellis", ".gitignore"),
    ".runtime/\n",
  );
  fs.writeFileSync(
    path.join(worktreeRoot, ".trellis", "spec", "guides", "index.md"),
    "# Guides\n",
  );
  writeTaskArtifacts(worktreeRoot, taskName, prd, implementPlan);
}

function setupSharedGitWorktree(repoRoot: string, taskName: string): string {
  commitRepoState(repoRoot, "main workspace");
  const worktreeRoot = path.join(
    repoRoot,
    ".trellis",
    "trellis-worktrees",
    taskName,
  );
  fs.mkdirSync(path.dirname(worktreeRoot), { recursive: true });
  const result = spawnSync(
    "git",
    ["worktree", "add", "-q", worktreeRoot, "-b", `trellis-${taskName}`],
    {
      cwd: repoRoot,
      encoding: "utf-8",
    },
  );
  if (result.status !== 0) {
    throw new Error(result.stderr || result.stdout || "git worktree add failed");
  }
  return worktreeRoot;
}

function commitRepoState(repoRoot: string, message = "init"): void {
  spawnSync("git", ["config", "user.email", "test@example.com"], {
    cwd: repoRoot,
    encoding: "utf-8",
  });
  spawnSync("git", ["config", "user.name", "Trellis Test"], {
    cwd: repoRoot,
    encoding: "utf-8",
  });
  const result = spawnSync("git", ["add", "."], {
    cwd: repoRoot,
    encoding: "utf-8",
  });
  if (result.status !== 0) {
    throw new Error(result.stderr || result.stdout || "git add failed");
  }
  const commit = spawnSync("git", ["commit", "-q", "-m", message], {
    cwd: repoRoot,
    encoding: "utf-8",
  });
  if (commit.status !== 0) {
    throw new Error(commit.stderr || commit.stdout || "git commit failed");
  }
}

function runSessionStart(
  worktreeRoot: string,
  hookInput: Record<string, unknown> = {},
): string {
  const sessionStart = getSharedHookScripts().find(
    (h) => h.name === "session-start.py",
  );
  if (!sessionStart) {
    throw new Error("session-start.py template missing");
  }
  const scriptDir = fs.mkdtempSync(
    path.join(os.tmpdir(), "trellis-session-start-"),
  );
  const scriptPath = path.join(scriptDir, "session-start.py");
  fs.writeFileSync(scriptPath, sessionStart.content);
  try {
    const result = spawnSync(PYTHON, [scriptPath], {
      cwd: worktreeRoot,
      encoding: "utf-8",
      env: {
        ...process.env,
        CLAUDE_PROJECT_DIR: worktreeRoot,
      },
      input: JSON.stringify({ cwd: worktreeRoot, ...hookInput }),
    });
    if (result.status !== 0) {
      throw new Error(result.stderr || result.stdout || "session-start failed");
    }
    return result.stdout;
  } finally {
    fs.rmSync(scriptDir, { recursive: true, force: true });
  }
}

function runWorkflowState(
  repoRoot: string,
  contextId: string,
  hookInput: Record<string, unknown> = {},
): string {
  const hook = getSharedHookScripts().find(
    (item) => item.name === "inject-workflow-state.py",
  );
  if (!hook) throw new Error("inject-workflow-state.py template missing");
  const scriptDir = fs.mkdtempSync(
    path.join(os.tmpdir(), "trellis-workflow-state-"),
  );
  const scriptPath = path.join(scriptDir, "inject-workflow-state.py");
  fs.writeFileSync(scriptPath, hook.content);
  try {
    const result = spawnSync(PYTHON, [scriptPath], {
      cwd: repoRoot,
      encoding: "utf-8",
      env: {
        ...process.env,
        CLAUDE_PROJECT_DIR: repoRoot,
        TRELLIS_CONTEXT_ID: contextId,
      },
      input: JSON.stringify({ cwd: repoRoot, session_id: contextId, ...hookInput }),
    });
    if (result.status !== 0) {
      throw new Error(result.stderr || result.stdout || "workflow-state failed");
    }
    return result.stdout;
  } finally {
    fs.rmSync(scriptDir, { recursive: true, force: true });
  }
}

function runPreToolUseHook(
  cwd: string,
  input: Record<string, unknown>,
  env: NodeJS.ProcessEnv = {},
): {
  hookSpecificOutput?: {
    updatedInput?: Record<string, unknown>;
    additionalContext?: string;
    permissionDecision?: string;
    permissionDecisionReason?: string;
  };
  updatedInput?: Record<string, unknown>;
  updated_input?: Record<string, unknown>;
  systemMessage?: string;
} {
  const hook = getSharedHookScripts().find(
    (h) => h.name === "inject-subagent-context.py",
  );
  if (!hook) {
    throw new Error("inject-subagent-context.py template missing");
  }
  const scriptDir = fs.mkdtempSync(path.join(os.tmpdir(), "trellis-pretool-"));
  const scriptPath = path.join(scriptDir, "inject-subagent-context.py");
  fs.writeFileSync(scriptPath, hook.content);
  try {
    const result = spawnSync(PYTHON, [scriptPath], {
      cwd,
      encoding: "utf-8",
      env: {
        ...process.env,
        ...env,
      },
      input: JSON.stringify(input),
    });
    if (result.status !== 0) {
      throw new Error(result.stderr || result.stdout || "pre-tool hook failed");
    }
    return JSON.parse(result.stdout) as {
      hookSpecificOutput?: {
        updatedInput?: Record<string, unknown>;
        additionalContext?: string;
      };
      updatedInput?: Record<string, unknown>;
      updated_input?: Record<string, unknown>;
    };
  } finally {
    fs.rmSync(scriptDir, { recursive: true, force: true });
  }
}

function runHermesRuntimeGuard(
  cwd: string,
  input: Record<string, unknown>,
  env: NodeJS.ProcessEnv = {},
): { stdout: string; stderr: string; status: number | null } {
  const hook = getSharedHookScripts().find(
    (h) => h.name === "hermes-runtime-guard.py",
  );
  if (!hook) {
    throw new Error("hermes-runtime-guard.py template missing");
  }
  const scriptDir = fs.mkdtempSync(
    path.join(os.tmpdir(), "research-trellis-guard-"),
  );
  const scriptPath = path.join(scriptDir, "hermes-runtime-guard.py");
  fs.writeFileSync(scriptPath, hook.content);
  try {
    const result = spawnSync(PYTHON, [scriptPath], {
      cwd,
      encoding: "utf-8",
      env: {
        ...process.env,
        CLAUDE_PROJECT_DIR: cwd,
        ...env,
      },
      input: JSON.stringify(input),
    });
    return {
      stdout: result.stdout.trim(),
      stderr: result.stderr.trim(),
      status: result.status,
    };
  } finally {
    fs.rmSync(scriptDir, { recursive: true, force: true });
  }
}

function runDispatchCli(
  repoRoot: string,
  args: string[],
): { status: number | null; stdout: string; stderr: string } {
  const result = spawnSync(
    PYTHON,
    [path.join(repoRoot, ".trellis", "scripts", "hermes", "dispatch.py"), ...args],
    {
      cwd: repoRoot,
      encoding: "utf-8",
      env: {
        ...process.env,
        TRELLIS_HOOKS_ACTIVE: "1",
        TRELLIS_PLATFORM: "claude",
      },
    },
  );
  return { status: result.status, stdout: result.stdout, stderr: result.stderr };
}

describe("shared-hooks capability table", () => {
  it("every capability-table entry names a real shared-hook file", () => {
    const realFiles = new Set(getSharedHookScripts().map((h) => h.name));
    for (const [platform, hooks] of Object.entries(SHARED_HOOKS_BY_PLATFORM)) {
      for (const hook of hooks) {
        expect(
          realFiles.has(hook),
          `${platform} declares ${hook} but no such file exists under shared-hooks/`,
        ).toBe(true);
      }
    }
  });

  it("every shared-hook file is distributed to at least one platform", () => {
    const distributed = new Set<string>();
    for (const hooks of Object.values(SHARED_HOOKS_BY_PLATFORM)) {
      for (const h of hooks) distributed.add(h);
    }
    for (const hook of getSharedHookScripts()) {
      expect(
        distributed.has(hook.name),
        `${hook.name} exists under shared-hooks/ but no platform installs it — dead template`,
      ).toBe(true);
    }
  });

  it("statusline.py is not distributed by default", () => {
    const realFiles = new Set(getSharedHookScripts().map((h) => h.name));
    expect(realFiles.has("statusline.py")).toBe(false);
    for (const [platform, hooks] of Object.entries(SHARED_HOOKS_BY_PLATFORM)) {
      expect(
        (hooks as readonly string[]).includes("statusline.py"),
        `${platform} must not install the generated statusline.py hook by default`,
      ).toBe(false);
    }
  });

  it("inject-subagent-context.py is restricted to class-1 push-based platforms", () => {
    // Class-2 (pull-based) platforms load context via agent-definition prelude,
    // not a hook-mutated prompt.
    const class2 = new Set(["codex", "copilot", "gemini", "qoder"]);
    for (const [platform, hooks] of Object.entries(SHARED_HOOKS_BY_PLATFORM)) {
      const has = hooks.includes("inject-subagent-context.py");
      if (class2.has(platform))
        expect(
          has,
          `${platform} is class-2 pull-based and must not ship inject-subagent-context.py`,
        ).toBe(false);
    }
  });

  it("codex + copilot do not take the shared session-start.py (they bundle their own)", () => {
    expect(SHARED_HOOKS_BY_PLATFORM.codex).not.toContain("session-start.py");
    expect(SHARED_HOOKS_BY_PLATFORM.copilot).not.toContain("session-start.py");
  });

  it("inject-shell-session-context.py goes to Cursor only", () => {
    for (const [platform, hooks] of Object.entries(SHARED_HOOKS_BY_PLATFORM)) {
      const has = hooks.includes("inject-shell-session-context.py");
      if (platform === "cursor") expect(has).toBe(true);
      else
        expect(
          has,
          `${platform} declares inject-shell-session-context.py but does not use Cursor beforeShellExecution`,
        ).toBe(false);
    }
  });

  it("kiro registers only inject-subagent-context.py (agentSpawn is its only hook event)", () => {
    expect([...SHARED_HOOKS_BY_PLATFORM.kiro]).toEqual([
      "inject-subagent-context.py",
    ]);
  });

  it("getSharedHookScriptsForPlatform returns exactly the declared set per platform", () => {
    for (const platform of Object.keys(
      SHARED_HOOKS_BY_PLATFORM,
    ) as SharedHookPlatform[]) {
      const names = getSharedHookScriptsForPlatform(platform)
        .map((h) => h.name)
        .sort();
      const expected = [...SHARED_HOOKS_BY_PLATFORM[platform]].sort();
      expect(names).toEqual(expected);
    }
  });

  it("shared-hooks directory only contains files enumerated by ALL_HOOK_FILES", () => {
    // Guards against a new shared hook being added without the capability
    // table being updated.
    const actual = new Set(getSharedHookScripts().map((h) => h.name));
    const expected = new Set(ALL_HOOK_FILES);
    expect(actual).toEqual(expected);
  });

  it("shared hooks do not read legacy .current-task state", () => {
    for (const hook of getSharedHookScripts()) {
      expect(
        hook.content,
        `${hook.name} must use the session-scoped active task resolver`,
      ).not.toContain(".current-task");
      expect(hook.content).not.toContain("global fallback");
    }
  });

  it("shared hooks honor trellis-switch.json gating", () => {
    const hooks = new Map(
      getSharedHookScripts().map((h) => [h.name, h.content]),
    );
    expect(hooks.get("session-start.py")).toContain(
      "_read_trellis_switch_enabled",
    );
    expect(hooks.get("session-start.py")).toContain("trellis-switch.json");
    expect(hooks.get("session-start.py")).toContain(
      '_detect_platform({}) == "claude"',
    );
    expect(hooks.get("inject-workflow-state.py")).toContain(
      "_read_trellis_switch_enabled",
    );
    expect(hooks.get("inject-workflow-state.py")).toContain(
      "trellis-switch.json",
    );
    expect(hooks.get("inject-subagent-context.py")).toContain(
      "_read_trellis_switch_enabled",
    );
    expect(hooks.get("inject-subagent-context.py")).toContain(
      "trellis-switch.json",
    );
    expect(hooks.get("inject-subagent-context.py")).toContain(
      "trellis-worktrees",
    );
    expect(hooks.get("inject-subagent-context.py")).toContain(
      "_infer_worktree_task",
    );
  });

  it("shared session-start.py injects compact task artifact guidance", () => {
    const sessionStart = getSharedHookScripts().find(
      (h) => h.name === "session-start.py",
    );
    expect(
      sessionStart,
      "session-start.py is missing from shared-hooks/",
    ).toBeDefined();
    const content = sessionStart ? sessionStart.content : "";
    expect(content).toContain("<trellis-workflow>");
    expect(content).toContain("Task context order");
    expect(content).toContain("jsonl entries -> `prd.md`");
    expect(content).toContain(
      "Lightweight task can request start review with PRD-only",
    );
    expect(content).toContain("complex task must add");
    expect(content).toContain("trellis-worktrees");
    expect(content).toContain("<worktree-sync>");
    expect(content).not.toContain("Status: READY");
    expect(content).not.toContain("<workflow>");
  });

  it("lists project context references for the main agent without inlining documents", () => {
    const repoRoot = fs.mkdtempSync(path.join(os.tmpdir(), "trellis-project-index-"));
    try {
      setupMainRepo(repoRoot, "project-index", "# prd\n");
      const projectDir = path.join(repoRoot, ".trellis", "project");
      fs.mkdirSync(projectDir, { recursive: true });
      fs.writeFileSync(
        path.join(projectDir, "BACKGROUND.md"),
        "BACKGROUND_BODY_MUST_NOT_BE_INJECTED\n",
      );
      fs.writeFileSync(path.join(projectDir, "RESEARCH_PLAN.md"), "# Plan\n");
      fs.writeFileSync(path.join(projectDir, "CONSTRAINTS.md"), "# Constraints\n");

      const payload = JSON.parse(runSessionStart(repoRoot)) as {
        hookSpecificOutput?: { additionalContext?: string };
      };
      const context = payload.hookSpecificOutput?.additionalContext ?? "";
      expect(context).toContain("<project-context-index>");
      expect(context).toContain(".trellis/project/BACKGROUND.md");
      expect(context).toContain(".trellis/project/RESEARCH_PLAN.md");
      expect(context).toContain(".trellis/project/CONSTRAINTS.md");
      expect(context).toContain("Subagents receive a project-context document only");
      expect(context).not.toContain("BACKGROUND_BODY_MUST_NOT_BE_INJECTED");
    } finally {
      fs.rmSync(repoRoot, { recursive: true, force: true });
    }
  });

  it("reinjects a compact closure capsule after a session compaction", () => {
    const repoRoot = fs.mkdtempSync(path.join(os.tmpdir(), "trellis-compact-capsule-"));
    try {
      setupMainRepo(repoRoot, "compact-task", "# prd\n");
      const taskDir = path.join(repoRoot, ".trellis", "tasks", "compact-task");
      const taskJsonPath = path.join(taskDir, "task.json");
      const task = JSON.parse(fs.readFileSync(taskJsonPath, "utf-8"));
      Object.assign(task, {
        closure_state: "open",
        closure_mode: "lean",
        hermes_phase: "running",
        intent: "Restore closure context after compaction",
        definition_of_done: ["Focused validation is recorded"],
        current_work_package: "WP1",
        next_action: "stale persisted text",
        blockers: [],
        repair_count: 0,
        max_repair_count: 1,
        work_packages: [{
          id: "WP1",
          title: "Restore state",
          outcome: "Current work package remains visible",
          done_when: ["Focused validation is recorded"],
          evidence_required: [],
          depends_on: [],
          status: "running",
          evidence_refs: [],
          blocker: null,
        }],
      });
      fs.writeFileSync(taskJsonPath, `${JSON.stringify(task, null, 2)}\n`);
      const contextId = setSessionActiveTask(repoRoot, "compact-task", "compact-session");
      const payload = JSON.parse(runSessionStart(repoRoot, {
        session_id: contextId,
        source: "compact",
      })) as { hookSpecificOutput?: { additionalContext?: string } };
      const context = payload.hookSpecificOutput?.additionalContext ?? "";
      expect(context).toContain("Status: HERMES CLOSURE");
      expect(context).toContain("Current: WP1");
      expect(context).toContain("Done when: Focused validation is recorded");
      expect(context).toContain("Complete WP1 outcome");
      expect(context).not.toContain("stale persisted text");
      expect(context.match(/Current: WP1/g)).toHaveLength(1);
    } finally {
      fs.rmSync(repoRoot, { recursive: true, force: true });
    }
  });

  it("gives Codex the same project context index through its first prompt hook", () => {
    const repoRoot = fs.mkdtempSync(path.join(os.tmpdir(), "trellis-codex-project-index-"));
    try {
      setupMainRepo(repoRoot, "project-index", "# prd\n");
      const projectDir = path.join(repoRoot, ".trellis", "project");
      fs.mkdirSync(projectDir, { recursive: true });
      fs.writeFileSync(
        path.join(projectDir, "BACKGROUND.md"),
        "CODEX_BACKGROUND_BODY_MUST_NOT_BE_INJECTED\n",
      );
      fs.writeFileSync(path.join(projectDir, "RESEARCH_PLAN.md"), "# Plan\n");
      fs.writeFileSync(path.join(projectDir, "CONSTRAINTS.md"), "# Constraints\n");

      const hook = getSharedHookScripts().find(
        (item) => item.name === "inject-workflow-state.py",
      );
      if (!hook) throw new Error("inject-workflow-state.py template missing");
      const hookPath = path.join(repoRoot, ".codex", "hooks", "inject-workflow-state.py");
      fs.mkdirSync(path.dirname(hookPath), { recursive: true });
      fs.writeFileSync(hookPath, hook.content);
      const result = spawnSync(PYTHON, [hookPath], {
        cwd: repoRoot,
        encoding: "utf-8",
        input: JSON.stringify({ cwd: repoRoot }),
      });
      expect(result.status, result.stderr).toBe(0);
      const payload = JSON.parse(result.stdout) as {
        hookSpecificOutput?: { additionalContext?: string };
      };
      const context = payload.hookSpecificOutput?.additionalContext ?? "";
      expect(context).toContain("<project-context-index>");
      expect(context).toContain(".trellis/project/BACKGROUND.md");
      expect(context).not.toContain("CODEX_BACKGROUND_BODY_MUST_NOT_BE_INJECTED");
    } finally {
      fs.rmSync(repoRoot, { recursive: true, force: true });
    }
  });

  it("injects a compact closure capsule without full task artifacts", () => {
    const repoRoot = fs.mkdtempSync(path.join(os.tmpdir(), "trellis-capsule-hook-"));
    try {
      setupMainRepo(
        repoRoot,
        "capsule-task",
        "FULL_PRD_MUST_NOT_BE_INJECTED\n",
      );
      const taskDir = path.join(repoRoot, ".trellis", "tasks", "capsule-task");
      const taskJsonPath = path.join(taskDir, "task.json");
      const task = JSON.parse(fs.readFileSync(taskJsonPath, "utf-8"));
      Object.assign(task, {
        closure_state: "open",
        closure_mode: "lean",
        hermes_phase: "running",
        intent: "Verify one bounded result",
        in_scope: ["current package"],
        out_of_scope: ["unrelated history"],
        definition_of_done: ["Result is tested"],
        current_work_package: "WP1",
        next_action: "Run the focused test",
        blockers: [],
        repair_count: 0,
        max_repair_count: 1,
        work_packages: [
          {
            id: "WP1",
            title: "Tested result",
            outcome: "Result is tested",
            done_when: ["Focused test passes"],
            evidence_required: [],
            depends_on: [],
            status: "running",
            evidence_refs: [],
            blocker: null,
          },
        ],
      });
      fs.writeFileSync(taskJsonPath, `${JSON.stringify(task, null, 2)}\n`);
      const contextId = setSessionActiveTask(
        repoRoot,
        "capsule-task",
        "capsule-hook",
      );
      const raw = runWorkflowState(repoRoot, contextId);
      const payload = JSON.parse(raw) as {
        hookSpecificOutput: { additionalContext: string };
      };
      const context = payload.hookSpecificOutput.additionalContext;
      expect(context).toContain("<task-capsule>");
      expect(context).toContain("Current: WP1");
      expect(context).toContain("Done when: Focused test passes");
      expect(context).toContain("Hermes closure task: capsule-task");
      expect(context).toContain("Route: delivery");
      expect(context).toContain("Route rule:");
      expect(context).toContain("Skill route: coder uses before-dev");
      expect(context).toContain("<task-resume>");
      expect(context).toContain(
        "Do not regenerate existing work packages for an in-scope continuation",
      );
      expect(context).toContain(
        ".trellis/tasks/capsule-task/task.json",
      );
      expect(context).not.toContain("HANDOFF.md");
      expect(context).not.toContain("Claude review gates are read-only gates");
      expect(context).not.toContain("FULL_PRD_MUST_NOT_BE_INJECTED");
      const capsule =
        /<task-capsule>\n([\s\S]*?)\n<\/task-capsule>/.exec(context)?.[1] ?? "";
      expect(capsule.length).toBeLessThanOrEqual(1000);

      fs.writeFileSync(
        path.join(taskDir, "HANDOFF.md"),
        "# Task Handoff\n\n## Task Revision\n0\n\nHANDOFF_BODY_MUST_NOT_BE_INJECTED\n",
      );

      const repeated = JSON.parse(runWorkflowState(repoRoot, contextId)) as {
        hookSpecificOutput: { additionalContext: string };
      };
      expect(repeated.hookSpecificOutput.additionalContext).toContain(
        "anchor revision 0 remains active",
      );
      expect(repeated.hookSpecificOutput.additionalContext).not.toContain(
        "<task-capsule>",
      );
      expect(repeated.hookSpecificOutput.additionalContext).toContain(
        "<task-resume>",
      );
      expect(repeated.hookSpecificOutput.additionalContext).toContain(
        "Skill route: coder uses before-dev",
      );
      expect(repeated.hookSpecificOutput.additionalContext).toContain(
        ".trellis/tasks/capsule-task/HANDOFF.md",
      );
      expect(repeated.hookSpecificOutput.additionalContext).not.toContain(
        "HANDOFF_BODY_MUST_NOT_BE_INJECTED",
      );

      const stableHandoff = JSON.parse(runWorkflowState(repoRoot, contextId)) as {
        hookSpecificOutput: { additionalContext: string };
      };
      expect(stableHandoff.hookSpecificOutput.additionalContext).not.toContain(
        "/HANDOFF.md",
      );

      fs.writeFileSync(
        path.join(taskDir, "HANDOFF.md"),
        "# Legacy Task Handoff\n\nLEGACY_HANDOFF_BODY_MUST_NOT_BE_INJECTED\n",
      );
      const legacyHandoff = JSON.parse(runWorkflowState(repoRoot, contextId)) as {
        hookSpecificOutput: { additionalContext: string };
      };
      expect(legacyHandoff.hookSpecificOutput.additionalContext).toContain(
        "Legacy HANDOFF.md has no Task Revision",
      );
      expect(legacyHandoff.hookSpecificOutput.additionalContext).not.toContain(
        "LEGACY_HANDOFF_BODY_MUST_NOT_BE_INJECTED",
      );

      fs.writeFileSync(
        path.join(taskDir, "HANDOFF.md"),
        "# Task Handoff\n\n## Task Revision\n0\n\nHANDOFF_BODY_MUST_NOT_BE_INJECTED\n",
      );
      runWorkflowState(repoRoot, contextId);

      const compacted = JSON.parse(runWorkflowState(repoRoot, contextId, {
        source: "compact",
      })) as { hookSpecificOutput: { additionalContext: string } };
      expect(compacted.hookSpecificOutput.additionalContext).toContain(
        "<task-capsule>",
      );

      const revisedTask = JSON.parse(fs.readFileSync(taskJsonPath, "utf-8"));
      revisedTask.hermes_revision = 1;
      revisedTask.next_action = "Record focused validation evidence";
      fs.writeFileSync(taskJsonPath, `${JSON.stringify(revisedTask, null, 2)}\n`);
      const revised = JSON.parse(runWorkflowState(repoRoot, contextId)) as {
        hookSpecificOutput: { additionalContext: string };
      };
      expect(revised.hookSpecificOutput.additionalContext).toContain(
        "revision 0 -> 1",
      );
      expect(revised.hookSpecificOutput.additionalContext).toContain(
        "<task-capsule>",
      );
      expect(revised.hookSpecificOutput.additionalContext).toContain(
        "HANDOFF.md is stale",
      );

      revisedTask.hermes_revision = 2;
      revisedTask.current_work_package =
        "PACKAGE_HEAD " + "x".repeat(2000) + " PACKAGE_TAIL";
      fs.writeFileSync(taskJsonPath, `${JSON.stringify(revisedTask, null, 2)}\n`);
      const longAction = JSON.parse(runWorkflowState(repoRoot, contextId)) as {
        hookSpecificOutput: { additionalContext: string };
      };
      const resume =
        /<task-resume>\n([\s\S]*?)\n<\/task-resume>/.exec(
          longAction.hookSpecificOutput.additionalContext,
        )?.[1] ?? "";
      expect(resume).toContain("PACKAGE_HEAD");
      expect(resume).not.toContain("PACKAGE_TAIL");
      expect(resume.length).toBeLessThanOrEqual(800);
    } finally {
      fs.rmSync(repoRoot, { recursive: true, force: true });
    }
  });

  it("shared session-start.py injects only a compact Hermes main-agent boot guard", () => {
    const sessionStart = getSharedHookScripts().find(
      (h) => h.name === "session-start.py",
    );
    expect(sessionStart).toBeDefined();
    const content = sessionStart?.content ?? "";
    expect(content).toContain("_build_hermes_main_agent_boot_guard");
    expect(content).toContain("<main-agent-boot-guard>");
    expect(content).toContain(
      ".trellis/hermes/HERMES_MAIN_AGENT_BOOT_GUARD.md",
    );
    expect(content).toContain("validated_dispatch_only");
    expect(content).not.toContain("You are running inside a Hermes-governed");
  });

  it("codex workflow-state hook emits a short Hermes boot-guard reminder instead of full guard text", () => {
    const workflowState = getSharedHookScripts().find(
      (h) => h.name === "inject-workflow-state.py",
    );
    expect(workflowState).toBeDefined();
    const content = workflowState?.content ?? "";
    expect(content).toContain("_build_codex_hermes_boot_guard_notice");
    expect(content).toContain("<main-agent-boot-guard>");
    expect(content).toContain(
      ".trellis/hermes/HERMES_MAIN_AGENT_BOOT_GUARD.md",
    );
    expect(content).not.toContain("You are running inside a Hermes-governed");
  });
});

describe.skipIf(!hasPython())(
  "shared subagent hook worktree isolation fix",
  () => {
    let tmpDir: string;
    let repoRoot: string;
    let worktreeRoot: string;
    const taskName = "06-05-hook-isolation-fix";

    beforeEach(() => {
      tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "trellis-subagent-hook-"));
      repoRoot = path.join(tmpDir, "repo");
      worktreeRoot = path.join(
        tmpDir,
        ".trellis",
        "trellis-worktrees",
        taskName,
      );
    });

    afterEach(() => {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    });

    it("removes conflicting Claude worktree isolation when cwd is already the shared worktree", () => {
      setupMainRepo(repoRoot, taskName, "# prd\n");
      worktreeRoot = setupSharedGitWorktree(repoRoot, taskName);

      const result = runPreToolUseHook(
        worktreeRoot,
        {
          cwd: worktreeRoot,
          tool_name: "Agent",
          tool_input: {
            subagent_type: "trellis-implement",
            prompt: "Implement the requested fix.",
            isolation: "worktree",
          },
        },
        {
          CLAUDE_PROJECT_DIR: worktreeRoot,
        },
      );

      expect(
        result.hookSpecificOutput?.updatedInput?.isolation,
      ).toBeUndefined();
      expect(result.systemMessage).toContain(
        '自动移除冲突的 `isolation: "worktree"`',
      );
      expect(result.hookSpecificOutput?.additionalContext).toContain(
        '自动移除 `isolation: "worktree"`',
      );
      expect(result.hookSpecificOutput?.updatedInput?.prompt).toContain(
        "<!-- trellis-hook-injected -->",
      );
    });

    it("uses structured tool_input path fields as the shared worktree signal without active task state", () => {
      setupMainRepo(repoRoot, taskName, "# prd\n", "# implement\n");
      const sharedWorktreeRoot = setupSharedGitWorktree(repoRoot, taskName);

      const result = runPreToolUseHook(
        repoRoot,
        {
          cwd: repoRoot,
          tool_name: "Agent",
          tool_input: {
            subagent_type: "trellis-implement",
            prompt: "Implement the requested fix.",
            target_path: `./.trellis/trellis-worktrees/${taskName}/src/index.ts`,
            isolation: "worktree",
          },
        },
        {
          CLAUDE_PROJECT_DIR: repoRoot,
        },
      );

      expect(
        result.hookSpecificOutput?.updatedInput?.isolation,
      ).toBeUndefined();
      expect(result.hookSpecificOutput?.additionalContext).toContain(
        '自动移除 `isolation: "worktree"`',
      );
      expect(result.hookSpecificOutput?.updatedInput?.prompt).toContain(
        "<!-- trellis-hook-injected -->",
      );
      expect(
        fs.existsSync(
          path.join(sharedWorktreeRoot, ".trellis", "scripts", "task.py"),
        ),
      ).toBe(true);
    });

    it("denies Claude dispatch when the shared worktree signal points at a plain directory", () => {
      setupMainRepo(repoRoot, taskName, "# prd\n", "# implement\n");
      const sharedWorktreeRoot = path.join(
        repoRoot,
        ".trellis",
        "trellis-worktrees",
        taskName,
      );
      fs.mkdirSync(sharedWorktreeRoot, { recursive: true });

      const result = runPreToolUseHook(
        repoRoot,
        {
          cwd: repoRoot,
          tool_name: "Agent",
          tool_input: {
            subagent_type: "trellis-implement",
            prompt: "Implement the requested fix.",
            target_path: `./.trellis/trellis-worktrees/${taskName}/src/index.ts`,
            isolation: "worktree",
          },
        },
        {
          CLAUDE_PROJECT_DIR: repoRoot,
        },
      );

      expect(result.hookSpecificOutput?.permissionDecision).toBe("deny");
      expect(result.hookSpecificOutput?.permissionDecisionReason).toContain(
        "Git worktree",
      );
      expect(result.hookSpecificOutput?.updatedInput).toBeUndefined();
    });

    it("denies Claude dispatch when the shared worktree path is an unrelated git repository", () => {
      setupMainRepo(repoRoot, taskName, "# prd\n", "# implement\n");
      const sharedWorktreeRoot = path.join(
        repoRoot,
        ".trellis",
        "trellis-worktrees",
        taskName,
      );
      setupManagedWorktreeRepo(sharedWorktreeRoot, taskName, "# prd\n");

      const result = runPreToolUseHook(
        repoRoot,
        {
          cwd: repoRoot,
          tool_name: "Agent",
          tool_input: {
            subagent_type: "trellis-implement",
            prompt: "Implement the requested fix.",
            target_path: `./.trellis/trellis-worktrees/${taskName}/src/index.ts`,
            isolation: "worktree",
          },
        },
        {
          CLAUDE_PROJECT_DIR: repoRoot,
        },
      );

      expect(result.hookSpecificOutput?.permissionDecision).toBe("deny");
      expect(result.hookSpecificOutput?.permissionDecisionReason).toContain(
        "registered Git worktree",
      );
      expect(result.hookSpecificOutput?.updatedInput).toBeUndefined();
    });

    it("creates the shared worktree before stripping isolation when the shared worktree is missing", () => {
      setupMainRepo(repoRoot, taskName, "# prd\n", "# implement\n");
      commitRepoState(repoRoot, "main workspace");

      const result = runPreToolUseHook(
        repoRoot,
        {
          cwd: repoRoot,
          tool_name: "Agent",
          tool_input: {
            subagent_type: "trellis-implement",
            prompt: "Implement the requested fix.",
            target_path: `./.trellis/trellis-worktrees/${taskName}/src/index.ts`,
            isolation: "worktree",
          },
        },
        {
          CLAUDE_PROJECT_DIR: repoRoot,
        },
      );

      const sharedWorktreeRoot = path.join(
        repoRoot,
        ".trellis",
        "trellis-worktrees",
        taskName,
      );
      expect(result.hookSpecificOutput?.permissionDecision).not.toBe("deny");
      expect(result.hookSpecificOutput?.updatedInput?.isolation).toBeUndefined();
      expect(result.hookSpecificOutput?.updatedInput?.prompt).toContain(
        "<!-- trellis-hook-injected -->",
      );
      expect(
        fs.existsSync(path.join(sharedWorktreeRoot, ".git")),
      ).toBe(true);
      const listed = spawnSync("git", ["worktree", "list", "--porcelain"], {
        cwd: repoRoot,
        encoding: "utf-8",
      });
      expect(listed.stdout).toContain(`worktree ${sharedWorktreeRoot}`);
      expect(
        fs.existsSync(
          path.join(sharedWorktreeRoot, ".trellis", "scripts", "task.py"),
        ),
      ).toBe(true);
    });

    it("bootstraps runtime bundle into the shared worktree before dispatch", () => {
      setupMainRepo(
        repoRoot,
        taskName,
        "# prd\n",
        "# implement\n- 开发模式：subagent\n- 分支策略：worktree（路径：./.trellis/trellis-worktrees/06-05-hook-isolation-fix）\n",
      );
      const sharedWorktreeRoot = setupSharedGitWorktree(repoRoot, taskName);
      const contextId = setSessionActiveTask(
        repoRoot,
        taskName,
        "bootstrap-session",
      );

      runPreToolUseHook(
        repoRoot,
        {
          cwd: repoRoot,
          tool_name: "Agent",
          tool_input: {
            subagent_type: "trellis-implement",
            prompt: "Implement the requested fix.",
          },
        },
        {
          CLAUDE_PROJECT_DIR: repoRoot,
          TRELLIS_CONTEXT_ID: contextId,
        },
      );

      expect(
        fs.existsSync(
          path.join(sharedWorktreeRoot, ".trellis", "scripts", "task.py"),
        ),
      ).toBe(true);
      expect(
        fs.existsSync(
          path.join(
            sharedWorktreeRoot,
            ".trellis",
            "tasks",
            taskName,
            "prd.md",
          ),
        ),
      ).toBe(true);
    });

    it("covers Claude review gates when the task strategy is recorded only in prd.md", () => {
      setupMainRepo(
        repoRoot,
        taskName,
        "# prd\n## 开发策略\n- 开发模式：subagent\n- 分支策略：worktree（路径：./.trellis/trellis-worktrees/06-05-hook-isolation-fix）\n",
        "# implement\n",
      );
      setupSharedGitWorktree(repoRoot, taskName);
      const contextId = setSessionActiveTask(
        repoRoot,
        taskName,
        "spec-review-session",
      );

      const result = runPreToolUseHook(
        repoRoot,
        {
          cwd: repoRoot,
          tool_name: "Agent",
          tool_input: {
            subagent_type: "trellis-spec-review",
            prompt: "Review this task against the spec.",
            isolation: "worktree",
          },
        },
        {
          CLAUDE_PROJECT_DIR: repoRoot,
          TRELLIS_CONTEXT_ID: contextId,
        },
      );

      expect(
        result.hookSpecificOutput?.updatedInput?.isolation,
      ).toBeUndefined();
      expect(result.hookSpecificOutput?.updatedInput?.prompt).toContain(
        "# Review Gate Task",
      );
      expect(result.hookSpecificOutput?.additionalContext).toContain(
        "共享 `./.trellis/trellis-worktrees/06-05-hook-isolation-fix` 路径工作",
      );
    });

    it("does not mis-detect prose mentions when the recorded strategy is not shared worktree", () => {
      setupMainRepo(
        repoRoot,
        taskName,
        "# prd\n本文讨论过 `subagent + worktree` 冲突，但本任务不采用该策略。\n",
        "# implement\n- 开发模式：当前会话持续开发\n- 分支策略：当前分支直接开发\n",
      );
      const contextId = setSessionActiveTask(
        repoRoot,
        taskName,
        "direct-branch-session",
      );

      const result = runPreToolUseHook(
        repoRoot,
        {
          cwd: repoRoot,
          tool_name: "Agent",
          tool_input: {
            subagent_type: "trellis-implement",
            prompt: `本文只是在讨论 ./.trellis/trellis-worktrees/${taskName}/src/index.ts 这个历史路径，不应触发共享 worktree 策略。`,
            isolation: "worktree",
          },
        },
        {
          CLAUDE_PROJECT_DIR: repoRoot,
          TRELLIS_CONTEXT_ID: contextId,
        },
      );

      expect(result.hookSpecificOutput?.updatedInput?.isolation).toBe(
        "worktree",
      );
      expect(result.hookSpecificOutput?.additionalContext).toBeUndefined();
      expect(result.hookSpecificOutput?.updatedInput?.prompt).toContain(
        "<!-- trellis-hook-injected -->",
      );
    });

    it("injects only the current Hermes role, profile, capsule, and direct refs", () => {
      setupMainRepo(repoRoot, taskName, "# prd\nFULL_PRD_MUST_NOT_BE_INJECTED\n");
      const taskDir = path.join(repoRoot, ".trellis", "tasks", taskName);
      fs.writeFileSync(
        path.join(taskDir, "task.json"),
        JSON.stringify({
          id: taskName,
          title: "Compact review",
          status: "in_progress",
          hermes_revision: 0,
          closure_state: "open",
          closure_mode: "lean",
          hermes_phase: "review",
          intent: "Review evidence for the current package",
          in_scope: ["evidence"],
          out_of_scope: ["implementation"],
          definition_of_done: ["Evidence review recorded"],
          work_packages: [
            {
              id: "WP1",
              outcome: "Evidence is independently reviewed",
              done_when: ["Review record exists"],
              status: "review",
            },
          ],
          current_work_package: "WP1",
          next_action: "Review WP1 evidence",
          blockers: [],
          relatedFiles: ["docs/direct.md", "docs/second.md", "docs/third.md", "docs/fourth.md"],
        }) + "\n",
      );
      fs.mkdirSync(path.join(repoRoot, "docs"), { recursive: true });
      for (const name of ["direct.md", "second.md", "third.md", "fourth.md"]) {
        fs.writeFileSync(path.join(repoRoot, "docs", name), name, "utf-8");
      }
      const created = runDispatchCli(repoRoot, [
        "create", "--task", taskName, "--job-id", "review-source",
        "--role", "researcher", "--profile", "codebase",
        "--work-package", "WP1",
        "--objective", "Locate the bounded evidence inputs.",
      ]);
      expect(created.status, created.stderr).toBe(0);
      const reviewCreated = runDispatchCli(repoRoot, [
        "create", "--task", taskName, "--job-id", "review-evidence",
        "--role", "reviewer", "--profile", "evidence",
        "--work-package", "WP1", "--parent-job-id", "review-source",
        "--objective", "Review the current package evidence.",
        "--ref", "docs/direct.md", "--ref", "docs/second.md", "--ref", "docs/third.md",
      ]);
      expect(reviewCreated.status, reviewCreated.stderr).toBe(0);
      const contextId = setSessionActiveTask(repoRoot, taskName, "hermes-role-session");
      const result = runPreToolUseHook(
        repoRoot,
        {
          cwd: repoRoot,
          tool_name: "Agent",
          tool_input: {
            subagent_type: "hermes-reviewer",
            prompt: "job_id: review-evidence",
          },
        },
        {
          CLAUDE_PROJECT_DIR: repoRoot,
          TRELLIS_CONTEXT_ID: contextId,
        },
      );
      const prompt = String(result.hookSpecificOutput?.updatedInput?.prompt ?? "");
      expect(prompt).toContain("Hermes Agent Context Firewall dispatch");
      expect(prompt).toContain("role: reviewer:evidence");
      expect(prompt).toContain("work_package: WP1");
      expect(prompt).toContain("parent_job_id: review-source");
      expect(prompt).toContain("docs/direct.md");
      expect(prompt).not.toContain("docs/fourth.md");
      expect(prompt).not.toContain("FULL_PRD_MUST_NOT_BE_INJECTED");
      expect(prompt).not.toContain("# design");
      expect(prompt.length).toBeLessThanOrEqual(2000);
    });

    it("keeps installed legacy Hermes agent aliases on the compact canonical path", () => {
      setupMainRepo(repoRoot, taskName, "# prd\nLEGACY_FULL_PRD\n");
      const taskPath = path.join(repoRoot, ".trellis", "tasks", taskName, "task.json");
      const task = JSON.parse(fs.readFileSync(taskPath, "utf-8"));
      Object.assign(task, {
        hermes_revision: 0,
        closure_state: "open",
        closure_mode: "lean",
        hermes_phase: "review",
        intent: "Review evidence",
        definition_of_done: ["Evidence reviewed"],
        work_packages: [],
        current_work_package: null,
      });
      fs.writeFileSync(taskPath, `${JSON.stringify(task)}\n`, "utf-8");
      const source = runDispatchCli(repoRoot, [
        "create", "--task", taskName, "--job-id", "legacy-source",
        "--role", "researcher", "--profile", "codebase",
        "--objective", "Locate the bounded evidence inputs.",
      ]);
      expect(source.status, source.stderr).toBe(0);
      const created = runDispatchCli(repoRoot, [
        "create", "--task", taskName, "--job-id", "legacy-evidence",
        "--role", "reviewer", "--profile", "evidence",
        "--parent-job-id", "legacy-source",
        "--objective", "Evaluate evidence.",
      ]);
      expect(created.status, created.stderr).toBe(0);
      const contextId = setSessionActiveTask(repoRoot, taskName, "legacy-role-session");
      const result = runPreToolUseHook(
        repoRoot,
        {
          cwd: repoRoot,
          tool_name: "Agent",
          tool_input: {
            subagent_type: "hermes-evaluator",
            prompt: "legacy-evidence",
          },
        },
        {
          CLAUDE_PROJECT_DIR: repoRoot,
          TRELLIS_CONTEXT_ID: contextId,
        },
      );
      const prompt = String(result.hookSpecificOutput?.updatedInput?.prompt ?? "");
      expect(prompt).toContain("role: reviewer:evidence");
      expect(prompt).not.toContain("LEGACY_FULL_PRD");
    });

    it("covers the documented A/B/C strategy block format in implement.md", () => {
      setupMainRepo(
        repoRoot,
        taskName,
        "# prd\n",
        "# implement\nReview-gate contract: explicit-selection-v1\n\n### A. 开发模式\n- 选择：A2 subagent\n\n### B. 分支 / worktree 方式\n- 选择：B2 worktree（路径：./.trellis/trellis-worktrees/06-05-hook-isolation-fix）\n\n### C. 开发流与架构指导\n- 选择：C1 默认流程\n",
      );
      setupSharedGitWorktree(repoRoot, taskName);
      const contextId = setSessionActiveTask(
        repoRoot,
        taskName,
        "abc-strategy-session",
      );

      const result = runPreToolUseHook(
        repoRoot,
        {
          cwd: repoRoot,
          tool_name: "Agent",
          tool_input: {
            subagent_type: "trellis-implement",
            prompt: "Implement the requested fix.",
            isolation: "worktree",
          },
        },
        {
          CLAUDE_PROJECT_DIR: repoRoot,
          TRELLIS_CONTEXT_ID: contextId,
        },
      );

      expect(
        result.hookSpecificOutput?.updatedInput?.isolation,
      ).toBeUndefined();
      expect(result.systemMessage).toContain(
        '自动移除冲突的 `isolation: "worktree"`',
      );
      expect(result.hookSpecificOutput?.additionalContext).toContain(
        '自动移除 `isolation: "worktree"`',
      );
      expect(result.hookSpecificOutput?.updatedInput?.prompt).toContain(
        "<!-- trellis-hook-injected -->",
      );
    });

    it("uses the current shared worktree path as a Claude-only signal even without prompt hints", () => {
      setupMainRepo(repoRoot, taskName, "# prd\n");
      worktreeRoot = setupSharedGitWorktree(repoRoot, taskName);

      const result = runPreToolUseHook(
        worktreeRoot,
        {
          cwd: worktreeRoot,
          tool_name: "Agent",
          tool_input: {
            subagent_type: "trellis-implement",
            prompt: "Implement the requested fix.",
            isolation: "worktree",
          },
        },
        {
          CLAUDE_PROJECT_DIR: worktreeRoot,
        },
      );

      expect(
        result.hookSpecificOutput?.updatedInput?.isolation,
      ).toBeUndefined();
      expect(result.hookSpecificOutput?.additionalContext).toContain(
        '自动移除 `isolation: "worktree"`',
      );
      expect(result.hookSpecificOutput?.updatedInput?.prompt).toContain(
        "<!-- trellis-hook-injected -->",
      );
    });

    it("denies Claude dispatch when cwd is a managed-worktree-shaped plain directory", () => {
      setupMainRepo(repoRoot, taskName, "# prd\n", "# implement\n");
      const plainWorktreeRoot = path.join(
        repoRoot,
        ".trellis",
        "trellis-worktrees",
        taskName,
      );
      writeTaskArtifacts(plainWorktreeRoot, taskName, "# prd\n");

      const result = runPreToolUseHook(
        plainWorktreeRoot,
        {
          cwd: plainWorktreeRoot,
          tool_name: "Agent",
          tool_input: {
            subagent_type: "trellis-implement",
            prompt: "Implement the requested fix.",
            isolation: "worktree",
          },
        },
        {
          CLAUDE_PROJECT_DIR: plainWorktreeRoot,
        },
      );

      expect(result.hookSpecificOutput?.permissionDecision).toBe("deny");
      expect(result.hookSpecificOutput?.permissionDecisionReason).toContain(
        "Git worktree",
      );
      expect(result.hookSpecificOutput?.updatedInput).toBeUndefined();
    });

    it("keeps isolation untouched on non-Claude platforms even when the shared worktree path appears", () => {
      setupManagedWorktreeRepo(worktreeRoot, taskName, "# prd\n");

      const result = runPreToolUseHook(
        worktreeRoot,
        {
          cwd: worktreeRoot,
          tool_name: "Agent",
          tool_input: {
            subagent_type: "trellis-implement",
            prompt: `Implement on ./.trellis/trellis-worktrees/${taskName}/src/index.ts`,
            isolation: "worktree",
          },
        },
        {
          CURSOR_PROJECT_DIR: worktreeRoot,
        },
      );

      expect(result.hookSpecificOutput?.updatedInput?.isolation).toBe(
        "worktree",
      );
      expect(result.hookSpecificOutput?.additionalContext).toBeUndefined();
    });
  },
);

describe.skipIf(!hasPython())("shared session-start worktree bootstrap", () => {
  let tmpDir: string;
  let repoRoot: string;
  let worktreeRoot: string;
  const taskName = "06-04-worktree-bootstrap";

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "trellis-shared-hooks-"));
    repoRoot = path.join(tmpDir, "repo");
    worktreeRoot = path.join(
      repoRoot,
      ".trellis",
      "trellis-worktrees",
      taskName,
    );
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("bootstraps runtime bundle and planning snapshot into a Trellis-managed worktree", () => {
    setupMainRepo(repoRoot, taskName, "main planning\n");
    worktreeRoot = setupSharedGitWorktree(repoRoot, taskName);
    fs.rmSync(path.join(worktreeRoot, ".trellis"), {
      recursive: true,
      force: true,
    });

    const raw = runSessionStart(worktreeRoot);
    const parsed = JSON.parse(raw) as {
      hookSpecificOutput?: { additionalContext?: string };
    };
    const context = parsed.hookSpecificOutput?.additionalContext ?? "";

    expect(context).toContain("<worktree-sync>");
    expect(context).toContain(
      "Bootstrapped runtime bundle from main workspace",
    );
    expect(context).toContain(
      "Bootstrapped current task planning snapshot from main workspace",
    );
    expect(context).toContain(
      `Current task: .trellis/tasks/${taskName}; status=in_progress.`,
    );
    expect(
      fs.existsSync(path.join(worktreeRoot, ".trellis", "scripts", "task.py")),
    ).toBe(true);
    expect(
      fs.readFileSync(
        path.join(worktreeRoot, ".trellis", "tasks", taskName, "prd.md"),
        "utf-8",
      ),
    ).toContain("main planning");
    expect(
      fs.existsSync(
        path.join(
          worktreeRoot,
          ".trellis",
          "tasks",
          taskName,
          "research",
          "note.md",
        ),
      ),
    ).toBe(true);
    expect(fs.existsSync(path.join(worktreeRoot, ".trellis", ".runtime"))).toBe(
      false,
    );
  });

  it("reports planning drift and asks for explicit main-workspace overwrite when the populated worktree is git-clean", () => {
    setupMainRepo(repoRoot, taskName, "main planning\n");
    worktreeRoot = setupSharedGitWorktree(repoRoot, taskName);
    fs.mkdirSync(path.join(worktreeRoot, "src"), { recursive: true });
    fs.writeFileSync(
      path.join(worktreeRoot, "src", "index.ts"),
      "export const clean = true;\n",
    );
    commitRepoState(worktreeRoot, "init worktree");
    fs.writeFileSync(
      path.join(repoRoot, ".trellis", "tasks", taskName, "prd.md"),
      "main planning updated\n",
    );

    const raw = runSessionStart(worktreeRoot);
    const parsed = JSON.parse(raw) as {
      hookSpecificOutput?: { additionalContext?: string };
    };
    const context = parsed.hookSpecificOutput?.additionalContext ?? "";

    expect(context).toContain(
      "Planning drift detected between main workspace and worktree",
    );
    expect(context).toContain(
      "已检测到主工作区的某个任务的prd.md/planning与worktree不一致，是否执行 主工作区覆盖worktree 的操作？",
    );
    expect(context).not.toContain(
      "Do NOT auto-overwrite: this worktree has local code changes.",
    );
    expect(context).toContain("`.backup-`");
    expect(context).toContain("inherit the original task's planning context");
  });

  it("blocks auto-overwrite when the populated worktree has local code changes", () => {
    setupMainRepo(repoRoot, taskName, "main planning\n");
    worktreeRoot = setupSharedGitWorktree(repoRoot, taskName);
    fs.mkdirSync(path.join(worktreeRoot, "src"), { recursive: true });
    const sourceFile = path.join(worktreeRoot, "src", "index.ts");
    fs.writeFileSync(sourceFile, "export const clean = true;\n");
    commitRepoState(worktreeRoot, "init worktree");
    fs.writeFileSync(sourceFile, "export const clean = false;\n");
    fs.writeFileSync(
      path.join(repoRoot, ".trellis", "tasks", taskName, "prd.md"),
      "main planning updated\n",
    );

    const raw = runSessionStart(worktreeRoot);
    const parsed = JSON.parse(raw) as {
      hookSpecificOutput?: { additionalContext?: string };
    };
    const context = parsed.hookSpecificOutput?.additionalContext ?? "";

    expect(context).toContain(
      "Planning drift detected between main workspace and worktree",
    );
    expect(context).toContain(
      "Do NOT auto-overwrite: this worktree has local code changes.",
    );
    expect(context).not.toContain(
      "已检测到主工作区的某个任务的prd.md/planning与worktree不一致，是否执行 主工作区覆盖worktree 的操作？",
    );
  });
});

describe.skipIf(!hasPython())("hermes runtime guard hook", () => {
  let tmpDir: string;
  let repoRoot: string;
  const taskName = "06-04-hermes-runtime";

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "research-trellis-hook-"));
    repoRoot = path.join(tmpDir, "repo");
    setupMainRepo(repoRoot, taskName, "# prd\n");
    const taskPath = path.join(
      repoRoot,
      ".trellis",
      "tasks",
      taskName,
      "task.json",
    );
    const task = JSON.parse(fs.readFileSync(taskPath, "utf-8"));
    Object.assign(task, {
      hermes_revision: 0,
      closure_state: "open",
      closure_mode: "lean",
      hermes_phase: "running",
      intent: "Runtime guard fixture",
      definition_of_done: ["Runtime checks pass"],
      work_packages: [],
      current_work_package: null,
    });
    fs.writeFileSync(taskPath, `${JSON.stringify(task)}\n`, "utf-8");
    setSessionActiveTask(repoRoot, taskName);
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  function writeHermesWorkerRecords(records: Record<string, unknown>[]): void {
    const hermesDir = path.join(
      repoRoot,
      ".trellis",
      "tasks",
      taskName,
      "hermes",
    );
    fs.mkdirSync(hermesDir, { recursive: true });
    fs.writeFileSync(
      path.join(hermesDir, "worker_records.jsonl"),
      records.map((record) => JSON.stringify(record)).join("\n") + "\n",
      "utf-8",
    );
  }

  function taskCard(
    jobId: string,
    role: string,
    extra: Record<string, unknown> = {},
  ): Record<string, unknown> {
    return {
      type: "task_card",
      id: `tc-${jobId}`,
      timestamp: "2026-06-29T00:00:00Z",
      job_id: jobId,
      role,
      worktree_id: "main",
      status: "queued",
      allowed_files: ["src/**"],
      forbidden_files: [],
      heartbeat_interval: "5m",
      timeout_at: "2099-01-01T00:00:00Z",
      checkpoint: "not-started",
      resume_from: "task_card",
      record_uri: `.trellis/tasks/${taskName}/hermes/worker_records.jsonl`,
      evidence_refs: [],
      risk_flags: [],
      ...extra,
    };
  }

  function checkpoint(
    jobId: string,
    checkpointName: string,
  ): Record<string, unknown> {
    return {
      type: "checkpoint",
      id: `cp-${jobId}`,
      timestamp: "2026-06-29T00:01:00Z",
      job_id: jobId,
      checkpoint: checkpointName,
      resume_from: "continue from checkpoint",
      evidence_refs: [],
      open_items: [],
    };
  }

  function heartbeat(jobId: string): Record<string, unknown> {
    return {
      type: "heartbeat",
      id: `hb-${jobId}`,
      timestamp: "2026-06-29T00:01:00Z",
      job_id: jobId,
      status: "running",
      checkpoint: "in-progress",
      summary: "active",
      next_check_at: "2099-01-01T00:00:00Z",
    };
  }

  function resultRecord(
    jobId: string,
    summary: string,
    extra: Record<string, unknown> = {},
  ): Record<string, unknown> {
    return {
      type: "result",
      id: `rs-${jobId}`,
      timestamp: "2026-06-29T00:02:00Z",
      job_id: jobId,
      status: "done",
      summary,
      changed_files: ["src/app.ts"],
      evidence_refs: [],
      risk_flags: [],
      handoff: "review",
      ...extra,
    };
  }

  function writeRunManifest(exitCode: number): void {
    const hermesDir = path.join(
      repoRoot,
      ".trellis",
      "tasks",
      taskName,
      "hermes",
    );
    fs.mkdirSync(hermesDir, { recursive: true });
    fs.writeFileSync(path.join(hermesDir, "stdout.txt"), "ok\n");
    fs.writeFileSync(
      path.join(hermesDir, "run_manifest.jsonl"),
      JSON.stringify({
        id: "run-tests",
        command: "pnpm test",
        cwd: ".",
        env_summary: { node: "test" },
        inputs: ["src/app.ts"],
        outputs: [`.trellis/tasks/${taskName}/hermes/stdout.txt`],
        exit_code: exitCode,
        started_at: "2026-06-29T00:03:00Z",
        finished_at: "2026-06-29T00:04:00Z",
      }) + "\n",
      "utf-8",
    );
  }

  function writeIdleSession(contextId = "idle-session"): void {
    const sessionsDir = path.join(repoRoot, ".trellis", ".runtime", "sessions");
    fs.mkdirSync(sessionsDir, { recursive: true });
    fs.writeFileSync(
      path.join(sessionsDir, `${contextId}.json`),
      JSON.stringify({ last_seen_at: "2026-06-29T00:00:00Z" }) + "\n",
    );
  }

  function parseDecision(result: { stdout: string }): {
    permissionDecision?: string;
    permissionDecisionReason?: string;
    additionalContext?: string;
  } {
    const payload = JSON.parse(result.stdout) as {
      hookSpecificOutput?: {
        permissionDecision?: string;
        permissionDecisionReason?: string;
        additionalContext?: string;
      };
    };
    return payload.hookSpecificOutput ?? {};
  }

  function expectMainAgentBashDenied(command: string): void {
    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "PreToolUse",
      tool_name: "Bash",
      tool_input: { command },
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const decision = parseDecision(result);
    expect(decision.permissionDecision).toBe("deny");
    expect(decision.permissionDecisionReason).toContain("main agent firewall");
  }

  function runDispatchCli(...args: string[]) {
    return spawnSync(
      PYTHON,
      [
        path.join(repoRoot, ".trellis", "scripts", "hermes", "dispatch.py"),
        ...args,
        "--task",
        taskName,
      ],
      {
        cwd: repoRoot,
        encoding: "utf-8",
        env: {
          ...process.env,
          TRELLIS_HOOKS_ACTIVE: "1",
          TRELLIS_PLATFORM: "claude",
        },
      },
    );
  }

  function applyDispatchResult(
    jobId: string,
    role: string,
    profile: string,
    parentJobId?: string,
  ) {
    const dispatchPath = path.join(
      repoRoot,
      ".trellis",
      "tasks",
      taskName,
      "hermes",
      "dispatches",
      `${jobId}.dispatch.json`,
    );
    const dispatch = JSON.parse(fs.readFileSync(dispatchPath, "utf-8")) as {
      task_revision: number;
    };
    const envelope: Record<string, unknown> = {
      schema: "hermes-result/v1",
      job_id: jobId,
      task_revision: dispatch.task_revision,
      role,
      profile,
      status: "success",
      conclusion: `${jobId} completed`,
      uncertainties: [],
      changed_files: [],
      evidence_refs: [],
      artifact_refs: [],
      verification: { run_refs: [] },
      risks: [],
      next_action: "review",
    };
    if (parentJobId) envelope.parent_job_id = parentJobId;
    return runDispatchCli(
      "apply",
      "--job-id",
      jobId,
      "--result-json",
      JSON.stringify(envelope),
    );
  }

  function markClosureClosed(): void {
    const taskPath = path.join(
      repoRoot,
      ".trellis",
      "tasks",
      taskName,
      "task.json",
    );
    const task = JSON.parse(fs.readFileSync(taskPath, "utf-8"));
    task.closure_state = "closed";
    task.hermes_phase = "closed";
    task.status = "completed";
    fs.writeFileSync(taskPath, `${JSON.stringify(task)}\n`, "utf-8");
  }

  it("blocks Stop when an active task has no Hermes worker records", () => {
    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "Stop",
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      decision?: string;
      reason?: string;
    };
    expect(payload.decision).toBe("block");
    expect(payload.reason).toContain("worker_records.jsonl");
    expect(payload.reason).not.toContain(".trellis/tasks");
    expect(payload.reason).not.toContain(taskName);
    expect(payload.reason).not.toContain(repoRoot);
    expect(result.stderr).toBe("");
  });

  it("honors TRELLIS_HOOKS=0 when Hermes worker records are missing", () => {
    const result = runHermesRuntimeGuard(
      repoRoot,
      {
        cwd: repoRoot,
        hook_event_name: "Stop",
        session_id: "test-session",
      },
      { TRELLIS_HOOKS: "0" },
    );

    expect(result.status).toBe(0);
    expect(result.stdout).toBe("");
    expect(result.stderr).toBe("");
  });

  it("blocks Stop when Hermes worker records are empty", () => {
    const hermesDir = path.join(
      repoRoot,
      ".trellis",
      "tasks",
      taskName,
      "hermes",
    );
    fs.mkdirSync(hermesDir, { recursive: true });
    fs.writeFileSync(path.join(hermesDir, "worker_records.jsonl"), "", "utf-8");

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "Stop",
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      decision?: string;
      reason?: string;
    };
    expect(payload.decision).toBe("block");
    expect(payload.reason).toContain("missing task_card");
  });

  it("blocks Stop when worker records have no completed coder result", () => {
    writeHermesWorkerRecords([taskCard("job-coder", "coder"), heartbeat("job-coder")]);

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "Stop",
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      decision?: string;
      reason?: string;
    };
    expect(payload.decision).toBe("block");
    expect(payload.reason).toContain("completed coder result");
  });

  it("blocks Stop when runner has no passing test record", () => {
    writeHermesWorkerRecords([
      taskCard("job-coder", "coder"),
      checkpoint("job-coder", "implementation-done"),
      taskCard("job-runner", "runner", { parent_job_id: "job-coder" }),
      checkpoint("job-runner", "tests-started"),
      resultRecord("job-runner", "tests ran"),
      taskCard("job-reviewer", "reviewer", { parent_job_id: "job-coder" }),
      checkpoint("job-reviewer", "diff-reviewed"),
      resultRecord("job-reviewer", "review passed"),
      resultRecord("job-coder", "changed files"),
    ]);

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "Stop",
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      decision?: string;
      reason?: string;
    };
    expect(payload.decision).toBe("block");
    expect(payload.reason).toContain("passing test");
  });

  it("blocks Stop when the recorded test run failed", () => {
    fs.mkdirSync(path.join(repoRoot, "src"), { recursive: true });
    fs.writeFileSync(path.join(repoRoot, "src", "app.ts"), "fixture\n");
    writeRunManifest(1);
    writeHermesWorkerRecords([
      taskCard("job-coder", "coder"),
      checkpoint("job-coder", "implementation-done"),
      taskCard("job-runner", "runner", { parent_job_id: "job-coder" }),
      checkpoint("job-runner", "tests-started"),
      resultRecord("job-runner", "tests ran", { evidence_refs: ["run-tests"] }),
      taskCard("job-reviewer", "reviewer", { parent_job_id: "job-coder" }),
      checkpoint("job-reviewer", "diff-reviewed"),
      resultRecord("job-reviewer", "review passed"),
      resultRecord("job-coder", "changed files"),
    ]);

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "Stop",
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      decision?: string;
      reason?: string;
    };
    expect(payload.decision).toBe("block");
    expect(payload.reason).toContain("passing test");
  });

  it("blocks Stop without leaking sensitive changed file names in the reason", () => {
    fs.mkdirSync(path.join(repoRoot, "config"), { recursive: true });
    fs.writeFileSync(path.join(repoRoot, ".env.secret"), "TOKEN=x\n");
    fs.writeFileSync(path.join(repoRoot, "config", "prod.env"), "TOKEN=x\n");
    writeHermesWorkerRecords([
      taskCard("job-coder", "coder"),
      checkpoint("job-coder", "implementation-done"),
      taskCard("job-runner", "runner", { parent_job_id: "job-coder" }),
      checkpoint("job-runner", "tests-started"),
      resultRecord("job-runner", "tests ran"),
      taskCard("job-reviewer", "reviewer", { parent_job_id: "job-coder" }),
      checkpoint("job-reviewer", "diff-reviewed"),
      resultRecord("job-reviewer", "review passed"),
      resultRecord("job-coder", "changed files"),
    ]);

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "Stop",
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      decision?: string;
      reason?: string;
    };
    expect(payload.decision).toBe("block");
    expect(payload.reason).toContain("2 changed file");
    expect(payload.reason).not.toContain(".env.secret");
    expect(payload.reason).not.toContain("config/prod.env");
  });

  it("allows Stop when records, passing tests, review, and git diff agree", () => {
    fs.mkdirSync(path.join(repoRoot, "src"), { recursive: true });
    fs.writeFileSync(path.join(repoRoot, "src", "app.ts"), "before\n");
    commitRepoState(repoRoot, "baseline");
    setSessionActiveTask(repoRoot, taskName);
    fs.writeFileSync(path.join(repoRoot, "src", "app.ts"), "after\n");
    writeRunManifest(0);
    writeHermesWorkerRecords([
      taskCard("job-coder", "coder"),
      checkpoint("job-coder", "implementation-done"),
      taskCard("job-runner", "runner", { parent_job_id: "job-coder" }),
      checkpoint("job-runner", "tests-started"),
      resultRecord("job-runner", "tests ran", { evidence_refs: ["run-tests"] }),
      taskCard("job-reviewer", "reviewer", { parent_job_id: "job-coder" }),
      checkpoint("job-reviewer", "diff-reviewed"),
      resultRecord("job-reviewer", "review passed"),
      resultRecord("job-coder", "changed files"),
    ]);

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "Stop",
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    expect(result.stdout).toBe("");
    expect(result.stderr).toBe("");
  });

  it("allows Stop for a recorded experiment despite unrelated worktree changes", () => {
    fs.mkdirSync(path.join(repoRoot, "src"), { recursive: true });
    fs.writeFileSync(path.join(repoRoot, "src", "app.ts"), "fixture\n");
    commitRepoState(repoRoot, "experiment baseline");
    fs.writeFileSync(path.join(repoRoot, "unrelated-user-note.md"), "keep me\n");
    setSessionActiveTask(repoRoot, taskName);
    writeRunManifest(0);
    writeHermesWorkerRecords([
      taskCard("job-runner", "runner", { profile: "experiment" }),
      checkpoint("job-runner", "experiment-recorded"),
      resultRecord("job-runner", "experiment ran", {
        changed_files: [],
        evidence_refs: ["run-tests"],
      }),
      taskCard("job-reviewer", "reviewer", {
        profile: "evidence",
        parent_job_id: "job-runner",
      }),
      checkpoint("job-reviewer", "evidence-reviewed"),
      resultRecord("job-reviewer", "evidence reviewed", {
        changed_files: [],
      }),
    ]);

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "Stop",
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    expect(result.stdout).toBe("");
    expect(result.stderr).toBe("");
  });

  it("uses an explicit dispatch parent chain from researcher results through Stop", () => {
    const researcher = runDispatchCli(
      "create",
      "--job-id",
      "job-research",
      "--role",
      "researcher",
      "--profile",
      "codebase",
      "--objective",
      "Inspect the bounded implementation context",
    );
    expect(researcher.status, researcher.stderr).toBe(0);
    const researcherResult = applyDispatchResult(
      "job-research",
      "researcher",
      "codebase",
    );
    expect(researcherResult.status, researcherResult.stderr).toBe(0);

    const reviewer = runDispatchCli(
      "create",
      "--job-id",
      "job-review",
      "--role",
      "reviewer",
      "--profile",
      "quality",
      "--parent-job-id",
      "job-research",
      "--objective",
      "Review the exact researcher result",
    );
    expect(reviewer.status, reviewer.stderr).toBe(0);
    const reviewerResult = applyDispatchResult(
      "job-review",
      "reviewer",
      "quality",
      "job-research",
    );
    expect(reviewerResult.status, reviewerResult.stderr).toBe(0);

    markClosureClosed();
    const stop = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "Stop",
      session_id: "test-session",
    });
    expect(stop.status).toBe(0);
    expect(stop.stdout).toBe("");

    const records = fs.readFileSync(
      path.join(
        repoRoot,
        ".trellis",
        "tasks",
        taskName,
        "hermes",
        "worker_records.jsonl",
      ),
      "utf-8",
    );
    expect(records).toContain('"parent_job_id":"job-research"');
  });

  it("warns when one legacy same-package parent candidate is used", () => {
    markClosureClosed();
    writeHermesWorkerRecords([
      taskCard("job-research", "researcher", {
        profile: "codebase",
        work_package: "WP1",
      }),
      checkpoint("job-research", "research-complete"),
      resultRecord("job-research", "research complete", {
        changed_files: [],
      }),
      taskCard("job-review", "reviewer", {
        profile: "quality",
        work_package: "WP1",
      }),
      checkpoint("job-review", "review-complete"),
      resultRecord("job-review", "review complete", {
        changed_files: [],
      }),
    ]);

    const stop = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "Stop",
      session_id: "test-session",
    });
    expect(stop.status).toBe(0);
    const decision = parseDecision(stop);
    expect(decision.additionalContext).toContain("compatibility warning");
    expect(decision.additionalContext).toContain("sole non-reviewer candidate");
    expect(decision.additionalContext).toContain("parent_job_id");
  });

  it("blocks ambiguous legacy reviewer records instead of guessing by time", () => {
    markClosureClosed();
    writeHermesWorkerRecords([
      taskCard("job-research", "researcher", {
        profile: "codebase",
        work_package: "WP1",
      }),
      checkpoint("job-research", "research-complete"),
      resultRecord("job-research", "research complete", {
        changed_files: [],
      }),
      taskCard("job-plan", "planner", {
        profile: "task_planning",
        work_package: "WP1",
      }),
      checkpoint("job-plan", "plan-complete"),
      resultRecord("job-plan", "plan complete", { changed_files: [] }),
      taskCard("job-review", "reviewer", {
        profile: "quality",
        work_package: "WP1",
      }),
      checkpoint("job-review", "review-complete"),
      resultRecord("job-review", "review complete", {
        changed_files: [],
      }),
    ]);

    const stop = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "Stop",
      session_id: "test-session",
    });
    expect(stop.status).toBe(0);
    const payload = JSON.parse(stop.stdout) as {
      decision?: string;
      reason?: string;
    };
    expect(payload.decision).toBe("block");
    expect(payload.reason).toContain("related independent reviewer record");
  });

  it("denies main-agent Write before worker file-boundary checks", () => {
    writeHermesWorkerRecords([
      taskCard("job-coder", "coder"),
      heartbeat("job-coder"),
    ]);

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "PreToolUse",
      tool_name: "Write",
      tool_input: {
        file_path: "src/app.ts",
      },
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      hookSpecificOutput?: {
        permissionDecision?: string;
        permissionDecisionReason?: string;
      };
    };
    expect(payload.hookSpecificOutput?.permissionDecision).toBe("deny");
    expect(payload.hookSpecificOutput?.permissionDecisionReason).toContain(
      "main agent firewall",
    );
    expect(payload.hookSpecificOutput?.permissionDecisionReason).toContain(
      "coder subagent",
    );
  });

  it("denies main-agent Write even when tool_input claims a coder role", () => {
    writeHermesWorkerRecords([
      taskCard("job-coder", "coder"),
      heartbeat("job-coder"),
    ]);

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "PreToolUse",
      tool_name: "Write",
      tool_input: {
        agent_role: "coder",
        file_path: "src/app.ts",
      },
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const decision = parseDecision(result);
    expect(decision.permissionDecision).toBe("deny");
    expect(decision.permissionDecisionReason).toContain("main agent firewall");
  });

  it("denies main-agent package/test Bash commands", () => {
    writeHermesWorkerRecords([
      taskCard("job-runner", "runner"),
      heartbeat("job-runner"),
    ]);

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "PreToolUse",
      tool_name: "Bash",
      tool_input: {
        command: "pnpm test",
      },
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      hookSpecificOutput?: {
        permissionDecision?: string;
        permissionDecisionReason?: string;
      };
    };
    expect(payload.hookSpecificOutput?.permissionDecision).toBe("deny");
    expect(payload.hookSpecificOutput?.permissionDecisionReason).toContain(
      "main agent firewall",
    );
    expect(payload.hookSpecificOutput?.permissionDecisionReason).toContain(
      "runner subagent",
    );
  });

  it("allows the bounded main-agent control and Git read matrix", () => {
    for (const command of [
      "python3 ./.trellis/scripts/hermes/dispatch.py create --task demo --role coder --objective bounded",
      "python3 ./.trellis/scripts/hermes/dispatch.py supersede --task demo --job-id old --reason stale",
      "python3 ./.trellis/scripts/task.py archive demo --no-commit",
      "python3 ./.trellis/scripts/task.py set-scope demo local",
      "python3 ./.trellis/scripts/closure.py plan --task demo --intent bounded",
      "python3 ./.trellis/scripts/closure.py route --task demo --route delivery",
      "python3 ./.trellis/scripts/closure.py grill --task demo --complete --decision-ref design.md",
      "python3 ./.trellis/scripts/closure.py validate --task demo",
      "python3 ./.trellis/scripts/closure.py status --task demo",
      "python3 ./.trellis/scripts/closure.py next --task demo",
      "python3 ./.trellis/scripts/closure.py capsule --task demo",
      "python3 ./.trellis/scripts/closure.py package-start --task demo",
      "python3 ./.trellis/scripts/closure.py package-check --task demo",
      "python3 ./.trellis/scripts/closure.py package-done --task demo",
      "python3 ./.trellis/scripts/closure.py package-block --task demo --reason blocked",
      "python3 ./.trellis/scripts/closure.py amend --task demo --field intent --value bounded --reason update",
      "python3 ./.trellis/scripts/closure.py repair --task demo",
      "python3 ./.trellis/scripts/closure.py audit --task demo",
      "python3 ./.trellis/scripts/closure.py close --task demo",
      "git branch --show-current",
      "git status --short -- src/app.ts",
      "git diff --name-only -- src/app.ts",
      "git log --oneline -n5",
    ]) {
      const result = runHermesRuntimeGuard(repoRoot, {
        cwd: repoRoot,
        hook_event_name: "PreToolUse",
        tool_name: "Bash",
        tool_input: { command },
        session_id: "test-session",
      });
      expect(result.status).toBe(0);
      expect(result.stdout).toBe("");
    }
  });

  it("allows main-agent git status short paths as read-only Bash", () => {
    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "PreToolUse",
      tool_name: "Bash",
      tool_input: {
        command: "git status --short -- src/app.ts",
      },
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    expect(result.stdout).toBe("");
    expect(result.stderr).toBe("");
  });

  it("allows main-agent git diff name-only paths as read-only Bash", () => {
    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "PreToolUse",
      tool_name: "Bash",
      tool_input: {
        command: "git diff --name-only -- src/app.ts",
      },
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    expect(result.stdout).toBe("");
    expect(result.stderr).toBe("");
  });


  it("denies main-agent execution and mutating git Bash commands", () => {
    for (const command of [
      "rm -rf dist",
      "npm test",
      "pnpm build",
      "git add src/app.ts",
      "git commit -m test",
      "git push",
      "git diff --output=diff.txt",
      "git diff --ext-diff",
      "git diff --no-index left right",
      "git diff --name-only -- .env.local",
      "git status --short -- .envrc",
      "cat .trellis/tasks/demo/task.json",
      "jq . .trellis/tasks/demo/task.json",
      "python3 ./.trellis/scripts/hermes/experiment.py validate --task demo",
      "python3 ./.trellis/scripts/hermes/runner.py run --task demo",
      "python3 ./.trellis/scripts/closure.py handoff --task demo",
      "python3 ./.trellis/scripts/task.py archive demo",
      "python3 ./.trellis/scripts/closure.py audit --task demo > audit.txt",
      "python3 ./.trellis/scripts/closure.py audit --task demo && touch src/app.ts",
      "pytest",
      "go test ./...",
      "cargo test",
    ]) {
      expectMainAgentBashDenied(command);
    }
  });

  it.each([
    "trellis-spec-review",
    "trellis-code-review",
    "trellis-code-architecture-review",
    "trellis-merge-review",
    "trellis-improve-codebase-architecture",
  ])("keeps %s inside the reviewer write boundary", (subagentType) => {
    writeHermesWorkerRecords([
      taskCard("job-review", "reviewer"),
      heartbeat("job-review"),
    ]);

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "PreToolUse",
      subagent_type: subagentType,
      tool_name: "Write",
      tool_input: {
        file_path: "src/app.ts",
      },
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const decision = parseDecision(result);
    expect(decision.permissionDecision).toBe("deny");
    expect(decision.permissionDecisionReason).toContain(
      "reviewer cannot write implementation files",
    );
  });

  it("binds common subagent identity fields to their task-card role", () => {
    const identities: [Record<string, string>, string][] = [
      [{ subagent_type: "coder" }, "coder"],
      [{ subagentType: "builder" }, "coder"],
      [{ subagent: "runner" }, "runner"],
      [{ agent_role: "hermes-coder" }, "coder"],
      [{ agent_role: "hermes-scientist" }, "planner"],
      [{ agent_role: "scientist" }, "planner"],
      [{ agent_role: "claim-reviewer" }, "reviewer"],
      [{ agent_role: "research/scout" }, "researcher"],
      [{ subagent_type: "trellis-implement" }, "coder"],
      [{ subagent_type: "trellis-spec-review" }, "reviewer"],
      [{ subagent_type: "trellis-code-architecture-review" }, "reviewer"],
    ];
    for (const [identity, role] of identities) {
      writeHermesWorkerRecords([
        taskCard("job-role", role),
        heartbeat("job-role"),
      ]);

      const result = runHermesRuntimeGuard(repoRoot, {
        cwd: repoRoot,
        hook_event_name: "PreToolUse",
        ...identity,
        tool_name: "Write",
        tool_input: {
          file_path: "src/app.ts",
        },
        session_id: "test-session",
      });

      expect(result.status).toBe(0);
      const decision = parseDecision(result);
      if (role === "coder") {
        expect(decision.permissionDecision).not.toBe("deny");
        expect(decision.additionalContext).toContain("Hermes Runtime");
      } else {
        expect(decision.permissionDecision).toBe("deny");
        expect(decision.permissionDecisionReason).not.toContain(
          "main agent firewall",
        );
      }
    }
  });

  it("allows reviewer records only inside the task review directory", () => {
    writeHermesWorkerRecords([
      taskCard("job-review", "reviewer", {
        allowed_files: [`.trellis/tasks/${taskName}/hermes/reviews/**`],
      }),
      heartbeat("job-review"),
    ]);
    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "PreToolUse",
      agent_role: "reviewer",
      tool_name: "Write",
      tool_input: {
        file_path: `.trellis/tasks/${taskName}/hermes/reviews/quality.md`,
      },
      session_id: "test-session",
    });
    expect(parseDecision(result).permissionDecision).not.toBe("deny");
  });

  it("denies main-agent writes without an active task while keeping read-only git allowed", () => {
    writeIdleSession();

    const writeResult = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "PreToolUse",
      tool_name: "Write",
      tool_input: {
        file_path: "src/app.ts",
      },
      session_id: "idle-session",
    });

    expect(writeResult.status).toBe(0);
    const decision = parseDecision(writeResult);
    expect(decision.permissionDecision).toBe("deny");
    expect(decision.permissionDecisionReason).toContain("main agent firewall");

    const gitResult = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "PreToolUse",
      tool_name: "Bash",
      tool_input: {
        command: "git diff --name-only -- src/app.ts",
      },
      session_id: "idle-session",
    });

    expect(gitResult.status).toBe(0);
    expect(gitResult.stdout).toBe("");
    expect(gitResult.stderr).toBe("");
  });

  it("denies subagent Write without an active task", () => {
    writeIdleSession();

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "PreToolUse",
      agent_role: "coder",
      tool_name: "Write",
      tool_input: {
        file_path: "src/app.ts",
      },
      session_id: "idle-session",
    });

    expect(result.status).toBe(0);
    expect(result.stdout).not.toBe("");
    const decision = parseDecision(result);
    expect(decision.permissionDecision).toBe("deny");
    expect(decision.permissionDecisionReason).toContain("active task");
    expect(decision.permissionDecisionReason).not.toContain("main agent firewall");
  });

  it("denies subagent execution Bash without an active task", () => {
    writeIdleSession();

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "PreToolUse",
      agent_role: "runner",
      tool_name: "Bash",
      tool_input: {
        command: "pnpm test",
      },
      session_id: "idle-session",
    });

    expect(result.status).toBe(0);
    expect(result.stdout).not.toBe("");
    const decision = parseDecision(result);
    expect(decision.permissionDecision).toBe("deny");
    expect(decision.permissionDecisionReason).toContain("active task");
    expect(decision.permissionDecisionReason).not.toContain("main agent firewall");
  });

  it("does not block Stop when there is no active task", () => {
    writeIdleSession();

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "Stop",
      session_id: "idle-session",
    });

    expect(result.status).toBe(0);
    expect(result.stdout).toBe("");
    expect(result.stderr).toBe("");
  });

  it("keeps coder writes behind task_card allowed_files checks", () => {
    writeHermesWorkerRecords([
      taskCard("job-coder", "coder"),
      heartbeat("job-coder"),
    ]);

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "PreToolUse",
      agent_role: "coder",
      tool_name: "Write",
      tool_input: {
        file_path: "docs/readme.md",
      },
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      hookSpecificOutput?: {
        permissionDecision?: string;
        permissionDecisionReason?: string;
      };
    };
    expect(payload.hookSpecificOutput?.permissionDecision).toBe("deny");
    expect(payload.hookSpecificOutput?.permissionDecisionReason).toContain(
      "outside allowed_files",
    );
  });

  it("allows runner Bash only through the registered runner command", () => {
    writeHermesWorkerRecords([
      taskCard("job-runner", "runner"),
      heartbeat("job-runner"),
    ]);

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "PreToolUse",
      agent_role: "runner",
      tool_name: "Bash",
      tool_input: {
        command: `python3 ./.trellis/scripts/hermes/runner.py validate --task ${taskName}`,
      },
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      hookSpecificOutput?: {
        additionalContext?: string;
        permissionDecision?: string;
      };
    };
    expect(payload.hookSpecificOutput?.permissionDecision).not.toBe("deny");
    expect(payload.hookSpecificOutput?.additionalContext).toContain(
      "Hermes Runtime",
    );

    const direct = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "PreToolUse",
      agent_role: "runner",
      tool_name: "Bash",
      tool_input: { command: "pnpm test" },
      session_id: "test-session",
    });
    expect(parseDecision(direct).permissionDecision).toBe("deny");
  });

  it("denies PreToolUse write tools when an active task has no Hermes worker records", () => {
    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "PreToolUse",
      agent_role: "coder",
      tool_name: "Write",
      tool_input: {
        file_path: "src/app.ts",
      },
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      hookSpecificOutput?: {
        permissionDecision?: string;
        permissionDecisionReason?: string;
      };
    };
    expect(payload.hookSpecificOutput?.permissionDecision).toBe("deny");
    expect(payload.hookSpecificOutput?.permissionDecisionReason).toContain(
      "worker_records.jsonl",
    );
  });

  it("denies PreToolUse write tools when records have no unique active task_card", () => {
    const hermesDir = path.join(
      repoRoot,
      ".trellis",
      "tasks",
      taskName,
      "hermes",
    );
    fs.mkdirSync(hermesDir, { recursive: true });
    fs.writeFileSync(
      path.join(hermesDir, "worker_records.jsonl"),
      ["job-a", "job-b"]
        .map((jobId) =>
          JSON.stringify({
            type: "task_card",
            id: `tc-${jobId}`,
            timestamp: "2026-06-29T00:00:00Z",
            job_id: jobId,
            role: "coder",
            worktree_id: "main",
            status: "queued",
            allowed_files: ["src/**"],
            forbidden_files: [],
            heartbeat_interval: "5m",
            timeout_at: "2099-01-01T00:00:00Z",
            checkpoint: "not-started",
            resume_from: "task_card",
            record_uri: `.trellis/tasks/${taskName}/hermes/worker_records.jsonl`,
            evidence_refs: [],
            risk_flags: [],
          }),
        )
        .join("\n") + "\n",
    );

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "PreToolUse",
      agent_role: "coder",
      tool_name: "Write",
      tool_input: {
        file_path: "src/app.ts",
      },
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      hookSpecificOutput?: {
        permissionDecision?: string;
        permissionDecisionReason?: string;
      };
    };
    expect(payload.hookSpecificOutput?.permissionDecision).toBe("deny");
    expect(payload.hookSpecificOutput?.permissionDecisionReason).toMatch(
      /unique active task_card|multiple active writers/,
    );
  });

  it("blocks Stop when Hermes worker records are invalid", () => {
    const hermesDir = path.join(
      repoRoot,
      ".trellis",
      "tasks",
      taskName,
      "hermes",
    );
    fs.mkdirSync(hermesDir, { recursive: true });
    fs.writeFileSync(
      path.join(hermesDir, "worker_records.jsonl"),
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

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "Stop",
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      decision?: string;
      reason?: string;
    };
    expect(payload.decision).toBe("block");
    expect(payload.reason).toContain("missing task_card");
  });

  it("sanitizes Stop validation errors before returning them to the model", () => {
    const hermesDir = path.join(
      repoRoot,
      ".trellis",
      "tasks",
      taskName,
      "hermes",
    );
    fs.mkdirSync(hermesDir, { recursive: true });
    const recordsPath = path.join(hermesDir, "worker_records.jsonl");
    fs.writeFileSync(recordsPath, "{not json}\n", "utf-8");

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "Stop",
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      decision?: string;
      reason?: string;
    };
    expect(payload.decision).toBe("block");
    expect(payload.reason).toContain("Hermes worker records");
    expect(payload.reason).toContain("invalid JSON");
    expect(payload.reason).not.toContain(recordsPath);
    expect(payload.reason).not.toContain(repoRoot);
    expect(payload.reason).not.toContain(".trellis/tasks");
    expect(payload.reason).not.toContain(taskName);
  });

  it("sanitizes Stop run manifest validation errors before returning them to the model", () => {
    const hermesDir = path.join(
      repoRoot,
      ".trellis",
      "tasks",
      taskName,
      "hermes",
    );
    fs.mkdirSync(hermesDir, { recursive: true });
    const manifestPath = path.join(hermesDir, "run_manifest.jsonl");
    fs.writeFileSync(manifestPath, "{not json}\n", "utf-8");
    writeHermesWorkerRecords([
      taskCard("job-coder", "coder"),
      checkpoint("job-coder", "implementation-done"),
      taskCard("job-runner", "runner", { parent_job_id: "job-coder" }),
      checkpoint("job-runner", "tests-started"),
      resultRecord("job-runner", "tests ran", { evidence_refs: ["run-tests"] }),
      taskCard("job-reviewer", "reviewer", { parent_job_id: "job-coder" }),
      checkpoint("job-reviewer", "diff-reviewed"),
      resultRecord("job-reviewer", "review passed"),
      resultRecord("job-coder", "changed files"),
    ]);

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "Stop",
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      decision?: string;
      reason?: string;
    };
    expect(payload.decision).toBe("block");
    expect(payload.reason?.toLowerCase()).toContain("run manifest");
    expect(payload.reason?.toLowerCase()).toContain("invalid");
    expect(payload.reason).not.toContain(manifestPath);
    expect(payload.reason).not.toContain(repoRoot);
    expect(payload.reason).not.toContain(".trellis/tasks");
    expect(payload.reason).not.toContain(taskName);
  });

  it("sanitizes Stop run manifest path validation errors before returning them to the model", () => {
    const hermesDir = path.join(
      repoRoot,
      ".trellis",
      "tasks",
      taskName,
      "hermes",
    );
    fs.mkdirSync(hermesDir, { recursive: true });
    const privateCwd = `.trellis/tasks/${taskName}/private-cwd`;
    const privateInput = `.trellis/tasks/${taskName}/secret-input.txt`;
    const privateOutput = path.join(hermesDir, "secret-output.txt");
    fs.writeFileSync(
      path.join(hermesDir, "run_manifest.jsonl"),
      JSON.stringify({
        id: "run-tests",
        command: "pnpm test",
        cwd: privateCwd,
        env_summary: { node: "test" },
        inputs: [privateInput],
        outputs: [privateOutput],
        exit_code: 0,
        started_at: "2026-06-29T00:03:00Z",
        finished_at: "2026-06-29T00:04:00Z",
      }) + "\n",
      "utf-8",
    );
    writeHermesWorkerRecords([
      taskCard("job-coder", "coder"),
      checkpoint("job-coder", "implementation-done"),
      taskCard("job-runner", "runner", { parent_job_id: "job-coder" }),
      checkpoint("job-runner", "tests-started"),
      resultRecord("job-runner", "tests ran", { evidence_refs: ["run-tests"] }),
      taskCard("job-reviewer", "reviewer", { parent_job_id: "job-coder" }),
      checkpoint("job-reviewer", "diff-reviewed"),
      resultRecord("job-reviewer", "review passed"),
      resultRecord("job-coder", "changed files"),
    ]);

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "Stop",
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      decision?: string;
      reason?: string;
    };
    expect(payload.decision).toBe("block");
    expect(payload.reason?.toLowerCase()).toContain("run manifest");
    expect(payload.reason?.toLowerCase()).toContain("invalid");
    expect(payload.reason).not.toContain(privateCwd);
    expect(payload.reason).not.toContain(privateInput);
    expect(payload.reason).not.toContain(privateOutput);
    expect(payload.reason).not.toContain(repoRoot);
    expect(payload.reason).not.toContain(".trellis/tasks");
    expect(payload.reason).not.toContain(taskName);
    expect(payload.reason).not.toContain("secret-output.txt");
    expect(payload.reason).not.toContain("secret-input.txt");
    expect(payload.reason).not.toContain("private-cwd");
  });

  it("blocks SubagentStop when Hermes worker records are invalid", () => {
    const hermesDir = path.join(
      repoRoot,
      ".trellis",
      "tasks",
      taskName,
      "hermes",
    );
    fs.mkdirSync(hermesDir, { recursive: true });
    fs.writeFileSync(
      path.join(hermesDir, "worker_records.jsonl"),
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

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "SubagentStop",
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      decision?: string;
      reason?: string;
    };
    expect(payload.decision).toBe("block");
    expect(payload.reason).toContain("missing task_card");
  });

  it("blocks Stop for timed-out Hermes jobs without mutating RecordBus", () => {
    const hermesDir = path.join(
      repoRoot,
      ".trellis",
      "tasks",
      taskName,
      "hermes",
    );
    fs.mkdirSync(hermesDir, { recursive: true });
    const recordsPath = path.join(hermesDir, "worker_records.jsonl");
    fs.writeFileSync(
      recordsPath,
      `${JSON.stringify({
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
        timeout_at: "2000-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: `.trellis/tasks/${taskName}/hermes/worker_records.jsonl`,
        evidence_refs: [],
        risk_flags: [],
      })}\n`,
    );

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "Stop",
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      decision?: string;
      reason?: string;
    };
    expect(payload.decision).toBe("block");
    expect(payload.reason).toContain("completed coder result");
    const records = fs.readFileSync(recordsPath, "utf-8");
    expect(records).not.toContain('"type":"rejection"');
    expect(records).not.toContain('"type":"stalled"');
  });

  it("adds PreToolUse guidance before write tools when Hermes worker records exist", () => {
    const hermesDir = path.join(
      repoRoot,
      ".trellis",
      "tasks",
      taskName,
      "hermes",
    );
    fs.mkdirSync(hermesDir, { recursive: true });
    fs.writeFileSync(
      path.join(hermesDir, "worker_records.jsonl"),
      `${JSON.stringify({
        type: "task_card",
        id: "tc-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-active",
        role: "coder",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: [],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: `.trellis/tasks/${taskName}/hermes/worker_records.jsonl`,
        evidence_refs: [],
        risk_flags: [],
      })}\n${JSON.stringify({
        type: "heartbeat",
        id: "hb-20260629-000100-demo",
        timestamp: "2026-06-29T00:01:00Z",
        job_id: "job-active",
        status: "running",
        checkpoint: "files-read",
        summary: "active",
        next_check_at: "2099-01-01T00:00:00Z",
      })}\n`,
    );

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "PreToolUse",
      agent_role: "coder",
      tool_name: "Edit",
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      hookSpecificOutput?: {
        hookEventName?: string;
        additionalContext?: string;
      };
    };
    expect(payload.hookSpecificOutput?.hookEventName).toBe("PreToolUse");
    expect(payload.hookSpecificOutput?.additionalContext).toContain(
      "Hermes Runtime",
    );
    expect(payload.hookSpecificOutput?.additionalContext).toContain(
      "validate.py",
    );
    expect(payload.hookSpecificOutput?.additionalContext).toContain(
      "guard.py changed-files check",
    );
  });

  it("denies PreToolUse write tools when the current tool_input targets unauthorized files", () => {
    const hermesDir = path.join(
      repoRoot,
      ".trellis",
      "tasks",
      taskName,
      "hermes",
    );
    fs.mkdirSync(hermesDir, { recursive: true });
    fs.writeFileSync(
      path.join(hermesDir, "worker_records.jsonl"),
      `${JSON.stringify({
        type: "task_card",
        id: "tc-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-active",
        role: "coder",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: ["secrets/**"],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: `.trellis/tasks/${taskName}/hermes/worker_records.jsonl`,
        evidence_refs: [],
        risk_flags: [],
      })}\n${JSON.stringify({
        type: "heartbeat",
        id: "hb-20260629-000100-demo",
        timestamp: "2026-06-29T00:01:00Z",
        job_id: "job-active",
        status: "running",
        checkpoint: "files-read",
        summary: "active",
        next_check_at: "2099-01-01T00:00:00Z",
      })}\n`,
    );

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "PreToolUse",
      agent_role: "coder",
      tool_name: "Write",
      tool_input: {
        file_path: "docs/readme.md",
      },
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      hookSpecificOutput?: {
        hookEventName?: string;
        permissionDecision?: string;
        permissionDecisionReason?: string;
      };
    };
    expect(payload.hookSpecificOutput?.hookEventName).toBe("PreToolUse");
    expect(payload.hookSpecificOutput?.permissionDecision).toBe("deny");
    expect(payload.hookSpecificOutput?.permissionDecisionReason).toContain(
      "outside allowed_files",
    );
  });

  it("denies PreToolUse MultiEdit when any edit targets unauthorized files", () => {
    const hermesDir = path.join(
      repoRoot,
      ".trellis",
      "tasks",
      taskName,
      "hermes",
    );
    fs.mkdirSync(hermesDir, { recursive: true });
    fs.writeFileSync(
      path.join(hermesDir, "worker_records.jsonl"),
      `${JSON.stringify({
        type: "task_card",
        id: "tc-20260629-000000-demo",
        timestamp: "2026-06-29T00:00:00Z",
        job_id: "job-active",
        role: "coder",
        worktree_id: "main",
        status: "queued",
        allowed_files: ["src/**"],
        forbidden_files: ["secrets/**"],
        heartbeat_interval: "5m",
        timeout_at: "2099-01-01T00:00:00Z",
        checkpoint: "not-started",
        resume_from: "task_card",
        record_uri: `.trellis/tasks/${taskName}/hermes/worker_records.jsonl`,
        evidence_refs: [],
        risk_flags: [],
      })}\n${JSON.stringify({
        type: "heartbeat",
        id: "hb-20260629-000100-demo",
        timestamp: "2026-06-29T00:01:00Z",
        job_id: "job-active",
        status: "running",
        checkpoint: "files-read",
        summary: "active",
        next_check_at: "2099-01-01T00:00:00Z",
      })}\n`,
    );

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "PreToolUse",
      agent_role: "coder",
      tool_name: "MultiEdit",
      tool_input: {
        job_id: "job-active",
        edits: [
          {
            file_path: "src/app.ts",
            old_string: "before",
            new_string: "after",
          },
          {
            file_path: "docs/readme.md",
            old_string: "before",
            new_string: "after",
          },
        ],
      },
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      hookSpecificOutput?: {
        hookEventName?: string;
        permissionDecision?: string;
        permissionDecisionReason?: string;
      };
    };
    expect(payload.hookSpecificOutput?.hookEventName).toBe("PreToolUse");
    expect(payload.hookSpecificOutput?.permissionDecision).toBe("deny");
    expect(payload.hookSpecificOutput?.permissionDecisionReason).toContain(
      "outside allowed_files",
    );
    expect(payload.hookSpecificOutput?.permissionDecisionReason).toContain(
      "docs/readme.md",
    );
  });


  it("denies PreToolUse write tools when Hermes worker records are invalid", () => {
    const hermesDir = path.join(
      repoRoot,
      ".trellis",
      "tasks",
      taskName,
      "hermes",
    );
    fs.mkdirSync(hermesDir, { recursive: true });
    fs.writeFileSync(
      path.join(hermesDir, "worker_records.jsonl"),
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

    const result = runHermesRuntimeGuard(repoRoot, {
      cwd: repoRoot,
      hook_event_name: "PreToolUse",
      agent_role: "coder",
      tool_name: "Edit",
      session_id: "test-session",
    });

    expect(result.status).toBe(0);
    const payload = JSON.parse(result.stdout) as {
      hookSpecificOutput?: {
        hookEventName?: string;
        permissionDecision?: string;
        permissionDecisionReason?: string;
      };
    };
    expect(payload.hookSpecificOutput?.hookEventName).toBe("PreToolUse");
    expect(payload.hookSpecificOutput?.permissionDecision).toBe("deny");
    expect(payload.hookSpecificOutput?.permissionDecisionReason).toContain(
      "missing task_card",
    );
  });
});
