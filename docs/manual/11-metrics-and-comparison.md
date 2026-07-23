# 11 指标与比较

## 目标

固定指标定义，记录基线与新方法比较，并了解当前质量门禁的统计要求和命令限制。

## 适用范围

适用于有明确数值指标、方向、阈值、数据切分和基线的评估任务。

## 前置条件

- 已有可追踪的运行结果、证据编号和主张编号。
- 已设置 `TASK`（任务目录名）。
- 指标、切分和基线定义已经人工确认。

## 操作步骤

1. 任务缺少指标结构时，从全局模板复制一份，再按任务修改：

```bash
cp .trellis/hermes/metrics/metrics_schema.yaml ".trellis/tasks/$TASK/hermes/metrics_schema.yaml"
python3 ./.trellis/scripts/hermes/validate.py --task "$TASK" --kind metrics_schema
```

指标至少应记录名称、方向、单位、聚合方式、切分和基线。方向只能在比较时使用 `higher_is_better`（越高越好）或 `lower_is_better`（越低越好）。

2. 比较前先创建真实输出、产物摘要、证据和主张：

```bash
mkdir -p results
printf 'accuracy=0.76\n' > results/accuracy.txt
HASH="sha256:$(sha256sum results/accuracy.txt | awk '{print $1}')"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
ARTIFACT="ar-$STAMP-accuracy"
EVIDENCE="ev-$STAMP-accuracy"
CLAIM="cl-$STAMP-accuracy"
python3 ./.trellis/scripts/hermes/record.py append --task "$TASK" --record-type artifact --json "{\"type\":\"artifact\",\"id\":\"$ARTIFACT\",\"path\":\"results/accuracy.txt\",\"hash\":\"$HASH\",\"run_id\":\"run-$STAMP-accuracy\",\"command_ref\":\"cmd-$STAMP-accuracy\",\"summary\":\"准确率输出\"}"
python3 ./.trellis/scripts/hermes/record.py append --task "$TASK" --record-type evidence --json "{\"type\":\"evidence\",\"id\":\"$EVIDENCE\",\"timestamp\":\"$NOW\",\"source\":\"results/accuracy.txt\",\"summary\":\"固定切分准确率为 0.76\",\"limits\":\"只适用于当前切分和环境\",\"artifact_refs\":[\"$ARTIFACT\"],\"command_refs\":[\"cmd-$STAMP-accuracy\"]}"
python3 ./.trellis/scripts/hermes/record.py append --task "$TASK" --record-type claim --json "{\"type\":\"claim\",\"id\":\"$CLAIM\",\"timestamp\":\"$NOW\",\"text\":\"新方法在固定切分上达到 0.76 准确率\",\"evidence_ids\":[\"$EVIDENCE\"],\"scope\":\"当前切分和环境\",\"limits\":\"不外推到其他数据\",\"state\":\"claim_ready\"}"
python3 ./.trellis/scripts/hermes/validate.py --task "$TASK" --kind artifact
python3 ./.trellis/scripts/hermes/validate.py --task "$TASK" --kind evidence
python3 ./.trellis/scripts/hermes/validate.py --task "$TASK" --kind claim
```

3. 当前 `report.py compare`（比较命令）可以计算差值并追加基本比较记录：

```bash
python3 ./.trellis/scripts/hermes/report.py compare --task "$TASK" --metric accuracy --baseline 0.70 --new 0.76 --threshold 0.05 --direction higher_is_better --evidence-ref "$EVIDENCE" --claim-ref "$CLAIM"
```

**当前限制**：上述命令没有 `sample_count`（样本数）、`variance`（方差）或 `confidence_interval`（置信区间）参数，而 `quality-gate`（质量门禁）要求至少存在其中一个。因此，这条命令生成的记录会被质量门禁拒绝。

4. 需要通过质量门禁时，不要先运行上面的比较命令；从一开始就通过通用记录命令写入带统计字段的完整比较记录：

```bash
CMP="cmp-$(date -u +%Y%m%d-%H%M%S)-accuracy"
python3 ./.trellis/scripts/hermes/record.py append --task "$TASK" --record-type compare --json "{\"type\":\"compare\",\"id\":\"$CMP\",\"timestamp\":\"$NOW\",\"metric\":\"accuracy\",\"direction\":\"higher_is_better\",\"threshold\":0.05,\"baseline\":0.70,\"new\":0.76,\"delta\":0.06,\"passed\":true,\"evidence_refs\":[\"$EVIDENCE\"],\"claim_refs\":[\"$CLAIM\"],\"sample_count\":100,\"conclusion_state\":\"claim_ready\"}"
python3 ./.trellis/scripts/hermes/validate.py --task "$TASK" --kind compare
python3 ./.trellis/scripts/hermes/report.py quality-gate --task "$TASK"
```

5. 修改指标、切分或基线定义时，在 `metrics_schema.yaml`（指标结构）写入变更记录。校验器会要求对应变更编号已有 `human/root`（人工根权限）批准记录。

## 预期结果

完整比较记录通过结构校验；所有比较均通过阈值、`evidence_refs`（证据引用）和 `claim_refs`（主张引用）的每个编号都真实存在于对应账本，并至少包含一个统计字段时，质量门禁返回通过。

## 失败恢复

- 已用基本比较命令写入缺统计字段的记录：由于记录按约定不可改写，该任务的质量门禁会继续看到这条失败记录。保留它作为已知限制证据，并在新的干净任务或经人工批准的恢复流程中重新比较。
- 差值方向错误：核对指标方向；当前差值始终写为“新值减基线”，通过判断再按方向计算。
- 指标结构变更被拒绝：先补齐变更原因、证据、待审批主张和真实人工批准，不要伪造批准记录。
- 比较无证据或主张引用：先完成[报告与主张](12-reports-and-claims.md)中的记录。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.7.1-beta.1`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n -m 1 "quality-gate|evidence_refs|claim_refs" packages/cli/src/templates/trellis/scripts/hermes packages/cli/test/templates/hermes-runtime.test.ts`（门禁和引用核对）。
- 结果：质量门禁已有账本编号存在性检查以及有效、缺失引用测试。
- 未验证项：文中完整命令示例未在外部项目手工执行。

## 来源

[S7、S8、S12](sources.md)

## 相关页面

- [运行与复查](10-runs-and-replay.md)
- [报告与主张](12-reports-and-claims.md)
- [功能状态](appendix-f-feature-status.md)
