# Hermes Deployment Candidate Hardening Preflight

这版是 `deployment candidate hardening`（部署候选加固），不是完整
`production ready`（生产就绪）平台。

## 紧急部署步骤

1. 先运行 quick gate：

```bash
pnpm --filter research-trellis hermes:preflight -- --quick
```

2. 发布前补跑完整验证：

```bash
pnpm --filter research-trellis exec vitest run test/templates/hermes-runtime.test.ts test/templates/trellis.test.ts test/templates/claude.test.ts test/templates/codex.test.ts test/templates/shared-hooks.test.ts
PYTHONPYCACHEPREFIX=/tmp/research-trellis-pycache python3 -m py_compile packages/cli/src/templates/trellis/scripts/hermes/*.py packages/cli/src/templates/shared-hooks/hermes-runtime-guard.py
pnpm --filter research-trellis typecheck
pnpm --filter research-trellis build
```

3. 若 Python 编译后出现 `__pycache__` 或 `.pyc` 在模板目录内，不能发布；用 `gio trash` 或 `trash` 清理后重跑 preflight。

## 安全 Gate

- `Bash` 写入守卫是最佳努力，不是完整 shell 沙箱。hook 会解析常见重定向和 `tee` 写入；遇到写入语义但无法明确解析目标时必须 `fail closed`。
- `runner.py` 必须按任务 `experiment.yaml` 的 `allowed_commands` 执行命令白名单；未匹配命令直接失败。`allowed_commands` is not a strong command sandbox（不是强命令沙箱）；如果允许 `python3`，仍能执行任意 Python 行为。需要更强控制时，应使用更严格 exact match（精确匹配）或外部 OS 级隔离。
- `sandbox.required=true` 且 `mode=none` 必须拒绝运行；`mode=none` 只是本地执行，不是隔离环境。`container` 当前只提供 `Docker`（容器运行时）薄切片：通过 `docker run --rm`（一次性容器执行命令）挂载仓库，并在容器工作目录执行已通过白名单的命令；这仍是 `not an OS sandbox`（不是操作系统沙箱），也不是 `production ready`（生产就绪）的强隔离。`external` 当前仍只做可用性检查，不能声称已经提供 `OS sandbox`（操作系统沙箱）。
- `runner.py --cwd`、`--input`、`--output` 必须留在仓库内；`report.py --output` 必须留在当前任务 Hermes 目录内。
- runner 默认使用最小环境变量白名单，`run_manifest` 不记录完整环境，避免 secret env 泄露。
- `approval_records` 必须依赖 `external human/root approval`（外部人工/根权限批准）流程写入。当前实现只能校验字段、claim/evidence 关联和决策值；它不是 OS 级不可写权限隔离。
- `JSONL` 记录是 append-only（追加写）约定，不是 `not tamper-proof`（不可篡改）存储。需要防篡改审计时，应使用外部日志、权限或签名机制。

## 失败处理

- 缺关键模板文件：补齐模板后重跑 `hermes:preflight`。
- Bash gate 失败：改用受 Hermes runner 管理的命令，或把写入文件纳入任务卡 `allowed_files`。
- 命令不在 `allowed_commands`：更新任务级 `experiment.yaml`，不要绕过 runner。
- approval 失败：由外部 human/root 流程补写完整 approval 记录，agent 不能自行生成批准。

## 已知边界

这版是部署候选加固薄切片：它阻断已知高风险绕过，并为 `container`（容器）模式提供可验证的 `Docker`（容器运行时）最小执行路径，但不提供用户权限、文件系统 `ACL`（访问控制列表）或系统调用级隔离；也就是 `not an OS sandbox`（不是操作系统沙箱），更不是生产级强隔离。需要强隔离时，应在后续版本把 `Hermes runner`（Hermes 运行器）放入独立受限执行环境。
