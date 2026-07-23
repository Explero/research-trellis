import { execFileSync } from "node:child_process";

export const MIN_CODEX_VERSION = "0.144.0";

export interface CodexVersionProbe {
  status: "available" | "missing" | "unreadable";
  raw: string | null;
  version: string | null;
  supported: boolean;
}

export type CodexVersionRunner = () => string;

const VERSION_PATTERN =
  /\bv?(\d+\.\d+\.\d+(?:-[0-9A-Za-z][0-9A-Za-z.-]*)?(?:\+[0-9A-Za-z][0-9A-Za-z.-]*)?)/;

function defaultRunner(): string {
  return String(
    execFileSync("codex", ["--version"], {
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "pipe"],
    }),
  );
}

export function parseCodexVersion(output: string): string | null {
  const match = output.match(VERSION_PATTERN);
  return match?.[1] ?? null;
}

function isSupportedCodexVersion(version: string): boolean {
  const match = version.match(
    /^(\d+)\.(\d+)\.(\d+)(-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/,
  );
  if (!match) return false;
  const current = [Number(match[1]), Number(match[2]), Number(match[3])];
  const minimum = [0, 144, 0];
  for (let index = 0; index < current.length; index += 1) {
    if (current[index] > minimum[index]) return true;
    if (current[index] < minimum[index]) return false;
  }
  return !match[4];
}

/** Probe `codex --version` without shelling out or contacting a network. */
export function probeCodexVersion(
  runner: CodexVersionRunner = defaultRunner,
): CodexVersionProbe {
  try {
    const raw = runner().trim();
    const version = parseCodexVersion(raw);
    return {
      status: version ? "available" : "unreadable",
      raw: raw || null,
      version,
      supported: version ? isSupportedCodexVersion(version) : false,
    };
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code;
    return {
      status: code === "ENOENT" ? "missing" : "unreadable",
      raw: null,
      version: null,
      supported: false,
    };
  }
}

let cachedProbe: CodexVersionProbe | undefined;

/** Cache the host probe for one CLI process so configuration never probes per turn. */
export function getCodexVersion(): CodexVersionProbe {
  cachedProbe ??= probeCodexVersion();
  return cachedProbe;
}

export function resetCodexVersionProbeForTests(): void {
  cachedProbe = undefined;
}

export function codexVersionWarning(probe: CodexVersionProbe): string | null {
  if (probe.status === "missing") {
    return (
      "Codex was not found on PATH. " +
      `Codex ${MIN_CODEX_VERSION} or newer is needed to recognize Trellis model and reasoning-effort defaults.`
    );
  }
  if (probe.status === "unreadable") {
    return (
      "Codex version could not be read. " +
      `Codex ${MIN_CODEX_VERSION} or newer is needed to recognize Trellis model and reasoning-effort defaults.`
    );
  }
  if (!probe.supported) {
    return (
      `Codex ${probe.version} is below ${MIN_CODEX_VERSION}. ` +
      "Trellis will continue, but this Codex version may not recognize the configured model and reasoning-effort defaults."
    );
  }
  return null;
}

export function warnCodexVersion(): void {
  if (process.env.VITEST || process.env.TRELLIS_QUIET) return;
  const warning = codexVersionWarning(getCodexVersion());
  if (warning) {
    process.stderr.write(`Warning: ${warning}\n`);
  }
}
