# 16 更新、恢复与卸载

## 目标

预览模板更新、升级全局命令、从中断状态恢复，并在明确备份后卸载项目文件。

## 适用范围

适用于已初始化项目的日常维护。卸载会删除项目内全部 `.trellis/`（工作流目录），属于高风险操作。

## 前置条件

- 已查看 `git status --short`（工作区状态）。
- 已备份任务、规范、科研记录和工作日志。
- 清楚区分 `upgrade`（升级全局命令）与 `update`（更新当前项目模板）。

## 操作步骤

1. 先升级预览全局命令，不实际安装：

```bash
research-trellis upgrade --dry-run
```

实际升级会运行 `npm install -g research-trellis@latest`（安装最新全局包）。需要可复现环境时，应安装明确版本。

2. 预览当前项目模板更新：

```bash
research-trellis update --dry-run
```

更新器会区分未修改模板、用户修改模板和用户数据。当前实现明确保留 `.trellis/workspace/`（工作日志）、`.trellis/tasks/`（任务）、`.trellis/spec/`（规范）和开发者身份。

3. 对冲突选择处理方式：

```bash
research-trellis update --create-new
```

该方式把有变化的模板写成 `.new`（新副本）供比较。`--skip-all`（全部跳过）保留本地文件，`--force`（强制覆盖）覆盖变化文件，`--migrate`（应用迁移）才执行待处理的重命名或删除。降级默认被拒绝，除非显式 `--allow-downgrade`（允许降级）。

4. 初始化中断后，修正环境并重新运行原初始化命令。当前实现会在 `.trellis/tasks/`（任务目录）为空时重新走完整流程，并补建启动任务。

5. 卸载前只做预览：

```bash
research-trellis uninstall --dry-run
```

预览会列出受管理的平台文件，并明确包含整个 `.trellis/`（工作流目录），其中的任务、记录和运行数据都会被删除。只有完成外部备份并确认列表后，才考虑：

```bash
research-trellis uninstall --yes
```

## 预期结果

更新预览不修改文件；候选更新以 `.new`（新副本）形式出现。卸载预览只列清单，不删除内容。实际卸载后，受管理平台文件和整个工作流目录被移除。

## 失败恢复

- 更新后行为变化：比较 `.new`（新副本）或用项目已有 `Git`（版本控制工具）检查点恢复，再重新选择冲突策略。
- 命令版本比项目旧：先升级命令，再预览项目更新。
- 误运行卸载：工具没有内置撤销；只能从 `Git`（版本控制工具）、备份或外部记录恢复。
- 自动归档或日志提交不符合项目习惯：在 `.trellis/config.yaml`（项目配置）中设置 `session_auto_commit: false`（关闭会话自动提交）。
- 更新时网络检查失败：可继续使用当前已安装版本，稍后再试，不要盲目强制更新。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.7.0-beta.0`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n -m 1 "dry-run|create-new|allow-downgrade" packages/cli/src/commands packages/cli/test/commands`（更新与恢复核对）。
- 结果：预览、冲突副本、降级拒绝和卸载预览分支均可定位。
- 未验证项：本轮未在临时项目手工执行更新、升级或卸载预览。

## 来源

[S3、S4、S6、S12](sources.md)

## 相关页面

- [安装](02-installation.md)
- [排障](appendix-e-troubleshooting.md)
- [目录参考](appendix-b-directory-reference.md)
