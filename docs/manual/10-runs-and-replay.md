# 10 运行与复查

## 目标

通过 `Hermes`（科研工作流）运行器执行一个已授权命令，保存日志、输入输出摘要和运行清单，并复查产物是否仍与记录一致。

## 适用范围

适用于本地脚本、测试和基准命令。示例假定项目中已有 `fixtures/input.jsonl`（输入数据）、`scripts/evaluate.py`（评估脚本），并会生成 `results/metrics.json`（指标结果）。

## 前置条件

- 实验配置已通过校验，并允许 `python3 scripts/evaluate.py`（评估命令）。
- 输入文件和脚本存在。
- 已审阅输出路径，且没有秘密信息。
- 已设置 `TASK`（任务目录名）。

## 操作步骤

1. 先追加一个 `runner`（运行代理）任务卡：

```bash
JOB="job-$(date -u +%Y%m%d-%H%M%S)-eval"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TIMEOUT="$(date -u -d '+30 minutes' +%Y-%m-%dT%H:%M:%SZ)"
python3 ./.trellis/scripts/hermes/record.py append --task "$TASK" --record-type worker --json "{\"type\":\"task_card\",\"id\":\"tc-$JOB\",\"timestamp\":\"$NOW\",\"job_id\":\"$JOB\",\"role\":\"runner\",\"worktree_id\":\"main\",\"status\":\"queued\",\"allowed_files\":[\"results/**\"],\"forbidden_files\":[\".env\",\"**/.env\"],\"heartbeat_interval\":\"5m\",\"timeout_at\":\"$TIMEOUT\",\"checkpoint\":\"not-started\",\"resume_from\":\"task_card\",\"record_uri\":\".trellis/tasks/$TASK/hermes/worker_records.jsonl\",\"evidence_refs\":[],\"risk_flags\":[]}"
```

2. 执行命令并声明输入输出：

```bash
python3 ./.trellis/scripts/hermes/runner.py run --task "$TASK" --job-id "$JOB" --checkpoint evaluate --summary "运行固定数据评估" --input fixtures/input.jsonl --input scripts/evaluate.py --output results/metrics.json -- python3 scripts/evaluate.py
```

运行器会写入检查点、心跳、标准输出日志、标准错误日志、运行清单，以及成功结果或失败拒绝记录。

3. 校验工作代理记录和运行清单：

```bash
python3 ./.trellis/scripts/hermes/validate.py --task "$TASK" --kind worker
python3 ./.trellis/scripts/hermes/validate.py --task "$TASK" --kind run_manifest
```

4. 取出最后一次运行编号并复查：

```bash
RUN_ID="$(python3 -c 'import json,sys; print(json.loads(open(sys.argv[1], encoding="utf-8").readlines()[-1])["id"])' ".trellis/tasks/$TASK/hermes/run_manifest.jsonl")"
python3 ./.trellis/scripts/hermes/runner.py replay --task "$TASK" --run-id "$RUN_ID"
```

`replay`（复查）不会重新运行原命令；它只检查记录中的输出文件仍可读取，且 `SHA-256`（文件摘要）与清单一致。

## 预期结果

命令返回原始退出码。成功时运行清单和工作代理结果都被追加，校验通过；复查输出 `replayable`（可复查）。失败时仍保存日志和退出码，并追加拒绝记录。

## 失败恢复

- 缺少任务卡或任务卡重复：为新运行创建唯一 `JOB`（工作编号），不要复用旧编号。
- 命令不在允许列表：回到实验配置审阅命令，不要绕过运行器。
- 输出文件没有生成：查看该次运行目录中的 `stderr.log`（标准错误日志），修正脚本后用新任务卡重试。
- 复查哈希不一致：把产物视为已变化，不要改旧清单；追加新的运行记录。
- 运行中断：使用工作代理记录中的检查点和恢复说明，创建新工作编号继续。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.6.0-beta.31`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n -m 1 "run_manifest|replay" packages/cli/src/templates/trellis/scripts/hermes packages/cli/test/templates/hermes-runtime.test.ts`（运行清单与复查核对）。
- 结果：运行清单、输出摘要和复查失败分支均有实现与测试依据。
- 未验证项：本轮未手工执行文中的完整任务卡、运行和复查示例。

## 来源

[S7、S8、S12](sources.md)

## 相关页面

- [实验配置](09-experiments.md)
- [指标与比较](11-metrics-and-comparison.md)
- [工作代理与门禁](13-workers-and-gates.md)
