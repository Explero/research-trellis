#!/usr/bin/env node
/**
 * Hermes deployment preflight.
 *
 * This is intentionally a thin gate: it checks the runtime templates that are
 * most likely to block deployment, and it prints explicit next commands when
 * quick mode skips heavy checks.
 */
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_REPO_ROOT = path.resolve(__dirname, "../../..");

const GREEN = "\x1b[32m";
const RED = "\x1b[31m";
const YELLOW = "\x1b[33m";
const RESET = "\x1b[0m";

const REQUIRED_FILES = [
  "packages/cli/src/templates/trellis/hermes/config.yaml",
  "packages/cli/src/templates/trellis/hermes/HERMES_MAIN_AGENT_BOOT_GUARD.md",
  "packages/cli/src/templates/trellis/hermes/experiments/experiment.yaml",
  "packages/cli/src/templates/trellis/hermes/metrics/metrics_schema.yaml",
  "packages/cli/src/templates/trellis/hermes/reports/report.md",
  "packages/cli/src/templates/trellis/hermes/roles/base.md",
  "packages/cli/src/templates/trellis/hermes/roles/planner.md",
  "packages/cli/src/templates/trellis/hermes/roles/researcher.md",
  "packages/cli/src/templates/trellis/hermes/roles/coder.md",
  "packages/cli/src/templates/trellis/hermes/roles/runner.md",
  "packages/cli/src/templates/trellis/hermes/roles/reviewer.md",
  "packages/cli/src/templates/trellis/scripts/closure.py",
  "packages/cli/src/templates/trellis/scripts/common/closure.py",
  "packages/cli/src/templates/trellis/scripts/common/roles.py",
  "packages/cli/src/templates/trellis/scripts/common/dispatch.py",
  "packages/cli/src/templates/trellis/scripts/common/firewall.py",
  "packages/cli/src/templates/trellis/scripts/hermes/dispatch.py",
  "packages/cli/src/templates/trellis/hermes/schemas/result-envelope.schema.json",
  "packages/cli/src/templates/trellis/scripts/hermes/evidence.py",
  "packages/cli/src/templates/trellis/scripts/hermes/runner.py",
  "packages/cli/src/templates/trellis/scripts/hermes/report.py",
  "packages/cli/src/templates/trellis/scripts/hermes/service.py",
  "packages/cli/src/templates/shared-hooks/hermes-runtime-guard.py",
];

const TEMPLATE_TEST_ARGS = [
  "exec",
  "vitest",
  "run",
  "test/templates/hermes-runtime.test.ts",
  "test/templates/trellis.test.ts",
  "test/templates/claude.test.ts",
  "test/templates/codex.test.ts",
  "test/templates/shared-hooks.test.ts",
  "test/scripts/agent-context-firewall.integration.test.ts",
  "test/scripts/closure.integration.test.ts",
];

function result(name, ok, messages = []) {
  return { name, ok, messages };
}

function rel(root, filePath) {
  return path.relative(root, filePath).split(path.sep).join("/");
}

function walkFiles(root, predicate) {
  const found = [];
  if (!fs.existsSync(root)) return found;
  const stack = [root];
  while (stack.length > 0) {
    const current = stack.pop();
    const stat = fs.lstatSync(current);
    if (stat.isDirectory()) {
      for (const entry of fs.readdirSync(current)) {
        stack.push(path.join(current, entry));
      }
      continue;
    }
    if (stat.isFile() && predicate(current)) {
      found.push(current);
    }
  }
  return found.sort();
}

export function checkHermesRequiredFiles(repoRoot = DEFAULT_REPO_ROOT) {
  const missing = REQUIRED_FILES.filter(
    (relativePath) => !fs.existsSync(path.join(repoRoot, relativePath)),
  );
  return result(
    "Hermes required files",
    missing.length === 0,
    missing.map((file) => `missing required file: ${file}`),
  );
}

