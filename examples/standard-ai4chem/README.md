# Standard AI4Chem Closure Example

这是一个 `standard`（标准）AI4Chem 任务规划快照：固定分子数据、切分、指标和基线，比较候选模型并形成有证据限制的结果。

示例故意停留在 planning（规划）阶段，不包含伪造的运行、指标、产物 hash 或证据。复制到真实任务后应先核对 `task.json`（任务状态）和 `hermes/experiment.yaml`（实验契约），再运行：

```bash
python3 ./.trellis/scripts/closure.py validate --task <task>
python3 ./.trellis/scripts/hermes/experiment.py validate --task <task>
```

standard 关闭前需要真实的成功 `run_manifest.jsonl`（运行清单）、带 hash 的产物、指标、证据和 claim limitations（主张限制）。数据集、切分、指标定义或基线变化必须通过高风险 `amend --approved-by human/root`（人工批准变更）记录。
