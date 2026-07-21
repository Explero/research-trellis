# Project Context

These files are the project-level inputs for the main agent. Session startup
lists their names and paths without injecting their contents. The main agent
reads only the files relevant to the incoming request before deciding whether
the request is in scope, needs discussion, or can be split into work packages.

- `BACKGROUND.md`: project origin, domain, current state, and intended value.
- `RESEARCH_PLAN.md`: research question, current approach, evidence standard,
  and known limitations.
- `CONSTRAINTS.md`: fixed boundaries, compatibility requirements, resources,
  data restrictions, and prohibited changes.
- `PROJECT_INDEX.md`: a deterministic, root-level reading map generated at
  initialization. It lists files and directories but does not summarize or
  infer project facts.

For an existing project, replace the placeholders with facts from its docs,
code, records, and maintainers. For a new repository, fill only what is known;
do not invent a research plan or constraints. These documents are project
context, not task plans and not automatic subagent context.
