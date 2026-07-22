import { describe, expect, it } from "vitest";

import {
  TASK_RECORD_FIELD_ORDER,
  emptyTaskRecord,
  taskRecordSchema,
} from "../../src/task/index.js";

describe("emptyTaskRecord", () => {
  it("emits every canonical field in canonical order", () => {
    const record = emptyTaskRecord();
    expect(Object.keys(record)).toEqual([...TASK_RECORD_FIELD_ORDER]);
  });

  it("uses canonical defaults: planning status, P2 priority, today ISO date", () => {
    const record = emptyTaskRecord();
    expect(record.status).toBe("planning");
    expect(record.priority).toBe("P2");
    expect(record.dev_type).toBeNull();
    expect(record.subtasks).toEqual([]);
    expect(record.children).toEqual([]);
    expect(record.relatedFiles).toEqual([]);
    expect(record.meta).toEqual({});
    expect(record.hermes_phase).toBe("planning");
    expect(record.closure_state).toBe("open");
    expect(record.closure_mode).toBe("lean");
    expect(record.work_packages).toEqual([]);
    expect(record.context_pins).toEqual([]);
    expect(record.research_route).toBe("delivery");
    expect(record.research_change_fields).toEqual([]);
    expect(record.grill_completed).toBe(false);
    expect(record.decision_ref).toBeNull();
    expect(record.constraints).toEqual({
      excluded_platforms: [],
      excluded_paths: [],
      validation_level: "targeted",
    });
    expect(record.max_repair_count).toBe(1);
    expect(record.hermes_revision).toBe(0);
    expect(record.createdAt).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("shallow-merges overrides on top of defaults", () => {
    const record = emptyTaskRecord({
      id: "demo",
      name: "demo",
      title: "Demo task",
      assignee: "developer",
      package: "core",
    });
    expect(record.id).toBe("demo");
    expect(record.title).toBe("Demo task");
    expect(record.assignee).toBe("developer");
    expect(record.package).toBe("core");
    expect(record.priority).toBe("P2");
  });

  it("copies collection overrides so callers cannot share mutable state", () => {
    const overrides = {
      children: ["child-a"],
      relatedFiles: ["src/demo.ts"],
      subtasks: ["subtask-a"],
      meta: { tracker: "demo", nested: { id: "n1" } },
    };
    const first = emptyTaskRecord(overrides);
    const second = emptyTaskRecord(overrides);

    overrides.children.push("child-b");
    overrides.meta.nested.id = "changed-by-override";
    first.relatedFiles.push("src/changed.ts");
    first.subtasks.push("subtask-b");
    first.meta.tracker = "changed";
    (first.meta.nested as { id: string }).id = "changed-by-first";

    expect(first.children).toEqual(["child-a"]);
    expect(second.relatedFiles).toEqual(["src/demo.ts"]);
    expect(second.subtasks).toEqual(["subtask-a"]);
    expect(second.meta).toEqual({ tracker: "demo", nested: { id: "n1" } });
  });
});

describe("taskRecordSchema", () => {
  it("parses a canonical record", () => {
    const input = emptyTaskRecord({ id: "x", name: "x", title: "X" });
    const parsed = taskRecordSchema.parse(input);
    expect(parsed).toEqual(input);
    expect(parsed).not.toBe(input);
  });

  it("parses compact closure work packages", () => {
    const parsed = taskRecordSchema.parse(
      emptyTaskRecord({
        work_packages: [
          {
            id: "WP1",
            title: "Verified result",
            outcome: "A result exists",
            done_when: ["Tests pass"],
            evidence_required: ["test output"],
            depends_on: [],
            status: "ready",
            evidence_refs: [],
            blocker: null,
          },
        ],
      }),
    );
    expect(parsed.work_packages?.[0]?.status).toBe("ready");
    expect(parsed.work_packages?.[0]?.done_when).toEqual(["Tests pass"]);
  });

  it("accepts legacy task records without closure fields", () => {
    const closureFields = new Set([
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
      "decision_ref",
      "constraints",
      "work_packages",
      "current_work_package",
      "next_action",
      "blockers",
      "repair_count",
      "max_repair_count",
      "hermes_revision",
    ]);
    const legacy = Object.fromEntries(
      Object.entries(emptyTaskRecord()).filter(
        ([field]) => !closureFields.has(field),
      ),
    );
    const parsed = taskRecordSchema.parse(legacy);
    expect(parsed.hermes_phase).toBeUndefined();
    expect(parsed.work_packages).toBeUndefined();
  });

  it("rejects non-object inputs", () => {
    expect(() => taskRecordSchema.parse("nope")).toThrow(/must be a JSON object/);
    expect(() => taskRecordSchema.parse(null)).toThrow();
    expect(() => taskRecordSchema.parse([])).toThrow();
  });

  it("rejects wrong field types", () => {
    expect(() =>
      taskRecordSchema.parse({ ...emptyTaskRecord(), title: 42 }),
    ).toThrow(/task.title must be a string/);
    expect(() =>
      taskRecordSchema.parse({ ...emptyTaskRecord(), children: ["ok", 1] }),
    ).toThrow(/task.children must be an array of strings/);
    expect(() =>
      taskRecordSchema.parse({ ...emptyTaskRecord(), meta: [] }),
    ).toThrow(/task.meta must be a JSON object/);
    expect(() =>
      taskRecordSchema.parse({
        ...emptyTaskRecord(),
        meta: { nested: new Date() },
      }),
    ).toThrow(/task.meta.nested must contain only JSON values/);
    expect(() =>
      taskRecordSchema.parse({
        ...emptyTaskRecord(),
        work_packages: [
          {
            id: "WP1",
            title: "Invalid",
            outcome: "Invalid status",
            done_when: ["never"],
            evidence_required: [],
            depends_on: [],
            status: "complete",
            evidence_refs: [],
            blocker: null,
          },
        ],
      }),
    ).toThrow(/status is invalid/);
    expect(() =>
      taskRecordSchema.parse({
        ...emptyTaskRecord(),
        closure_mode: "fast",
      }),
    ).toThrow(/closure_mode is invalid/);
    expect(() =>
      taskRecordSchema.parse({
        ...emptyTaskRecord(),
        hermes_phase: "complete",
      }),
    ).toThrow(/hermes_phase is invalid/);
    expect(() =>
      taskRecordSchema.parse({
        ...emptyTaskRecord(),
        hermes_revision: -1,
      }),
    ).toThrow(/hermes_revision must be a non-negative integer/);
    const invalidDispatchField = emptyTaskRecord({
      work_packages: [
        {
          id: "WP1",
          title: "Invalid dispatch fields",
          outcome: "Result exists",
          done_when: ["Result exists"],
          evidence_required: [],
          depends_on: [],
          status: "ready",
          evidence_refs: [],
          blocker: null,
        },
      ],
    });
    const invalidPackage = invalidDispatchField.work_packages?.[0] as Record<
      string,
      unknown
    >;
    invalidPackage.confirmed_dispatches = "job-1";
    expect(() => taskRecordSchema.parse(invalidDispatchField)).toThrow(
      /confirmed_dispatches must be an array of strings/,
    );
    invalidPackage.confirmed_dispatches = [];
    invalidPackage.dispatch_blockers = "job-1";
    expect(() => taskRecordSchema.parse(invalidDispatchField)).toThrow(
      /dispatch_blockers must be an array of strings/,
    );
    invalidPackage.dispatch_blockers = ["job-1"];
    invalidPackage.dispatch_blocked_from_status = "done";
    expect(() => taskRecordSchema.parse(invalidDispatchField)).toThrow(
      /dispatch_blocked_from_status must be running or review/,
    );
  });

  it("rejects records missing canonical fields", () => {
    expect(() =>
      taskRecordSchema.parse({
        ...emptyTaskRecord(),
        meta: undefined,
      }),
    ).toThrow(/task.meta must be a JSON object/);

    const partial = { ...emptyTaskRecord() } as Record<string, unknown>;
    delete partial.base_branch;
    expect(() => taskRecordSchema.parse(partial)).toThrow(
      /task.base_branch is required/,
    );
  });

  it("allows null for nullable string fields", () => {
    const parsed = taskRecordSchema.parse({
      ...emptyTaskRecord(),
      branch: null,
      worktree_path: null,
      parent: null,
    });
    expect(parsed.branch).toBeNull();
    expect(parsed.worktree_path).toBeNull();
    expect(parsed.parent).toBeNull();
  });

  it("safeParse returns success / error discriminated result", () => {
    const ok = taskRecordSchema.safeParse(emptyTaskRecord());
    expect(ok.success).toBe(true);
    const bad = taskRecordSchema.safeParse({ title: 1 });
    expect(bad.success).toBe(false);
    if (!bad.success) {
      expect(bad.error.message).toMatch(/task.id is required/);
    }
  });

  it("drops unknown fields from the structured output (load surface)", () => {
    const parsed = taskRecordSchema.parse({
      ...emptyTaskRecord({ id: "x" }),
      // @ts-expect-error - simulate older/newer on-disk field
      legacy_field: "keep-me-on-disk",
    });
    expect("legacy_field" in parsed).toBe(false);
  });
});
