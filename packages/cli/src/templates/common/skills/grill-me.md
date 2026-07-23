# Trellis Grill Me

The main agent uses this skill after repository-first analysis only when a
material research decision remains unresolved. Typical triggers are a changed
hypothesis, functional model architecture, dataset, split, preprocessing,
objective/loss, metric definition, baseline, claim scope, or explicit user
request. Task size alone is not a trigger.

## Purpose

Resolve the smallest decision needed to make the research contract testable.
A `planner` may compare methods or experimental designs, but cannot approve a
high-risk change. The main agent leads user discussion and delegates every task
artifact update.

This is the Trellis-built-in replacement for external `grill-me` dependency patterns. Do not rely on any local third-party skill path.

## Entry Conditions

Use this skill only when:
- a Trellis task already exists
- repository-answerable questions have already been resolved through inspection
- the remaining uncertainty is about research intent, scope, method trade-offs,
  evidence standards, claim boundaries, preferences, or risk tolerance

Do **not** use this skill for questions the codebase can answer directly.

## Interview Contract

- Ask one question at a time.
- Each question must include:
  - the exact decision needed
  - why it matters
  - your recommended answer
  - what trade-off the user accepts if they choose differently
- After each answer, record the proposed `prd.md` update for a validated planner
  or coder dispatch before asking the next question. A main agent must not edit
  `prd.md` directly.
- Stop once `prd.md` has converged enough to enter development-strategy decisions.

## Questioning Style

Push for missing details across these dimensions when relevant:
- user-visible behavior
- scope boundaries
- success / failure behavior
- edge cases
- sequencing and rollout expectations
- what is explicitly out of scope
- what would make the user reject the implementation even if it "works"

Prefer concrete trade-offs over generic brainstorming.

## Output Standard

By the time this skill is done:
- `prd.md` has testable acceptance criteria
- unresolved questions are truly strategic, not factual
- implementation can move on to development mode / worktree / TDD decisions
