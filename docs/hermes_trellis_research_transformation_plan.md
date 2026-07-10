# Hermes on Trellis 科研化改造总计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`（子代理驱动开发） or `superpowers:executing-plans`（执行计划） to implement this plan task-by-task. Steps should be tracked with checkbox syntax in later implementation issues.

**Goal:** 把 Trellis 从任务协作脚手架，改造成可审计、可复现、可评估的科研实验框架。

**Architecture:** Trellis 继续负责任务目录、模板、平台注入和工作流；Hermes 作为 `overlay`（叠加层）负责权限、记录、证据、状态机、人类确认和多代理治理。核心原则是：`chat`（聊天）不是事实源，`record`（记录）才是事实源。

**Tech Stack:** Python runtime scripts, Trellis templates, JSONL records, YAML config, platform hooks, Codex/Claude skills and subagents.

---

## 1. 当前基线

这版已经形成 `Hermes Runtime MVP`（Hermes 运行时最小版本），基础能力包括：

- `RecordBus`（记录总线）：通过 `worker_records.jsonl` 保存 `task_card`（任务卡）、`heartbeat`（心跳）、`checkpoint`（检查点）、`result`（结果）、`risk`（风险）、`rejection`（拒绝）。
- 运行时脚本：已有 append、validate、guard、jobs、heartbeat 等脚本骨架。
- 科研记录：已有 `evidence_ledger.jsonl`（证据账本）、`claim_ledger.jsonl`（结论账本）、`approval_records.jsonl`（批准记录）、`state_transition_log.jsonl`（状态迁移记录）的模板约定。
- 状态机：当前流程是 `planning -> running -> review -> claim_ready -> approved`。
- 多代理治理：已明确 `main agent`（主代理）是监督者和状态裁决者，`subagent`（子代理）是受限、可中断、可复核的工作单元。

已有验证记录显示：模板测试、定点初始化/更新测试、Python compile、`typecheck`（类型检查）、`build`（构建）已经跑通过过。后续每一阶段仍要重新跑对应验证，不能沿用旧结论。

## 2. 设计原则

### 2.1 主代理职责

`main agent`（主代理）主要做：

- 明确目标、任务边界和验收标准。
- 派发带权限边界的 `task_card`（任务卡）。
- 读取结构化记录、证据索引、风险标记和决策请求。
- 在等待子代理时做监督工作：检查前置证据、整理验收清单、准备失败预案、更新状态板。
- 判断是否能进入下一状态；遇到 `HumanGate`（人类闸门）时停下来请求人类确认。

主代理不应该长期持有原始日志、长 `diff`（差异）和子代理探索过程，也不应该把聊天当作事实来源。

### 2.2 子代理职责

`subagent`（子代理）主要做：

- 在任务卡限定范围内执行代码、实验、搜索、评估或复核。
- 通过 `JSONL`（逐行 JSON）记录留下心跳、检查点、结果、风险和失败原因。
- 只读取必要上下文，不默认继承主代理完整对话。
- 不自我扩权；需要扩大范围时写风险或请求新任务卡。

### 2.3 外部调研给出的约束

外部实践对这套设计有几条一致提醒：

- Claude Code 文档强调子代理有自己的 `context window`（上下文窗口），完成后只返回摘要；这支持最小上下文和隔离执行。
- OpenAI Codex 文档把子代理用于并行审查、探索和验证，也强调主代理需要汇总结果，而不是让子代理自由改全局状态。
- Addy Osmani 关于 `maker/checker`（写作者/审查者）分离的观点，支持 coder、runner、reviewer、evaluator 分工。
- Simon Willison 对并行 coding agent 的判断提醒：瓶颈常在 review，不在启动更多 agent。
- Claude/OpenAI hooks 文档都说明 hook 能提供确定性的生命周期控制，不能只依赖 prompt 自觉。
- 关于 `AGENTS.md`（代理上下文文件）和长上下文的研究提醒：上下文越长不等于越好，容易带来 `context bloat`（上下文膨胀）和成本上升。

所以 Hermes 的路线不是“更多 agent 更自由”，而是“每个 agent 更小、更窄、更可审计”。

## 3. 总体阶段

### P7-P11：deployment candidate hardening（部署候选加固）

当前 P7-P11 只做可验证薄切片：sandbox 配置 fail-closed、provenance
ledger、local service queue、audit ledger、evaluation quality gate。这里不能
声称完整 `production ready`（生产就绪）或 OS 级生产平台。

边界约定：

