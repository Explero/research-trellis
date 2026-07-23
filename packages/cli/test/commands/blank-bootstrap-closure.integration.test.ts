import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";

import { init } from "../../src/commands/init.js";

const PYTHON = process.platform === "win32" ? "python" : "python3";

function run(root: string, script: string, args: string[]) {
  return spawnSync(PYTHON, [path.join(root, ".trellis", "scripts", script), ...args], {
    cwd: root,
    encoding: "utf-8",
    env: {
      ...process.env,
      TRELLIS_HOOKS_ACTIVE: "1",
      TRELLIS_PLATFORM: "claude",
    },
  });
}

describe("empty repository bootstrap closure", () => {
  const roots: string[] = [];

  afterEach(() => {
    for (const root of roots.splice(0)) {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });

  it("moves an empty repository from research contract to archived bootstrap task", async () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "trellis-blank-bootstrap-"));
    roots.push(root);
    const cwd = process.cwd();
    process.chdir(root);
    try {
      await init({ yes: true, force: true, user: "alice" });

      const project = path.join(root, ".trellis", "project");
      fs.writeFileSync(path.join(project, "BACKGROUND.md"), "# Background\n\nGoal: reproduce one agreed sample.\n");
      fs.writeFileSync(path.join(project, "RESEARCH_PLAN.md"), "# Research Plan\n\nMethod: run one fixed sample.\n");
      fs.writeFileSync(path.join(project, "CONSTRAINTS.md"), "# Constraints\n\nLimit: keep the first task small.\n");

      const bootstrapPrd = path.join(
        root,
        ".trellis",
        "tasks",
        "00-bootstrap-guidelines",
        "prd.md",
      );
      fs.appendFileSync(
        bootstrapPrd,
        [
          "",
          "## Decision",
          "Verify one agreed sample before expanding the project.",
          "",
          "## Rationale",
          "A fixed sample provides the smallest observable result.",
          "",
          "## Evidence",
          "The project contract records the agreed sample and constraints.",
          "",
          "## Alternatives",
          "Build a larger evaluation workflow first.",
          "",
          "## Failure Conditions",
          "The sample cannot be reproduced under the recorded constraints.",
          "",
        ].join("\n"),
        "utf-8",
      );

      const closure = (args: string[]) => run(root, "closure.py", args);
      expect(closure([
        "grill", "--task", "00-bootstrap-guidelines", "--complete",
        "--decision-ref", "prd.md",
      ]).status).toBe(0);
      expect(closure(["validate", "--task", "00-bootstrap-guidelines"]).status).toBe(0);
      expect(closure(["package-start", "--task", "00-bootstrap-guidelines", "--package-id", "WP1"]).status).toBe(0);
      expect(closure(["package-check", "--task", "00-bootstrap-guidelines", "--package-id", "WP1"]).status).toBe(0);
      expect(closure([
        "package-done", "--task", "00-bootstrap-guidelines", "--package-id", "WP1",
        "--evidence", ".trellis/project/BACKGROUND.md",
        "--evidence", ".trellis/project/RESEARCH_PLAN.md",
        "--evidence", ".trellis/project/CONSTRAINTS.md",
      ]).status).toBe(0);

      const created = run(root, "task.py", [
        "create", "Verify the first sample", "--slug", "first-sample", "--assignee", "alice",
      ]);
      expect(created.status, created.stderr).toBe(0);
      const firstTask = created.stdout.trim().split("\n").at(-1);
      if (!firstTask) {
        throw new Error("task.py create did not return a task path");
      }
      expect(closure([
        "plan", "--task", firstTask,
        "--intent", "Verify one agreed minimal result",
        "--done-when", "The agreed sample has a reproducible result",
      ]).status).toBe(0);

      expect(closure(["package-start", "--task", "00-bootstrap-guidelines", "--package-id", "WP2"]).status).toBe(0);
      expect(closure(["package-check", "--task", "00-bootstrap-guidelines", "--package-id", "WP2"]).status).toBe(0);
      expect(closure([
        "package-done", "--task", "00-bootstrap-guidelines", "--package-id", "WP2",
        "--evidence", `${firstTask}/task.json`,
      ]).status).toBe(0);
      const audit = closure(["audit", "--task", "00-bootstrap-guidelines"]);
      expect(audit.status, audit.stderr).toBe(0);
      const close = closure(["close", "--task", "00-bootstrap-guidelines"]);
      expect(close.status, close.stderr).toBe(0);

      const archive = run(root, "task.py", ["archive", "00-bootstrap-guidelines", "--no-commit"]);
      expect(archive.status, archive.stderr).toBe(0);
      const archivePath = archive.stdout.trim().split("\n").at(-1);
      if (!archivePath) {
        throw new Error("task.py archive did not return an archive path");
      }
      const archivedTask = JSON.parse(
        fs.readFileSync(path.join(root, archivePath, "task.json"), "utf-8"),
      ) as { status: string; hermes_phase: string; closure_state: string };
      expect(archivedTask).toMatchObject({
        status: "completed",
        hermes_phase: "closed",
        closure_state: "closed",
      });
      expect(fs.existsSync(path.join(root, archivePath, "closure-report.md"))).toBe(true);
      const events = fs.readFileSync(path.join(root, archivePath, "hermes", "task-events.jsonl"), "utf-8");
      expect(events).toContain("package_completed");
      expect(events).toContain("task_closed");
    } finally {
      process.chdir(cwd);
    }
  });
});
