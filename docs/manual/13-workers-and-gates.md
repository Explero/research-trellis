# 13 工作代理与门禁

## 目标

用五个固定角色和轻量模式划定工作边界，减少重复模板和派发上下文，同时保留独立复核、心跳恢复和结束门禁。

## 适用范围

适用于有写文件、运行测试、独立复核或长时间执行的任务。门禁能减少流程跳步，但不是恶意代码防护。

## 前置条件

- 已有活动任务和有效实验配置。
- 已为每个工作代理准备唯一 validated dispatch（已验证派发）。
- 所选平台已正确安装并启用对应钩子。

## 操作步骤

### 科研协作触发

主代理以事实和证据为先，不以同意用户为目标；应明确重要假设、不确定性和有依据的异议，科研取舍仍由用户批准。普通可逆任务直接执行，有限不确定性声明假设后执行，只有高风险研究变化才暂停讨论。证据冲突或关键假设失效时进入 `blocked`（阻塞），通过人工批准的 `amend`（修改）更新协议后继续。

高风险 exploration（探索）完成 `grill-me`（方案讨论）后，必须用 `decision_ref`（决策记录引用）指向已有 `prd.md`（需求文档）或 `design.md`（设计文档）。记录包含决定、理由、证据、备选方案和失效条件，派发事件与 Task Capsule（任务胶囊）只传引用。提示词不能替代该记录；旧完成标记没有引用时仅警告，普通任务不新增讨论门禁。

只有 exploration 且研究变化包含 `dataset`（数据集）、`split`（数据切分）或 `preprocessing`（预处理）时，运行代理才检查任务级 `data_preflight`（数据预检）。其他任务的角色派发、运行和复核步骤保持不变。

### 五个角色

`Role`（角色）决定权限、工具和责任边界。`Profile`（模式）决定这个角色本次具体做什么。模式不是新的子代理，也没有单独的平台代理模板。

| 角色 | 主要职责 | 默认模式 | 不能代替的工作 |
| --- | --- | --- | --- |
| `planner`（规划代理） | 研究设计、任务规划、根因分析、方法选择 | `task_planning`（任务规划） | 不改代码、不批准高风险科研变更、不关闭任务 |
| `researcher`（检索代理） | 文献、代码库、官方文档和已有方案检索 | `codebase`（代码库检索） | 不改代码、结果、主张或关闭状态 |
| `coder`（编码代理） | 代码、测试、配置和限定修复 | `implementation`（实现） | 不判断证据可信、不批准主张、不关闭任务 |
| `runner`（运行代理） | 实验、测试、构建和验证 | `validation`（验证） | 原则上不改核心代码，不把运行成功当作批准 |
| `reviewer`（复核代理） | 质量、证据、主张、安全、关闭和统计复核 | `quality`（质量复核） | 不改源代码、原始结果、指标值或人工批准记录 |

支持的模式如下：

- `planner`（规划代理）：`research_design`（研究设计）、`task_planning`（任务规划）、`root_cause`（根因分析）、`method_selection`（方法选择）。
- `researcher`（检索代理）：`literature`（文献）、`codebase`（代码库）、`external_docs`（外部官方文档）、`prior_art`（已有方案）。
- `coder`（编码代理）：`implementation`（实现）、`tests`（测试）、`configuration`（配置）、`repair`（修复）。
- `runner`（运行代理）：`experiment`（实验）、`test`（测试）、`build`（构建）、`validation`（验证）。
- `reviewer`（复核代理）：`quality`（质量）、`evidence`（证据）、`claim`（主张）、`safety`（安全）、`closure`（关闭）、`statistics`（统计）。

### 科研技能路由

技能由主代理按实际需要触发，不设每轮固定数量，也不要求组成完整流水线。多个技能确有依赖时按顺序使用，前一步结果通过文件引用复用。

| 场景 | 主代理动作 | 执行角色 |
| --- | --- | --- |
| 新任务 | 分析意图、范围、完成定义、科研分流和 1–4 个结果型工作包 | 复杂设计可由 `planner`（规划代理）提供候选 |
| 需求不清楚 | 按需触发 `brainstorm`（问题梳理） | 主代理与用户讨论，`researcher`（检索代理）补资料 |
| 关键科研决策 | 按需触发 `grill-me`（方案讨论） | 主代理与用户讨论，`planner` 比较方案但不批准 |
| 代码工作包 | 触发 `before-dev`（开发前准备），任务明确选择时才使用 TDD | `coder`（编码代理）实现，`runner`（运行代理）执行测试 |
| 工程验收 | 触发代码检查 | `runner` 执行，`reviewer:quality`（质量复核）独立判断 |
| 正式实验 | 触发 `hermes-research`（科研记录） | `runner` 登记运行，证据或统计由对应 `reviewer` 复核 |
| 重复技术失败 | 触发 `break-loop`（失败归因） | `planner:root_cause`（根因分析）判断，`coder` 执行限定修复 |
| 交接或收尾 | 请求交接、关闭审查和最终验证 | `coder:configuration` 写交接，`reviewer:closure` 审计，`runner` 验证和归档 |
| 稳定知识 | 关闭前评估一次 `update-spec`（更新规范） | `coder:configuration` 写入，`reviewer` 核对证据 |

