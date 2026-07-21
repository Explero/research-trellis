/**
 * Canonical task.json shape — single source of truth for Trellis tasks.
 *
 * The runtime Python writer is `.trellis/scripts/common/task_store.py`
 * (`cmd_create`). The field shape and field order below mirror that
 * writer exactly so every TS and Python entry point produces structurally
 * identical task.json files.
 *
 * Downstream consumers (CLI bootstrap, migration tooling, external Node
 * services) should depend on this type instead of redefining their own
 * task.json shape.
 */
export type ClosureMode = "lean" | "standard" | "publication";
export type ResearchRoute = "delivery" | "execution" | "exploration";
export type HermesPhase =
  | "planning"
  | "ready"
  | "running"
  | "review"
  | "blocked"
  | "closed";
export type ClosureWorkPackageStatus =
  | "pending"
  | "ready"
  | "running"
  | "review"
  | "done"
  | "blocked"
  | "deferred"
  | "waived";

export interface ClosureWorkPackage {
  id: string;
  title: string;
  outcome: string;
  done_when: string[];
  evidence_required: string[];
  depends_on: string[];
  status: ClosureWorkPackageStatus;
  evidence_refs: string[];
  blocker: string | null;
  confirmed_dispatches?: string[];
  dispatch_blockers?: string[];
  dispatch_blocked_from_status?: "running" | "review";
}

export interface ClosureConstraints {
  excluded_platforms: string[];
  excluded_paths: string[];
  validation_level: "targeted" | "basic" | "standard";
}

export interface TrellisTaskRecord {
  id: string;
  name: string;
  title: string;
  description: string;
  status: string;
  dev_type: string | null;
  scope: string | null;
  package: string | null;
  priority: string;
  creator: string;
  assignee: string;
  createdAt: string;
  completedAt: string | null;
  branch: string | null;
  base_branch: string | null;
  worktree_path: string | null;
  commit: string | null;
  pr_url: string | null;
  subtasks: string[];
  children: string[];
  parent: string | null;
  relatedFiles: string[];
  notes: string;
  meta: Record<string, unknown>;
  hermes_phase?: HermesPhase;
  closure_state?: "open" | "closed";
  closure_mode?: ClosureMode;
  intent?: string;
  in_scope?: string[];
  out_of_scope?: string[];
  definition_of_done?: string[];
  context_pins?: string[];
  research_route?: ResearchRoute;
  research_change_fields?: string[];
  grill_completed?: boolean;
  constraints?: ClosureConstraints;
  work_packages?: ClosureWorkPackage[];
  current_work_package?: string | null;
  next_action?: string | null;
  blockers?: string[];
  repair_count?: number;
  max_repair_count?: number;
  hermes_revision?: number;
  confirmed_dispatches?: string[];
}

/**
 * Canonical task field order — matches `task_store.py::cmd_create`. Used
 * by `writeTaskRecord` so the on-disk JSON layout is deterministic.
 */
export const TASK_RECORD_FIELD_ORDER = [
  "id",
  "name",
  "title",
  "description",
  "status",
  "dev_type",
  "scope",
  "package",
  "priority",
  "creator",
  "assignee",
  "createdAt",
  "completedAt",
  "branch",
  "base_branch",
  "worktree_path",
  "commit",
  "pr_url",
  "subtasks",
  "children",
  "parent",
  "relatedFiles",
  "notes",
  "meta",
  "hermes_phase",
  "closure_state",
  "closure_mode",
  "intent",
  "in_scope",
  "out_of_scope",
  "definition_of_done",
  "context_pins",
  "research_route",
  "research_change_fields",
  "grill_completed",
  "constraints",
  "work_packages",
  "current_work_package",
  "next_action",
  "blockers",
  "repair_count",
  "max_repair_count",
  "hermes_revision",
  "confirmed_dispatches",
] as const satisfies readonly (keyof TrellisTaskRecord)[];

export type TaskRecordField = (typeof TASK_RECORD_FIELD_ORDER)[number];

const STRING_FIELDS: ReadonlySet<TaskRecordField> = new Set([
  "id",
  "name",
  "title",
  "description",
  "status",
  "priority",
  "creator",
  "assignee",
  "createdAt",
  "notes",
  "hermes_phase",
  "closure_state",
  "closure_mode",
  "intent",
  "research_route",
]);

const NULLABLE_STRING_FIELDS: ReadonlySet<TaskRecordField> = new Set([
  "dev_type",
  "scope",
  "package",
  "completedAt",
  "branch",
  "base_branch",
  "worktree_path",
  "commit",
  "pr_url",
  "parent",
  "current_work_package",
  "next_action",
]);

