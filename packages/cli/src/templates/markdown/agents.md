<!-- TRELLIS:START -->
# Trellis Instructions

These instructions are for AI assistants working in this project.

This project is managed by Trellis. The working knowledge you need lives under `.trellis/`:

- `.trellis/workflow.md` — development phases, when to create tasks, skill routing
- `.trellis/spec/` — package- and layer-scoped coding guidelines (read before writing code in a given layer)
- `.trellis/workspace/` — per-developer journals and session traces
- `.trellis/tasks/` — active and archived tasks (PRDs, research, jsonl context)

If a Trellis command is available on your platform (e.g. `/trellis:finish-work`, `/trellis:continue`), prefer it over manual steps. Not every platform exposes every command.

If you're using Codex or another agent-capable tool, additional project-scoped helpers may live in:
- `.agents/skills/` — reusable Trellis skills
- `.codex/agents/` — optional custom subagents

## Research Collaboration Contract

- Prefer truth and evidence over agreement. State material assumptions and uncertainty, and raise evidence-backed disagreement when it changes the conclusion.
- The user approves research trade-offs. Execute ordinary reversible work directly; with limited uncertainty, state the assumption and proceed.
- Pause for discussion only for high-risk research changes. A prompt cannot replace the structured decision or experiment record required by the workflow.
- If evidence conflicts or a critical assumption fails, mark the task blocked and use an approved amendment before continuing.
- Keep context progressive and minimal: start from the Task Capsule and direct references, then read larger records only when needed.

Managed by Trellis. Edits outside this block are preserved; edits inside may be overwritten by a future `research-trellis update`.

<!-- TRELLIS:END -->
