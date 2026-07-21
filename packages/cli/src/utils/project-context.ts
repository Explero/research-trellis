import fs from "node:fs";
import path from "node:path";

export type ProjectInitializationKind = "existing" | "blank";

export interface ProjectFactIndex {
  kind: ProjectInitializationKind;
  documentation: string[];
  conventions: string[];
  configuration: string[];
  implementation: string[];
  records: string[];
}

const IGNORED_ENTRIES = new Set([
  ".git",
  ".trellis",
  ".claude",
  ".codex",
  ".agents",
  "node_modules",
  ".venv",
  "venv",
  "__pycache__",
  "dist",
  "build",
  "coverage",
]);

const DOCUMENTATION_NAMES = new Set([
  "README.md",
  "README",
  "CONTRIBUTING.md",
  "CHANGELOG.md",
  "DESIGN.md",
  "ARCHITECTURE.md",
  "CONTEXT.md",
  "PROJECT.md",
]);

const CONVENTION_NAMES = new Set([
  "AGENTS.md",
  "CLAUDE.md",
  "CLAUDE.local.md",
  "CONVENTIONS.md",
  ".editorconfig",
  ".cursorrules",
  ".windsurfrules",
  ".clinerules",
]);

const CONFIGURATION_NAMES = new Set([
  "package.json",
  "pnpm-workspace.yaml",
  "pyproject.toml",
  "requirements.txt",
  "poetry.lock",
  "Cargo.toml",
  "go.mod",
  "go.work",
  "pom.xml",
  "build.gradle",
  "docker-compose.yml",
  "Dockerfile",
  ".gitmodules",
]);

const IMPLEMENTATION_DIRECTORIES = new Set([
  "src",
  "app",
  "lib",
  "packages",
  "apps",
  "services",
  "server",
  "client",
  "tests",
  "test",
  "scripts",
]);

const RECORD_DIRECTORIES = new Set([
  "docs",
  "reports",
  "results",
  "artifacts",
  "data",
  "notebooks",
  "experiments",
]);

const IMPLEMENTATION_EXTENSIONS = new Set([
  ".c",
  ".cc",
  ".cpp",
  ".cs",
  ".go",
  ".java",
  ".js",
  ".jsx",
  ".kt",
  ".py",
  ".rb",
  ".rs",
  ".sh",
  ".swift",
  ".ts",
  ".tsx",
]);

function sorted(values: Iterable<string>): string[] {
  return [...values].sort((left, right) => left.localeCompare(right));
}

/**
 * Inspect only stable, root-level facts present before Trellis writes its own
 * files. This is deliberately an index, not a repository summary: callers
 * must still read the referenced source before adding project claims.
 */
export function collectProjectFactIndex(cwd: string): ProjectFactIndex {
  const documentation = new Set<string>();
  const conventions = new Set<string>();
  const configuration = new Set<string>();
  const implementation = new Set<string>();
  const records = new Set<string>();

  let entries: fs.Dirent[] = [];
  try {
    entries = fs.readdirSync(cwd, { withFileTypes: true });
  } catch {
    // The init command will surface normal filesystem failures elsewhere. An
    // empty index here keeps this helper deterministic and easy to recover.
  }

  for (const entry of entries) {
    if (IGNORED_ENTRIES.has(entry.name)) continue;
    const relative = entry.name;

    if (entry.isFile()) {
      if (DOCUMENTATION_NAMES.has(entry.name)) documentation.add(relative);
      if (CONVENTION_NAMES.has(entry.name)) conventions.add(relative);
      if (CONFIGURATION_NAMES.has(entry.name)) configuration.add(relative);
      if (IMPLEMENTATION_EXTENSIONS.has(path.extname(entry.name))) {
        implementation.add(relative);
      }
      continue;
    }

    if (!entry.isDirectory()) continue;
    if (IMPLEMENTATION_DIRECTORIES.has(entry.name))
      implementation.add(`${relative}/`);
    if (RECORD_DIRECTORIES.has(entry.name)) records.add(`${relative}/`);

    if (entry.name === ".cursor") {
      const rules = path.join(cwd, entry.name, "rules");
      if (fs.existsSync(rules)) conventions.add(".cursor/rules/");
    }
  }

  const index = {
    documentation: sorted(documentation),
    conventions: sorted(conventions),
    configuration: sorted(configuration),
    implementation: sorted(implementation),
    records: sorted(records),
  };
  const kind: ProjectInitializationKind = Object.values(index).some(
    (values) => values.length > 0,
  )
    ? "existing"
    : "blank";

  return { kind, ...index };
}

function section(title: string, entries: string[]): string {
  const lines =
    entries.length > 0
      ? entries.map((entry) => `- \`${entry}\``)
      : ["- None found at initialization time."];
  return `## ${title}\n\n${lines.join("\n")}`;
}

/** Render a stable, factual index without inferring facts from source files. */
export function renderProjectFactIndex(index: ProjectFactIndex): string {
  const introduction =
    index.kind === "existing"
      ? "This index lists root-level facts found before Trellis initialization. Read the referenced material before recording project background, research claims, or engineering rules."
      : "No project documentation, configuration, source, or record directories were found before Trellis initialization. Establish the research contract before creating implementation work.";

  return [
    "# Project Fact Index",
    "",
    introduction,
    "",
    `Initialization kind: **${index.kind}**`,
    "",
    section("Documentation", index.documentation),
    "",
    section("Conventions", index.conventions),
    "",
    section("Configuration", index.configuration),
    "",
    section("Implementation", index.implementation),
    "",
    section("Records And Data", index.records),
    "",
    "Do not treat this index as a project summary. It is a compact reading map for the main agent and the startup task.",
    "",
  ].join("\n");
}
