# 附录 A 常用命令

## 目标

集中查看日常任务最常用的入口。本页不是完整命令参考，全部参数以命令自身的 `--help`（帮助）输出为准。

## 适用范围

适用于 `0.6.0-beta.30`（测试版）。

## 前置条件

已安装 `trellis`（命令）；项目脚本需在已初始化项目根目录运行。

## 操作步骤

主要命令：

| 命令 | 用途 | 副作用 |
| --- | --- | --- |
| `trellis init`（初始化） | 生成工作流与平台文件 | 写文件 |
| `trellis update --dry-run`（更新预览） | 比较项目模板 | 无 |
| `trellis upgrade --dry-run`（升级预览） | 显示全局升级命令 | 无 |
| `trellis workflow --list`（工作流列表） | 列出工作流 | 可能访问网络 |
| `trellis uninstall --dry-run`（卸载预览） | 列出删除范围 | 无 |
| `trellis channel --help`（频道帮助） | 查看频道子命令 | 无 |
| `trellis mem help`（记忆帮助） | 查看会话检索子命令 | 无 |

任务命令：

```bash
python3 ./.trellis/scripts/task.py --help
python3 ./.trellis/scripts/task.py create "标题" --slug name
python3 ./.trellis/scripts/task.py list
python3 ./.trellis/scripts/task.py current --source
python3 ./.trellis/scripts/task.py validate "$TASK"
python3 ./.trellis/scripts/task.py start "$TASK"
python3 ./.trellis/scripts/task.py finish
python3 ./.trellis/scripts/task.py archive "$TASK" --no-commit
```

科研命令：

```bash
python3 ./.trellis/scripts/hermes/experiment.py --help
python3 ./.trellis/scripts/hermes/runner.py --help
python3 ./.trellis/scripts/hermes/report.py --help
python3 ./.trellis/scripts/hermes/validate.py --help
python3 ./.trellis/scripts/hermes/validate.py --task "$TASK" --kind worker
python3 ./.trellis/scripts/hermes/validate.py --task "$TASK" --kind evidence
python3 ./.trellis/scripts/hermes/validate.py --task "$TASK" --kind claim
python3 ./.trellis/scripts/hermes/report.py quality-gate --task "$TASK"
python3 ./.trellis/scripts/hermes/jobs.py check --task "$TASK"
```

高风险入口包括 `trellis init --force`（强制初始化）、`trellis update --force`（强制更新）、`trellis uninstall --yes`（确认卸载）、`trellis channel rm`（删除频道）和 `task.py archive`（归档任务，默认可能提交）。

## 预期结果

帮助输出与本页命令名称一致。

## 失败恢复

命令不识别时先检查 `trellis --version`（版本）；项目脚本不存在时重新检查初始化是否完成。

## 验证记录

- 日期：2026-07-14。
- 版本：`0.6.0-beta.30`（测试版）。
- 基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`（当前基准）。
- 命令：`rg -n -m 1 "\.command\(|task.py|hermes/" packages/cli/src/cli packages/cli/src/templates/trellis/scripts`（常用入口核对）。
- 结果：本页列出的主命令、任务脚本和科研脚本入口均可定位。
- 未验证项：本页明确不是全量参数参考，本轮也未逐个执行所有帮助命令。

## 来源

[S3、S4、S6、S8](sources.md)

## 相关页面

- [安装](02-installation.md)
- [更新、恢复与卸载](16-update-recovery-and-uninstall.md)