纯实验、文献和证据任务不触发代码技能。代码测试通过不等于科研证据充分；正常的负实验结果也不进入技术调试循环。

三个最小示例：

```yaml
role: planner
profile: research_design
```

```yaml
role: researcher
profile: literature
```

```yaml
role: reviewer
profile: evidence
```

### 派发与结果防火墙

1. 每次派发先创建 dispatch（派发）。命令会绑定当前 `hermes_revision`（Hermes 修订号），并同时写入兼容的 `task_card`（任务卡）。`coder`（编码代理）和 `runner`（运行代理）必须绑定当前工作包。测试、构建或代码验证 runner 必须用 `parent_job_id`（父工作编号）绑定被检查的 coder；独立实验 runner 可以不绑定。`reviewer:quality/evidence/claim/statistics`（质量、证据、主张或统计复核）也必须绑定被审查的具体工作；`reviewer:closure/safety`（关闭或独立安全复核）可以保持任务级。

```bash
JOB="job-$(date -u +%Y%m%d-%H%M%S)-coder"
python3 ./.trellis/scripts/hermes/dispatch.py create --task "$TASK" \
  --job-id "$JOB" --role coder --profile implementation \
  --work-package WP1 --objective "完成当前工作包" \
  --ref prd.md --allowed-file 'src/**' --allowed-file 'test/**'
python3 ./.trellis/scripts/hermes/dispatch.py validate --task "$TASK" --job-id "$JOB"
```

2. 派发正文最多 2000 字符、直接引用最多 3 个。绝对用户路径、敏感信息、越界或不存在的引用会被拒绝。任务状态变化后，旧派发会返回 `stale_dispatch`（过期派发）。

3. `Claude Code`（Claude 代码工具）的 `Agent`（代理）调用只传 `job_id`（工作编号），钩子会机械替换长提示，并禁止异步派发。`Codex`（代码代理平台）的派发输入依赖同一协议和结构化文件，属于 advisory（建议性）约束；下面的命令只显示经过校验的紧凑派发，不会创建沙箱或升级成严格执行器：

```bash
python3 ./.trellis/scripts/hermes/dispatch.py run --task "$TASK" \
  --job-id "$JOB" --platform codex
```

4. 返回必须是单个 `Result Envelope`（结果信封）JSON，包含 `uncertainties`（不确定项），其中 `conclusion`（结论）最多 1200 字符。非法 JSON、长日志、完整差异、搜索过程、敏感信息和越界改动会被拒绝；raw trace（原始跟踪）只保存在 `.trellis/.runtime/hermes-traces/`（本地运行目录）。

```bash
python3 ./.trellis/scripts/hermes/dispatch.py apply --task "$TASK" --job-id "$JOB" --result result.json
python3 ./.trellis/scripts/hermes/validate.py --task "$TASK" --kind worker
python3 ./.trellis/scripts/hermes/guard.py --task "$TASK" --job-id "$JOB" --changed-files results/metrics.json
```

5. 长任务应写心跳；超时后检查并恢复：

```bash
python3 ./.trellis/scripts/hermes/heartbeat.py beat --task "$TASK" --job-id "$JOB" --checkpoint running-eval --summary "正在评估固定切分"
python3 ./.trellis/scripts/hermes/jobs.py check --task "$TASK"
python3 ./.trellis/scripts/hermes/jobs.py resume --task "$TASK" --job-id "$JOB"
```

测试、构建、实验和验证命令由 `runner`（运行代理）通过 `runner.py run`（登记运行）执行。直接运行 `pnpm test`（运行测试）等命令不会经过运行清单，因此在正式角色门禁下会被拒绝。

6. 当前工作代理校验还会检查：

- 同一工作树不能同时存在多个未结束的 `coder`（编码代理）或 `runner`（运行代理）；
- 结果中的改动文件必须落在任务卡允许范围内，且不能命中禁止范围；
- `coder`（编码代理）可以按任务卡修改实现文件；规划、检索和复核角色只能写当前任务下各自的分析、研究或审查记录目录；`runner`（运行代理）不能通过编辑工具修改文件；
- 配置了心跳间隔的结果需要已有检查点；
- `runner`（运行代理）成功只接受已有 `run_refs`（运行引用），不能把成功输出写成证据；
- `reviewer:evidence/claim`（证据或主张复核）只能提出判断，不能批准事实或人工记录；需要独立复核的记录必须显式绑定被审工作，旧记录只在同一工作包只有一个候选时兼容；
- 经 `Dispatch Packet`（派发包）确认的编码结果进入 `review`（复核）或 `claim_ready`（待审批）前，需要 `runner:test/build/validation`（运行代理的测试、构建或验证模式）结果，以及 `reviewer:quality/safety`（复核代理的质量或安全模式）记录。证据、主张或关闭复核不能替代代码质量复核。这个派发结果门禁不替代 `package-check`（工作包复核）或 `close`（关闭）的各自收口审计；未经过正式派发的旧任务继续按兼容流程处理。