export function checkNoPythonCaches(repoRoot = DEFAULT_REPO_ROOT) {
  const templateRoot = path.join(repoRoot, "packages/cli/src/templates");
  const polluted = [];
  const stack = fs.existsSync(templateRoot) ? [templateRoot] : [];
  while (stack.length > 0) {
    const current = stack.pop();
    const stat = fs.lstatSync(current);
    if (stat.isDirectory()) {
      if (path.basename(current) === "__pycache__") {
        polluted.push(current);
      }
      for (const entry of fs.readdirSync(current)) {
        stack.push(path.join(current, entry));
      }
      continue;
    }
    if (stat.isFile() && current.endsWith(".pyc")) {
      polluted.push(current);
    }
  }
  return result(
    "Template Python cache pollution",
    polluted.length === 0,
    polluted.sort().map((file) => `template cache pollution: ${rel(repoRoot, file)}`),
  );
}

export function checkHookMatcherIncludes(repoRoot = DEFAULT_REPO_ROOT) {
  const hookPath = path.join(
    repoRoot,
    "packages/cli/src/templates/shared-hooks/hermes-runtime-guard.py",
  );
  if (!fs.existsSync(hookPath)) {
    return result("Hermes hook matcher", false, [
      "missing shared-hooks/hermes-runtime-guard.py",
    ]);
  }
  const content = fs.readFileSync(hookPath, "utf-8");
  const messages = [];
  for (const matcher of ["MultiEdit", "Bash"]) {
    if (!content.includes(`"${matcher}"`) && !content.includes(`'${matcher}'`)) {
      messages.push(`hook matcher missing ${matcher}`);
    }
  }
  if (!content.includes("BASH_EXECUTION_ROLES")) {
    messages.push("Bash execution role boundary is missing");
  }
  return result("Hermes hook matcher", messages.length === 0, messages);
}

export function checkLocalRunnerConfiguration(repoRoot = DEFAULT_REPO_ROOT) {
  const configPath = path.join(
    repoRoot,
    "packages/cli/src/templates/trellis/hermes/config.yaml",
  );
  const experimentPath = path.join(
    repoRoot,
    "packages/cli/src/templates/trellis/hermes/experiments/experiment.yaml",
  );
  const messages = [];
  for (const requiredPath of [configPath, experimentPath]) {
    if (!fs.existsSync(requiredPath)) {
      messages.push(`missing local runner file: ${rel(repoRoot, requiredPath)}`);
    }
  }
  const config = fs.existsSync(configPath) ? fs.readFileSync(configPath, "utf-8") : "";
  const experiment = fs.existsSync(experimentPath) ? fs.readFileSync(experimentPath, "utf-8") : "";
  if (!config.includes("runs directly in the project workspace")) {
    messages.push("config.yaml must describe direct project-workspace execution");
  }
  for (const text of ["allowed_commands:", "artifact_dir:"]) {
    if (!experiment.includes(text)) {
      messages.push(`experiment.yaml must include ${text}`);
    }
  }
  if (config.includes("sandbox:") || experiment.includes("sandbox:")) {
    messages.push("local runner templates must not configure a sandbox");
  }
  return result("Hermes local runner configuration", messages.length === 0, messages);
}

export function checkPythonCompile(repoRoot = DEFAULT_REPO_ROOT) {
  const pythonFiles = [
    ...walkFiles(
      path.join(repoRoot, "packages/cli/src/templates/trellis/scripts"),
      (file) => file.endsWith(".py"),
    ),
    ...walkFiles(
      path.join(repoRoot, "packages/cli/src/templates/shared-hooks"),
      (file) => file.endsWith(".py"),
    ),
  ];
  if (pythonFiles.length === 0) {
    return result("Python compile", false, ["no Python template files found"]);
  }
  const pycache = fs.mkdtempSync(path.join(os.tmpdir(), "research-trellis-pycache-"));
  try {
    const run = spawnSync("python3", ["-m", "py_compile", ...pythonFiles], {
      cwd: repoRoot,
      encoding: "utf-8",
      env: {
        ...process.env,
        PYTHONPYCACHEPREFIX: pycache,
      },
    });
    const messages = [];
    if (run.status !== 0) {
      messages.push((run.stderr || run.stdout || "python compile failed").trim());
    }
    const cacheCheck = checkNoPythonCaches(repoRoot);
    messages.push(...cacheCheck.messages);
    return result("Python compile", run.status === 0 && cacheCheck.ok, messages);
  } finally {
    fs.rmSync(pycache, { recursive: true, force: true });
  }
}

