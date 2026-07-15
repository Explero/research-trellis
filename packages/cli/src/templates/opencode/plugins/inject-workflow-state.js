/* global process */
/**
 * Trellis Workflow State Injection Plugin
 *
 * Per-turn UserPromptSubmit equivalent for OpenCode.
 *
 * On every chat.message, if a Trellis task is active, inject a short
 * <workflow-state> breadcrumb reminding the main AI what task is
 * active and its expected flow. Breadcrumb text is pulled exclusively
 * from the project's workflow.md [workflow-state:STATUS] tag blocks —
 * workflow.md is the single source of truth. There are no fallback
 * tables in this plugin: when workflow.md is missing or a tag is
 * absent, the breadcrumb degrades to a generic
 * "Refer to workflow.md for current step." line so users see (and fix)
 * the broken state instead of the plugin silently masking it.
 *
 * Unlike session-start, this plugin does NOT dedupe — the breadcrumb
 * should surface on every turn so long conversations don't drift.
 *
 * Silently skips when:
 *   - No .trellis/ directory
 *   - No active task in the session runtime context
 *   - task.json malformed or missing status
 */

import { existsSync, readFileSync } from "fs"
import { join } from "path"
import { TrellisContext, debugLog, isTrellisSubagent } from "../lib/trellis-context.js"

// Supports STATUS values with letters, digits, underscores, hyphens
// (so "in-review" / "blocked-by-team" work alongside "in_progress").
const TAG_RE = /\[workflow-state:([A-Za-z0-9_-]+)\]\s*\n([\s\S]*?)\n\s*\[\/workflow-state:\1\]/g

/**
 * Parse workflow.md for [workflow-state:STATUS] blocks.
 *
 * Returns {status: body}. workflow.md is the single source of truth —
 * there are no fallback tables here. Missing tags (or a missing /
 * unreadable workflow.md) fall back to a generic line in
 * buildBreadcrumb so users see the broken state and fix workflow.md
 * rather than the plugin silently masking it.
 */
function loadBreadcrumbs(directory) {
  const workflowPath = join(directory, ".trellis", "workflow.md")
  if (!existsSync(workflowPath)) return {}
  let content
  try {
    content = readFileSync(workflowPath, "utf-8")
  } catch {
    return {}
  }
  const result = {}
  for (const match of content.matchAll(TAG_RE)) {
    const status = match[1]
    const body = match[2].trim()
    if (body) result[status] = body
  }
  return result
}

/**
 * Get (taskId, status) from active task, or null if no active task.
 */
function getActiveTask(ctx, platformInput = null) {
  const active = ctx.getActiveTask(platformInput)
  const taskRef = active.taskPath
  if (!taskRef) return null
  const taskDir = ctx.resolveTaskDir(taskRef)
  if (active.stale || !taskDir || !existsSync(taskDir)) {
    return { id: taskRef.split("/").pop(), status: "stale", source: active.source }
  }
  const taskJsonPath = join(taskDir, "task.json")
  if (!existsSync(taskJsonPath)) return null
  try {
    const data = JSON.parse(readFileSync(taskJsonPath, "utf-8"))
    const status = typeof data.status === "string" ? data.status : ""
    if (!status) return null
    const id = data.id || taskRef.split("/").pop()
    return { id, status, source: active.source, data, taskDir }
  } catch {
    return null
  }
}

function clip(value, limit) {
  const compact = String(value || "").replace(/\s+/g, " ").trim()
  return compact.length <= limit ? compact : `${compact.slice(0, limit - 3).trim()}...`
}

function compactList(value, count, limit = 180) {
  return clip(Array.isArray(value) ? value.slice(0, count).join("; ") : "", limit)
}

function contextRefs(task) {
  const refs = []
  for (const filename of ["implement.jsonl", "check.jsonl"]) {
    try {
      const content = readFileSync(join(task.taskDir, filename), "utf-8")
      for (const line of content.split(/\r?\n/)) {
        if (!line.trim()) continue
        const row = JSON.parse(line)
        if (typeof row?.file === "string" && row.file.trim()) refs.push(row.file.trim())
      }
    } catch {
      // Missing or malformed optional context is skipped.
    }
  }
  if (Array.isArray(task.data.relatedFiles)) refs.push(...task.data.relatedFiles)
  return [...new Set(refs.filter(value => typeof value === "string" && value.trim()))].slice(0, 3)
}

