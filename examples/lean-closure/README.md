# Lean Closure Example

这是一个单工作包 `lean`（轻量）任务快照，适合本地脚本、文档或小型工程验证。

把 `task.json`（任务状态）放入 `.trellis/tasks/<task>/` 后，先运行：

```bash
python3 ./.trellis/scripts/closure.py validate --task <task>
export TRELLIS_CONTEXT_ID=lean-example
python3 ./.trellis/scripts/task.py start <task>
python3 ./.trellis/scripts/closure.py capsule --task <task>
```

实际验证完成后，使用 `package-check`（工作包检查）、`package-done --evidence`（记录验证证据）、`audit`（收口审计）和 `close`（关闭任务）。示例没有预填证据，避免把示例记录误认为真实结果。