const STRING_ARRAY_FIELDS: ReadonlySet<TaskRecordField> = new Set([
  "subtasks",
  "children",
  "relatedFiles",
  "in_scope",
  "out_of_scope",
  "definition_of_done",
  "context_pins",
  "research_change_fields",
  "blockers",
  "confirmed_dispatches",
]);

const OPTIONAL_CLOSURE_FIELDS: ReadonlySet<TaskRecordField> = new Set([
  "hermes_phase",
  "closure_state",
  "closure_mode",
  "intent",
  "in_scope",
  "out_of_scope",
  "definition_of_done",
  "context_pins",
  "research_route",
  "research_change_fields",
  "grill_completed",
  "constraints",
  "work_packages",
  "current_work_package",
  "next_action",
  "blockers",
  "repair_count",
  "max_repair_count",
  "hermes_revision",
  "confirmed_dispatches",
]);

const CLOSURE_MODES: ReadonlySet<string> = new Set([
  "lean",
  "standard",
  "publication",
]);
const HERMES_PHASES: ReadonlySet<string> = new Set([
  "planning",
  "ready",
  "running",
  "review",
  "blocked",
  "closed",
]);
const CLOSURE_STATES: ReadonlySet<string> = new Set(["open", "closed"]);
const RESEARCH_ROUTES: ReadonlySet<string> = new Set([
  "delivery",
  "execution",
  "exploration",
]);

/**
 * Lightweight runtime schema for {@link TrellisTaskRecord}. Zero-dep on
 * purpose — `taskRecordSchema.parse(input)` returns a canonicalized
 * record, throwing on shape violations; `taskRecordSchema.safeParse`
 * returns a result discriminated by `success`.
 *
 * Original Trellis fields remain required. Optional Hermes closure fields are
 * parsed when present so legacy records keep working unchanged. Unknown fields
 * on the input are intentionally omitted from this structured output.
 * `writeTaskRecord` preserves unknown fields already present on disk by merging
 * canonical updates over the existing JSON object.
 */
export const taskRecordSchema = {
  parse(input: unknown): TrellisTaskRecord {
    return parseTaskRecord(input);
  },
  safeParse(
    input: unknown,
  ):
    | { success: true; data: TrellisTaskRecord }
    | { success: false; error: Error } {
    try {
      return { success: true, data: parseTaskRecord(input) };
    } catch (err) {
      return {
        success: false,
        error: err instanceof Error ? err : new Error(String(err)),
      };
    }
  },
} as const;

function parseTaskRecord(input: unknown): TrellisTaskRecord {
  if (!isPlainObject(input)) {
    throw new Error("task record must be a JSON object");
  }
  const out = {} as TrellisTaskRecord;
  for (const field of TASK_RECORD_FIELD_ORDER) {
    if (!(field in input)) {
      if (OPTIONAL_CLOSURE_FIELDS.has(field)) {
        continue;
      }
      throw new Error(`task.${field} is required`);
    }
    const value = (input as Record<string, unknown>)[field];
    assignField(out, field, value);
  }
  return out;
}

