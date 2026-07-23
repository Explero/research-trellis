# 事实来源

## 目标

列出本手册使用的正式仓库依据，便于后续版本复核。

## 适用范围

行为事实来自当前代码、根说明、包配置、命令帮助、模板和测试。上游官方中文手册只用于参考教学顺序和基础概念，不用于证明科研版功能。

## 前置条件

从仓库根目录阅读以下相对路径。

## 操作步骤

- **S1**：[根说明](https://github.com/Explero/research-trellis/blob/main/README.md)：项目定位、上游关系、试用建议和安全边界。
- **S2**：[根包配置](https://github.com/Explero/research-trellis/blob/main/package.json)、[命令包配置](https://github.com/Explero/research-trellis/blob/main/packages/cli/package.json)、[核心包配置](https://github.com/Explero/research-trellis/blob/main/packages/core/package.json)：版本、依赖、脚本和运行时要求。
- **S3**：[命令入口](https://github.com/Explero/research-trellis/blob/main/packages/cli/src/cli/index.ts)：正式主命令与参数；另以各命令 `--help`（帮助）实测核对。
- **S4**：[初始化实现](https://github.com/Explero/research-trellis/blob/main/packages/cli/src/commands/init.ts)、[更新实现](https://github.com/Explero/research-trellis/blob/main/packages/cli/src/commands/update.ts)、[卸载实现](https://github.com/Explero/research-trellis/blob/main/packages/cli/src/commands/uninstall.ts)、[工作流实现](https://github.com/Explero/research-trellis/blob/main/packages/cli/src/commands/workflow.ts)。
- **S5**：[工作流结构生成](https://github.com/Explero/research-trellis/blob/main/packages/cli/src/configurators/workflow.ts)和 `packages/cli/src/templates/`（初始化模板目录）。
- **S6**：[任务脚本](https://github.com/Explero/research-trellis/blob/main/packages/cli/src/templates/trellis/scripts/task.py)及其 `common/`（公共脚本目录）。
- **S7**：`packages/cli/src/templates/trellis/hermes/`（科研配置、状态机、协议、角色和报告模板）。
- **S8**：`packages/cli/src/templates/trellis/scripts/hermes/`（科研记录、校验、运行、报告、服务和恢复脚本）。
- **S9**：[平台注册表](https://github.com/Explero/research-trellis/blob/main/packages/cli/src/types/ai-tools.ts)及平台配置器、技能、代理和钩子模板。
- **S10**：`packages/cli/src/commands/channel/`（频道命令）和 `packages/core/src/channel/`（频道核心）。
- **S11**：[会话记忆命令](https://github.com/Explero/research-trellis/blob/main/packages/cli/src/commands/mem.ts)和 `packages/core/src/mem/`（会话记忆核心）。
- **S12**：`packages/cli/test/`（命令与模板测试）、`packages/core/test/`（核心测试）和[科研预检脚本](https://github.com/Explero/research-trellis/blob/main/packages/cli/scripts/hermes-preflight.js)。
- **S13**：[上游官方中文手册](https://docs.trytrellis.app/zh)：参考“概览、安装、首个任务、工作原理、日常使用、高级内容、附录”的教学顺序；访问日期为 2026-07-14。本手册不是该网站的官方翻译或镜像，科研功能仍以 S1 至 S12 为准。
- **S14**：`packages/cli/src/templates/trellis/scripts/closure.py`（收口命令）、`common/closure.py`（收口状态与审计）、共享 hook（上下文钩子）、`packages/core/src/task/schema.ts`（任务结构）以及对应集成测试。

## 预期结果

每条功能说明都能回到至少一个当前正式来源。

## 失败恢复

来源文件移动或版本变化时，先更新来源编号，再修正文中事实和相对链接。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.7.1-beta.1`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n -m 1 "^## |^# " docs/manual/*.md`（手册结构核对）。
- 结果：所有手册页的标题结构可读，来源索引仍指向当前仓库文件。
- 未验证项：本轮未重新访问所有外部网址，外部来源的可用性不在本记录中声称。

## 来源

本页即统一来源索引。

## 相关页面

- [手册首页](README.md)
- [功能状态](appendix-f-feature-status.md)
