# Code Quality Check

Comprehensive quality verification for recently written code. Combines spec compliance, cross-layer safety, and pre-commit checks.

---

## Step 1: Identify What Changed

```bash
git diff --name-only HEAD
git status
```

## Step 2: Read Task Artifacts and Applicable Specs

For a Hermes closure task, start with the compact capsule and current package:

```bash
python3 ./.trellis/scripts/closure.py capsule --task <task>
```

Read full task artifacts only when the capsule or changed files require them:

- `prd.md`
- `design.md` if present
- `implement.md` if present

```bash
python3 ./.trellis/scripts/get_context.py --mode packages
```

For each changed package/layer, read the spec index and follow its **Quality Check** section:

```bash
cat .trellis/spec/<package>/<layer>/index.md
```

Read the specific guideline files referenced — the index is a pointer, not the goal.

## Step 3: Run Project Checks

Run the project's lint, type-check, and test commands. Fix any failures before proceeding.

## Step 4: Run Hermes Quality Gates

Use the current active task name for `<task>`. First finish the current package checks and record its evidence. Run closure audit only after all packages are disposed. Gate depth follows `closure_mode`; lean does not require publication evidence:

```bash
# after all packages are done/deferred/waived
{{PYTHON_CMD}} ./.trellis/scripts/closure.py audit --task <task>

# standard and publication
{{PYTHON_CMD}} ./.trellis/scripts/hermes/validate.py --task <task> --kind audit
{{PYTHON_CMD}} ./.trellis/scripts/hermes/validate.py --task <task> --kind provenance
{{PYTHON_CMD}} ./.trellis/scripts/hermes/validate.py --task <task> --kind service_queue

# publication only
{{PYTHON_CMD}} ./.trellis/scripts/hermes/report.py quality-gate --task <task>
```

Fix any Hermes failures before proceeding, but run only the commands required by the active mode. Do not promote a lean engineering check into scientific claim approval.

## Step 5: Review Against Checklist

### Code Quality

- [ ] Linter passes?
- [ ] Type checker passes (if applicable)?
- [ ] Tests pass?
- [ ] No debug logging left in?
- [ ] No suppressed warnings or type-safety bypasses?

### Test Coverage

- [ ] New function → unit test added?
- [ ] Bug fix → regression test added?
- [ ] Changed behavior → existing tests updated?

### Spec Sync

- [ ] Does `.trellis/spec/` need updates? (new patterns, conventions, lessons learned)

> "If I fixed a bug or discovered something non-obvious, should I document it so future me won't hit the same issue?" → If YES, update the relevant spec doc.

## Step 6: Cross-Layer Dimensions (if applicable)

Skip this step if your change is confined to a single layer.

### A. Data Flow (changes touch 3+ layers)

- [ ] Read flow traces correctly: Storage → Service → API → UI
- [ ] Write flow traces correctly: UI → API → Service → Storage
- [ ] Types/schemas correctly passed between layers?
- [ ] Errors properly propagated to caller?

### B. Code Reuse (modifying constants, creating utilities)

- [ ] Searched for existing similar code before creating new?
  ```bash
  grep -r "pattern" src/
  ```
- [ ] If 2+ places define same value → extracted to shared constant?
- [ ] After batch modification, all occurrences updated?

### C. Import/Dependency (creating new files)

- [ ] Correct import paths (relative vs absolute)?
- [ ] No circular dependencies?

### D. Same-Layer Consistency

- [ ] Other places using the same concept are consistent?

---

## Step 7: Report and Fix

Report violations found and fix them directly. Re-run project checks after fixes.

For a running Hermes package, move it to review with `closure.py package-check`. Mark it done only after the checks above pass and provide concrete `--evidence` references. When all packages are disposed, run `closure.py audit`; do not substitute a successful test run for task closure or claim approval.
