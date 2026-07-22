/**
 * Scrubbers for structured config files during `research-trellis uninstall`.
 *
 * Each scrubber takes the file content (and any context it needs) and returns
 * `{ content, fullyEmpty }`:
 * - `content` is the post-scrub text to write back if the file should remain.
 * - `fullyEmpty` is true when, after stripping every trellis-managed value,
 *   nothing meaningful is left. The caller deletes the file in that case.
 *
 * Manifest path matching (for hooks.json scrubbers) uses substring containment
 * on the resolved `command` string. The leading `python3 ` / `python ` prefix
 * does not matter — we just look for the manifest-relative file path.
 */

import { stripTrellisCodexConfig } from "./codex-config.js";

const LEGACY_CODEX_COMMENTS = new Set([
  "Project-scoped Codex defaults for Trellis workflows.",
  "Codex loads this after ~/.codex/config.toml when you work in this project.",
  "Codex merges this layer after the user-level config when the project",
  "is marked as a trusted project. To trust this project, add it under",
  "`[projects]` in ~/.codex/config.toml, e.g.:",
  '[projects."/abs/path/to/this/repo"]',
  'trust_level = "trusted"',
  "Without trust, the [features] block below is loaded but disabled.",
  "Default coordinator model for this research workflow.",
  "Default coordinator model for this research workflow. Codex 0.144.0 or",
  "newer is required to recognize these model and reasoning-effort values.",
  "Keep AGENTS.md as the primary project instruction file.",
  "NOTE: Trellis's SessionStart + UserPromptSubmit hooks require opt-in.",
  "Add the following to your USER-level config at ~/.codex/config.toml",
  "(not this project file - features.* must be enabled globally):",
  "[features]",
  "hooks = true",
  "codex_hooks = true",
  "Without this flag, hooks.json is ignored and Trellis context won't",
  "be injected into Codex sessions.",
  "Codex hooks (`hooks.json` in this directory) only fire when the user",
  "has enabled them in their USER-level config: `[features].hooks = true`",
  "in ~/.codex/config.toml (Codex 0.129+; legacy name: `codex_hooks = true`,",
  "still works but emits a deprecation warning on 0.129+). Project-level",
  "config.toml cannot set feature flags; they must be user-level.",
  "Codex 0.129+ additionally gates each installed hook behind a one-time",
  "`/hooks` TUI review; until the user approves it, the hook stays inactive.",
  "multi_agent_v2 forces structured subagent orchestration with the",
  "instead of cancelling / re-spawning. Incompatible with",
  "[agents].max_threads (codex will reject the combination).",
  "NOT auto-enable the feature without it.",
  "report progress through its task record instead of holding the coordinator.",
  "short for Trellis subagents that routinely take 2-10 min. Hard",
  "ceiling is 3,600,000 (1 h).",
  "Native custom-agent dispatch cannot mechanically replace or validate the",
  "agent prompt/output, so its Context Firewall authority is advisory only.",
  "Use the generated dispatch CLI strict wrapper for enforced Hermes work:",
  "python3 ./.trellis/scripts/hermes/dispatch.py run --task <task> --job-id <job> --platform codex --mode strict",
  "Native custom-agent dispatch uses the validated Hermes dispatch and Result",
  "Envelope files. It works directly in the current project workspace.",
]);

const LEGACY_CODEX_TABLE_VALUES = new Map<string, Set<string>>([
  [
    "[features.multi_agent_v2]",
    new Set([
      "enabled = true",
      "max_concurrent_threads_per_session = 6",
      "min_wait_timeout_ms = 480000",
      "max_concurrent_threads_per_session = 3",
      "min_wait_timeout_ms = 120000",
    ]),
  ],
  [
    "[hermes.context_firewall]",
    new Set([
      'native_authority = "advisory"',
      'strict_authority = "enforced"',
      'strict_runtime = "codex exec --output-schema --json -o"',
      'native_authority = "protocol"',
    ]),
  ],
]);

