# 附录 B 目录参考

## 目标

快速定位初始化后的项目文件。

## 适用范围

适用于默认单仓库；平台目录随初始化参数变化。

## 前置条件

项目已完成初始化。

## 操作步骤

按以下结构查找：

```text
.trellis/
├── config.yaml
├── workflow.md
├── project/
│   ├── PROJECT_INDEX.md
│   ├── BACKGROUND.md
│   ├── RESEARCH_PLAN.md
│   └── CONSTRAINTS.md
├── spec/
│   ├── guides/
│   │   └── general-code-guidelines.md
│   └── languages/
│       ├── typescript-javascript.md
│       ├── python.md
│       ├── go.md
│       ├── rust.md
│       ├── cpp.md
│       └── shell.md
├── tasks/
│   └── <task>/
│       ├── task.json
│       ├── prd.md
│       ├── implement.jsonl
│       ├── check.jsonl
│       ├── HANDOFF.md
│       ├── closure-report.md
│       └── hermes/
│           └── task-events.jsonl
├── workspace/
├── hermes/
└── scripts/
    └── hermes/
```

- `.trellis/hermes/`（全局科研模板）只保存约定和模板。
- `.trellis/project/`（项目资料）保存项目背景、研究方案、约束和初始化时生成的事实索引。事实索引只列出原始资料路径，不自动总结内容。
- `.trellis/spec/languages/`（语言书写规范）预置常用语言基线；任务只能按当前修改的语言选择引用，避免一次加载全部规则。
- `.trellis/tasks/<task>/hermes/`（任务科研记录）保存任务事实。
- `task.json`（任务状态）保存当前 closure 状态；`task-events.jsonl`（任务事件）只追加重要历史。
- `HANDOFF.md`（交接）按条件生成；`closure-report.md`（关闭报告）由通过的收口审计生成。
- `.trellis/.runtime/`（会话运行状态）保存活动任务指针，通常不提交。
- `.codex/`（Codex 配置）、`.claude/`（Claude 配置）等目录由平台选择决定。

## 预期结果

任务记录与全局模板不会混淆，活动任务、规范和工作日志各有固定位置。

## 失败恢复

缺少任务内科研目录时运行 `python3 ./.trellis/scripts/hermes/experiment.py init --task "$TASK"`（初始化实验）。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.7.1-beta.0`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n -m 1 "tasks|hermes|workflow" packages/cli/src/constants packages/cli/src/configurators packages/cli/src/templates/trellis`（目录来源核对）。
- 结果：项目、任务和科研记录目录均与当前常量及模板对齐。
- 未验证项：本轮未在新初始化项目中重新生成完整文件树。

## 来源

[S5、S6、S7](sources.md)

## 相关页面

- [工作原理](04-how-it-works.md)
- [记录格式](appendix-d-record-schema.md)
