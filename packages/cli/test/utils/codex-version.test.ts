import { describe, expect, it } from "vitest";
import {
  codexVersionWarning,
  parseCodexVersion,
  probeCodexVersion,
} from "../../src/utils/codex-version.js";

describe("parseCodexVersion", () => {
  it("reads stable, v-prefixed, and prerelease versions", () => {
    expect(parseCodexVersion("codex-cli 0.144.0")).toBe("0.144.0");
    expect(parseCodexVersion("codex v0.145.0-beta.1+build.7")).toBe(
      "0.145.0-beta.1+build.7",
    );
  });

  it("returns null when no semantic version is available", () => {
    expect(parseCodexVersion("codex-cli development build")).toBeNull();
  });
});

describe("probeCodexVersion", () => {
  it("classifies supported and unsupported releases", () => {
    expect(probeCodexVersion(() => "codex-cli 0.144.0")).toMatchObject({
      status: "available",
      version: "0.144.0",
      supported: true,
    });
    expect(probeCodexVersion(() => "codex-cli 0.144.0-rc.1")).toMatchObject({
      status: "available",
      version: "0.144.0-rc.1",
      supported: false,
    });
    expect(probeCodexVersion(() => "codex-cli 0.145.0-beta.1")).toMatchObject({
      status: "available",
      version: "0.145.0-beta.1",
      supported: true,
    });
  });

  it("distinguishes a missing binary from unreadable output", () => {
    const missing = Object.assign(new Error("missing"), { code: "ENOENT" });

    expect(
      probeCodexVersion(() => {
        throw missing;
      }),
    ).toMatchObject({
      status: "missing",
      raw: null,
      version: null,
      supported: false,
    });
    expect(probeCodexVersion(() => "not a version")).toMatchObject({
      status: "unreadable",
      raw: "not a version",
      version: null,
      supported: false,
    });
  });
});

describe("codexVersionWarning", () => {
  it("explains unsupported and unavailable installations", () => {
    expect(
      codexVersionWarning({
        status: "available",
        raw: "codex-cli 0.143.9",
        version: "0.143.9",
        supported: false,
      }),
    ).toContain("0.143.9 is below 0.144.0");
    expect(
      codexVersionWarning({
        status: "missing",
        raw: null,
        version: null,
        supported: false,
      }),
    ).toContain("not found on PATH");
  });
});
