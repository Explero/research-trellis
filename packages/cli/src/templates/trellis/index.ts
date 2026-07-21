/**
 * Trellis workflow templates
 *
 * These are GENERIC templates for user projects.
 * Do NOT use Trellis project's own .trellis/ directory (which may be customized).
 *
 * Directory structure:
 *   trellis/
 *   ├── scripts/
 *   │   ├── __init__.py
 *   │   ├── common/           # Shared utilities (Python)
 *   │   └── *.py              # Main scripts (Python)
 *   ├── scripts-shell-archive/ # Archived shell scripts (for reference)
 *   ├── workflow.md           # Workflow guide
 *   ├── config.yaml            # Trellis configuration
 *   └── gitignore.txt         # .gitignore content
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

function readTemplate(relativePath: string): string {
  return readFileSync(join(__dirname, relativePath), "utf-8");
}

function shouldSkipTemplateEntry(entry: string): boolean {
  return (
    entry === "__pycache__" || entry.endsWith(".pyc") || entry.endsWith(".pyo")
  );
}

function listTemplateFiles(relativePath: string): string[] {
  const root = join(__dirname, relativePath);
  const files: string[] = [];

  function walk(dir: string): void {
    for (const entry of readdirSync(dir)) {
      if (shouldSkipTemplateEntry(entry)) {
        continue;
      }
      const fullPath = join(dir, entry);
      if (statSync(fullPath).isDirectory()) {
        walk(fullPath);
      } else {
        files.push(
          fullPath
            .slice(root.length + 1)
            .split("\\")
            .join("/"),
        );
      }
    }
  }

  walk(root);
  return files.sort();
}

// Python scripts - package init
export const scriptsInit = readTemplate("scripts/__init__.py");

// Python scripts - common
export const commonInit = readTemplate("scripts/common/__init__.py");
export const commonPaths = readTemplate("scripts/common/paths.py");
export const commonDeveloper = readTemplate("scripts/common/developer.py");
export const commonGitContext = readTemplate("scripts/common/git_context.py");
export const commonTaskQueue = readTemplate("scripts/common/task_queue.py");
export const commonTaskUtils = readTemplate("scripts/common/task_utils.py");
export const commonActiveTask = readTemplate("scripts/common/active_task.py");
export const commonCliAdapter = readTemplate("scripts/common/cli_adapter.py");
export const commonConfig = readTemplate("scripts/common/config.py");
export const commonIo = readTemplate("scripts/common/io.py");
export const commonLog = readTemplate("scripts/common/log.py");
export const commonGit = readTemplate("scripts/common/git.py");
export const commonTypes = readTemplate("scripts/common/types.py");
export const commonTasks = readTemplate("scripts/common/tasks.py");
export const commonTaskContext = readTemplate("scripts/common/task_context.py");
export const commonTaskStore = readTemplate("scripts/common/task_store.py");
export const commonClosure = readTemplate("scripts/common/closure.py");
export const commonRoles = readTemplate("scripts/common/roles.py");
export const commonDispatch = readTemplate("scripts/common/dispatch.py");
export const commonFirewall = readTemplate("scripts/common/firewall.py");
export const commonSessionContext = readTemplate(
  "scripts/common/session_context.py",
);
export const commonPackagesContext = readTemplate(
  "scripts/common/packages_context.py",
);
export const commonWorkflowPhase = readTemplate(
  "scripts/common/workflow_phase.py",
);
export const commonTrellisConfig = readTemplate(
  "scripts/common/trellis_config.py",
);
export const commonSafeCommit = readTemplate("scripts/common/safe_commit.py");
export const commonWorktreeSync = readTemplate(
  "scripts/common/worktree_sync.py",
);
export const trellisSwitch = readTemplate("scripts/trellis_switch.py");
export const assertTrellisEnabled = readTemplate(
  "scripts/assert_trellis_enabled.py",
);

// Python scripts - main
export const getDeveloperScript = readTemplate("scripts/get_developer.py");
export const initDeveloperScript = readTemplate("scripts/init_developer.py");
export const taskScript = readTemplate("scripts/task.py");
export const getContextScript = readTemplate("scripts/get_context.py");
export const addSessionScript = readTemplate("scripts/add_session.py");
export const closureScript = readTemplate("scripts/closure.py");

// Configuration files
export const workflowMdTemplate = readTemplate("workflow.md");
export const configYamlTemplate = readTemplate("config.yaml");
export const gitignoreTemplate = readTemplate("gitignore.txt");
export const projectBackgroundTemplate = readTemplate("project/BACKGROUND.md");
export const projectResearchPlanTemplate = readTemplate(
  "project/RESEARCH_PLAN.md",
);
export const projectConstraintsTemplate = readTemplate(
  "project/CONSTRAINTS.md",
);
export const projectReadmeTemplate = readTemplate("project/README.md");

/**
 * Get all script templates as a map of relative path to content
 */
export function getAllScripts(): Map<string, string> {
  const scripts = new Map<string, string>();

  // Package init
  scripts.set("__init__.py", scriptsInit);

  // Common
  scripts.set("common/__init__.py", commonInit);
  scripts.set("common/paths.py", commonPaths);
  scripts.set("common/developer.py", commonDeveloper);
  scripts.set("common/git_context.py", commonGitContext);
  scripts.set("common/task_queue.py", commonTaskQueue);
  scripts.set("common/task_utils.py", commonTaskUtils);
  scripts.set("common/active_task.py", commonActiveTask);
  scripts.set("common/cli_adapter.py", commonCliAdapter);
  scripts.set("common/config.py", commonConfig);
  scripts.set("common/io.py", commonIo);
  scripts.set("common/log.py", commonLog);
  scripts.set("common/git.py", commonGit);
  scripts.set("common/types.py", commonTypes);
  scripts.set("common/tasks.py", commonTasks);
  scripts.set("common/task_context.py", commonTaskContext);
  scripts.set("common/task_store.py", commonTaskStore);
  scripts.set("common/closure.py", commonClosure);
  scripts.set("common/roles.py", commonRoles);
  scripts.set("common/dispatch.py", commonDispatch);
  scripts.set("common/firewall.py", commonFirewall);
  scripts.set("common/session_context.py", commonSessionContext);
  scripts.set("common/packages_context.py", commonPackagesContext);
  scripts.set("common/workflow_phase.py", commonWorkflowPhase);
  scripts.set("common/trellis_config.py", commonTrellisConfig);
  scripts.set("common/safe_commit.py", commonSafeCommit);
  scripts.set("common/worktree_sync.py", commonWorktreeSync);

  // Main
  scripts.set("get_developer.py", getDeveloperScript);
  scripts.set("init_developer.py", initDeveloperScript);
  scripts.set("task.py", taskScript);
  scripts.set("get_context.py", getContextScript);
  scripts.set("add_session.py", addSessionScript);
  scripts.set("closure.py", closureScript);
  scripts.set("trellis_switch.py", trellisSwitch);
  scripts.set("assert_trellis_enabled.py", assertTrellisEnabled);

  for (const file of listTemplateFiles("scripts/hermes")) {
    scripts.set(`hermes/${file}`, readTemplate(`scripts/hermes/${file}`));
  }

  return scripts;
}

/**
 * Get all Hermes research overlay templates as relative paths under hermes/.
 */
export function getAllHermesTemplates(): Map<string, string> {
  const templates = new Map<string, string>();

  for (const file of listTemplateFiles("hermes")) {
    templates.set(file, readTemplate(`hermes/${file}`));
  }

  return templates;
}
