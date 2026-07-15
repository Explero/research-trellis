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

`codex.dispatch_mode: inline`（Codex 主会话路由）是显式兼容模式，只改变工作流提示路由，不会绕过已启用的 `PreToolUse`（工具使用前）门禁。门禁活跃时不要使用它要求主会话直接写入。

v0.7 的 closure 任务优先注入 Task Capsule（紧凑任务上下文），不默认注入完整 PRD、历史报告、事件和全部规范。Claude Code、Codex 和 OpenCode 使用相同字段与长度上限；Gemini、Qoder、CodeBuddy、Copilot 和 Factory Droid 通过共享每轮 hook 获得相同 Python 实现；Cursor 只在会话开始获得 capsule。Kiro、Kilo、Antigravity、Windsurf 和没有触发主会话 hook 的环境需要显式运行 `closure.py capsule`（生成紧凑上下文）。

6. 逐平台能力和限制如下。“子代理”表示仓库会安装对应代理模板；“门禁”专指 `hermes-runtime-guard.py`（Hermes 运行时门禁），不包括只做上下文注入的同名钩子事件。

| 平台 | 主会话上下文 | 子代理与上下文 | `PreToolUse / Stop`（门禁） | 启用条件与限制 |
| --- | --- | --- | --- | --- |
| `Claude Code`（Claude 代码工具） | `SessionStart + UserPromptSubmit`（会话开始和用户提交） | 支持；`Task / Agent`（代理工具）前推送任务上下文 | 两者都有 | 需平台读取项目 `settings.json`（设置）；环境开关可关闭 |
| `Cursor`（Cursor 编辑器） | `sessionStart`（会话开始）注入 capsule 和命令行上下文 | 支持；`Task / Subagent`（子代理工具）前推送 | 无 | 没有每轮 capsule；只有平台实际触发 `.cursor/hooks.json`（Cursor 钩子）时才注入 |
| `OpenCode`（开放代码工具） | `chat.message`（会话消息）注入会话摘要、每轮状态和 capsule | 支持；代理按派发首行自行读取 | 无 | 依赖 OpenCode 插件被实际加载；会话检索功能仍未实现 |
| `Codex`（代码代理） | `UserPromptSubmit`（用户提交），无会话开始注入 | 支持；代理前置说明按派发首行拉取 | 两者都有 | 需用户级开关、项目信任和 `/hooks`（钩子审阅）；默认子代理 |
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
- 版本：`0.7.0-beta.0`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n -m 1 "dispatch_mode|agentCapable|hasHooks" packages/cli/src packages/cli/test`（平台能力核对）。
- 结果：14 个平台的上下文注入、子代理、门禁和启用条件已与注册表及钩子配置对齐。
- 未验证项：本轮未启动 14 种平台主机，也未访问远程工作流市场。

## 来源

[S3、S4、S5、S9、S12](sources.md)

## 相关页面

- [项目初始化](05-project-setup.md)
- [配置参考](appendix-c-configuration-reference.md)
- [功能状态](appendix-f-feature-status.md)