function runCommandCheck(name, repoRoot, command, args) {
  const run = spawnSync(command, args, {
    cwd: repoRoot,
    encoding: "utf-8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  const output = `${run.stdout || ""}${run.stderr || ""}`.trim();
  return result(name, run.status === 0, output ? [output] : []);
}

function printResult(check) {
  const mark = check.ok ? `${GREEN}ok${RESET}` : `${RED}fail${RESET}`;
  console.log(`${mark} ${check.name}`);
  for (const message of check.messages) {
    console.log(`  ${message}`);
  }
}

function parseArgs(argv) {
  const args = {
    quick: false,
    skipPythonCompile: false,
    repoRoot: DEFAULT_REPO_ROOT,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--") {
      continue;
    } else if (arg === "--quick") {
      args.quick = true;
    } else if (arg === "--skip-python-compile") {
      args.skipPythonCompile = true;
    } else if (arg === "--repo-root") {
      args.repoRoot = path.resolve(argv[i + 1] || "");
      i += 1;
    } else if (arg === "--help" || arg === "-h") {
      args.help = true;
    } else {
      throw new Error(`unknown argument: ${arg}`);
    }
  }
  return args;
}

function usage() {
  return [
    "Usage: node packages/cli/scripts/hermes-preflight.js [--quick] [--skip-python-compile]",
    "",
    "--quick skips template vitest, typecheck, and build, but keeps template/file/cache checks.",
  ].join("\n");
}

export function runPreflight(options = {}) {
  const repoRoot = options.repoRoot || DEFAULT_REPO_ROOT;
  const quick = Boolean(options.quick);
  const checks = [
    checkHermesRequiredFiles(repoRoot),
    checkNoPythonCaches(repoRoot),
    checkHookMatcherIncludes(repoRoot),
    checkLocalRunnerConfiguration(repoRoot),
  ];

  if (options.skipPythonCompile) {
    checks.push(result("Python compile", true, ["skipped by --skip-python-compile"]));
  } else {
    checks.push(checkPythonCompile(repoRoot));
  }

  if (quick) {
    checks.push(
      result("Template tests", true, [
        `${YELLOW}quick mode${RESET}: skipped; run pnpm --filter research-trellis ${TEMPLATE_TEST_ARGS.join(" ")}`,
      ]),
      result("Typecheck", true, [
        `${YELLOW}quick mode${RESET}: skipped; run pnpm --filter research-trellis typecheck`,
      ]),
      result("Build", true, [
        `${YELLOW}quick mode${RESET}: skipped; run pnpm --filter research-trellis build`,
      ]),
    );
  } else {
    checks.push(
      runCommandCheck("Template tests", repoRoot, "pnpm", [
        "--filter",
        "research-trellis",
        ...TEMPLATE_TEST_ARGS,
      ]),
      runCommandCheck("Typecheck", repoRoot, "pnpm", [
        "--filter",
        "research-trellis",
        "typecheck",
      ]),
      runCommandCheck("Build", repoRoot, "pnpm", [
        "--filter",
        "research-trellis",
        "build",
      ]),
    );
  }

  return checks;
}

async function main() {
  let args;
  try {
    args = parseArgs(process.argv.slice(2));
  } catch (error) {
    console.error(`${RED}x ${error.message}${RESET}`);
    console.error(usage());
    return 2;
  }
  if (args.help) {
    console.log(usage());
    return 0;
  }

  console.log(
    `Hermes local workflow preflight${args.quick ? " (quick mode)" : ""}`,
  );
  console.log(
    "Scope: lightweight local research collaboration.",
  );
  console.log(
    "Runner: commands execute in the current project workspace; allowed_commands records the experiment contract.",
  );
  const checks = runPreflight(args);
  for (const check of checks) {
    printResult(check);
  }
  return checks.every((check) => check.ok) ? 0 : 1;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main().then((code) => {
    process.exitCode = code;
  });
}
