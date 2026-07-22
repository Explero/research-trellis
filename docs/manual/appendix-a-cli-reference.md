# 附录 A 常用命令

## 目标

集中查看日常任务最常用的入口。本页不是完整命令参考，全部参数以命令自身的 `--help`（帮助）输出为准。

## 适用范围

适用于 `0.7.1`（测试版）。

## 前置条件

已安装 `trellis`（命令）；项目脚本需在已初始化项目根目录运行。

## 操作步骤

主要命令：

| 命令 | 用途 | 副作用 |
| --- | --- | --- |
| `research-trellis init`（初始化） | 生成工作流与平台文件 | 写文件 |
| `research-trellis update --dry-run`（更新预览） | 比较项目模板 | 无 |
| `research-trellis upgrade --dry-run`（升级预览） | 显示全局升级命令 | 无 |
| `research-trellis workflow --list`（工作流列表） | 列出工作流 | 可能访问网络 |
| `research-trellis uninstall --dry-run`（卸载预览） | 列出删除范围 | 无 |
| `research-trellis channel --help`（频道帮助） | 查看频道子命令 | 无 |
| `research-trellis mem help`（记忆帮助） | 查看会话检索子命令 | 无 |

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

平台命令入口：

| 入口 | 用途 | 任务状态影响 |
| --- | --- | --- |
| `continue`（继续） | 恢复活动任务 | 无直接写入 |
| `status`（状态） | 显示阶段、工作包、阻塞和下一动作 | 只读 |
| `handoff`（交接） | 生成或下发子代理编写 `HANDOFF.md`（交接摘要） | 只更新交接文件 |
| `finish-work`（收尾） | 审计、关闭并归档满足条件的任务 | 可能归档 |
| `start`（启动） | 兼容无自动启动钩子的环境 | 无直接写入 |

平台决定命令前缀。`Claude Code`（Claude 代码工具）等原生命令平台使用斜杠命令；`Codex`（代码代理平台）使用同名技能入口。`status`（状态）不会运行修复、关闭或归档；`handoff`（交接）不会完成或关闭任务。

Closure 命令：

```bash
python3 ./.trellis/scripts/closure.py --help
python3 ./.trellis/scripts/closure.py plan --task "$TASK"
python3 ./.trellis/scripts/closure.py validate --task "$TASK"
python3 ./.trellis/scripts/closure.py status --task "$TASK"
python3 ./.trellis/scripts/closure.py next --task "$TASK"
python3 ./.trellis/scripts/closure.py capsule --task "$TASK"
python3 ./.trellis/scripts/closure.py package-start --task "$TASK"
python3 ./.trellis/scripts/closure.py package-check --task "$TASK"
python3 ./.trellis/scripts/closure.py package-done --task "$TASK" --evidence artifacts/validation-output.txt
python3 ./.trellis/scripts/closure.py package-block --task "$TASK" --reason "阻塞原因"
python3 ./.trellis/scripts/closure.py amend --task "$TASK" --field <field> --value <value> --reason <reason>
python3 ./.trellis/scripts/closure.py audit --task "$TASK"
python3 ./.trellis/scripts/closure.py repair --task "$TASK"
python3 ./.trellis/scripts/closure.py handoff --task "$TASK"
python3 ./.trellis/scripts/closure.py close --task "$TASK"
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
python3 ./.trellis/scripts/hermes/evidence.py collect --task "$TASK"
python3 ./.trellis/scripts/hermes/evidence.py validate --task "$TASK"
python3 ./.trellis/scripts/hermes/evidence.py summary --task "$TASK"
python3 ./.trellis/scripts/hermes/report.py quality-gate --task "$TASK"
python3 ./.trellis/scripts/hermes/jobs.py check --task "$TASK"
```

Agent Context Firewall（代理上下文防火墙）统一命令：

```bash
python3 ./.trellis/scripts/hermes/dispatch.py create --task "$TASK" --role <role> --profile <profile> --objective <text>
python3 ./.trellis/scripts/hermes/dispatch.py validate --task "$TASK" --job-id <job>
python3 ./.trellis/scripts/hermes/dispatch.py show --task "$TASK" --job-id <job> --prompt
python3 ./.trellis/scripts/hermes/dispatch.py run --task "$TASK" --job-id <job> --platform codex
python3 ./.trellis/scripts/hermes/dispatch.py apply --task "$TASK" --job-id <job> --result result.json
python3 ./.trellis/scripts/hermes/dispatch.py list --task "$TASK"
python3 ./.trellis/scripts/hermes/dispatch.py status --task "$TASK" --job-id <job>
```

`create`（创建）会同时生成派发文件和任务卡；`validate`（校验）检查修订号与边界；`show`（显示）默认不读取 raw trace（原始跟踪）；`run`（运行）在当前项目工作区使用紧凑派发协议；`apply`（应用）保存原始结果后只写入净化结果并更新 `next_action`（下一动作）。

高风险入口包括 `research-trellis init --force`（强制初始化）、`research-trellis update --force`（强制更新）、`research-trellis uninstall --yes`（确认卸载）、`research-trellis channel rm`（删除频道）、高风险 `closure.py amend`（计划变更）和 `task.py archive`（归档任务，默认可能提交）。

## 预期结果

帮助输出与本页命令名称一致。

## 失败恢复

命令不识别时先检查 `research-trellis --version`（版本）；项目脚本不存在时重新检查初始化是否完成。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.7.1`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n -m 1 "\.command\(|task.py|hermes/" packages/cli/src/cli packages/cli/src/templates/trellis/scripts`（常用入口核对）。
- 结果：本页列出的主命令、任务脚本和科研脚本入口均可定位。
- 未验证项：本页明确不是全量参数参考，本轮也未逐个执行所有帮助命令。

## 来源

[S3、S4、S6、S8](sources.md)

## 相关页面

- [安装](02-installation.md)
- [更新、恢复与卸载](16-update-recovery-and-uninstall.md)