function codexCommentText(line: string): string | null {
  const trimmed = line.trim();
  return trimmed.startsWith("#") ? trimmed.replace(/^#+\s?/, "").trim() : null;
}

function isLegacyCodexComment(comment: string | null): boolean {
  if (comment === null) return false;
  return (
    comment === "" ||
    LEGACY_CODEX_COMMENTS.has(comment) ||
    comment.startsWith("(not this project file") ||
    comment.startsWith("`wait` tool") ||
    comment.startsWith("`enabled = true`") ||
    comment.startsWith("- max_concurrent_threads_per_session:") ||
    comment.startsWith("- min_wait_timeout_ms:")
  );
}

function legacyCodexTableEnd(lines: string[], start: number): number | null {
  const allowedValues = LEGACY_CODEX_TABLE_VALUES.get(lines[start].trim());
  if (!allowedValues) return null;

  let end = start + 1;
  let hasValue = false;
  while (
    end < lines.length &&
    !/^\s*\[\[?[^\]]+\]\]?\s*(?:#.*)?$/.test(lines[end])
  ) {
    const trimmed = lines[end].trim();
    if (trimmed.length === 0) {
      end += 1;
      continue;
    }
    const comment = codexCommentText(lines[end]);
    if (comment !== null) {
      if (!isLegacyCodexComment(comment)) return null;
    } else if (allowedValues.has(trimmed)) {
      hasValue = true;
    } else {
      return null;
    }
    end += 1;
  }

  return hasValue ? end : null;
}

export interface ScrubResult {
  content: string;
  fullyEmpty: boolean;
}

/**
 * Test whether a hook command string references any of the given manifest paths.
 *
 * Trellis-emitted hook commands always have the shape
 *   `<python-cmd> <manifest-path>`
 * so the trailing whitespace-delimited token is the script path. We compare
 * that last token (with surrounding quotes stripped) against the manifest
 * delete-set. This is intentionally stricter than substring matching: a
 * user-added hook whose body merely mentions a deleted path inside an `echo`
 * or comment argument (`echo "see .claude/hooks/session-start.py"`) does NOT
 * match, because the trailing token is `inspiration"` (or similar) — not the
 * path. We also accept absolute-path variants like
 * `/Users/me/proj/.claude/hooks/session-start.py` via `endsWith("/" + p)`.
 */
function commandMatchesDeletedPath(
  command: string,
  deletedPaths: readonly string[],
): boolean {
  const trimmed = command.trim();
  if (trimmed.length === 0) return false;

  const tokens = trimmed.split(/\s+/);
  const lastToken = tokens[tokens.length - 1].replace(/^["']|["']$/g, "");
  if (lastToken.length === 0) return false;

  for (const p of deletedPaths) {
    if (lastToken === p || lastToken.endsWith("/" + p)) {
      return true;
    }
  }
  return false;
}

/**
 * Read the `command` (or fallback `bash` / `powershell`) string out of an
 * arbitrary hook entry. Copilot's flat schema uses `bash` + `powershell`
 * instead of `command` for some events.
 */
function getEntryCommand(entry: unknown): string | null {
  if (entry === null || typeof entry !== "object") {
    return null;
  }
  const obj = entry as Record<string, unknown>;
  if (typeof obj.command === "string") return obj.command;
  if (typeof obj.bash === "string") return obj.bash;
  if (typeof obj.powershell === "string") return obj.powershell;
  return null;
}

/**
 * Scrub a hooks-shaped settings JSON file.
 *
 * `mode = "nested"` → `hooks.{Event}.[ {matcher?, hooks: [ {command,...} ]} ]`
 * `mode = "flat"`   → `hooks.{Event}.[ {command,...} ]`
 *
 * Strips every entry whose command references a path in `deletedPaths`,
 * then bottom-up cleans empty containers (matcher block, event array, hooks
 * object). Any user-defined keys outside `hooks` (e.g. `env`, `model`,
 * `permissions`, `version`) are preserved verbatim.
 */
export function scrubHooksJson(
  content: string,
  deletedPaths: readonly string[],
  mode: "nested" | "flat",
): ScrubResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(content);
  } catch {
    // Malformed JSON — leave it untouched, caller will skip.
    return { content, fullyEmpty: false };
  }

  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    return { content, fullyEmpty: false };
  }

  const root = parsed as Record<string, unknown>;
  const hooks = root.hooks;

  if (hooks === undefined) {
    // No hooks block — nothing to scrub. Treat as fully empty only if the
    // entire file has no other keys.
    const fullyEmpty = Object.keys(root).length === 0;
    return { content: JSON.stringify(root, null, 2) + "\n", fullyEmpty };
  }

  if (hooks === null || typeof hooks !== "object" || Array.isArray(hooks)) {
    // hooks is some unexpected shape — leave it alone.
    return { content, fullyEmpty: false };
  }

  const hooksObj = hooks as Record<string, unknown>;

  for (const eventName of Object.keys(hooksObj)) {
    const eventArr = hooksObj[eventName];
    if (!Array.isArray(eventArr)) continue;

    const filteredEvent: unknown[] = [];

    for (const entry of eventArr) {
      if (mode === "flat") {
        const cmd = getEntryCommand(entry);
        if (cmd !== null && commandMatchesDeletedPath(cmd, deletedPaths)) {
          continue; // drop trellis entry
        }
        filteredEvent.push(entry);
      } else {
        // nested: entry is { matcher?, hooks: [...] }
        if (entry === null || typeof entry !== "object") {
          filteredEvent.push(entry);
          continue;
        }
        const matcherBlock = entry as Record<string, unknown>;
        const inner = matcherBlock.hooks;
        if (!Array.isArray(inner)) {
          filteredEvent.push(entry);
          continue;
        }

        const filteredInner = inner.filter((sub) => {
          const cmd = getEntryCommand(sub);
          return !(
            cmd !== null && commandMatchesDeletedPath(cmd, deletedPaths)
          );
        });

        if (filteredInner.length === 0) {
          // Whole matcher block is now empty → drop the block.
          continue;
        }

        // Reconstruct the block with the filtered inner list.
        const rebuilt: Record<string, unknown> = { ...matcherBlock };
        rebuilt.hooks = filteredInner;
        filteredEvent.push(rebuilt);
      }
    }

    if (filteredEvent.length === 0) {
      // Drop the whole event array.
      // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
      delete hooksObj[eventName];
    } else {
      hooksObj[eventName] = filteredEvent;
    }
  }

  // If hooks is empty → drop the key.
  if (Object.keys(hooksObj).length === 0) {
    delete root.hooks;
  } else {
    root.hooks = hooksObj;
  }

  const fullyEmpty = Object.keys(root).length === 0;
  return {
    content: JSON.stringify(root, null, 2) + "\n",
    fullyEmpty,
  };
}

