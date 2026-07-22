export const CODEX_CONFIG_BLOCK_START = "# TRELLIS:CODEX_CONFIG:START";
export const CODEX_CONFIG_BLOCK_END = "# TRELLIS:CODEX_CONFIG:END";
export const CODEX_MODEL_BLOCK_START = "# TRELLIS:CODEX_MODEL_DEFAULTS:START";
export const CODEX_MODEL_BLOCK_END = "# TRELLIS:CODEX_MODEL_DEFAULTS:END";
export const CODEX_TABLES_BLOCK_START = "# TRELLIS:CODEX_TABLES:START";
export const CODEX_TABLES_BLOCK_END = "# TRELLIS:CODEX_TABLES:END";

const LEGACY_MODEL_LINE = /^\s*model\s*=\s*"gpt-5\.6-sol"\s*$/;
const LEGACY_REASONING_LINE = /^\s*model_reasoning_effort\s*=\s*"high"\s*$/;
const MODEL_ASSIGNMENT = /^\s*model\s*=/;
const REASONING_ASSIGNMENT = /^\s*model_reasoning_effort\s*=/;
const TABLE_HEADER = /^\s*\[\[?[^\]]+\]\]?\s*(?:#.*)?$/;

export interface CodexConfigMergeResult {
  content: string;
  changed: boolean;
  migratedLegacyDefaults: boolean;
}

interface BlockRange {
  start: number;
  end: number;
}

interface TopLevelModelAssignment {
  index: number;
  line: string;
  kind: "model" | "reasoning";
}

function markerRange(
  content: string,
  startMarker: string,
  endMarker: string,
): BlockRange | null {
  const start = content.indexOf(startMarker);
  if (
    start < 0 ||
    content.indexOf(startMarker, start + startMarker.length) !== -1
  ) {
    return null;
  }
  const endStart = content.indexOf(endMarker, start + startMarker.length);
  if (
    endStart < 0 ||
    content.indexOf(endMarker, endStart + endMarker.length) !== -1
  ) {
    return null;
  }
  return { start, end: endStart + endMarker.length };
}

function hasAnyTrellisMarker(content: string): boolean {
  return [
    CODEX_CONFIG_BLOCK_START,
    CODEX_CONFIG_BLOCK_END,
    CODEX_MODEL_BLOCK_START,
    CODEX_MODEL_BLOCK_END,
    CODEX_TABLES_BLOCK_START,
    CODEX_TABLES_BLOCK_END,
  ].some((marker) => content.includes(marker));
}

function replaceRange(
  content: string,
  range: BlockRange,
  replacement: string,
): string {
  return content.slice(0, range.start) + replacement + content.slice(range.end);
}

function topLevelModelAssignments(content: string): TopLevelModelAssignment[] {
  const assignments: TopLevelModelAssignment[] = [];
  let inTable = false;

  for (const [index, line] of content.split(/\r?\n/).entries()) {
    if (TABLE_HEADER.test(line)) {
      inTable = true;
      continue;
    }
    if (inTable) continue;
    if (MODEL_ASSIGNMENT.test(line)) {
      assignments.push({ index, line, kind: "model" });
    } else if (REASONING_ASSIGNMENT.test(line)) {
      assignments.push({ index, line, kind: "reasoning" });
    }
  }

  return assignments;
}

function topLevelLegacyDefaultLines(content: string): {
  model: number;
  reasoning: number;
} | null {
  const assignments = topLevelModelAssignments(content);
  if (assignments.length !== 2) return null;

  const model = assignments.find(
    (assignment) =>
      assignment.kind === "model" && LEGACY_MODEL_LINE.test(assignment.line),
  );
  const reasoning = assignments.find(
    (assignment) =>
      assignment.kind === "reasoning" &&
      LEGACY_REASONING_LINE.test(assignment.line),
  );

  return model && reasoning
    ? { model: model.index, reasoning: reasoning.index }
    : null;
}

function customTopLevelModelLines(content: string): string[] | null {
  const assignments = topLevelModelAssignments(content);
  if (assignments.length === 0 || topLevelLegacyDefaultLines(content)) {
    return null;
  }
  return assignments.map((assignment) => assignment.line);
}

function modelBlock(template: string): string | null {
  const range = markerRange(
    template,
    CODEX_MODEL_BLOCK_START,
    CODEX_MODEL_BLOCK_END,
  );
  return range ? template.slice(range.start, range.end) : null;
}

function buildModelBlock(lines: string[]): string {
  return [CODEX_MODEL_BLOCK_START, ...lines, CODEX_MODEL_BLOCK_END].join("\n");
}

function preserveCustomModelBlock(template: string, source: string): string {
  const customLines = customTopLevelModelLines(source);
  if (!customLines) return template;

  const range = markerRange(
    template,
    CODEX_MODEL_BLOCK_START,
    CODEX_MODEL_BLOCK_END,
  );
  return range
    ? replaceRange(template, range, buildModelBlock(customLines))
    : template;
}

function removeModelBlock(content: string): string {
  const range = markerRange(
    content,
    CODEX_MODEL_BLOCK_START,
    CODEX_MODEL_BLOCK_END,
  );
  return range ? replaceRange(content, range, "") : content;
}

function migrateLegacyDefaults(
  existing: string,
  template: string,
): string | null {
  const defaults = topLevelLegacyDefaultLines(existing);
  const replacement = modelBlock(template);
  if (!defaults || !replacement) return null;

  const lines = existing.split(/\r?\n/);
  const insertAt = Math.min(defaults.model, defaults.reasoning);
  const remove = new Set([defaults.model, defaults.reasoning]);
  const result: string[] = [];
  for (const [index, line] of lines.entries()) {
    if (index === insertAt) {
      result.push(replacement);
    }
    if (!remove.has(index)) {
      result.push(line);
    }
  }
  return result.join("\n");
}

function mergeWholeConfigBlock(
  existing: string,
  template: string,
): string | null {
  const current = markerRange(
    existing,
    CODEX_CONFIG_BLOCK_START,
    CODEX_CONFIG_BLOCK_END,
  );
  const replacement = markerRange(
    template,
    CODEX_CONFIG_BLOCK_START,
    CODEX_CONFIG_BLOCK_END,
  );
  if (!current || !replacement) return null;

  const existingBlock = existing.slice(current.start, current.end);
  const existingPrefix = existing.slice(0, current.start);
  const hasUserModelBeforeBlock =
    topLevelModelAssignments(existingPrefix).length > 0;
  let nextBlock = template.slice(replacement.start, replacement.end);

  if (hasUserModelBeforeBlock) {
    nextBlock = removeModelBlock(nextBlock);
  } else {
    nextBlock = preserveCustomModelBlock(nextBlock, existingBlock);
  }

  const legacyWholeBlock = existingBlock
    .split(/\r?\n/)
    .some((line) => TABLE_HEADER.test(line));
  const tables = markerRange(
    template,
    CODEX_TABLES_BLOCK_START,
    CODEX_TABLES_BLOCK_END,
  );
  if (legacyWholeBlock && tables) {
    nextBlock += `\n\n${template.slice(tables.start, tables.end)}`;
  }
  return replaceRange(existing, current, nextBlock);
}

function mergeTablesBlock(existing: string, template: string): string {
  const current = markerRange(
    existing,
    CODEX_TABLES_BLOCK_START,
    CODEX_TABLES_BLOCK_END,
  );
  const replacement = markerRange(
    template,
    CODEX_TABLES_BLOCK_START,
    CODEX_TABLES_BLOCK_END,
  );
  if (!current || !replacement) return existing;
  return replaceRange(
    existing,
    current,
    managedTablesForExisting(template, existing),
  );
}

function tableHeaders(content: string): Set<string> {
  return new Set(
    content
      .split(/\r?\n/)
      .filter((line) => TABLE_HEADER.test(line))
      .map((line) => line.trim()),
  );
}

function managedTablesForExisting(template: string, existing: string): string {
  const templateRange = markerRange(
    template,
    CODEX_TABLES_BLOCK_START,
    CODEX_TABLES_BLOCK_END,
  );
  if (!templateRange) return "";
  const currentRange = markerRange(
    existing,
    CODEX_TABLES_BLOCK_START,
    CODEX_TABLES_BLOCK_END,
  );
  const external = currentRange
    ? replaceRange(existing, currentRange, "")
    : existing;
  const existingHeaders = tableHeaders(external);
  if (existingHeaders.size === 0) {
    return template.slice(templateRange.start, templateRange.end);
  }

  const lines = template
    .slice(templateRange.start, templateRange.end)
    .split(/\r?\n/);
  const sections: string[][] = [];
  for (let index = 0; index < lines.length; index += 1) {
    if (!TABLE_HEADER.test(lines[index])) continue;
    let end = index + 1;
    while (
      end < lines.length &&
      !TABLE_HEADER.test(lines[end]) &&
      lines[end] !== CODEX_TABLES_BLOCK_END
    ) {
      end += 1;
    }
    if (!existingHeaders.has(lines[index].trim())) {
      sections.push(lines.slice(index, end));
    }
    index = end - 1;
  }
  return [
    CODEX_TABLES_BLOCK_START,
    ...sections.flat(),
    CODEX_TABLES_BLOCK_END,
  ].join("\n");
}

function firstTableLine(lines: string[]): number {
  const index = lines.findIndex((line) => TABLE_HEADER.test(line));
  return index < 0 ? lines.length : index;
}

function withoutProjectDocDefault(block: string): string {
  return block
    .split(/\r?\n/)
    .filter((line) => !/^\s*project_doc_fallback_filenames\s*=/.test(line))
    .join("\n");
}

function mergeUnmarkedConfig(
  existing: string,
  template: string,
): string | null {
  const topRange = markerRange(
    template,
    CODEX_CONFIG_BLOCK_START,
    CODEX_CONFIG_BLOCK_END,
  );
  const tablesRange = markerRange(
    template,
    CODEX_TABLES_BLOCK_START,
    CODEX_TABLES_BLOCK_END,
  );
  if (!topRange || !tablesRange) return null;

  const lines = existing.split(/\r?\n/);
  const tableAt = firstTableLine(lines);
  const userTop = lines.slice(0, tableAt).join("\n").trim();
  const userTables = lines.slice(tableAt).join("\n").trim();
  let managedTop = template.slice(topRange.start, topRange.end);
  if (topLevelModelAssignments(userTop).length > 0) {
    managedTop = removeModelBlock(managedTop);
  }
  if (/^\s*project_doc_fallback_filenames\s*=/m.test(userTop)) {
    managedTop = withoutProjectDocDefault(managedTop);
  }
  const managedTables = managedTablesForExisting(template, existing);
  return (
    [userTop, managedTop.trim(), userTables, managedTables.trim()]
      .filter(Boolean)
      .join("\n\n") + "\n"
  );
}

function mergeModelDefaultsBlock(
  existing: string,
  template: string,
): string | null {
  const current = markerRange(
    existing,
    CODEX_MODEL_BLOCK_START,
    CODEX_MODEL_BLOCK_END,
  );
  const replacement = markerRange(
    template,
    CODEX_MODEL_BLOCK_START,
    CODEX_MODEL_BLOCK_END,
  );
  if (!current || !replacement) return null;

  const existingPrefix = existing.slice(0, current.start);
  const hasUserModelBeforeBlock =
    topLevelModelAssignments(existingPrefix).length > 0;
  const nextBlock = hasUserModelBeforeBlock
    ? ""
    : preserveCustomModelBlock(
        template.slice(replacement.start, replacement.end),
        existing.slice(current.start, current.end),
      );

  return replaceRange(existing, current, nextBlock);
}

/**
 * Preserve content outside Trellis markers. A user-selected model inside a
 * managed block survives template updates. An old unmarked exact default pair
 * is migrated in place; other unmarked configuration is left untouched.
 */
export function mergeTrellisCodexConfig(
  existing: string,
  template: string,
): CodexConfigMergeResult {
  const wholeBlock = mergeWholeConfigBlock(existing, template);
  if (wholeBlock !== null) {
    const merged = mergeTablesBlock(wholeBlock, template);
    return {
      content: merged,
      changed: merged !== existing,
      migratedLegacyDefaults: false,
    };
  }

  const defaultsBlock = mergeModelDefaultsBlock(existing, template);
  if (defaultsBlock !== null) {
    return {
      content: defaultsBlock,
      changed: defaultsBlock !== existing,
      migratedLegacyDefaults: false,
    };
  }

  if (hasAnyTrellisMarker(existing)) {
    return { content: existing, changed: false, migratedLegacyDefaults: false };
  }

  const migrated = migrateLegacyDefaults(existing, template);
  if (migrated !== null) {
    return {
      content: migrated,
      changed: migrated !== existing,
      migratedLegacyDefaults: true,
    };
  }
  const merged = mergeUnmarkedConfig(existing, template);
  return {
    content: merged ?? existing,
    changed: merged !== null && merged !== existing,
    migratedLegacyDefaults: false,
  };
}

export function isLegacyCodexDefaultMigration(
  existing: string,
  candidate: string,
): boolean {
  const migrated = migrateLegacyDefaults(existing, candidate);
  return migrated !== null && migrated === candidate;
}

/** True when an update candidate only replaces Trellis-managed configuration. */
export function isTrellisCodexConfigMerge(
  existing: string,
  candidate: string,
): boolean {
  return (
    stripTrellisCodexConfig(existing) === stripTrellisCodexConfig(candidate) ||
    isLegacyCodexDefaultMigration(existing, candidate)
  );
}

function removeLegacyDefaultLines(content: string): string {
  const defaults = topLevelLegacyDefaultLines(content);
  if (!defaults) return content;
  const remove = new Set([defaults.model, defaults.reasoning]);
  return content
    .split(/\r?\n/)
    .filter((_line, index) => !remove.has(index))
    .join("\n");
}

function customModelLinesFromBlock(content: string): string {
  return customTopLevelModelLines(content)?.join("\n") ?? "";
}

/**
 * Remove Trellis configuration while preserving a user-selected model. Older
 * unmarked files lose only the exact legacy default model pair.
 */
export function stripTrellisCodexConfig(content: string): string {
  const wholeBlock = markerRange(
    content,
    CODEX_CONFIG_BLOCK_START,
    CODEX_CONFIG_BLOCK_END,
  );
  let result = content;

  if (wholeBlock) {
    result = replaceRange(
      result,
      wholeBlock,
      customModelLinesFromBlock(
        content.slice(wholeBlock.start, wholeBlock.end),
      ),
    );
  } else {
    const defaultsBlock = markerRange(
      result,
      CODEX_MODEL_BLOCK_START,
      CODEX_MODEL_BLOCK_END,
    );
    if (defaultsBlock) {
      result = replaceRange(
        result,
        defaultsBlock,
        customModelLinesFromBlock(
          result.slice(defaultsBlock.start, defaultsBlock.end),
        ),
      );
    }
  }

  const tablesBlock = markerRange(
    result,
    CODEX_TABLES_BLOCK_START,
    CODEX_TABLES_BLOCK_END,
  );
  if (tablesBlock) {
    result = replaceRange(result, tablesBlock, "");
  }

  result = removeLegacyDefaultLines(result);
  const lines = result.split(/\r?\n/);
  const compacted: string[] = [];
  let previousBlank = true;
  for (const line of lines) {
    const blank = line.trim().length === 0;
    if (blank && previousBlank) continue;
    compacted.push(line);
    previousBlank = blank;
  }
  while (
    compacted.length > 0 &&
    compacted[compacted.length - 1].trim() === ""
  ) {
    compacted.pop();
  }
  return compacted.length > 0 ? `${compacted.join("\n")}\n` : "";
}
