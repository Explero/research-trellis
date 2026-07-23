# 附录 E 排障

## 目标

用最短路径处理常见安装、初始化、任务、运行和审批失败。

## 适用范围

适用于本手册覆盖的当前测试版。

## 前置条件

保留原始报错，并先运行 `git status --short`（工作区状态）。

## 操作步骤

| 现象 | 处理 |
| --- | --- |
| 初始化提示 Python 不可用 | 确认 `python3 --version`（Python 版本）至少为 3.9，必要时设置 `TRELLIS_PYTHON_CMD`（Python 命令覆盖） |
| 不允许在主目录初始化 | 进入真实项目根目录，不要绕过保护 |
| 任务启动提示缺少会话身份 | 在人工智能会话运行，或设置唯一 `TRELLIS_CONTEXT_ID`（会话标识） |
| 任务启动提示 closure 未准备 | 先填写 intent 和完成定义，再运行 `closure.py plan` 与 `closure.py validate` |
| 任务启动提示实验无效 | 填完 `experiment.yaml`（实验配置）后单独运行实验校验 |
| 工作包不能标记 done | 先运行 `package-check`，再用 `package-done --evidence` 登记已有仓库文件或证据账本编号 |
| audit 显示 has_gaps | 按第一条 package、missing 和 action 补齐；不要自动生成新计划 |
| repair 后仍有缺口 | 完成 repair 打开的工作包；超过上限后由人工停止任务，或批准 amend `max_repair_count` 并重新 validate |
| amend 提示需要批准 | 数据集、假设、切分、指标、基线、主张范围和 scope 变化需真实 `human/root` 批准 |
| archive 提示 closure 未关闭 | 先运行 `closure.py audit` 和 `closure.py close`；旧任务无 closure 字段时不受此限制 |
| 运行命令被拒绝 | 核对允许命令和任务卡，不要扩大为笼统命令 |
| 工作代理记录无效 | 先校验必填字段、唯一任务卡和文件范围 |
| 提示角色或模式不匹配 | 按[工作代理与门禁](13-workers-and-gates.md)使用五个正式角色及其合法模式 |
| 旧角色出现弃用提示 | 更新后续任务卡；旧追加式记录保持原样，不要批量重写 |
| `evidence-curator` 不能派发 | 使用 `evidence.py collect/validate/summary`（证据整理、校验和摘要），质量判断交给 `reviewer:evidence`（证据复核模式） |
| 子代理上下文仍很长 | 检查是否走正式 Hermes 角色入口；派发只应包含公共摘要、角色/模式摘要、任务胶囊和最多 3 个引用 |
| 派发提示 `missing_dispatch`（缺少派发） | 先运行 `dispatch.py create`（创建派发），Claude Agent 只传 `job_id`（工作编号） |
| 派发提示 `stale_dispatch`（过期派发） | 当前 `hermes_revision`（Hermes 修订号）已变化，重新创建派发 |
| 返回提示 `invalid_json`（非法 JSON）或 `long_log`（长日志） | 只返回结果信封 JSON；日志、差异和搜索过程保留在文件或本地原始跟踪中 |
| 两次返回无效后 job 被阻塞 | 修正返回契约并创建替代派发；不要把整个科研任务改成完成 |
| 子代理派发没有收到最小上下文 | 检查 Claude/Codex 钩子是否启用，或显式读取当前派发文件；关闭仍以任务记录、证据和审计为准 |
| `close`（关闭）提示结果未确认 | 先处理所有派发结果和工作包，再显式运行 `audit`（审计）与 `close`（关闭） |
| 质量门禁缺少统计字段 | 见[指标与比较](11-metrics-and-comparison.md)中的当前限制 |
| 审批门禁失败 | 等待真实 `human/root`（人工根权限）批准记录 |
| 记忆搜索提示 OpenCode 不可用 | 当前未实现，不是本地故障 |
| 更新有冲突 | 使用 `research-trellis update --create-new`（生成新副本）比较 |

进一步检查：

```bash
research-trellis --version
python3 ./.trellis/scripts/task.py current --source
python3 ./.trellis/scripts/task.py list
python3 ./.trellis/scripts/closure.py status --task "$TASK"
python3 ./.trellis/scripts/closure.py capsule --task "$TASK"
python3 ./.trellis/scripts/hermes/dispatch.py status --task "$TASK"
```

## 预期结果

能把问题定位到环境、活动任务、实验配置、任务卡、记录或当前未实现功能。

## 失败恢复

仍无法恢复时停止写入，保留日志和差异，从已有 `Git`（版本控制工具）检查点或备份恢复。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.7.1-beta.0`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n -m 1 "quality gate|missing evidence|approval" packages/cli/src/templates/trellis/scripts/hermes packages/cli/test/templates/hermes-runtime.test.ts`（失败关闭分支核对）。
- 结果：质量门禁、缺失证据和审批失败分支都有实现或测试依据。
- 未验证项：本页不包含所有平台主机和网络环境的故障组合。

## 来源

[S3、S4、S6、S8、S11](sources.md)

## 相关页面

- [功能状态](appendix-f-feature-status.md)
- [更新、恢复与卸载](16-update-recovery-and-uninstall.md)