/**
 * Scrub `.opencode/package.json`:
 * - remove `dependencies["@opencode-ai/plugin"]`
 * - if `dependencies` ends up empty → drop the field
 * - fully empty when nothing is left in the object
 */
export function scrubOpencodePackageJson(content: string): ScrubResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(content);
  } catch {
    return { content, fullyEmpty: false };
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    return { content, fullyEmpty: false };
  }

  const root = parsed as Record<string, unknown>;
  const deps = root.dependencies;

  if (deps !== null && typeof deps === "object" && !Array.isArray(deps)) {
    const depsObj = deps as Record<string, unknown>;
    if ("@opencode-ai/plugin" in depsObj) {
      delete depsObj["@opencode-ai/plugin"];
    }
    if (Object.keys(depsObj).length === 0) {
      delete root.dependencies;
    } else {
      root.dependencies = depsObj;
    }
  }

  const fullyEmpty = Object.keys(root).length === 0;
  return {
    content: JSON.stringify(root, null, 2) + "\n",
    fullyEmpty,
  };
}

/**
 * Trellis-specific values written by the Pi configurator.
 *
 * The `extensions`/`skills`/`prompts` arrays are paths relative to `.pi/`. We
 * remove the exact entries that the Pi configurator emits.
 */
const PI_TRELLIS_EXTENSION = "./extensions/trellis/index.ts";
const PI_TRELLIS_SKILLS = "./skills";
const PI_TRELLIS_PROMPTS = "./prompts";
const PI_SUBAGENTS_PACKAGE = "npm:pi-subagents";

