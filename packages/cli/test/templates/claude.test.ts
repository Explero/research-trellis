import { describe, expect, it } from "vitest";
import {
  settingsTemplate,
  getAllAgents,
  getSettingsTemplate,
} from "../../src/templates/claude/index.js";
import { getBundledSkillTemplates } from "../../src/templates/common/index.js";

// =============================================================================
// settingsTemplate — module-level constant
// =============================================================================

describe("settingsTemplate", () => {
  it("is valid JSON", () => {
    expect(() => JSON.parse(settingsTemplate)).not.toThrow();
  });

  it("is a non-empty string", () => {
    expect(settingsTemplate.length).toBeGreaterThan(0);
  });

  // v0.5.0-beta.8: pin CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR=1 at the project
  // level so Bash tool cwd changes don't leak into subsequent hook invocations.
  // Without this, a user who runs `cd frontend/` via Bash tool leaves cwd stuck
  // in `frontend/`, and the next UserPromptSubmit hook (which resolves
  // `.claude/hooks/inject-workflow-state.py` relative to cwd) crashes with
  // ENOENT. We can't fix this via command-string rewriting because
  // $CLAUDE_PROJECT_DIR doesn't expand on Windows shells (see CC issue #6023).
  // The env-var approach is read by CC internally, identical on all platforms.
  it("sets CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR=1 in env", () => {
    const settings = JSON.parse(settingsTemplate) as {
      env?: Record<string, string>;
    };
    expect(settings.env?.CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR).toBe("1");
  });
});

// =============================================================================
// settingsTemplate — SessionStart hook matchers
// =============================================================================

describe("settingsTemplate SessionStart matchers", () => {
  const settings = JSON.parse(settingsTemplate);
  const sessionStartEntries = settings.hooks.SessionStart as {
    matcher: string;
    hooks: { type: string; command: string; timeout: number }[];
  }[];

  it("includes startup, clear, and compact matchers", () => {
    const matchers = sessionStartEntries.map((e) => e.matcher);
    expect(matchers).toContain("startup");
    expect(matchers).toContain("clear");
    expect(matchers).toContain("compact");
  });

  it("all SessionStart entries invoke the same session-start.py hook", () => {
    for (const entry of sessionStartEntries) {
      expect(entry.hooks).toHaveLength(1);
      expect(entry.hooks[0].command).toContain("session-start.py");
    }
  });

  it("all SessionStart entries use {{PYTHON_CMD}} placeholder", () => {
    for (const entry of sessionStartEntries) {
      expect(entry.hooks[0].command).toContain("{{PYTHON_CMD}}");
    }
  });

  it("registers Hermes runtime guard for Stop and SubagentStop", () => {
    const settings = JSON.parse(settingsTemplate) as {
      hooks: Record<
        string,
        { hooks: { command: string; timeout: number }[] }[]
      >;
    };

    for (const eventName of ["Stop", "SubagentStop"]) {
      const entries = settings.hooks[eventName];
      expect(entries).toBeDefined();
      expect(entries[0].hooks[0].command).toContain("hermes-runtime-guard.py");
      expect(entries[0].hooks[0].timeout).toBeGreaterThanOrEqual(15);
    }
  });

  it("registers Hermes runtime guard before write tools", () => {
    const settings = JSON.parse(settingsTemplate) as {
      hooks: {
        PreToolUse: {
          matcher?: string;
          hooks: { command: string; timeout: number }[];
        }[];
      };
    };

    const entry = settings.hooks.PreToolUse.find((candidate) =>
      candidate.hooks.some((hook) =>
        hook.command.includes("hermes-runtime-guard.py"),
      ),
    );

    expect(entry).toBeDefined();
    expect(entry?.matcher).toBe("Edit|Write|MultiEdit|Bash|apply_patch");
    expect(entry?.hooks[0].timeout).toBeGreaterThanOrEqual(15);
  });
});

// Commands are now sourced from common/ templates and tested in platforms.test.ts

// =============================================================================
// getAllAgents — reads agent templates
// =============================================================================

