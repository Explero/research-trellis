# 17 Lean Research Closure

## 目标

用一个 Trellis 任务完成适度拆解、状态记录、缺口修复和关闭检查，避免计划过宽或部分完成后提前结束。

## 一项任务如何拆

新任务默认使用 `lean`（轻量）模式。一般先保留一个 task，在 task 内安排 1–4 个 work packages（工作包）。工作包描述可观察结果，不描述命令步骤。

例如，“生成可安装包并通过安装验证”可以是一个工作包；“读取配置、修改文件、运行构建、查看输出”不能拆成四个工作包。

只有下面五项中至少满足两项，才适合单独建立工作包：

1. 产生独立产物；
2. 有独立验证标准；
3. 依赖前一结果；
4. 可以独立失败或阻塞；
5. 需要不同代理、环境或权限。

出现 5 个以上工作包时，工具只提示考虑拆成多个 task，不会自动拆分。真正的 subtask（子任务）用于独立交付、独立审查或并行工作；work package 仍属于同一任务并共享范围。

## 最短流程

```bash
python3 ./.trellis/scripts/task.py create "验证本地分析脚本" --slug verify-analysis
TASK="$(find .trellis/tasks -maxdepth 1 -type d -name '*-verify-analysis' -printf '%f\n' | tail -n 1)"

python3 ./.trellis/scripts/closure.py plan --task "$TASK" \
  --intent "得到可重复运行且经过验证的分析结果" \
  --in-scope "本地固定样例" \
  --out-of-scope "正式论文结论" \
  --done-when "分析脚本在固定样例上运行成功"
python3 ./.trellis/scripts/closure.py validate --task "$TASK"

export TRELLIS_CONTEXT_ID=manual-closure-example
python3 ./.trellis/scripts/task.py start "$TASK"
python3 ./.trellis/scripts/closure.py capsule --task "$TASK"
```

完成当前工作包后：

```bash
python3 ./.trellis/scripts/closure.py package-check --task "$TASK"
python3 ./.trellis/scripts/closure.py package-done --task "$TASK" \
  --evidence "tests/test_analysis.py: passed"
python3 ./.trellis/scripts/closure.py audit --task "$TASK"
python3 ./.trellis/scripts/closure.py close --task "$TASK"
python3 ./.trellis/scripts/task.py archive "$TASK" --no-commit
```

`task.json`（任务状态）是当前状态的唯一事实源。每次 Closure 语义写入都会原子替换文件并递增 `hermes_revision`（Hermes 修订号）。阶段和工作包状态只能通过命令变更；对话里说“已经完成”不会把任务改成 `completed`（已完成）。

## Task Capsule

`capsule`（紧凑上下文）默认控制在约 500–1000 个字符，包含任务目标、范围、模式、阶段、当前工作包、完成条件、下一动作、阻塞项和最多 3 个相关引用。

每轮自动注入优先使用 capsule，不自动读取完整 `prd.md`（需求文档）、全部报告、全部事件、全部 ledger（账本）、历史任务和无关规范。这些文件不会删除，仍可按需读取。

普通任务恢复仍可使用 `capsule`（紧凑上下文）。正式 `Hermes`（科研工作流）角色改为读取 validated dispatch（已验证派发）：派发绑定当前修订号、角色、模式、工作包、目标和最多 3 个引用，正文不超过 2000 字符。

Claude Code、Codex 和 OpenCode 使用同一 capsule 语义。其他具有共享每轮 hook 的平台也会收到 capsule；只有会话开始注入或没有主会话 hook 的平台，应在恢复任务时显式运行 `closure.py capsule`。

## Agent Context Firewall

正式防火墙只支持 `Claude Code`（Claude 代码工具）和 `Codex`（代码代理平台）。派发文件位于 `.trellis/tasks/<task>/hermes/dispatches/<job>.dispatch.json`（派发文件），净化结果位于同目录的 `<job>.result.json`（结果文件）。