function isTrellisPiEntry(value: unknown, target: string): boolean {
  return typeof value === "string" && value === target;
}

/**
 * Scrub `.pi/settings.json`:
 * - drop `enableSkillCommands` (trellis-flagged)
 * - remove trellis entries from `extensions`/`skills`/`prompts` arrays
 * - remove trellis-managed `packages["npm:pi-subagents"]` isolation override
 * - drop arrays that become empty
 */
export function scrubPiSettings(content: string): ScrubResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(content);
  } catch {
    return { content, fullyEmpty: false };
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    return { content, fullyEmpty: false };
  }

  const root = parsed as Record<string, unknown>;

  if ("enableSkillCommands" in root) {
    delete root.enableSkillCommands;
  }

  const arrayCleanups: [string, string][] = [
    ["extensions", PI_TRELLIS_EXTENSION],
    ["skills", PI_TRELLIS_SKILLS],
    ["prompts", PI_TRELLIS_PROMPTS],
  ];
  for (const [key, target] of arrayCleanups) {
    const arr = root[key];
    if (!Array.isArray(arr)) continue;
    const filtered = arr.filter((v) => !isTrellisPiEntry(v, target));
    if (filtered.length === 0) {
      // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
      delete root[key];
    } else {
      root[key] = filtered;
    }
  }

  const packagesValue = root.packages;
  if (Array.isArray(packagesValue)) {
    const filtered = packagesValue.filter((entry) => {
      if (
        entry !== null &&
        typeof entry === "object" &&
        !Array.isArray(entry)
      ) {
        const obj = entry as Record<string, unknown>;
        return obj.source !== PI_SUBAGENTS_PACKAGE;
      }
      // String entries — keep unless they exactly match the package name
      return entry !== PI_SUBAGENTS_PACKAGE;
    });
    if (filtered.length === 0) {
      delete root.packages;
    } else {
      root.packages = filtered;
    }
  }

  const fullyEmpty = Object.keys(root).length === 0;
  return {
    content: JSON.stringify(root, null, 2) + "\n",
    fullyEmpty,
  };
}

/**
 * Scrub `.codex/config.toml`.
 *
 * Explicit Trellis marker blocks are removed as units. A custom model inside
 * those blocks is retained. Older unmarked Trellis defaults are recognized by
 * their exact values, so user-owned configuration stays intact.
 */
export function scrubCodexConfigToml(content: string): ScrubResult {
  const stripped = stripTrellisCodexConfig(content);
  const lines = stripped.split(/\r?\n/);
  const kept: string[] = [];
  let previousBlank = true;
  for (let index = 0; index < lines.length; index += 1) {
    const tableEnd = legacyCodexTableEnd(lines, index);
    if (tableEnd !== null) {
      index = tableEnd - 1;
      continue;
    }

    const line = lines[index];
    const trimmed = line.trim();
    const comment = codexCommentText(line);
    const trellisLegacyLine =
      /^\s*project_doc_fallback_filenames\s*=\s*\[\s*"AGENTS\.md"\s*\]\s*$/.test(
        line,
      ) || isLegacyCodexComment(comment);
    if (trellisLegacyLine) continue;
    const blank = trimmed.length === 0;
    if (blank && previousBlank) continue;
    kept.push(line);
    previousBlank = blank;
  }
  while (kept.length > 0 && kept[kept.length - 1].trim() === "") {
    kept.pop();
  }
  const result = kept.length > 0 ? `${kept.join("\n")}\n` : "";
  const fullyEmpty = result.trim().length === 0;
  return { content: result, fullyEmpty };
}
