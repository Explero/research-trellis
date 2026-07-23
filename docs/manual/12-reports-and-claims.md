# 12 报告与主张

## 目标

把证据、主张、比较和适用限制整理成任务报告，并把待审批与已审批明确分开。

## 适用范围

适用于已经产生可追踪证据和比较记录、准备进行科研复核或人工决策的任务。

## 前置条件

- 证据文件和比较记录已经存在并通过校验。
- 主张用语限定了适用范围，没有超出证据。
- 人工审批者能独立查看任务文件和原始产物。

## 操作步骤

1. 先按[指标与比较](11-metrics-and-comparison.md)创建真实输出、产物摘要和证据，再追加引用该证据编号的主张：

```bash
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 ./.trellis/scripts/hermes/record.py append --task "$TASK" --record-type claim --json "{\"type\":\"claim\",\"id\":\"cl-accuracy\",\"timestamp\":\"$NOW\",\"text\":\"新方法在固定切分上达到 0.76 准确率\",\"evidence_ids\":[\"ev-accuracy\"],\"scope\":\"固定数据切分和当前环境\",\"limits\":\"不能外推到其他数据或环境\",\"state\":\"claim_ready\"}"
python3 ./.trellis/scripts/hermes/validate.py --task "$TASK" --kind claim
```

2. 只读检查主张是否能解析到证据：

```bash
python3 ./.trellis/scripts/hermes/report.py claim-review --task "$TASK" --claim-id cl-accuracy
```

该命令不会写批准记录，也不会把状态改为 `approved`（已批准）。

3. 生成报告：

```bash
python3 ./.trellis/scripts/hermes/report.py report --task "$TASK" --question "新方法是否优于固定基线" --method "在固定切分和随机种子上运行同一评估脚本" --data "fixtures/eval.jsonl，固定切分" --metrics "accuracy，越高越好，阈值 0.05" --limitations "仅一次固定环境评估" --risks "数据代表性和环境漂移"
```

报告会汇总比较、主张和证据索引，但结论状态固定保持 `claim_ready`（待审批）。

4. 真实人工审批者在外部完成复核后，才可通过受控流程追加：

```json
{"type":"human_approval","id":"ap-YYYYMMDD-HHMMSS-accuracy","timestamp":"YYYY-MM-DDTHH:MM:SSZ","claim_id":"cl-accuracy","approver":"human/root","decision":"approved","notes":"批准范围和条件"}
```

当前工具只校验这些字段和值，不验证操作者身份。批准记录必须由项目外部权限和审阅流程保证真实性。

5. 检查已有批准：

```bash
python3 ./.trellis/scripts/hermes/validate.py --task "$TASK" --kind approval
python3 ./.trellis/scripts/hermes/report.py approval-gate --task "$TASK" --claim-id cl-accuracy
```

## 预期结果

报告包含问题、方法、数据、指标、结果、核心结论、证据索引、限制和风险。没有真实人工记录时，审批门禁失败；记录有效且引用待审批主张时，门禁才返回已批准。

## 失败恢复

- 主张缺少证据：退回 `claim_ready`（待审批）之前的复核阶段，补充证据，不要降低校验标准。
- 报告生成失败：先分别校验证据、主张和比较记录。
- 审批门禁提示记录缺失：这是预期的失败关闭行为，等待真实人工决定。
- 批准范围需要修改：追加新主张和新批准记录，不要改写旧记录。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.7.1-beta.1`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n -m 1 "claim-review|approval-gate" packages/cli/src/templates/trellis/scripts/hermes packages/cli/test/templates/hermes-runtime.test.ts`（主张与审批边界核对）。
- 结果：主张审查和审批门禁入口可定位，报告与人工批准保持分离。
- 未验证项：本轮未进行真实人工审批，也未验证外部身份系统。

## 来源

[S7、S8、S12](sources.md)

## 相关页面

- [指标与比较](11-metrics-and-comparison.md)
- [记录格式](appendix-d-record-schema.md)
- [功能状态](appendix-f-feature-status.md)