```bash
python3 ./.trellis/scripts/hermes/dispatch.py create --task "$TASK" \
  --role reviewer --profile closure --objective "检查当前关闭条件"
python3 ./.trellis/scripts/hermes/dispatch.py list --task "$TASK"
```

执行前会比较当前修订号，状态变化后的旧派发返回 `stale_dispatch`（过期派发）。结果必须包含 `uncertainties`（不确定项），结论最多 1200 字符；长日志、完整差异、搜索过程、敏感信息和绝对用户路径不会进入主上下文。两次非法返回只阻塞该 job（工作编号）和当前工作包，不会把科研任务标成完成。

## 角色与阶段

工作包仍是任务内部的结果分组，不因为使用不同角色自动变成子任务。常见顺序如下：

1. `planner:task_planning`（规划代理的任务规划模式）提出 1–4 个工作包候选；状态变更仍由 closure 命令应用。
2. `coder`（编码代理）完成需要修改代码、测试或配置的当前工作包。
3. `runner`（运行代理）登记测试、构建、实验或验证结果。
4. `reviewer`（复核代理）进行质量、证据或关闭复核；不同模式不能互相替代门禁。
5. `researcher`（检索代理）只在规划或实现明确缺少代码库、文献或官方文档信息时加入。

`planner`（规划代理）不能直接把工作包标记为完成，`coder`（编码代理）不能批准主张，`runner`（运行代理）不能把命令成功当作证据批准，`reviewer`（复核代理）也不能伪造人工批准。

## 三种模式

| 模式 | 适合场景 | 关闭前增加的检查 |
| --- | --- | --- |
| `lean`（轻量） | 日常代码、探索、文档、小规模试验 | 完成定义、工作包处置、基础验证、无阻塞、关闭报告 |
| `standard`（标准） | 需要可重复运行记录的正式项目阶段 | 成功运行清单、产物 hash、指标、证据、主张限制 |
| `publication`（发表） | 正式论文证据和可公开主张 | 统计比较、主张处置、证据引用、`STATE.md`、`CLAIMS.md` 和人工批准 |

`run finished`（运行结束）、`package done`（工作包完成）、`task closed`（任务关闭）和 `claim approved`（主张批准）是不同状态。运行成功只生成运行记录，不能直接成为已接受证据；任务关闭也不能代替论文主张批准。

模式还会检查防火墙可用性：`lean`（轻量）在没有新鲜钩子或严格模式心跳时强警告；`standard`（标准）要求钩子或严格模式；`publication`（发表）缺少硬门禁时拒绝派发和关闭。

## Audit 与有限修复

```bash
python3 ./.trellis/scripts/closure.py audit --task "$TASK"
```

审计只输出紧凑缺口和下一动作。例如：

```yaml
gaps:
  - package: WP2
    missing: "seed 44 metrics"
    action: "补跑 seed 44 并登记 metrics"
```

`repair`（有限修复）只重新打开审计指出的未完成工作包，不修改已完成工作包，也不会自动运行实验或扩大范围。lean 默认 1 轮，standard 和 publication 默认 2 轮；再次超过上限时任务进入 `blocked`（阻塞）并生成 `HANDOFF.md`（交接文件）。

```bash
python3 ./.trellis/scripts/closure.py repair --task "$TASK"
```

人工审阅后确需增加一次修复机会时，显式批准上限变更：

```bash
python3 ./.trellis/scripts/closure.py amend --task "$TASK" \
  --field max_repair_count --value 2 \
  --reason "人工审阅后允许一次额外修复" \
  --approved-by 'human/root'
python3 ./.trellis/scripts/closure.py validate --task "$TASK"
```

数据集、研究假设、数据切分、指标定义、基线、主张范围、任务范围、closure mode 和修复上限变化不能由 repair 自动处理。

## 计划变更

低风险变更直接更新 `task.json` 并记录 `plan_amended`（计划已修改）事件：

```bash
python3 ./.trellis/scripts/closure.py amend --task "$TASK" \
  --field work_packages.WP2.done_when \
  --value '["固定测试通过"]' \
  --reason "验收条件需要可执行"
```

