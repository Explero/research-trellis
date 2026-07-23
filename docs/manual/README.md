# Research Trellis 中文手册

这套手册面向第一次把 `Research Trellis`（科研改造版）放进真实科研项目的人。当前仓库版本为 `0.7.1-beta.1`（测试版）；它基于 `mindfold-ai/Trellis`（上游项目）修改，不是上游官方版本，也不代表上游立场。

## 最短上手路径

1. 阅读[项目概览](01-overview.md)，确认实验性边界。
2. 按[安装](02-installation.md)安装并检查版本。
3. 在可回滚的低风险项目中完成[第一个科研任务](03-first-research-task.md)。
4. 遇到问题时先查[排障附录](appendix-e-troubleshooting.md)和[功能状态表](appendix-f-feature-status.md)。

最短命令如下。请先进入目标科研项目；初始化会写入当前目录。

```bash
git status --short
research-trellis init -y -u "$USER" --codex --no-monorepo
python3 ./.trellis/scripts/task.py list
```

## 阅读导航

| 阶段 | 页面 |
| --- | --- |
| 认识与安装 | [01 项目概览](01-overview.md) · [02 安装](02-installation.md) · [03 第一个科研任务](03-first-research-task.md) · [04 工作原理](04-how-it-works.md) |
| 项目与任务 | [05 项目初始化](05-project-setup.md) · [06 任务与规划](06-tasks-and-planning.md) · [07 规范与上下文](07-spec-and-context.md) |
| 科研记录 | [08 Hermes 记录](08-hermes-records.md) · [09 实验配置](09-experiments.md) · [10 运行与复查](10-runs-and-replay.md) · [11 指标与比较](11-metrics-and-comparison.md) · [12 报告与主张](12-reports-and-claims.md) |
| 协作与维护 | [13 工作代理与门禁](13-workers-and-gates.md) · [14 工作流与平台](14-workflows-and-platforms.md) · [15 频道与会话记忆](15-channel-and-memory.md) · [16 更新、恢复与卸载](16-update-recovery-and-uninstall.md) · [17 Lean Research Closure](17-lean-research-closure.md) |
| 参考 | [命令参考](appendix-a-cli-reference.md) · [目录参考](appendix-b-directory-reference.md) · [配置参考](appendix-c-configuration-reference.md) · [记录格式](appendix-d-record-schema.md) · [排障](appendix-e-troubleshooting.md) · [功能状态、安全与许可证](appendix-f-feature-status.md) · [事实来源](sources.md) |

## 使用边界

- **已实现**：初始化、更新、任务与规范文件、多个平台模板、科研记录脚本、实验运行清单、比较、报告、频道和会话检索命令均有当前代码与测试依据。
- **实验性**：整个科研改造版仍是测试版；`Hermes`（科研工作流）门禁、代理协作和频道工作代理都应先在低风险项目试用。当前版本直接在真实项目环境运行，不提供容器或沙箱执行模式。
- **未实现**：操作系统级安全沙箱、防篡改记录库、人工审批界面、远程任务服务，以及当前版本的 `OpenCode`（开放代码工具）会话读取器。

手册只描述当前正式仓库中的代码、命令、模板和测试。各页的“验证记录”说明本次实际执行过的检查，“来源”统一指向[事实来源](sources.md)。

本项目沿用并修改上游项目。再次分发、公开部署或更名发布前，应保留上游版权和许可证文件，并核对[安全与许可证说明](appendix-f-feature-status.md)。
