# Research Trellis

面向科研项目的 `Trellis`（原版 Trellis）实验性改造分支。

[![CI](https://github.com/Explero/research-trellis/actions/workflows/ci.yml/badge.svg)](https://github.com/Explero/research-trellis/actions/workflows/ci.yml)
[![License: AGPL-3.0-or-later](https://img.shields.io/badge/license-AGPL--3.0--or--later-16a34a.svg?style=flat-square)](LICENSE)

这个仓库是在原版 `Trellis`（原版项目）基础上改造出来的科研实验分支，不是上游官方版本，也不代表上游项目立场。它更接近一个科研项目里的工作流工具实验：在原版 Trellis 的任务、规范、平台接入基础上，加入更强的 `Hermes`（科研工作流）记录、门禁和子代理协作约束。

当前状态：可以放进低风险真实科研项目里试部署；不建议直接用于不可回滚的关键项目。

从 `0.6.0-beta.31`（测试版）开始，项目使用 `research-trellis`（CLI 包）和 `research-trellis-core`（核心包），与上游原版名称明确区分。旧包 `trellis-hermes` 和 `trellis-hermes-core` 停留在 `0.6.0-beta.30`（旧测试版），仅用于已有安装迁移。

## 上游来源与修改声明

本项目基于 `mindfold-ai/Trellis`（上游 Trellis 项目）继续修改，原项目地址为 `https://github.com/mindfold-ai/Trellis`（上游仓库）。

为了避免混淆，这里先说明几个边界：

- `Research Trellis`（科研改造版）不是上游 `Trellis`（原版项目）的官方发布版本；
- 仓库中的原始 Trellis 代码、模板、文档结构和许可证声明应继续归属于其原始作者和贡献者；
- 本仓库新增和改动的部分主要围绕 `Hermes`（科研工作流）、记录门禁、子代理治理、科研计划变更记录和发布前预检；
- 如果后续公开发布到 `npm`（包平台）或 `GitHub`（代码托管平台），应继续保留上游来源、许可证和修改说明。

## 这是什么

`Research Trellis`（科研改造版）是一个本地开发工具，用来把 AI 协作开发过程里的关键动作落到仓库文件中：

- 需求、设计、实现计划和检查记录放进 `.trellis/tasks/`；
- 项目规范和工作流规则放进 `.trellis/spec/` 与 `.trellis/workflow.md`；
- 子代理执行记录、实验配置、指标结构和报告模板放进 `.trellis/hermes/` 相关目录；
- 关键门禁采用“缺记录就失败”的方式，减少 AI 在流程里跳步。

它的目标不是让 AI 更快地直接写代码，而是让科研项目里的 AI 协作更可追踪、可复盘、可审查。

## 当前验证状态

远程 `CI`（持续集成）已经配置在 GitHub Actions 中。每次推送到 `main`（主分支）或提交 `pull request`（合并请求）时，会运行：

```bash
pnpm install --frozen-lockfile
pnpm lint
pnpm test
pnpm build
pnpm --filter research-trellis hermes:preflight
```

这些检查覆盖：

- TypeScript 代码规范；
- 核心包与 CLI 的自动化测试；
- 构建产物生成；
- Hermes 模板、Python 文件、门禁配置和预检逻辑。

你可以在 GitHub 的 `Actions`（自动化运行）页面里查看最新结果。绿色通过只说明当前仓库在干净环境里能安装、测试、构建和通过 Hermes 预检；它不等于已经完成公开发布级验证。

## CD 发布准备

仓库已经准备了 `.github/workflows/publish.yml`（发布流程）。这个流程不会在普通 `push`（推送）时发布，只会在 GitHub 上发布 `Release`（发布版本）时触发。

发布流程会重新运行：

```bash
pnpm lint
pnpm test
pnpm build
pnpm --filter research-trellis hermes:preflight
node packages/cli/scripts/release-preflight.js check-versions --require-tag
node packages/cli/scripts/release-preflight.js verify-packed-cli
```

检查通过后，它会先发布 `research-trellis-core`（核心包），再发布 `research-trellis`（CLI 包），最后从 npm registry 验证两个包是否可见。

发布前还需要在 `npm`（包平台）侧完成：

- 创建或认领 `research-trellis-core` 与 `research-trellis` 两个包；
- 给两个包配置 `trusted publishing`（可信发布）；
- `Owner`（所有者）填写 `Explero`，`Repository`（仓库）填写 `research-trellis`；
- `Workflow filename`（流程文件名）填写 `publish.yml`；
- `Environment`（环境）填写 `npm-production`。

这个仓库不会保存 `NPM_TOKEN`（npm 令牌）。发布依赖 GitHub Actions 的 `id-token: write`（OIDC 身份令牌权限）和 npm 的 `trusted publishing`（可信发布）配置。

## 适合先放到什么项目里试

建议先选择一个低风险真实项目：

- 有真实科研流程，不是空目录；
- 即使工具生成内容不理想，也能通过 git 回滚；
- 不包含必须保密的凭据、数据或不可提交文件；
- 当前任务规模适中，适合观察完整流程。

不建议一开始就放进最重要的主项目，尤其不要在没有备份的情况下直接覆盖现有 `.trellis/`、`.claude/`、`.codex/` 或 `AGENTS.md`。

## 从源码试用

新包发布后，可固定安装本次测试版：

```bash
npm install -g research-trellis@0.7.1-beta.0
research-trellis --version
```

原有 `trellis` 与 `tl` 命令继续可用，便于已有脚本迁移；新文档统一使用 `research-trellis` 作为主命令。

已经安装旧包时，发布后按下面的方式迁移：

```bash
npm uninstall -g trellis-hermes
npm install -g research-trellis@0.7.1-beta.0
research-trellis --version
```

需要修改或审阅实现时，再从 GitHub 源码运行：

```bash
git clone git@github.com:Explero/research-trellis.git
cd research-trellis
corepack enable
pnpm install --frozen-lockfile
pnpm build
```

然后进入要试部署的科研项目：

```bash
cd /path/to/your/research-project
git status
git add .
git commit -m "chore: checkpoint before Research Trellis trial"
node /path/to/research-trellis/packages/cli/bin/trellis.js init -u your-name --claude
```

如果项目里已经有 Trellis，可以先用 `update`（更新）而不是重新初始化：

```bash
node /path/to/research-trellis/packages/cli/bin/trellis.js update
```

执行前请先看清楚提示，涉及覆盖文件时不要盲目确认。

## 建议的真实项目试跑方式

第一次试跑不要追求复杂任务，先验证一条短链路：

```text
准备一个干净 git checkpoint
→ 初始化或更新 Research Trellis
→ 用自然语言提出一个小任务
→ 让 AI 创建任务并补齐 planning
→ 用 closure plan/validate 生成 1–4 个结果型工作包
→ 检查 .trellis/tasks/ 下的 prd/design/implement 产物
→ 派发一个低风险实现或检查子任务
→ 查看 Hermes worker records、报告和门禁结果
→ 运行项目自己的测试
→ 执行 closure audit/close，确认不能提前结束
→ 决定保留、回滚或继续调整
```

这一步主要验证三件事：

1. 它能不能适配你的项目结构；
2. 它生成的任务文档是否方便你审阅；
3. Hermes 门禁是否真的能阻止“没有记录就继续”的情况。

## Hermes 改造重点

### 1. 子代理记录必须可追踪

科研项目里最麻烦的不是 AI 没做事，而是做了什么说不清。这个分支要求关键子代理动作写入记录文件，后续检查会读取这些记录。

如果记录缺失、为空或格式不对，相关门禁会失败，而不是默认放行。

### 2. 三道闸门形成闭环

`PreToolUse`（工具使用前）负责拦写入权限和危险动作；`RecordBus`（记录总线）负责保存每个 `agent`（代理）的 `JSONL`（逐行 JSON）记录；`Stop`（结束前）只读取 `RecordBus`（记录总线）、`git diff`（Git 差异）和测试运行记录做最终判定。

也就是说：没有完成的 `coder`（编码代理）记录、没有 `passing`（通过）的 `runner`（运行代理）测试记录、没有 `reviewer`（审核代理）记录，任务就不能被判定为完成。

### 3. 任务计划先落盘

任务不再只是聊天里的临时约定。`prd.md`、`design.md`、`implement.md`、`implement.jsonl` 和 `check.jsonl` 用来保存需求、设计、实现策略和子代理上下文。

这样做的代价是流程会慢一点；收益是后面可以 review、复盘和修正。

### 4. 共享 worktree 策略更严格

对于需要子代理实现的任务，科研版更强调使用明确的共享工作目录，避免多个代理在不同目录里重复实现同一个任务。

如果配置指向普通目录、无关仓库或不可识别的 worktree，流程会拒绝继续。

### 5. Lean Research Closure 防止提前结束

新任务默认使用一个 Trellis task，并在内部安排 1–4 个结果型工作包。`task.json` 保存当前状态，`hermes/task-events.jsonl` 追加重要变化；每轮 hook 优先注入紧凑 Task Capsule，减少完整 PRD、历史报告和全部规范的重复加载。

只有 `closure.py audit`（收口审计）通过后，`closure.py close`（关闭任务）才会写入 `completed`（已完成）。`lean`（轻量）、`standard`（标准）和 `publication`（发表）按需增加证据门禁；有限 repair（修复）不会扩大任务范围或改写已完成工作包。

详见[中文手册：Lean Research Closure](docs/manual/17-lean-research-closure.md)。

### 6. 五角色与轻量模式

五个正式 `Hermes`（科研工作流）角色现在是 `planner`（规划代理）、`researcher`（检索代理）、`coder`（编码代理）、`runner`（运行代理）和 `reviewer`（复核代理）。角色决定权限，`Profile`（模式）决定本次关注点；正式模板目前只提供给 `Claude Code`（Claude 代码工具）和 `Codex`（代码代理平台）。

### 7. Agent Context Firewall

每次正式角色派发先生成绑定 `hermes_revision`（Hermes 修订号）的结构化文件，正文最多 2000 字符、引用最多 3 个。`Claude Code`（Claude 代码工具）钩子只接收 `job_id`（工作编号）并替换长提示；`Codex`（代码代理平台）使用同一份紧凑派发和结果契约，在当前项目工作区协作。

返回必须包含 `uncertainties`（不确定项），长日志、完整差异和搜索过程不会进入主上下文。原始跟踪保存在 `.trellis/.runtime/`（本地运行目录），成功或失败都会机械更新下一动作，但不会仅凭聊天关闭任务。

### 8. 预检不是形式检查

`hermes:preflight`（Hermes 预检）会检查模板文件、Python 编译、Hermes hook、门禁文档、沙箱配置、模板测试、类型检查和构建。

它不能证明项目已经适合生产环境，但可以挡住一批明显会在使用阶段爆出来的问题。

## 与原版 Trellis 的关系

这个项目基于原版 `Trellis`（原版 AI coding 工作流工具）继续改造，仍然保留：

- `research-trellis init` / `research-trellis update`；
- `.trellis/spec/` 项目规范；
- `.trellis/tasks/` 任务系统；
- 多平台接入模板；
- CLI 构建与测试体系。

科研版新增或强化的部分主要在：

- Hermes 实验记录；
- 子代理记录门禁；
- planning 产物约束；
- Lean Research Closure、Task Capsule 和有限修复；
- 共享 worktree 检查；
- 发布前预检。

后续若再次改名或发布新版本，需同步核对包名、仓库链接、许可证说明、上游致谢、发布脚本和安装文档。

## 目录速览

```text
.
├── .github/workflows/ci.yml          # GitHub Actions 远程检测
├── packages/core/                    # 核心领域逻辑
├── packages/cli/                     # trellis CLI 和模板
├── packages/cli/src/templates/       # 初始化到用户项目里的模板
├── packages/cli/src/templates/trellis/hermes/
│   ├── config.yaml                   # Hermes 配置
│   ├── state_machine.yaml            # Hermes 状态机
│   ├── records/                      # 子代理记录协议
│   ├── roles/                        # 科研角色提示词
│   ├── metrics/                      # 指标结构
│   └── reports/                      # 报告模板
└── package.json                      # workspace 脚本
```

真实项目初始化后，重点看目标项目里的：

```text
.trellis/
├── spec/
├── tasks/
├── workflow.md
└── hermes/
```

## 本地开发检查

修改这个仓库后，至少运行：

```bash
pnpm lint
pnpm test
pnpm build
pnpm --filter research-trellis hermes:preflight
```

如果改动涉及 Hermes 模板、hook 或任务流，优先补充对应测试，再看 GitHub Actions 结果。

## 重要边界

- 这不是操作系统级沙箱，不能防止恶意命令执行。
- Hermes 的 JSONL 记录不是防篡改存储。
- `allowed_commands`（允许命令）只能作为流程门禁的一部分，不应理解成强安全边界。
- 不要把 API Key、密码、令牌、私有数据或 `.env` 文件提交进仓库。
- 真实科研项目试部署前，先做 git checkpoint。

## License

本项目沿用上游项目授予的 `AGPL-3.0-or-later`（AGPL 第 3 版或任何后续版本）许可，不缩减 `COPYRIGHT`（版权声明）原文授予的权利。

本仓库是基于 `mindfold-ai/Trellis`（上游 Trellis 项目）的修改版本。公开发布或分发时，应保留上游许可证、上游来源和本仓库的修改说明；当前仓库名称、包名和 `Hermes`（科研工作流）相关改造不表示上游官方认可或背书。
