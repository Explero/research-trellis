# 14 工作流与平台

## 目标

选择合适的工作流模板和人工智能平台，并安全预览工作流切换结果。

## 适用范围

适用于初始化时选择平台、现有项目增加平台，以及在默认流程、测试驱动流程和频道协作流程之间切换。

## 前置条件

- 已安装对应人工智能工具并完成登录。
- 项目已初始化或准备初始化。
- 切换工作流前已查看 `.trellis/workflow.md`（当前工作流）是否有本地修改。

## 操作步骤

1. 查看正式命令支持的平台：

```bash
research-trellis init --help
```

当前提供 `Claude Code`（Claude 代码工具）、`Cursor`（Cursor 编辑器）、`OpenCode`（开放代码工具）、`Codex`（代码代理平台）、`Kilo CLI`（Kilo 命令行工具）、`Kiro Code`（Kiro 代码工具）、`Gemini CLI`（Gemini 命令行工具）、`Antigravity`（Antigravity 工作流）、`Windsurf`（Windsurf 编辑器）、`Qoder`（Qoder 工具）、`CodeBuddy`（CodeBuddy 工具）、`GitHub Copilot`（GitHub 编程助手）、`Factory Droid`（Factory Droid 工具）和 `Pi Agent`（Pi 代理）模板。

这些平台的模板深度不同；“可初始化”不等于所有平台都有同等的钩子和子代理能力。

2. 初始化时显式选择平台：

```bash
research-trellis init -y -u "$USER" --claude --codex --no-monorepo
```

不指定平台且使用 `-y`（自动确认）时，当前默认选择 `Claude Code`（Claude 代码工具）和 `Cursor`（Cursor 编辑器）。

3. 查看工作流模板：

```bash
research-trellis workflow --list
```

当前列表包含内置 `native`（默认工作流），以及市场中的 `tdd`（测试驱动工作流）和 `channel-driven-subagent-dispatch`（频道驱动子代理工作流）。市场模板需要网络，内容来源可能随市场更新。

4. 安全预览另一个工作流，不替换当前文件：

```bash
research-trellis workflow --template tdd --create-new
diff -u .trellis/workflow.md .trellis/workflow.md.new
```

确认后再执行替换：

```bash
research-trellis workflow --template tdd --force
```

5. `Codex`（代码代理平台）缺省为 `sub-agent`（子代理）调度，与 `PreToolUse`（工具使用前）的主代理只读门禁保持一致。需要钩子时，在用户级 `~/.codex/config.toml`（Codex 用户配置）启用：

```toml
[features]
hooks = true

[projects."/absolute/path/to/project"]
trust_level = "trusted"
```

重启 `Codex`（代码代理）后运行 `/hooks`（钩子审阅），逐项检查并批准 `.codex/hooks.json`（Codex 钩子配置）中的工作流注入和 `Hermes`（科研工作流）门禁。旧版 `Codex`（代码代理）使用 `codex_hooks = true`（旧钩子开关）。项目未信任、功能开关未开、未经 `/hooks`（钩子审阅）批准，或设置 `TRELLIS_HOOKS=0`（关闭钩子）、`TRELLIS_DISABLE_HOOKS=1`（禁用钩子）时，注入和门禁都不生效。

项目模板为 `Codex 0.144.0`（代码代理 0.144.0 版）及以上版本设置默认模型：主代理以及 `planner/researcher/reviewer`（规划、检索和复核代理）使用 `gpt-5.6-sol`（推理模型）和 `high`（高推理强度），`coder/runner`（编码和运行代理）使用 `gpt-5.6-terra`（执行模型）和 `max`（最大推理强度）。初始化和更新只维护两个带 Trellis 标记的配置块，分别保存顶层默认值和平台表配置；未标记的用户配置会原样保留并与受管块合并，用户自行选择的项目模型在更新和卸载时都不会被当成 Trellis 默认值删除。旧版 `Codex`（代码代理）只显示兼容警告，不阻止初始化。

`codex.dispatch_mode: inline`（Codex 主会话路由）是显式兼容模式，只改变普通 Trellis 提示路由，不会绕过已启用的 Hermes 写入和结束门禁，也不会提供操作系统隔离。