function assignField(
  record: TrellisTaskRecord,
  field: TaskRecordField,
  value: unknown,
): void {
  const bag = record as unknown as Record<string, unknown>;
  if (STRING_FIELDS.has(field)) {
    if (typeof value !== "string") {
      throw new Error(`task.${field} must be a string`);
    }
    if (field === "closure_mode" && !CLOSURE_MODES.has(value)) {
      throw new Error("task.closure_mode is invalid");
    }
    if (field === "hermes_phase" && !HERMES_PHASES.has(value)) {
      throw new Error("task.hermes_phase is invalid");
    }
    if (field === "closure_state" && !CLOSURE_STATES.has(value)) {
      throw new Error("task.closure_state is invalid");
    }
    if (field === "research_route" && !RESEARCH_ROUTES.has(value)) {
      throw new Error("task.research_route is invalid");
    }
    bag[field] = value;
    return;
  }
  if (NULLABLE_STRING_FIELDS.has(field)) {
    if (value !== null && typeof value !== "string") {
      throw new Error(`task.${field} must be a string or null`);
    }
    bag[field] = value;
    return;
  }
  if (STRING_ARRAY_FIELDS.has(field)) {
    if (!Array.isArray(value) || value.some((v) => typeof v !== "string")) {
      throw new Error(`task.${field} must be an array of strings`);
    }
    bag[field] = [...value];
    return;
  }
  if (field === "meta") {
    if (!isPlainObject(value)) {
      throw new Error("task.meta must be a JSON object");
    }
    record.meta = cloneJsonObject(value, "task.meta");
    return;
  }
  if (field === "grill_completed") {
    if (typeof value !== "boolean") {
      throw new Error("task.grill_completed must be a boolean");
    }
    record.grill_completed = value;
    return;
  }
  if (field === "constraints") {
    if (!isPlainObject(value)) {
      throw new Error("task.constraints must be a JSON object");
    }
    const platforms = value.excluded_platforms;
    const paths = value.excluded_paths;
    const level = value.validation_level;
    if (
      !Array.isArray(platforms) ||
      platforms.some((item) => typeof item !== "string") ||
      !Array.isArray(paths) ||
      paths.some((item) => typeof item !== "string") ||
      !["targeted", "basic", "standard"].includes(String(level))
    ) {
      throw new Error("task.constraints is invalid");
    }
    record.constraints = {
      excluded_platforms: [...platforms] as string[],
      excluded_paths: [...paths] as string[],
      validation_level: level as ClosureConstraints["validation_level"],
    };
    return;
  }
  if (field === "work_packages") {
    if (!Array.isArray(value)) {
      throw new Error("task.work_packages must be an array");
    }
    record.work_packages = value.map((item, index) =>
      parseClosureWorkPackage(item, index),
    );
    return;
  }
  if (
    field === "repair_count" ||
    field === "max_repair_count" ||
    field === "hermes_revision"
  ) {
    if (!Number.isInteger(value) || (value as number) < 0) {
      throw new Error(`task.${field} must be a non-negative integer`);
    }
    record[field] = value as number;
    return;
  }
  // Should be unreachable given the field sets cover every canonical field.
  /* c8 ignore next */
  throw new Error(`unknown canonical task field: ${field}`);
}

/**
 * Produce a fully-populated canonical-shape {@link TrellisTaskRecord}.
 *
 * All canonical fields are present in canonical order. `overrides` shallow-merges
 * over the defaults — callers supply per-task values (id, name, title,
 * assignee, createdAt, etc.) and leave null-default fields untouched
 * unless they have a real value.
 */
export function emptyTaskRecord(
  overrides: Partial<TrellisTaskRecord> = {},
): TrellisTaskRecord {
  const today = new Date().toISOString().split("T")[0] ?? "";
  const base: TrellisTaskRecord = {
    id: "",
    name: "",
    title: "",
    description: "",
    status: "planning",
    dev_type: null,
    scope: null,
    package: null,
    priority: "P2",
    creator: "",
    assignee: "",
    createdAt: today,
    completedAt: null,
    branch: null,
    base_branch: null,
    worktree_path: null,
    commit: null,
    pr_url: null,
    subtasks: [],
    children: [],
    parent: null,
    relatedFiles: [],
    notes: "",
    meta: {},
    hermes_phase: "planning",
    closure_state: "open",
    closure_mode: "lean",
    intent: "",
    in_scope: [],
    out_of_scope: [],
    definition_of_done: [],
    context_pins: [],
    research_route: "delivery",
    research_change_fields: [],
    grill_completed: false,
    constraints: {
      excluded_platforms: [],
      excluded_paths: [],
      validation_level: "targeted",
    },
    work_packages: [],
    current_work_package: null,
    next_action: null,
    blockers: [],
    repair_count: 0,
    max_repair_count: 1,
    hermes_revision: 0,
    confirmed_dispatches: [],
  };
  const record = { ...base, ...overrides };
  if (overrides.subtasks !== undefined) {
    record.subtasks = [...overrides.subtasks];
  }
  if (overrides.children !== undefined) {
    record.children = [...overrides.children];
  }
  if (overrides.relatedFiles !== undefined) {
    record.relatedFiles = [...overrides.relatedFiles];
  }
  if (overrides.in_scope !== undefined) {
    record.in_scope = [...overrides.in_scope];
  }
  if (overrides.out_of_scope !== undefined) {
    record.out_of_scope = [...overrides.out_of_scope];
  }
  if (overrides.definition_of_done !== undefined) {
    record.definition_of_done = [...overrides.definition_of_done];
  }
  if (overrides.context_pins !== undefined) {
    record.context_pins = [...overrides.context_pins];
  }
  if (overrides.research_change_fields !== undefined) {
    record.research_change_fields = [...overrides.research_change_fields];
  }
  if (overrides.constraints !== undefined) {
    record.constraints = {
      excluded_platforms: [...overrides.constraints.excluded_platforms],
      excluded_paths: [...overrides.constraints.excluded_paths],
      validation_level: overrides.constraints.validation_level,
    };
  }
  if (overrides.blockers !== undefined) {
    record.blockers = [...overrides.blockers];
  }
  if (overrides.confirmed_dispatches !== undefined) {
    record.confirmed_dispatches = [...overrides.confirmed_dispatches];
  }
  if (overrides.work_packages !== undefined) {
    record.work_packages = overrides.work_packages.map((item) => ({
      ...item,
      done_when: [...item.done_when],
      evidence_required: [...item.evidence_required],
      depends_on: [...item.depends_on],
      evidence_refs: [...item.evidence_refs],
      ...(item.confirmed_dispatches !== undefined
        ? { confirmed_dispatches: [...item.confirmed_dispatches] }
        : {}),
      ...(item.dispatch_blockers !== undefined
        ? { dispatch_blockers: [...item.dispatch_blockers] }
        : {}),
    }));
  }
  if (overrides.meta !== undefined) {
    record.meta = cloneJsonObject(overrides.meta, "task.meta");
  }
  return record;
}

