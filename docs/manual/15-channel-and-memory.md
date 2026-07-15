# 15 频道与会话记忆

## 目标

使用本地频道交换代理消息，并检索已有 `Claude Code`（Claude 代码工具）和 `Codex`（代码代理平台）会话。

## 适用范围

适用于需要多个本地代理协作、查看事件历史或从旧会话找回信息的进阶场景。两项能力均属于测试版中的实验性功能。

## 前置条件

- 频道工作代理需要已安装并登录 `claude`（Claude 命令）或 `codex`（Codex 命令）。
- 会话检索需要对应工具已在本机保存历史文件。
- 已理解频道事件与 `Hermes RecordBus`（Hermes 记录总线）是两套独立记录；会话记忆也不读取频道事件。

## 操作步骤

1. 创建项目范围聊天频道并发送消息：

```bash
research-trellis channel create research-sync --scope project --description "研究任务协作"
research-trellis channel send research-sync --scope project --as main "请核对当前证据清单"
research-trellis channel messages research-sync --scope project --last 20
research-trellis channel list --scope project
```

频道事件保存在用户目录下的 `.trellis/channels/`（频道存储），项目范围会按当前目录分桶，不写入项目的任务记录。

2. 需要工作代理时，可启动当前仅支持的 `claude`（Claude 提供方）或 `codex`（Codex 提供方）：

```bash
research-trellis channel spawn research-sync --scope project --provider codex --as evaluator --cwd "$PWD"
research-trellis channel send research-sync --scope project --as main --to evaluator "检查固定指标的证据引用"
research-trellis channel wait research-sync --scope project --as main --from evaluator --kind done --timeout 5m
```

`spawn`（启动工作代理）会创建后台监督进程。工作完成后用 `channel kill`（停止工作代理）结束仍在运行的进程；删除频道前先看[命令参考](appendix-a-cli-reference.md)。

3. 查看会话记忆命令：

```bash
research-trellis mem help
research-trellis mem projects --json
research-trellis mem search "固定指标" --platform codex --cwd "$PWD" --limit 10
```

默认只搜索当前项目；`--global`（全局搜索）会扩大到所有项目，应注意本地隐私。`extract`（提取）和 `context`（上下文）可进一步查看命中的对话。

4. 当前 `OpenCode`（开放代码工具）读取器未实现：命令会提示其新版本历史已迁移到 `SQLite`（嵌入式数据库），并返回空结果。帮助中仍保留参数，不代表读取可用。

## 预期结果

频道创建、发送和读取事件成功；本机存在历史时，会话检索返回按项目和时间过滤的结果。频道工作代理能否运行还取决于外部工具和认证。

## 失败恢复

- 频道同名已存在：换名，或在确认旧频道可删除后处理；不要直接使用 `--force`（强制覆盖）。
- 工作代理启动后无响应：查看频道事件和工作代理日志，确认外部命令可执行、已登录并检查超时。
- `wait`（等待）超时：超时不等于工作完成，先查看 `messages`（消息）和工作代理状态。
- 会话搜索为空：先运行 `mem projects`（项目列表），再用正确 `--cwd`（工作目录）和平台筛选。
- `OpenCode`（开放代码工具）提示不可用：这是当前未实现状态，不是本地配置错误。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.6.0-beta.31`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n -m 1 "OpenCode|channel|mem" packages/cli/src/commands packages/core/src packages/cli/test packages/core/test`（频道与会话读取核对）。
- 结果：频道、会话读取和 `OpenCode`（开放代码工具）未实现分支均有当前代码与测试依据。
- 未验证项：本轮未登录真实 `Claude`（Claude 工具）或 `Codex`（代码代理）会话账户。

## 来源

[S3、S10、S11、S12](sources.md)

## 相关页面

- [工作代理与门禁](13-workers-and-gates.md)
- [命令参考](appendix-a-cli-reference.md)
- [功能状态](appendix-f-feature-status.md)