- `not an OS sandbox`（不是操作系统级沙箱）。`container` 模式已有 `Docker`（容器运行时）薄切片，会通过 `docker run --rm`（一次性容器执行命令）挂载仓库并运行白名单命令；它仍不是生产级强隔离。`external` 模式当前只做可用性检查。
- `approval_records` 依赖 `external human/root approval`（外部人工/根权限批准）。
- `JSONL` 不是不可篡改存储，只是 append-only（追加写）约定。
- `allowed_commands` 不是 strong command sandbox（强命令沙箱）；允许 `python3` 时仍可执行任意 Python 行为。

### P0：收口 Runtime MVP 的重要尾项

目标：把已经实现的运行时最小版本从“能跑”推进到“可作为后续科研层的可信底座”。

要改的范围：

- `packages/cli/src/templates/trellis/scripts/hermes/`
- `packages/cli/src/templates/trellis/hermes/config.yaml`
- `packages/cli/src/templates/trellis/hermes/records/`
- 相关模板测试

交付物：

- `jobs check`（任务检查）拒绝重复 `task_card`（任务卡）。
- 坏的 `heartbeat.next_check_at`（下次检查时间）不能被静默跳过，应写出明确拒绝或校验失败。
- `approval`（批准）校验同时检查证据、`decision`（决定）和 `approver`（批准者）。
- `PreToolUse`（工具调用前）按本次 `tool_input`（工具输入）直接校验写入文件是否越权。
- `records/README.md` 与 `worker_records.jsonl` 主路径保持一致，不再混用旧的 `reviews/`、`subagent_records/` 口径。
- `config.yaml` 的 runtime commands 补齐 heartbeat 命令。

验收标准：

- 针对重复任务卡、坏心跳、越权写入、缺批准字段分别有失败用例。
- 模板测试、定点 init/update 测试、Python compile、`typecheck`（类型检查）、`build`（构建）重新通过。
- 文档中的命令能与实际脚本一一对应。

主要风险：

- 不同平台 hook 能力不同，不能假设所有平台都支持同等强度的拦截。
- 文件路径拦截必须直接读取工具输入，不能只在事后看 `git diff`（Git 差异）。

### P1：实验配置层

目标：让每次科研任务都有可复现的实验入口，而不是只靠自然语言说明。

要改的范围：

- `.trellis/tasks/<task>/prd.md`
- `.trellis/tasks/<task>/design.md`
- `.trellis/tasks/<task>/implement.md`
- 新增或模板化 `experiment.yaml`（实验配置）
- 新增或模板化 `run_manifest.jsonl`（运行清单）

交付物：

- `experiment.yaml` 记录问题、假设、数据、模型、指标、随机种子、环境、允许命令和产物目录。
- `run_manifest.jsonl` 记录每次运行的 command、cwd、env 摘要、输入、输出、退出码和时间。
- 任务初始化时能生成科研任务骨架。

验收标准：

- 没有 `experiment.yaml` 时，不能进入 `running`（运行中）。
- 每次实验运行至少有一条 `run_manifest`（运行清单）。
- 配置字段缺失时给出明确错误，而不是继续执行。

主要风险：

- 早期字段不要设计过重；先覆盖复现必需项，不把配置写成论文管理系统。

### P2：证据与指标层

目标：把“跑过实验”变成“证据可追踪、指标可复核、结论可约束”。

要改的范围：

- `evidence_ledger.jsonl`
- `claim_ledger.jsonl`
- `approval_records.jsonl`
- 新增或模板化 `metrics_schema.yaml`（指标模式）
- 新增或模板化 `artifact_ledger.jsonl`（产物账本）

交付物：

- 证据记录包含 source、summary、limits、artifact refs、command refs。
- 结论记录必须链接证据 id，不能只有自然语言判断。
- 指标定义记录 metric name、direction、unit、aggregation、split、baseline。
- 产物账本记录输出文件、hash、生成命令和对应运行 id。

验收标准：

- 没有证据 id 的 claim 只能是 draft，不能进入 `claim_ready`（结论待批准）。
- metric、split、baseline 的变更必须触发 `HumanGate`（人类闸门）。
- 产物文件缺失或 hash 不匹配时，证据校验失败。

主要风险：

- 证据层容易变成形式主义，所以每个字段都要服务于复现或审计。

### P3：实验执行与复现层

目标：让长任务、失败任务和中断任务能被系统管理，而不是让主代理被迫等待。

要改的范围：

- `heartbeat.py`
- `jobs.py`
- `validate.py`
- `guard.py`
- 新增或扩展 runner 命令

交付物：

- 自动心跳执行器：长任务期间定期写 `heartbeat`（心跳）。
- 超时检查器：发现缺失心跳或过期任务时写 `rejection`（拒绝）或 `stalled`（停滞）记录。
- 续跑机制：从最近 `checkpoint`（检查点）和 `resume_from`（续跑点）恢复。
- replay/validate 命令：按 manifest 复核某次运行是否可重放。

