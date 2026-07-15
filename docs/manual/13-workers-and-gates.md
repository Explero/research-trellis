# 13 工作代理与门禁

## 目标

为工作代理划定文件范围，使用心跳和检查点恢复长任务，并理解工具使用前门禁和结束门禁实际检查什么。

## 适用范围

适用于有写文件、运行测试、独立复核或长时间执行的任务。门禁能减少流程跳步，但不是恶意代码防护。

## 前置条件

- 已有活动任务和有效实验配置。
- 已为每个工作代理准备唯一任务卡。
- 所选平台已正确安装并启用对应钩子。

## 操作步骤

1. 按工作形态选角色：`coder`（编码代理）负责授权文件修改，`runner`（运行代理）负责命令和测试，`reviewer`（复核代理）负责质量与安全检查，`evaluator`（评估代理）负责证据标准，`literature`（文献代理）负责来源整理。
2. 每次派发前写 `task_card`（任务卡），至少限定 `allowed_files`（允许文件）、`forbidden_files`（禁止文件）、`worktree_id`（工作树编号）、心跳间隔、超时和恢复点。

```bash
JOB="job-$(date -u +%Y%m%d-%H%M%S)-coder"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TIMEOUT="$(date -u -d '+30 minutes' +%Y-%m-%dT%H:%M:%SZ)"
python3 ./.trellis/scripts/hermes/record.py append --task "$TASK" --record-type worker --json "{\"type\":\"task_card\",\"id\":\"tc-$JOB\",\"timestamp\":\"$NOW\",\"job_id\":\"$JOB\",\"role\":\"coder\",\"worktree_id\":\"main\",\"status\":\"queued\",\"allowed_files\":[\"src/**\",\"test/**\"],\"forbidden_files\":[\".env\",\"**/.env\"],\"heartbeat_interval\":\"5m\",\"timeout_at\":\"$TIMEOUT\",\"checkpoint\":\"not-started\",\"resume_from\":\"task_card\",\"record_uri\":\".trellis/tasks/$TASK/hermes/worker_records.jsonl\",\"evidence_refs\":[],\"risk_flags\":[]}"
python3 ./.trellis/scripts/hermes/validate.py --task "$TASK" --kind worker
```

3. 使用平台的子代理工具派发。派发提示的第一行必须是 `Active task: .trellis/tasks/<task>`（活动任务路径），随后写明角色、`JOB`（工作编号）、允许与禁止文件、期望输出、停止条件和需追加的记录。`Codex`（代码代理）默认走这条 `sub-agent`（子代理）路径。

4. 工作代理返回后先校验，再检查改动范围：

```bash
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
- 编码结果进入 `review`（复核）或 `claim_ready`（待审批）前，需要相关运行结果和复核记录。

7. 在支持并启用 `Hermes`（科研工作流）运行时钩子的平台中，`PreToolUse`（工具使用前）门禁会限制主代理直接写入和执行，并按任务卡检查工作代理目标文件；`Stop`（结束）门禁读取记录、运行清单和当前文件差异，不会在结束时重新运行测试。当前内置完整运行时门禁只在 `Claude Code`（Claude 代码工具）和已启用钩子的 `Codex`（代码代理）配置中注册。

当前 `Stop`（结束）完成检查偏向代码任务：它要求编码结果覆盖当前非 `.trellis/`（工作流目录）差异，并有相关的成功运行清单和复核记录。纯研究任务也可能触发这个要求，这是测试版的已知限制。

## 预期结果

每个修改和运行都能追溯到任务卡；长任务可以从检查点恢复；缺少运行或复核记录时，完成门禁按预期阻止结束。

## 失败恢复

- 多个活动写入者：先为旧工作追加结果、拒绝或停滞记录，或使用不同工作树。
- 改动超出范围：拒绝当前结果，扩大范围必须由协调者重新签发任务卡。
- 心跳超时：运行 `jobs.py check`（检查工作），从最新检查点创建替代工作，不要静默等待。
- 钩子未触发：检查平台配置；环境变量 `TRELLIS_HOOKS=0`（关闭钩子）或 `TRELLIS_DISABLE_HOOKS=1`（禁用钩子）会直接关闭门禁。
- 门禁与任务类型不匹配：保留失败记录并由人工决定调整流程，不要把门禁当作安全认证。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.6.0-beta.31`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n -m 1 "PreToolUse|Stop" packages/cli/src/templates/{claude,codex,shared-hooks} packages/cli/test`（钩子与门禁核对）。
- 结果：`Claude Code`（Claude 代码工具）和 `Codex`（代码代理）的门禁注册、主代理防火墙和结束检查测试均可定位。
- 未验证项：平台主机是否实际触发钩子仍取决于安装版本和用户配置。

## 来源

[S7、S8、S9、S12](sources.md)

## 相关页面

- [Hermes 记录](08-hermes-records.md)
- [运行与复查](10-runs-and-replay.md)
- [记录格式](appendix-d-record-schema.md)
