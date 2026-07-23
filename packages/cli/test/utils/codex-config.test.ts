import { describe, expect, it } from "vitest";
import { getConfigTemplate } from "../../src/templates/codex/index.js";
import {
  CODEX_CONFIG_BLOCK_END,
  CODEX_CONFIG_BLOCK_START,
  CODEX_MODEL_BLOCK_END,
  CODEX_MODEL_BLOCK_START,
  CODEX_TABLES_BLOCK_END,
  CODEX_TABLES_BLOCK_START,
  isTrellisCodexConfigMerge,
  mergeTrellisCodexConfig,
  stripTrellisCodexConfig,
} from "../../src/utils/codex-config.js";

const TEMPLATE = getConfigTemplate().content;

function withoutMarkers(content: string): string {
  return content
    .replace(`${CODEX_CONFIG_BLOCK_START}\n`, "")
    .replace(`\n${CODEX_CONFIG_BLOCK_END}`, "")
    .replace(`${CODEX_MODEL_BLOCK_START}\n`, "")
    .replace(`\n${CODEX_MODEL_BLOCK_END}`, "")
    .replace(`${CODEX_TABLES_BLOCK_START}\n`, "")
    .replace(`\n${CODEX_TABLES_BLOCK_END}`, "");
}

describe("mergeTrellisCodexConfig", () => {
  it("refreshes managed settings without replacing a user-selected model", () => {
    const existing = `${TEMPLATE.replace(
      'model = "gpt-5.6-sol"',
      'model = "gpt-5.6-custom"',
    )
      .replace(
        'model_reasoning_effort = "high"',
        'model_reasoning_effort = "medium"',
      )
      .replace(
        "max_concurrent_threads_per_session = 3",
        "max_concurrent_threads_per_session = 1",
      )}
[local]
keep = true
`;
    const nextTemplate = TEMPLATE.replace(
      "max_concurrent_threads_per_session = 3",
      "max_concurrent_threads_per_session = 4",
    );

    const merged = mergeTrellisCodexConfig(existing, nextTemplate);

    expect(merged.content).toContain('model = "gpt-5.6-custom"');
    expect(merged.content).toContain('model_reasoning_effort = "medium"');
    expect(merged.content).toContain("max_concurrent_threads_per_session = 4");
    expect(merged.content).toContain("[local]\nkeep = true");
    expect(merged.migratedLegacyDefaults).toBe(false);
    expect(isTrellisCodexConfigMerge(existing, merged.content)).toBe(true);
  });

  it("migrates only the exact legacy default pair", () => {
    const legacy = withoutMarkers(TEMPLATE);
    const migrated = mergeTrellisCodexConfig(legacy, TEMPLATE);

    expect(migrated.migratedLegacyDefaults).toBe(true);
    expect(migrated.content).toContain(CODEX_MODEL_BLOCK_START);
    expect(migrated.content).toContain(CODEX_MODEL_BLOCK_END);
    expect(migrated.content).not.toContain(CODEX_CONFIG_BLOCK_START);
    expect(isTrellisCodexConfigMerge(legacy, migrated.content)).toBe(true);
  });

  it("installs managed settings around an unmarked user config without replacing its model", () => {
    const existing = `model = "my-project-model"
model_reasoning_effort = "low"

[project]
name = "example"
`;

    const merged = mergeTrellisCodexConfig(existing, TEMPLATE);
    expect(merged.changed).toBe(true);
    expect(merged.migratedLegacyDefaults).toBe(false);
    expect(merged.content).toContain('model = "my-project-model"');
    expect(merged.content).toContain('model_reasoning_effort = "low"');
    expect(merged.content).not.toContain('model = "gpt-5.6-sol"');
    expect(merged.content).toContain(CODEX_CONFIG_BLOCK_START);
    expect(merged.content).toContain(CODEX_TABLES_BLOCK_START);
    expect(merged.content).toContain("[project]\nname = \"example\"");
    expect(isTrellisCodexConfigMerge(existing, merged.content)).toBe(true);
  });

  it("does not alter malformed marker blocks", () => {
    const existing = `${CODEX_CONFIG_BLOCK_START}
model = "my-project-model"
`;

    expect(mergeTrellisCodexConfig(existing, TEMPLATE).content).toBe(existing);
  });

  it("does not duplicate a user-owned Codex table when adding managed settings", () => {
    const existing = `[features.multi_agent_v2]
enabled = false
max_concurrent_threads_per_session = 1
`;
    const merged = mergeTrellisCodexConfig(existing, TEMPLATE).content;

    expect(merged.match(/\[features\.multi_agent_v2\]/g)).toHaveLength(1);
    expect(merged).toContain("enabled = false");
    expect(merged).toContain("[hermes.context_firewall]");
  });
});

describe("stripTrellisCodexConfig", () => {
  it("keeps a custom model while removing the managed block", () => {
    const custom = TEMPLATE.replace(
      'model = "gpt-5.6-sol"',
      'model = "gpt-5.6-custom"',
    );

    expect(stripTrellisCodexConfig(custom)).toBe(
      'model = "gpt-5.6-custom"\nmodel_reasoning_effort = "high"\n',
    );
  });
});