7. 在支持并启用 `Hermes`（科研工作流）运行时钩子的平台中，`PreToolUse`（工具使用前）门禁会限制主代理直接写入和执行，并按任务卡检查工作代理目标文件；`Stop`（结束）门禁读取记录、运行清单和当前文件差异，不会在结束时重新运行测试。Claude 可额外替换 Agent 派发输入并净化返回；Codex 当前只对写入、受控命令和结束条件做机械检查，不能声明为完整输入隔离。两者都不是操作系统沙箱。

`Stop`（结束）按实际工作类型检查：存在实现代码改动时要求编码结果、成功运行清单和独立质量复核；没有代码改动的实验、检索或规划工作要求对应角色结果和独立复核，正式运行还必须引用成功的运行清单。它不会为了纯研究任务强制创建编码结果。

### 证据整理工具

`evidence-curator`（证据整理代理）不再是可派发角色。机械工作由确定性命令完成：

```bash
python3 ./.trellis/scripts/hermes/evidence.py collect --task "$TASK"
python3 ./.trellis/scripts/hermes/evidence.py validate --task "$TASK"
python3 ./.trellis/scripts/hermes/evidence.py summary --task "$TASK"
```

这些命令检查产物路径、`SHA-256`（哈希值）、运行清单关联、悬空引用、重复引用和缺失字段，并生成稳定的 `evidence_summary.json`（证据摘要）。它们不判断证据是否足以支持完成条件或主张；这部分由 `reviewer:evidence`（证据复核模式）完成。

### 旧角色迁移

旧任务卡仍可读取，校验时会给出一次弃用提示；新写入会保存正式角色和模式。

| 旧名称 | 新写法 |
| --- | --- |
| `scientist`（科学家） | `planner:research_design`（规划代理的研究设计模式） |
| `builder`（构建代理） | `coder:implementation`（编码代理的实现模式） |
| `literature`（文献代理） | `researcher:literature`（检索代理的文献模式） |
| `evaluator`（评估代理） | `reviewer:evidence`（复核代理的证据模式） |
| `claim-reviewer`（主张审查代理） | `reviewer:claim`（复核代理的主张模式） |
| `research/scout`（检索侦察代理） | 根据目标转为检索代理的文献、代码库或外部文档模式 |
| `analyst`（分析代理） | 根据目标转为规划代理的根因/方法模式，或复核代理的质量/证据/统计模式 |

无法判断旧 `analyst`（分析代理）目标时，使用 `planner:root_cause`（规划代理的根因模式）并提示显式选择。旧 `evidence-curator`（证据整理代理）记录可以继续校验，但不能创建新的同名任务卡。

## 预期结果

每个修改和运行都能追溯到正式角色、模式和任务卡；子代理默认只接收当前任务所需的最小上下文；长任务可以从检查点恢复；缺少运行或独立复核记录时，完成门禁按预期阻止结束。

## 失败恢复

- 多个活动写入者：先为旧工作追加结果、拒绝或停滞记录，或使用不同工作树。
- 改动超出范围：拒绝当前结果，扩大范围必须由协调者重新签发任务卡。
- 心跳超时：运行 `jobs.py check`（检查工作），从最新检查点创建替代工作，不要静默等待。
- 钩子未触发：检查平台配置；环境变量 `TRELLIS_HOOKS=0`（关闭钩子）或 `TRELLIS_DISABLE_HOOKS=1`（禁用钩子）会直接关闭门禁。
- 角色或模式组合无效：只使用本页五个正式角色及其模式，不要把模式写成新角色。
- 旧角色出现弃用提示：按迁移表更新派发配置；历史 `JSONL`（逐行 JSON）记录不需要重写。
- 子代理读取内容过多：确认 Claude 只传 `job_id`（工作编号），Codex 使用紧凑派发；引用不能超过 3 个。
- 门禁与任务类型不匹配：保留失败记录并由人工决定调整流程，不要把门禁当作安全认证。

## 验证记录

- 日期：2026-07-16。
- 版本：`0.7.1-beta.0`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n -m 1 "PreToolUse|Stop" packages/cli/src/templates/{claude,codex,shared-hooks} packages/cli/test`（钩子与门禁核对）。
- 结果：五个正式角色、模式校验、旧角色迁移、两平台模板、最小上下文、证据工具和模式感知门禁均有自动化覆盖。
- 未验证项：平台主机是否实际触发钩子仍取决于安装版本和用户配置。

## 来源

[S7、S8、S9、S12](sources.md)

## 相关页面

- [Hermes 记录](08-hermes-records.md)
- [运行与复查](10-runs-and-replay.md)
- [记录格式](appendix-d-record-schema.md)
