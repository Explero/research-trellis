# 06 任务与规划

## 目标

用任务目录保存需求和计划，通过 1–4 个工作包适度拆解，并正确区分运行、工作包完成、任务关闭和归档。

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
- 默认只保留一个 task（任务），内部使用 1–4 个 work packages（工作包）；读取文件、修改文件和运行命令不是独立工作包。
- 只有独立产物、独立验证、独立执行环境、可并行或独立审查等条件中至少满足两项时，才建立独立工作包或真正的 subtask（子任务）。

3. 生成候选工作包并校验：

```bash
TASK="$(find .trellis/tasks -maxdepth 1 -type d -name '*-fixed-eval' -printf '%f\n' | sort | tail -n 1)"
python3 ./.trellis/scripts/closure.py plan --task "$TASK" \
  --intent "在固定数据切分上得到经过验证的评估结果" \
  --in-scope "固定数据与固定指标" \
  --out-of-scope "论文级主张" \
  --done-when "评估运行成功并记录基础验证证据"
python3 ./.trellis/scripts/closure.py validate --task "$TASK"
python3 ./.trellis/scripts/task.py validate "$TASK"
python3 ./.trellis/scripts/hermes/experiment.py validate --task "$TASK"
python3 ./.trellis/scripts/task.py start "$TASK"
```

4. 查看当前任务、来源和紧凑上下文：

```bash
python3 ./.trellis/scripts/task.py current --source
python3 ./.trellis/scripts/closure.py capsule --task "$TASK"
```

5. 工作结束后的状态含义不同：

```bash
python3 ./.trellis/scripts/closure.py package-check --task "$TASK"
python3 ./.trellis/scripts/closure.py package-done --task "$TASK" --evidence "验证命令或报告引用"
python3 ./.trellis/scripts/closure.py audit --task "$TASK"
python3 ./.trellis/scripts/closure.py close --task "$TASK"
python3 ./.trellis/scripts/task.py finish
python3 ./.trellis/scripts/task.py archive "$TASK" --no-commit
```

`package-done`（工作包完成）只处置当前结果；`close`（关闭）先做收口审计，成功后才把任务改为 `completed`（已完成）；`finish`（结束会话）只清除当前会话指针；`archive`（归档）移动已关闭任务。closure 未关闭时归档会被拒绝，旧任务没有 closure 字段时继续走原版兼容流程。

6. 执行中需要改动计划时，使用 closure 变更命令：

```bash
python3 ./.trellis/scripts/closure.py amend --task "$TASK" \
  --field work_packages.WP1.done_when \
  --value '["固定切分评估通过"]' \
  --reason "验收条件需要明确固定切分"
```

数据集、研究假设、数据切分、指标定义、基线、主张范围和任务范围属于高风险字段，必须增加 `--approved-by human/root`（人工批准）。变更直接写入 `task.json`（任务状态），同时向 `task-events.jsonl`（任务事件）追加 `plan_amended`（计划已修改）记录；变更后重新运行 closure 校验。正式研究仍可额外使用 Hermes `plan_change`（研究计划变更记录）保存更完整的提案和审阅链。

## 预期结果

任务创建时状态为 `planning`（规划中）；启动后变为 `in_progress`（进行中）；只有 close gate（关闭门禁）通过后才变为 `completed`（已完成），随后可移动到 `.trellis/tasks/archive/<year-month>/`（月度归档目录）。

## 失败恢复

- 启动时报实验配置无效：先修正任务下的 `experiment.yaml`（实验配置）。
- 启动时报缺少会话身份：在人工智能会话中执行，或设置 `TRELLIS_CONTEXT_ID`（会话标识）。
- 错误归档：归档会移动文件且可能提交；操作前先有 `Git`（版本控制工具）检查点，并优先使用 `--no-commit`（不自动提交）审阅结果。
- 当前任务指针过期：运行 `current --source`（查看来源），再对正确任务执行 `start`（启动）。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.7.1-beta.0`（测试版）。
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