describe("getAllAgents", () => {
  it("each agent has name and content", () => {
    const agents = getAllAgents();
    for (const agent of agents) {
      expect(agent.name.length).toBeGreaterThan(0);
      expect(agent.content.length).toBeGreaterThan(0);
    }
  });

  it("includes Claude review-gate agents", () => {
    const names = getAllAgents().map((agent) => agent.name);
    expect(names).toEqual(
      expect.arrayContaining([
        "trellis-implement",
        "trellis-check",
        "trellis-spec-review",
        "trellis-code-review",
        "trellis-code-architecture-review",
        "trellis-merge-review",
      ]),
    );
  });

  it("includes Hermes research agents that load global config and task records", () => {
    const agents = new Map(
      getAllAgents().map((agent) => [agent.name, agent.content]),
    );

    expect([...agents.keys()]).toEqual(
      expect.arrayContaining(["hermes-scientist", "hermes-claim-reviewer"]),
    );

    for (const name of ["hermes-scientist", "hermes-claim-reviewer"]) {
      const content = agents.get(name);
      expect(content).toBeDefined();
      expect(content).toContain(".trellis/hermes/config.yaml");
      expect(content).toContain(".trellis/hermes/state_machine.yaml");
      expect(content).toContain(".trellis/tasks/<task>/hermes/");
      expect(content).toContain("append-only");
    }

    expect(agents.get("hermes-claim-reviewer")).toContain("claim_ready");
    expect(agents.get("hermes-claim-reviewer")).toContain("approved");
    expect(agents.get("hermes-claim-reviewer")).toContain(
      "human approval record",
    );
  });

  it("includes the expanded Hermes worker roster and task-card discipline", () => {
    const agents = new Map(
      getAllAgents().map((agent) => [agent.name, agent.content]),
    );

    expect([...agents.keys()]).toEqual(
      expect.arrayContaining([
        "hermes-scientist",
        "hermes-claim-reviewer",
        "hermes-coder",
        "hermes-runner",
        "hermes-evaluator",
        "hermes-reviewer",
        "hermes-literature",
      ]),
    );

    for (const name of [
      "hermes-scientist",
      "hermes-claim-reviewer",
      "hermes-coder",
      "hermes-runner",
      "hermes-evaluator",
      "hermes-reviewer",
      "hermes-literature",
    ]) {
      const content = agents.get(name);
      expect(content).toBeDefined();
      expect(content).toContain(".trellis/hermes/roles/");
      expect(content).toContain("worker_records.jsonl");
      expect(content).toContain("task card");
      expect(content).toContain("HumanGate");
    }
  });

  it("bundles hermes-research skill for evidence, claim, and approval records", () => {
    const skills = new Map(
      getBundledSkillTemplates().map((skill) => [skill.name, skill.files]),
    );
    const files = skills.get("hermes-research");

    expect(files).toBeDefined();
    const skill = files?.find((file) => file.relativePath === "SKILL.md");
    expect(skill?.content).toContain("name: hermes-research");
    expect(skill?.content).toContain(".trellis/hermes/config.yaml");
    expect(skill?.content).toContain(".trellis/hermes/state_machine.yaml");
    expect(skill?.content).toContain(".trellis/hermes/records/recordbus.md");
    expect(skill?.content).toContain(
      ".trellis/hermes/records/subagent_protocol.md",
    );
    expect(skill?.content).toContain(".trellis/tasks/<task>/hermes/");
    expect(skill?.content).toContain("evidence");
    expect(skill?.content).toContain("claim");
    expect(skill?.content).toContain("approval");
    expect(skill?.content).toContain("heartbeat");
    expect(skill?.content).toContain("checkpoint");
    expect(skill?.content).toContain("rejection");
    expect(skill?.content).toContain("append-only");
    expect(skill?.content).toContain("long logs");
    expect(skill?.content).toContain("long diffs");
  });

  it("Claude review-gate agents are read-only Opus gates", () => {
    const agents = new Map(
      getAllAgents().map((agent) => [agent.name, agent.content]),
    );
    const reviewGateNames = [
      "trellis-spec-review",
      "trellis-code-review",
      "trellis-code-architecture-review",
      "trellis-merge-review",
    ];

    for (const name of reviewGateNames) {
      const content = agents.get(name);
      expect(content).toBeDefined();
      expect(content).toContain("model: opus");
      expect(content).toContain("tools: Read, Bash, Glob, Grep");
      expect(content).not.toContain("Write");
      expect(content).not.toContain("Edit");
      expect(content).toContain("reports blocking issues to the main session");
    }
  });

  it("trellis implement agent opts into acceptEdits without widening other Claude agents", () => {
    const agents = new Map(
      getAllAgents().map((agent) => [agent.name, agent.content]),
    );

    const implementContent = agents.get("trellis-implement");
    const checkContent = agents.get("trellis-check");

    expect(implementContent).toBeDefined();
    expect(implementContent).toContain("permissionMode: acceptEdits");
    expect(checkContent).toBeDefined();
    expect(checkContent).not.toContain("permissionMode: acceptEdits");
  });

  it("trellis implement and check agents preserve explicit review-gate contract semantics", () => {
    const agents = new Map(
      getAllAgents().map((agent) => [agent.name, agent.content]),
    );

    for (const name of ["trellis-implement", "trellis-check"]) {
      const content = agents.get(name);
      expect(content).toBeDefined();
      expect(content).toContain("Review-gate contract: explicit-selection-v1");
      expect(content).toContain("Review-gate contract: explicit-selection-v1");
      expect(content).toContain("Optional review gates status: configured");
      expect(content).toContain("trellis-improve-codebase-architecture");
      expect(content).toContain("trellis-code-architecture-review");
      expect(content).toContain("trellis-merge-review");
      expect(content).toContain("legacy task");
    }
  });

  it("Claude review-gate agents validate the explicit gate contract and deep-review prerequisite", () => {
    const agents = new Map(
      getAllAgents().map((agent) => [agent.name, agent.content]),
    );
    const reviewGates = [
      "trellis-spec-review",
      "trellis-code-review",
      "trellis-code-architecture-review",
      "trellis-merge-review",
    ] as const;

    for (const name of reviewGates) {
      const content = agents.get(name);
      expect(content).toBeDefined();
      expect(content).toContain("## Strategy Alignment");
      expect(content).toContain("Review-gate contract: explicit-selection-v1");
      expect(content).toContain("Optional review gates status: configured");
      expect(content).toContain("verify that `");
      expect(content).toContain("trellis-code-architecture-review");
      expect(content).toContain("legacy task");
    }
  });
});

// =============================================================================
// getSettingsTemplate — returns settings as SettingsTemplate
// =============================================================================

describe("getSettingsTemplate", () => {
  it("returns correct shape with valid JSON", () => {
    const result = getSettingsTemplate();
    expect(result.targetPath).toBe("settings.json");
    expect(result.content.length).toBeGreaterThan(0);
    expect(() => JSON.parse(result.content)).not.toThrow();
  });
});
