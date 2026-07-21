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

1. 每次派发先创建 dispatch（派发）。命令会绑定当前 `hermes_revision`（Hermes 修订号），并同时写入兼容的 `task_card`（任务卡）。`coder`（编码代理）和 `runner`（运行代理）必须绑定当前工作包；任务级 `planner`（规划代理）和 `reviewer`（复核代理）可不绑定。

```bash
JOB="job-$(date -u +%Y%m%d-%H%M%S)-coder"
python3 ./.trellis/scripts/hermes/dispatch.py create --task "$TASK" \
  --job-id "$JOB" --role coder --profile implementation \
  --work-package WP1 --objective "完成当前工作包" \
  --ref prd.md --allowed-file 'src/**' --allowed-file 'test/**'
python3 ./.trellis/scripts/hermes/dispatch.py validate --task "$TASK" --job-id "$JOB"
```

2. 派发正文最多 2000 字符、直接引用最多 3 个。绝对用户路径、敏感信息、越界或不存在的引用会被拒绝。任务状态变化后，旧派发会返回 `stale_dispatch`（过期派发）。

3. `Claude Code`（Claude 代码工具）的 `Agent`（代理）调用只传 `job_id`（工作编号），钩子会机械替换长提示，并禁止异步派发。`Codex`（代码代理平台）的 native（原生）代理仅为 advisory（建议性）；需要硬门禁时运行：

```bash
python3 ./.trellis/scripts/hermes/dispatch.py run --task "$TASK" \
  --job-id "$JOB" --platform codex --mode strict
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

6. 当前工作代理校验还会检查：

- 同一工作树不能同时存在多个未结束的 `coder`（编码代理）或 `runner`（运行代理）；
- 结果中的改动文件必须落在任务卡允许范围内，且不能命中禁止范围；
- 配置了心跳间隔的结果需要已有检查点；
- `runner`（运行代理）成功只接受已有 `run_refs`（运行引用），不能把成功输出写成证据；
- `reviewer:evidence/claim`（证据或主张复核）只能提出判断，不能批准事实或人工记录；
- 经 `Dispatch Packet`（派发包）确认的编码结果进入 `review`（复核）或 `claim_ready`（待审批）前，需要 `runner:test/build/validation`（运行代理的测试、构建或验证模式）结果，以及 `reviewer:quality/safety`（复核代理的质量或安全模式）记录。证据、主张或关闭复核不能替代代码质量复核。这个派发结果门禁不替代 `package-check`（工作包复核）或 `close`（关闭）的各自收口审计；未经过正式派发的旧任务继续按兼容流程处理。

7. 在支持并启用 `Hermes`（科研工作流）运行时钩子的平台中，`PreToolUse`（工具使用前）门禁会限制主代理直接写入和执行，并按任务卡检查工作代理目标文件；`Stop`（结束）门禁读取记录、运行清单和当前文件差异，不会在结束时重新运行测试。当前内置完整运行时门禁只在 `Claude Code`（Claude 代码工具）和已启用钩子的 `Codex`（代码代理）配置中注册。

当前 `Stop`（结束）完成检查偏向代码任务：它要求编码结果覆盖当前非 `.trellis/`（工作流目录）差异，并有相关的成功运行清单和质量复核记录。纯研究任务也可能触发这个要求，这是测试版的已知限制。

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
- 子代理读取内容过多：确认 Claude 只传 `job_id`（工作编号），或 Codex 使用 strict（严格）包装器；引用不能超过 3 个。
- 门禁与任务类型不匹配：保留失败记录并由人工决定调整流程，不要把门禁当作安全认证。

## 验证记录

- 日期：2026-07-16。
- 版本：`0.7.1`（测试版）。
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
