# 04 工作原理

## 目标

理解一次科研任务从命令、项目文件、平台钩子到科研记录的实际传递路径。

## 适用范围

适合排查“代理为什么知道当前任务”“记录为什么没有生成”以及“普通任务状态和科研状态为何不同”等问题。

## 前置条件

- 已完成一次初始化。
- 能查看 `.trellis/`（工作流目录）和所选平台目录。

## 操作步骤

按五层结构检查当前项目：

1. `CLI`（命令行界面）层：`research-trellis init`（初始化）复制模板，`research-trellis update`（更新）比较模板哈希，`workflow`（工作流）切换流程文件。
2. 项目层：`.trellis/spec/`（项目规范）和 `.trellis/workflow.md`（工作流说明）保存长期规则。
3. 任务层：`.trellis/tasks/<task>/`（任务目录）以 `task.json`（任务状态）保存当前 closure 状态，并保存需求、设计、实施计划和代理上下文清单。
4. 平台层：技能、代理和钩子优先读取 Task Capsule（紧凑上下文）及当前工作包，再按需读取完整材料。
5. `Hermes`（科研工作流）层：任务内 `hermes/`（科研记录目录）保存追加式记录、实验配置、运行清单、比较和报告。

实际流程可以简化为：

```text
初始化项目
  -> 创建任务并写 planning 产物
  -> plan/validate 生成并校验 1–4 个工作包
  -> 启动任务，状态变为 in_progress，首个工作包变为 running
  -> 平台每轮读取 capsule 和当前工作包
  -> 工作代理按 task_card 边界执行
  -> runner 写运行清单，reviewer 检查记录
  -> package done 后执行 closure audit/close
  -> 证据支持 claim_ready 主张
  -> human/root 记录批准后才算 approved
```

需要特别区分：

- `task.py finish`（结束当前任务）只清除当前会话的活动任务指针，不把任务标记为完成；
- `closure.py close`（关闭任务）通过审计后才把新任务状态写为 `completed`（已完成）；
- `task.py archive`（归档任务）只移动已关闭的新任务；旧任务没有 closure 字段时保留原版兼容行为；
- `run finished`（运行结束）、`package done`（工作包完成）、`task closed`（任务关闭）和 `claim approved`（主张批准）互不等同；
- `Hermes`（科研工作流）的 `approved`（已批准）是主张审批状态，不等同于任务归档；
- 聊天内容不是科研事实来源，任务目录中的记录才是后续门禁读取对象。

`.trellis/hermes/state_machine.yaml`（科研状态协议）仍是角色和科研记录协议，不是通用 claim 状态机引擎。v0.7 只把 task closure（任务收口）的紧凑阶段接入 CLI；claim 审批继续由科研记录和人工门禁处理。

## 预期结果

你能从活动任务一路定位到任务文档、平台注入和科研记录，并能解释某个门禁读取的是哪一类文件。

## 失败恢复

- 当前任务为空：运行 `python3 ./.trellis/scripts/task.py current --source`（查看来源），必要时重新启动任务。
- 平台未注入上下文：检查初始化时是否选择了该平台、平台钩子是否启用，以及 `implement.jsonl`（实现上下文）和 `check.jsonl`（检查上下文）是否有效。
- 科研记录为空：确认任务已初始化 `hermes/`（科研记录目录），并检查代理是否先写了 `task_card`（任务卡）。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.7.0-beta.0`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n "state_machine|approval-gate|task.py" packages/cli/src/templates`（协议与实现核对）。
- 结果：任务生命周期有实现支持；科研状态文件已准确标为协议模板。
- 未验证项：没有通用运行时状态迁移引擎可供端到端验证。

## 来源

[S4、S5、S6、S7、S8、S9](sources.md)

## 相关页面

- [规范与上下文](07-spec-and-context.md)
- [Hermes 记录](08-hermes-records.md)
- [工作代理与门禁](13-workers-and-gates.md)