验收标准：

- 人为构造长任务时能看到连续心跳。
- 人为构造超时任务时能被 jobs check 拦截。
- 人为中断后能从最近 checkpoint 恢复，不需要回读长聊天。

主要风险：

- 自动执行器不能吞掉失败；失败要写记录并可定位原始日志。

### P4：评估与报告层

目标：把实验结果整理成可审查的科研报告，而不是只输出命令日志。

要改的范围：

- 新增 `report.md`（报告）
- 新增或模板化 `compare.jsonl`（对比记录）
- 新增 aggregate/compare/report 命令
- 扩展 reviewer/evaluator 角色模板

交付物：

- aggregate：聚合多个 run 的指标、方差、失败次数和异常。
- compare：比较 baseline 与新方法，记录是否达到预设阈值。
- report：生成包含问题、方法、数据、指标、结果、限制、风险、结论状态的报告。
- claim review：独立检查 claim 是否被 evidence 支撑。

验收标准：

- 报告中的每个核心结论都能回链到 claim 和 evidence。
- evaluator 不能修改源码、metric、split、baseline。
- reviewer 只读 diff、record、evidence 和任务说明，不继承 coder 长对话。

主要风险：

- 自动报告不能替代人类批准；它只能把证据整理到 `claim_ready`（结论待批准）。

### P5：多代理科研协作层

目标：把 coder、runner、evaluator、reviewer、literature 的协作固定成可复用模式。

要改的范围：

- `.trellis/hermes/roles/`
- bundled skills
- platform agents/subagents templates
- `worker_records.jsonl` 校验

交付物：

- 角色模板：scientist、coder、runner、evaluator、reviewer、literature。
- 默认 `maker/checker`（写作者/审查者）分离。
- 同一 worktree 默认只有一个 active writer。
- 子代理任务卡强制包含 allowed_files、forbidden_files、timeout_at、heartbeat_interval、record_uri。

验收标准：

- 没有 `task_card` 的子代理结果不被接受。
- coder 的输出必须经过 runner 和 reviewer 才能进入 review 状态。
- reviewer/evaluator 的记录不能替代 human approval。

主要风险：

- 子代理过多会把瓶颈转移到 review；默认先用少量角色跑通闭环。

## 4. 实施顺序

推荐顺序如下：

1. 先做 P0，确保运行时、文档和 hook 口径一致。
2. 再做 P1，把每个科研任务的配置入口固定下来。
3. 做 P2，让证据、指标、产物和结论能互相追踪。
4. 做 P3，处理长任务、心跳、超时、续跑和复现。
5. 做 P4，把结果转成可审查报告。
6. 最后做 P5，把多代理协作固化为模板和默认流程。

这套顺序的理由是：没有可信记录底座，就不应该急着做报告；没有实验配置，就很难谈复现；没有证据和指标约束，就不应该推进 claim。

## 5. 当前完成状态

当前 P0-P5 已按子代理分工完成实现、复审和本地主验证。后续如果继续扩展，应在这个基线上新增阶段，不再把 P1-P5 当作待办。

P0 已完成：

- [x] 修 `jobs check`（任务检查）对重复 `task_card`（任务卡）的拒绝逻辑。
- [x] 修 `heartbeat.next_check_at`（下次检查时间）坏格式的显式失败。
- [x] 补 `approval`（批准）对 evidence、decision、approver 的严格校验。
- [x] 补 `PreToolUse`（工具调用前）基于本次 tool input 的越权写入拦截。
- [x] 统一 records 文档，把旧的 `reviews/`、`subagent_records/` 口径收敛到 `worker_records.jsonl`。
- [x] 补齐 `config.yaml` runtime commands 中的 heartbeat 命令。
- [x] 跑完整验证。

P1 已完成：

- [x] 任务级 `experiment.yaml`（实验配置）和 `run_manifest.jsonl`（运行清单）固定为科研运行入口。
- [x] `experiment.py init` 能生成任务级实验骨架和运行清单文件。
- [x] `runner.py run` 在缺少任务级 `experiment.yaml` 或必填字段缺失时失败，不写伪成功运行记录。
- [x] 每次受控运行写入 `run_manifest.jsonl`。

P2 已完成：

- [x] `evidence_ledger.jsonl`、`claim_ledger.jsonl`、`approval_records.jsonl`、`artifact_ledger.jsonl` 和 `metrics_schema.yaml` 已纳入校验。
- [x] `claim_ready`（结论待批准）必须链接证据，不能只靠自然语言结论。
- [x] artifact（产物）校验会检查真实文件存在、hash 格式和 sha256 是否匹配。
- [x] metric、split、baseline 变更必须由 `approval_records.jsonl` 中 `human/root` 的 `approved` 记录批准；evidence 文本不能替代批准。

