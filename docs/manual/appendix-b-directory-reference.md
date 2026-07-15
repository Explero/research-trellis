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
├── spec/
├── tasks/
│   └── <task>/
│       ├── task.json
│       ├── prd.md
│       ├── implement.jsonl
│       ├── check.jsonl
│       └── hermes/
├── workspace/
├── hermes/
└── scripts/
    └── hermes/
```

- `.trellis/hermes/`（全局科研模板）只保存约定和模板。
- `.trellis/tasks/<task>/hermes/`（任务科研记录）保存任务事实。
- `.trellis/.runtime/`（会话运行状态）保存活动任务指针，通常不提交。
- `.codex/`（Codex 配置）、`.claude/`（Claude 配置）等目录由平台选择决定。

## 预期结果

任务记录与全局模板不会混淆，活动任务、规范和工作日志各有固定位置。

## 失败恢复

缺少任务内科研目录时运行 `python3 ./.trellis/scripts/hermes/experiment.py init --task "$TASK"`（初始化实验）。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.6.0-beta.31`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n -m 1 "tasks|hermes|workflow" packages/cli/src/constants packages/cli/src/configurators packages/cli/src/templates/trellis`（目录来源核对）。
- 结果：项目、任务和科研记录目录均与当前常量及模板对齐。
- 未验证项：本轮未在新初始化项目中重新生成完整文件树。

## 来源

[S5、S6、S7](sources.md)

## 相关页面

- [工作原理](04-how-it-works.md)
- [记录格式](appendix-d-record-schema.md)
