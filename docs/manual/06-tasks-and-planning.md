# 06 任务与规划

## 目标

用任务目录保存需求和计划，并正确区分创建、启动、结束当前会话和归档。

## 适用范围

适用于代码、实验、文献整理、评估和文档任务。轻量任务与复杂任务使用同一套目录，但规划产物要求不同。

## 前置条件

- 项目已初始化。
- 已获得创建任务的同意并明确任务范围。
- 复杂任务开始执行前，已有可审阅的需求、设计和实施计划。

## 操作步骤

1. 创建任务：

```bash
python3 ./.trellis/scripts/task.py create "固定数据集评估" --slug fixed-eval --priority P2 --description "在固定数据切分上运行本地评估"
python3 ./.trellis/scripts/task.py list
```

2. 找到新任务并填写规划产物：

- 轻量任务可以只有 `prd.md`（需求文档）；
- 复杂任务应在启动前补齐 `prd.md`（需求文档）、`design.md`（设计文档）和 `implement.md`（实施计划）；
- 需要工作代理读取额外规范或研究材料时，整理 `implement.jsonl`（实现上下文）和 `check.jsonl`（检查上下文）。

3. 检查上下文并启动：

```bash
TASK="$(find .trellis/tasks -maxdepth 1 -type d -name '*-fixed-eval' -printf '%f\n' | sort | tail -n 1)"
python3 ./.trellis/scripts/task.py validate "$TASK"
python3 ./.trellis/scripts/hermes/experiment.py validate --task "$TASK"
python3 ./.trellis/scripts/task.py start "$TASK"
```

4. 查看当前任务和来源：

```bash
python3 ./.trellis/scripts/task.py current --source
```

5. 工作结束后的两个动作含义不同：

```bash
python3 ./.trellis/scripts/task.py finish
python3 ./.trellis/scripts/task.py archive "$TASK" --no-commit
```

第一条只清除当前会话指针；第二条把任务标为已完成并移动到按月份组织的归档目录。去掉 `--no-commit`（不自动提交）后，默认配置可能自动提交归档改动。

6. 执行中需要改动需求、实验配置或评估基线时，使用追加式计划变更流程：

```bash
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
PROPOSAL="pc-$(date -u +%Y%m%d-%H%M%S)-proposal"
python3 ./.trellis/scripts/hermes/record.py append --task "$TASK" --record-type plan_change --json "{\"type\":\"plan_change\",\"id\":\"$PROPOSAL\",\"timestamp\":\"$NOW\",\"plan_ref\":\"implement.md\",\"change_summary\":\"将评估限定为固定切分\",\"reason\":\"原范围超出任务时间\",\"requested_by\":\"coordinator\",\"decision_state\":\"proposed\",\"evidence_refs\":[],\"supersedes\":[]}"
python3 ./.trellis/scripts/hermes/validate.py --task "$TASK" --kind plan_change
```

审阅者先读取 `plan_ref`（计划引用）、变更理由和证据，再用新编号追加 `accepted`（已接受）或 `rejected`（已拒绝）记录，并令 `supersedes`（替代对象）指向 `$PROPOSAL`。只有接受后才修改计划文件；新方案取代已接受方案时，再追加 `superseded`（已被替代）记录指向旧决定，然后为新方案重复提出和审阅。最后重新运行 `plan_change`（计划变更）、任务和实验校验。

校验器只检查必填字段、决定值、唯一编号和引用列表的结构；它不验证审阅者身份、证据编号是否存在、决定链是否完整，也不会自动修改计划文件。

## 预期结果

任务创建时状态为 `planning`（规划中）；启动后变为 `in_progress`（进行中）；归档后变为 `completed`（已完成）并移动到 `.trellis/tasks/archive/<year-month>/`（月度归档目录）。

## 失败恢复

- 启动时报实验配置无效：先修正任务下的 `experiment.yaml`（实验配置）。
- 启动时报缺少会话身份：在人工智能会话中执行，或设置 `TRELLIS_CONTEXT_ID`（会话标识）。
- 错误归档：归档会移动文件且可能提交；操作前先有 `Git`（版本控制工具）检查点，并优先使用 `--no-commit`（不自动提交）审阅结果。
- 当前任务指针过期：运行 `current --source`（查看来源），再对正确任务执行 `start`（启动）。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.6.0-beta.31`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n "plan_change|decision_state|supersedes" packages/cli/src/templates/trellis/scripts/hermes packages/cli/test/templates/hermes-runtime.test.ts`（变更协议核对）。
- 结果：提出、审阅、接受或拒绝、替代和校验流程已补全，并明示了结构校验边界。
- 未验证项：审阅者身份、决定链语义和证据存在性仍需外部流程保证。

## 来源

[S5、S6、S7](sources.md)

## 相关页面

- [规范与上下文](07-spec-and-context.md)
- [实验配置](09-experiments.md)
- [命令参考](appendix-a-cli-reference.md)
