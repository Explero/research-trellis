import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";

const repoRoot = path.resolve(import.meta.dirname, "../../../..");
const cliRoot = path.join(repoRoot, "packages", "cli");

describe("codex template packaging", () => {
  const temporaryRoots: string[] = [];

  afterEach(() => {
    for (const root of temporaryRoots.splice(0)) {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });

  it("copies config.toml with its managed markers into the package template tree", () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "trellis-codex-pack-"));
    temporaryRoots.push(root);
    fs.mkdirSync(path.join(root, "scripts"), { recursive: true });
    fs.cpSync(
      path.join(cliRoot, "src", "templates"),
      path.join(root, "src", "templates"),
      { recursive: true },
    );
    fs.cpSync(
      path.join(cliRoot, "src", "migrations", "manifests"),
      path.join(root, "src", "migrations", "manifests"),
      { recursive: true },
    );
    fs.copyFileSync(
      path.join(cliRoot, "scripts", "copy-templates.js"),
      path.join(root, "scripts", "copy-templates.js"),
    );

    execFileSync(process.execPath, ["scripts/copy-templates.js"], {
      cwd: root,
      stdio: "pipe",
    });

    const copied = fs.readFileSync(
      path.join(root, "dist", "templates", "codex", "config.toml"),
      "utf-8",
    );
    expect(copied).toContain("# TRELLIS:CODEX_CONFIG:START");
    expect(copied).toContain("# TRELLIS:CODEX_MODEL_DEFAULTS:END");
    expect(copied).toContain("# TRELLIS:CODEX_TABLES:END");
  });
});
