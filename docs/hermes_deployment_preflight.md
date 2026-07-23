# Hermes 本地工作流预检

Hermes 面向真实科研项目工作区，不提供容器、沙箱或隔离运行环境。它使用任务状态、最小派发、运行记录和关闭审计协助科研迭代。

## 发布前检查

```bash
pnpm --filter research-trellis hermes:preflight -- --quick
pnpm --filter research-trellis exec vitest run test/scripts/agent-context-firewall.integration.test.ts test/scripts/closure.integration.test.ts test/templates/hermes-runtime.test.ts test/templates/hermes-roles.test.ts test/templates/trellis.test.ts test/templates/claude.test.ts test/templates/codex.test.ts test/templates/shared-hooks.test.ts
pnpm --filter research-trellis typecheck
pnpm --filter research-trellis build
```

## 当前约定

- `runner.py`（运行器）直接在当前项目环境执行。`allowed_commands`（允许命令）用于记录实验可复现的命令边界，不是安全隔离。
- `Claude Code`（Claude 代码工具）和 `Codex`（代码代理平台）都使用紧凑派发和结果摘要；完整日志、差异和搜索过程保留在文件中。
- `task.json`（任务状态）是事实源。`HANDOFF.md`（交接摘要）只用于暂停、阶段切换和恢复上下文，不阻止结束任务或关闭任务。
- `close`（关闭）仍需满足工作包、证据和审计条件；人工科研决策仍由项目负责人确认。

## 常见问题

- 命令不在 `allowed_commands`（允许命令）中：更新当前任务的 `experiment.yaml`（实验配置），并保持命令尽可能具体。
- 任务暂停：生成 `HANDOFF.md`（交接摘要）；恢复时先读取 `task.json`（任务状态），再按需读取交接摘要。
- 模板目录出现 `__pycache__` 或 `.pyc`：使用 `trash`（回收站命令）清理后重跑预检。