P3 已完成：

- [x] `runner.py` 支持受控命令运行、自动心跳、checkpoint、result/rejection 和失败日志。
- [x] `jobs.py` 能发现超时或缺失心跳并写入 `stalled/rejection`（停滞/拒绝）记录。
- [x] `jobs.py resume` 能从最近 checkpoint 和 `resume_from` 输出续跑点。
- [x] `runner.py replay` 会按 `run_manifest.jsonl` 中输出文件的 hash 复核可重放性。

P4 已完成：

- [x] `report.py aggregate` 聚合 run 指标、失败、输出和异常。
- [x] `report.py compare` 写入 `compare.jsonl`（对比记录）并校验阈值方向。
- [x] `report.py report` 生成任务级 `report.md`（报告）。
- [x] `report.py claim-review` 独立检查 claim 和 evidence 关联，不写 human approval，不推进 approved。

P5 已完成：

- [x] 角色模板覆盖 scientist、coder、runner、evaluator、reviewer、literature、evidence-curator、claim-reviewer。
- [x] bundled skill 和 Claude Hermes agents 已加入多代理科研协作入口。
- [x] `task_card` 强制包含 allowed_files、forbidden_files、timeout_at、heartbeat_interval、record_uri 等边界字段。
- [x] 没有 `task_card` 的结果记录会被拒收。
- [x] 同一 worktree 只允许一个未完成 coder/runner active writer。
- [x] coder 进入 review/claim_ready 前必须经过 runner 和 reviewer 记录。
- [x] reviewer/evaluator 记录不能替代 `human/root` approval。

P6 部署前安全 gate：

- [x] 增加 `hermes:preflight`（Hermes 部署前自检），quick 模式保留安全、文件、缓存和 Python 编译检查。
- [x] `runner.py` 实际执行 `allowed_commands`（允许命令）白名单，限制 `cwd`、input、output 不逃出仓库。
- [x] runner 默认使用最小环境变量白名单，避免把常见 secret env 传给子进程或写入 `run_manifest`。
- [x] `report.py --output` 限制在任务 Hermes 目录内。
- [x] Hermes hook guard 覆盖 `Bash` 常见写入；无法解析写入目标时 `fail closed`（保守拒绝）。
- [x] preflight 和部署文档明确：`Bash` gate 不是完整 OS 沙箱，`approval_records` 必须由 `human/root` 外部流程写入。

补充 hook 强化：

- [x] Hermes hook guard 已覆盖 `Edit`、`Write`、`MultiEdit` 和 `apply_patch`。
- [x] `MultiEdit` 会从当前 `tool_input`（工具输入）递归提取目标路径并按任务卡权限拦截。

最终验证记录：

- [x] `pnpm --filter trellis-hermes exec vitest run test/templates/hermes-runtime.test.ts test/templates/trellis.test.ts test/templates/claude.test.ts test/templates/codex.test.ts test/templates/shared-hooks.test.ts`：5 个文件、135 个测试通过。
- [x] `PYTHONPYCACHEPREFIX=/tmp/trellis-hermes-final-pycache python3 -m py_compile packages/cli/src/templates/trellis/scripts/hermes/*.py packages/cli/src/templates/shared-hooks/hermes-runtime-guard.py`：通过。
- [x] `pnpm --filter trellis-hermes test`：44 个文件、1259 个测试通过。
- [x] `pnpm --filter trellis-hermes typecheck`：通过。
- [x] `pnpm --filter trellis-hermes build`：通过。
- [x] 模板目录无 `__pycache__` / `.pyc` 缓存污染。

## 6. 完成定义

这个改造不能用“代码都写了”作为完成标准。至少要同时满足：

- 每个科研任务都有明确配置、运行记录、证据、结论、批准路径。
- 每个长任务都有心跳、超时、检查点和恢复路径。
- 每个子代理都有任务卡、权限边界和结构化结果。
- 每个 claim 都能追溯到 evidence，且 human approval 不能被 agent 替代。
- 每个报告结论都能复核，不依赖聊天历史。
- 核心命令、模板测试、类型检查、构建都能通过。

## 7. 保留问题

- 平台 hook 能力差异需要继续实测，尤其是 Codex/Claude 对 `PreToolUse`（工具调用前）文件写入输入的可见性。
- JSONL schema 后续是否引入独立 JSON Schema 文件，需要看校验复杂度再决定。
- 是否为实验运行引入容器化环境，不应在 P0/P1 里强行加入。
- 是否需要 agent team，不作为默认路线；只有当多个子代理必须互相讨论时再评估。
