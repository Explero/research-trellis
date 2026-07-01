import { describe, expect, it } from "vitest";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  checkHermesRequiredFiles,
  checkHookMatcherIncludes,
  checkNoPythonCaches,
  checkSandboxConfiguration,
  checkSecurityGateDocumentation,
} from "../../scripts/hermes-preflight.js";

const repoRoot = path.resolve(import.meta.dirname, "../../../../");
const scriptPath = path.join(
  repoRoot,
  "packages/cli/scripts/hermes-preflight.js",
);

function withTempRoot<T>(run: (root: string) => T): T {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "trellis-hermes-preflight-"));
  try {
    return run(tmpDir);
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
}

function writeFile(root: string, relativePath: string, content = "ok\n"): void {
  const filePath = path.join(root, ...relativePath.split("/"));
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content, "utf-8");
}

describe("hermes-preflight checks", () => {
  it("reports missing Hermes required files", () => {
    withTempRoot((root) => {
      writeFile(root, "packages/cli/src/templates/trellis/hermes/config.yaml");

      const result = checkHermesRequiredFiles(root);

      expect(result.ok).toBe(false);
      expect(result.messages.join("\n")).toContain("experiment.yaml");
      expect(result.messages.join("\n")).toContain("runner.py");
    });
  });

  it("reports Python cache pollution under template directories", () => {
    withTempRoot((root) => {
      writeFile(root, "packages/cli/src/templates/trellis/scripts/hermes/__pycache__/runtime.pyc");

      const result = checkNoPythonCaches(root);

      expect(result.ok).toBe(false);
      expect(result.messages.join("\n")).toContain("__pycache__");
      expect(result.messages.join("\n")).toContain(".pyc");
    });
  });

  it("reports missing MultiEdit and Bash hook matchers", () => {
    withTempRoot((root) => {
      writeFile(
        root,
        "packages/cli/src/templates/shared-hooks/hermes-runtime-guard.py",
        'WRITE_TOOL_NAMES = {"Edit", "Write"}\n',
      );

      const result = checkHookMatcherIncludes(root);

      expect(result.ok).toBe(false);
      expect(result.messages.join("\n")).toContain("MultiEdit");
      expect(result.messages.join("\n")).toContain("Bash");
    });
  });

  it("requires deployment docs to state Bash and approval security boundaries", () => {
    withTempRoot((root) => {
      writeFile(
        root,
        "docs/hermes_deployment_preflight.md",
        "`Bash` is partially guarded.\n",
      );

      const result = checkSecurityGateDocumentation(root);

      expect(result.ok).toBe(false);
      expect(result.messages.join("\n")).toContain("approval_records");
      expect(result.messages.join("\n")).toContain("human/root");
    });
  });

  it("requires deployment docs to state hardening and storage boundaries", () => {
    withTempRoot((root) => {
      writeFile(
        root,
        "docs/hermes_deployment_preflight.md",
        [
          "`deployment candidate hardening` is the scope.",
          "`Bash` writes fail closed.",
          "`allowed_commands` is not a strong command sandbox.",
          "`not an OS sandbox`.",
          "`approval_records` require `external human/root approval`.",
          "",
        ].join("\n"),
      );

      const result = checkSecurityGateDocumentation(root);

      expect(result.ok).toBe(false);
      expect(result.messages.join("\n")).toContain("JSONL");
      expect(result.messages.join("\n")).toContain("not tamper-proof");
    });
  });

  it("checks sandbox configuration defaults and documentation boundaries", () => {
    withTempRoot((root) => {
      writeFile(
        root,
        "packages/cli/src/templates/trellis/hermes/config.yaml",
        [
          'runtime_scope: "deployment candidate hardening"',
          "sandbox:",
          '  mode: "none"',
          "  required: false",
          '  note: "not an OS sandbox"',
          "",
        ].join("\n"),
      );
      writeFile(
        root,
        "packages/cli/src/templates/trellis/hermes/experiments/experiment.yaml",
        [
          "sandbox:",
          '  mode: "none"',
          "  required: false",
          "",
        ].join("\n"),
      );
      writeFile(
        root,
        "docs/hermes_deployment_preflight.md",
        [
          "`sandbox.required=true` with `mode=none` must fail closed.",
          "`mode=none` is only local execution.",
          "`container` and `external` modes are availability checks only.",
          "`not an OS sandbox`.",
          "`allowed_commands` is not a strong command sandbox.",
          "",
        ].join("\n"),
      );

      const result = checkSandboxConfiguration(root);

      expect(result.ok).toBe(true);
    });
  });

  it("quick CLI runs security gate without build/typecheck", () => {
    const result = spawnSync(
      process.execPath,
      [scriptPath, "--", "--quick", "--skip-python-compile"],
      {
        cwd: repoRoot,
        encoding: "utf-8",
      },
    );

    expect(result.status).toBe(0);
    expect(result.stdout).toContain("Hermes deployment preflight");
    expect(result.stdout).toContain("quick mode");
    expect(result.stdout).toContain("Bash");
    expect(result.stdout).toContain("approval_records");
  });
});