const WORK_PACKAGE_STATUSES: ReadonlySet<string> = new Set([
  "pending",
  "ready",
  "running",
  "review",
  "done",
  "blocked",
  "deferred",
  "waived",
]);

function parseClosureWorkPackage(
  input: unknown,
  index: number,
): ClosureWorkPackage {
  if (!isPlainObject(input)) {
    throw new Error(`task.work_packages[${index}] must be an object`);
  }
  const readString = (field: "id" | "title" | "outcome"): string => {
    const value = input[field];
    if (typeof value !== "string") {
      throw new Error(`task.work_packages[${index}].${field} must be a string`);
    }
    return value;
  };
  const readStringArray = (
    field:
      | "done_when"
      | "evidence_required"
      | "depends_on"
      | "evidence_refs"
      | "confirmed_dispatches"
      | "dispatch_blockers",
  ): string[] => {
    const value = input[field];
    if (
      !Array.isArray(value) ||
      value.some((item) => typeof item !== "string")
    ) {
      throw new Error(
        `task.work_packages[${index}].${field} must be an array of strings`,
      );
    }
    return [...value] as string[];
  };

  const status = input.status;
  if (typeof status !== "string" || !WORK_PACKAGE_STATUSES.has(status)) {
    throw new Error(`task.work_packages[${index}].status is invalid`);
  }
  const blocker = input.blocker;
  if (blocker !== null && typeof blocker !== "string") {
    throw new Error(
      `task.work_packages[${index}].blocker must be a string or null`,
    );
  }
  const hasOptionalField = (field: string): boolean =>
    Object.prototype.hasOwnProperty.call(input, field);
  const dispatchState = input.dispatch_blocked_from_status;
  if (
    hasOptionalField("dispatch_blocked_from_status") &&
    dispatchState !== "running" &&
    dispatchState !== "review"
  ) {
    throw new Error(
      `task.work_packages[${index}].dispatch_blocked_from_status must be running or review`,
    );
  }
  return {
    id: readString("id"),
    title: readString("title"),
    outcome: readString("outcome"),
    done_when: readStringArray("done_when"),
    evidence_required: readStringArray("evidence_required"),
    depends_on: readStringArray("depends_on"),
    status: status as ClosureWorkPackageStatus,
    evidence_refs: readStringArray("evidence_refs"),
    blocker,
    confirmed_dispatches: hasOptionalField("confirmed_dispatches")
      ? readStringArray("confirmed_dispatches")
      : undefined,
    dispatch_blockers: hasOptionalField("dispatch_blockers")
      ? readStringArray("dispatch_blockers")
      : undefined,
    dispatch_blocked_from_status: dispatchState as
      | "running"
      | "review"
      | undefined,
  };
}

export function isPlainObject(value: unknown): value is Record<string, unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value) &&
    Object.getPrototypeOf(value) === Object.prototype
  );
}

function cloneJsonObject(
  value: Record<string, unknown>,
  path: string,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, child] of Object.entries(value)) {
    out[key] = cloneJsonValue(child, `${path}.${key}`);
  }
  return out;
}

function cloneJsonValue(value: unknown, path: string): unknown {
  if (
    value === null ||
    typeof value === "string" ||
    typeof value === "boolean"
  ) {
    return value;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      throw new Error(`${path} must be a finite JSON number`);
    }
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((item, index) => cloneJsonValue(item, `${path}[${index}]`));
  }
  if (isPlainObject(value)) {
    return cloneJsonObject(value, path);
  }
  throw new Error(`${path} must contain only JSON values`);
}