`v0.7.1-beta.0`（当前测试版）的 closure 任务仍可在各平台读取 `Task Capsule`（紧凑任务上下文），但可执行的 `Agent Context Firewall`（代理上下文防火墙）只正式支持 `Claude Code`（Claude 代码工具）和 `Codex`（代码代理平台）。其他平台保留原有 Trellis 上下文和代理行为，不宣称具备派发替换、结构化返回或状态确认门禁。

五个正式 `Hermes`（科研工作流）角色模板目前只为 `Claude Code`（Claude 代码工具）和 `Codex`（代码代理平台）提供。`Claude Code`（Claude 代码工具）可使用已批准的 `PreToolUse / SubagentStop / PostToolUse`（工具前、子代理结束、工具后）钩子完成派发替换和结果净化；`Codex`（代码代理平台）使用相同的紧凑派发与结果契约，并通过项目钩子限制主代理写入、直接执行和提前结束。Codex 的子代理输入仍依赖协议，不宣称完全硬隔离。

## 用户入口

科研版只保留少量用户可见入口。主代理先根据任务状态、当前工作包和自然语言请求自动路由；命令和技能只是明确入口或兼容入口，不能绕过状态、审计和人工决策门禁。

| 入口 | 用途 | 说明 |
| --- | --- | --- |
| `continue`（继续任务） | 恢复活动任务 | 读取紧凑任务状态并只推进下一动作 |
| `status`（查看状态） | 查看阶段、工作包、阻塞和下一动作 | 只读，不会改变任务状态 |
| `handoff`（写入交接） | 在暂停、切换会话或压缩上下文前生成交接摘要 | 推荐下发子代理写入 `HANDOFF.md`（交接摘要），不会关闭任务 |
| `finish-work`（完成收尾） | 审计、关闭并归档已完成任务 | closure 任务必须先通过审计和关闭门禁 |
| `start`（启动会话） | 兼容没有会话开始钩子的环境 | 支持钩子的主会话通常自动完成启动 |

`Claude Code`（Claude 代码工具）和其他原生命令平台会把这些入口显示为平台的命令形式；`Codex`（代码代理平台）使用同名技能入口。命令前缀由平台决定，不应把某个平台的前缀复制到另一个平台。

建议用户主动理解和调用的技能只有 `grill-me`（聚焦讨论）和 `update-spec`（更新规范）。其他技能按科研阶段和实际工作触发，不设每轮固定数量：需求确有缺口才使用 `brainstorm`（问题梳理）；代码工作包才使用 `before-dev`（开发前准备）和 `check`（代码检查）；`tdd`（测试驱动）必须由用户或任务策略明确选择；`break-loop`（失败归因）只处理重复技术失败；软件架构技能不能代替科研模型设计；正式实验和证据记录使用 `hermes-research`（科研记录）。技能不替代 closure 的状态、审计和关闭门禁。

6. 逐平台能力和限制如下。“子代理”表示仓库会安装对应代理模板；“门禁”专指 `hermes-runtime-guard.py`（Hermes 运行时门禁），不包括只做上下文注入的同名钩子事件。

