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
| `codex.dispatch_mode`（Codex 调度模式） | 旧 Trellis 实现/检查代理的路由设置；不会把 Hermes 原生派发升级为强门禁 |

`.trellis/hermes/config.yaml`（科研全局配置）定义记录位置、任务卡规则、运行命令、审批边界和 `context_firewall`（上下文防火墙）。正式平台只有 `claude`（Claude）与 `codex`（Codex）：Claude 依赖钩子强制替换，`Codex native`（Codex 原生派发）仅提供建议，`Codex strict`（Codex 严格模式）通过统一派发命令执行。

防火墙相关环境变量：

| 环境变量 | 含义 |
| --- | --- |
| `TRELLIS_HOOKS=0`（关闭钩子） | 明确关闭钩子；`lean`（轻量）强警告，`standard`（标准）和 `publication`（发表）拒绝缺少强门禁的操作 |
| `TRELLIS_DISABLE_HOOKS=1`（禁用钩子） | 与上一项相同，用于兼容现有启动方式 |
| `TRELLIS_HOOKS_ACTIVE=1`（钩子活动标记） | 仅作状态提示；必须同时存在签名且新鲜的心跳，不能单独通过门禁 |
| `TRELLIS_PLATFORM`（平台） | 仅接受 `claude`（Claude）或 `codex`（Codex）作为正式防火墙平台 |
| `TRELLIS_CODEX_STRICT=1`（Codex 严格标记） | 仅作状态提示；严格包装仍需实际隔离执行和签名心跳，手工设置无效 |
| `TRELLIS_CONTEXT_FIREWALL_HEARTBEAT_TTL`（心跳有效期） | 新鲜心跳的秒数，默认 900 |

`SessionStart`（会话启动）、运行守卫和 Codex 严格包装会在 `.trellis/.runtime/context-firewall/`（防火墙运行目录）写入心跳。`lean`（轻量）缺少新鲜心跳时继续但强警告；`standard`（标准）必须有钩子或严格执行；`publication`（发表）缺少硬门禁时拒绝派发和关闭。原始跟踪只写入 `.trellis/.runtime/hermes-traces/`（原始跟踪目录），默认不进入模板发布包。

`.trellis/tasks/<task>/hermes/experiment.yaml`（任务实验配置）定义问题、假设、数据、指标、随机种子、环境、允许命令、隔离模式和产物目录。

修改实验配置后运行：

```bash
python3 ./.trellis/scripts/hermes/experiment.py validate --task "$TASK"
```

## 预期结果

项目行为与配置一致，实验配置通过校验。

## 失败恢复

生命周期钩子失败只会警告，不阻止主操作；实验配置失败会阻止任务启动和运行，应先修正。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.7.1`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n -m 1 "dispatch_mode|session_auto_commit|allowed_commands" packages/cli/src/templates/trellis`（配置模板核对）。
- 结果：会话、Hermes 防火墙、`Codex`（代码代理）调度和实验命令配置均可定位，模式门禁与心跳设置已对齐。
- 未验证项：生命周期钩子中的用户自定义命令需在具体项目单独验证。

## 来源

[S5、S7、S8](sources.md)

## 相关页面

- [实验配置](09-experiments.md)
- [项目初始化](05-project-setup.md)