高风险研究契约变更必须显式记录人工批准：

```bash
python3 ./.trellis/scripts/closure.py amend --task "$TASK" \
  --field dataset --value 'dataset-v2' \
  --reason "数据来源修订" --approved-by 'human/root'
```

变更后任务回到 planning，需重新运行 `closure.py validate`。工具不会重写已经完成的工作包。

## Handoff

`handoff`（交接）通常下发给 `coder:configuration`（配置修改）子代理生成当前任务的 `HANDOFF.md`（交接摘要）。它也可由 closure 命令直接生成紧凑状态摘要。

`HANDOFF.md` 只在代理切换、压缩或清理上下文前、任务阻塞、显式调用和关闭时需要。它记录当前目标、阶段、工作包、已完成结果、改动文件、证据、失败尝试、阻塞和下一动作，但不会修改任务、证据或主张状态。

有活动 closure 任务时，主代理的每次用户请求都会收到一条紧凑续接提示：当前阶段、当前工作包、下一动作和 `task.json`（任务状态）路径。暂停后恢复、切换代理或压缩上下文时，提示会给出 `HANDOFF.md`（交接摘要）路径；任务状态仍以 `task.json` 为准。交接文件全文不会自动注入，也不会默认传给子代理。

上下文采用渐进披露：首次进入任务或任务修订变化时，才注入不超过约 1000 字符的 `Task Capsule`（任务胶囊）；后续请求只保留短续接提示。项目背景、研究方案、约束、任务详情和历史记录只提供文件路径，由主代理按当前请求读取直接相关的一个文件，不默认预读全部内容。

## 常见失败

- `validate` 提示缺少完成定义：用 `plan --done-when` 补充可观察验收条件。
- `package-done` 提示缺少证据：先运行实际验证，再通过 `--evidence` 登记已有仓库文件或 `evidence_ledger.jsonl`（证据账本）中的证据编号；任意文字不会被接受为证据。
- `close` 提示工作包未处置：完成、defer 或 waive 对应工作包；不要直接改 JSON 状态。
- `close` 提示派发未确认：先校验或处置对应结果；满足关闭条件后仍要显式运行 `audit`（审计）和 `close`（关闭）。
- `stale_dispatch`（过期派发）：当前状态已变化，按新修订号重新创建派发，不要复用旧结果。
- `repair` 达到上限：查看 `HANDOFF.md` 和阻塞原因，由人工决定停止任务，或批准提高 `max_repair_count` 后重新校验。
- `archive` 被拒绝：先运行 `closure.py audit` 和 `closure.py close`。旧任务没有 closure 字段时仍走原版兼容归档。

## 示例

- `examples/lean-closure/`（单工作包轻量示例）；
- `examples/standard-ai4chem/`（固定数据和指标契约的标准 AI4Chem 示例）。

## 已知限制

- 自动规划只根据 intent 和完成定义生成候选工作包，研究者仍需审阅拆解质量。
- JSONL 事件便于 Git 审阅，但不是防篡改数据库。
- repair 只调整安全的任务状态，不会自动补跑实验、伪造证据或批准主张。
- publication 的人工批准真实性依赖外部流程，本项目只校验记录字段。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.7.1`（测试版）。
- 命令：closure CLI 集成测试、共享 hook 测试、核心 task schema 测试和场景 smoke test（冒烟测试）。
- 结果：适度拆解、修订号、派发过期、结果净化、模式心跳、有限 repair、关闭和归档兼容均有自动化覆盖。
- 未验证项：自动候选工作包的科研语义仍需任务负责人审阅；人工审批身份真实性由外部流程保证。

## 来源

[S6、S9、S12、S14](sources.md)

## 相关页面

- [第一个科研任务](03-first-research-task.md)
- [任务与规划](06-tasks-and-planning.md)
- [规范与上下文](07-spec-and-context.md)
- [命令参考](appendix-a-cli-reference.md)
- [排障](appendix-e-troubleshooting.md)