function buildTaskCapsule(task) {
  const data = task?.data
  if (!data || !["closure_state", "hermes_phase", "work_packages"].some(field => field in data)) {
    return ""
  }
  const packages = Array.isArray(data.work_packages) ? data.work_packages : []
  const current = packages.find(item => item?.id === data.current_work_package)
  const lines = [
    `Task: ${data.id || task.id} | ${data.title || task.id}`,
    `Intent: ${clip(data.intent || data.description || "", 180)}`,
    `Scope: ${compactList(data.in_scope, 2) || "-"} | Out: ${compactList(data.out_of_scope, 2) || "-"}`,
    `Mode/Phase: ${data.closure_mode || "lean"} / ${data.hermes_phase || "planning"}`,
    `Current: ${data.current_work_package || "-"}${current ? ` - ${clip(current.outcome, 140)}` : ""}`,
  ]
  if (current) lines.push(`Done when: ${compactList(current.done_when, 3, 240)}`)
  lines.push(`Next: ${clip(data.next_action || "-", 180)}`)
  lines.push(`Blockers: ${compactList(data.blockers, 2) || "-"}`)
  const refs = contextRefs(task)
  if (refs.length > 0) lines.push(`Refs: ${refs.join(", ")}`)
  const capsule = lines.join("\n")
  return capsule.length <= 1000 ? capsule : `${capsule.slice(0, 997).trim()}...`
}

/**
 * Build the <workflow-state>...</workflow-state> block.
 * - Known status (tag present in workflow.md) → detailed body
 * - Unknown status (no tag, or workflow.md missing) → generic
 *   "Refer to workflow.md for current step." line
 * - no_task pseudo-status (id === null) → header omits task info
 */
function buildBreadcrumb(id, status, templates) {
  let body = templates[status]
  if (body === undefined) {
    body = "Refer to workflow.md for current step."
  }
  let header = id === null ? `Status: ${status}` : `Task: ${id} (${status})`
  return `<workflow-state>\n${header}\n${body}\n</workflow-state>`
}

function buildClosureBreadcrumb(task) {
  return `<workflow-state>\nTask: ${task.id} (${task.status})\nHermes closure: use only the Task Capsule and its next action. Plan/validate before start; execute only the current package; audit in review; use bounded repair for listed gaps; close before archive. Load full artifacts on demand.\n</workflow-state>`
}

// OpenCode 1.2.x expects plugins to be factory functions (see inject-subagent-context.js comment).
export default async ({ directory }) => {
  const ctx = new TrellisContext(directory)
  debugLog("workflow-state", "Plugin loaded, directory:", directory)

  return {
      // chat.message fires on every user message. Inject breadcrumb in-place
      // so it persists in conversation history.
      "chat.message": async (input, output) => {
        try {
          // Skip Trellis sub-agent turns — the per-turn breadcrumb is for the
          // main session only; sub-agent context comes from the parent's
          // tool.execute.before injection.
          if (isTrellisSubagent(input)) {
            debugLog("workflow-state", "Skipping trellis subagent turn:", input?.agent)
            return
          }
          if (process.env.TRELLIS_HOOKS === "0" || process.env.TRELLIS_DISABLE_HOOKS === "1") {
            return
          }
          if (process.env.OPENCODE_NON_INTERACTIVE === "1") {
            return
          }
          if (!ctx.isTrellisProject()) {
            return
          }
          const templates = loadBreadcrumbs(directory)
          const task = getActiveTask(ctx, input)
          const capsule = buildTaskCapsule(task)
          let breadcrumb = task
            ? (capsule ? buildClosureBreadcrumb(task) : buildBreadcrumb(task.id, task.status, templates, task.source))
            : buildBreadcrumb(null, "no_task", templates)
          if (capsule) breadcrumb += `\n\n<task-capsule>\n${capsule}\n</task-capsule>`

          const parts = output?.parts || []
          const textPartIndex = parts.findIndex(
            p => p.type === "text" && p.text !== undefined,
          )
          if (textPartIndex !== -1) {
            const originalText = parts[textPartIndex].text || ""
            parts[textPartIndex].text = `${breadcrumb}\n\n${originalText}`
          } else {
            parts.unshift({ type: "text", text: breadcrumb })
          }
          debugLog(
            "workflow-state",
            "Injected breadcrumb for task",
            task ? task.id : "none",
            "status",
            task ? task.status : "no_task",
          )
        } catch (error) {
          debugLog(
            "workflow-state",
            "Error in chat.message:",
            error instanceof Error ? error.message : String(error),
          )
        }
      },
  }
}