| 平台 | 主会话上下文 | 子代理与上下文 | `PreToolUse / Stop`（门禁） | 启用条件与限制 |
| --- | --- | --- | --- | --- |
| `Claude Code`（Claude 代码工具） | `SessionStart + UserPromptSubmit`（会话开始和用户提交） | 正式 Hermes Agent 只传 `job_id`（工作编号），钩子替换提示并净化结果 | 完整 | 需平台读取项目设置；异步 Hermes Agent 被拒绝；环境开关可关闭 |
| `Cursor`（Cursor 编辑器） | `sessionStart`（会话开始）注入 capsule 和命令行上下文 | 支持；`Task / Subagent`（子代理工具）前推送 | 无 | 没有每轮 capsule；只有平台实际触发 `.cursor/hooks.json`（Cursor 钩子）时才注入 |
| `OpenCode`（开放代码工具） | `chat.message`（会话消息）注入会话摘要、每轮状态和 capsule | 支持；代理按派发首行自行读取 | 无 | 依赖 OpenCode 插件被实际加载；会话检索功能仍未实现 |
| `Codex`（代码代理） | `UserPromptSubmit`（用户提交），无会话开始注入 | 使用紧凑派发与结果文件，直接在当前工作区执行 | 写入、登记命令和结束条件 | 钩子需用户级开关、项目信任和 `/hooks`（钩子审阅）；派发输入仍为协议约束 |
| `Kilo CLI`（Kilo 命令行） | 手动运行 capsule | 无，主会话执行模板 | 无 | 依赖工作流文件和手动读取 |
| `Kiro Code`（Kiro 代码工具） | 无通用主会话注入 | 支持；`agentSpawn`（代理创建）时推送 | 无 | 只注册代理创建钩子，无会话开始和每轮主会话钩子 |
| `Gemini CLI`（Gemini 命令行） | `SessionStart + BeforeAgent`（会话开始和代理前） | 支持；代理前置说明拉取 | 无 | 依赖 `.gemini/settings.json`（Gemini 设置）的当前钩子协议 |
| `Antigravity`（Antigravity 工作流） | 手动运行 capsule | 无，主会话执行模板 | 无 | 依赖工作流和技能文件 |
| `Windsurf`（Windsurf 编辑器） | 手动运行 capsule | 无，主会话执行模板 | 无 | 依赖工作流和技能文件 |
| `Qoder`（Qoder 工具） | `SessionStart + UserPromptSubmit`（会话开始和用户提交） | 支持；代理前置说明拉取 | 无 | 平台钩子失效时必须依赖派发首行 |
| `CodeBuddy`（CodeBuddy 工具） | `SessionStart + UserPromptSubmit`（会话开始和用户提交） | 支持；`Task`（代理工具）前推送 | 无 | 其 `PreToolUse`（工具前）只用于上下文，不是 `Hermes`（科研工作流）门禁 |
| `GitHub Copilot`（GitHub 编程助手） | `SessionStart + userPromptSubmitted`（会话开始和用户提交） | 支持；代理前置说明拉取 | 无 | `VS Code`（代码编辑器）代理钩子仍属预览能力，是否消费注入取决于安装版本 |
| `Factory Droid`（Factory Droid 工具） | `SessionStart + UserPromptSubmit`（会话开始和用户提交） | 支持；`Task`（代理工具）前推送 | 无 | `PreToolUse`（工具前）只用于上下文 |
| `Pi Agent`（Pi 代理） | `TypeScript`（TypeScript 扩展）在会话、输入和代理前注入 | 支持；扩展直接构造任务上下文 | 无 | 不安装 `Python`（Python 语言）平台钩子；依赖 `pi-subagents`（Pi 子代理包）和扩展加载 |

## 预期结果

平台文件按选择写入，工作流列表可读；使用 `--create-new`（创建新副本）时只生成 `.trellis/workflow.md.new`（工作流候选），原工作流不变。

## 失败恢复

- 只是 `workflow --list`（工作流列表）时市场失败：列表仍保留内置 `native`（默认工作流）并显示警告。显式选择市场模板时，索引或文件下载失败会终止，不会静默改用 `native`（默认工作流）。
- 工作流有本地修改：优先生成 `.new`（新副本）比较，不要直接 `--force`（强制替换）。
- 平台没有自动注入：核对上表是否支持钩子、钩子是否启用，以及初始化是否真的选择了该平台；不支持自动注入的平台应按派发协议手动读取。
- 添加平台时已有配置：重复运行 `research-trellis init --平台参数`（平台初始化）会跳过已配置平台。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.7.1-beta.0`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n -m 1 "dispatch_mode|agentCapable|hasHooks" packages/cli/src packages/cli/test`（平台能力核对）。
- 结果：常规平台能力表保留；代理上下文防火墙的正式范围收窄为 Claude Code 和 Codex，并使用相同的最小上下文语义。
- 未验证项：本轮未启动 14 种平台主机，也未访问远程工作流市场。

## 来源

[S3、S4、S5、S9、S12](sources.md)

## 相关页面

- [项目初始化](05-project-setup.md)
- [配置参考](appendix-c-configuration-reference.md)
- [功能状态](appendix-f-feature-status.md)
