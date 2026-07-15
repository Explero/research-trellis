# 附录 C 配置参考

## 目标

说明项目配置、科研配置和实验配置的当前关键项。

## 适用范围

适用于需要调整日志、自动提交、多包项目、调度和实验运行的项目。

## 前置条件

修改前已备份对应配置，并准备运行校验。

## 操作步骤

`.trellis/config.yaml`（项目配置）常用项：

| 配置 | 含义 |
| --- | --- |
| `session_commit_message`（会话提交说明） | 日志自动提交说明 |
| `max_journal_lines`（日志最大行数） | 工作日志轮转阈值，默认 2000 |
| `session_auto_commit`（会话自动提交） | 设为 `false`（关闭）可避免脚本自动提交 |
| `hooks`（生命周期钩子） | 任务创建、启动、结束和归档后的命令 |
| `packages`（包列表） | 多包项目路径和类型 |
| `codex.dispatch_mode`（Codex 调度模式） | 缺省和非法值均为 `sub-agent`（子代理）；`inline`（当前会话）只改变提示路由，不绕过已启用的 `PreToolUse`（工具前）门禁 |

`.trellis/hermes/config.yaml`（科研全局配置）定义记录位置、任务卡规则、运行命令和审批边界。`.trellis/tasks/<task>/hermes/experiment.yaml`（任务实验配置）定义问题、假设、数据、指标、随机种子、环境、允许命令、隔离模式和产物目录。

修改实验配置后运行：

```bash
python3 ./.trellis/scripts/hermes/experiment.py validate --task "$TASK"
```

## 预期结果

项目行为与配置一致，实验配置通过校验。

## 失败恢复

生命周期钩子失败只会警告，不阻止主操作；实验配置失败会阻止任务启动和运行，应先修正。

## 验证记录

- 日期：2026-07-14。
- 版本：`0.6.0-beta.30`（测试版）。
- 基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`（当前基准）。
- 命令：`rg -n -m 1 "dispatch_mode|session_auto_commit|allowed_commands" packages/cli/src/templates/trellis`（配置模板核对）。
- 结果：会话、`Codex`（代码代理）调度和实验命令配置均可定位，默认子代理语义已对齐。
- 未验证项：生命周期钩子中的用户自定义命令需在具体项目单独验证。

## 来源

[S5、S7、S8](sources.md)

## 相关页面

- [实验配置](09-experiments.md)
- [项目初始化](05-project-setup.md)
