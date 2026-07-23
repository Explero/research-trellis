# 08 Hermes 记录

## 目标

为工作代理、证据、主张、来源、审计和计划变更写入可校验的逐行记录。

## 适用范围

适用于需要复查工作过程、命令、证据来源和人工审批边界的科研任务。

## 前置条件

- 任务目录存在，并已生成任务内 `hermes/`（科研记录目录）。
- 明确要写入的记录种类和必填字段。
- 接受 `JSONL`（逐行 JSON）只是追加式约定，不是防篡改存储。

## 操作步骤

1. 先查看任务记录目录：

```bash
find ".trellis/tasks/$TASK/hermes" -maxdepth 1 -type f -print
```

2. 先创建真实输出、计算摘要，并写入产物账本：

```bash
mkdir -p results
printf 'accuracy=0.76\n' > results/accuracy.txt
HASH="sha256:$(sha256sum results/accuracy.txt | awk '{print $1}')"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
ARTIFACT="ar-$(date -u +%Y%m%d-%H%M%S)-accuracy"
python3 ./.trellis/scripts/hermes/record.py append --task "$TASK" --record-type artifact --json "{\"type\":\"artifact\",\"id\":\"$ARTIFACT\",\"path\":\"results/accuracy.txt\",\"hash\":\"$HASH\",\"run_id\":\"run-manual-accuracy\",\"command_ref\":\"cmd-manual-accuracy\",\"summary\":\"固定输入的准确率输出\"}"
python3 ./.trellis/scripts/hermes/validate.py --task "$TASK" --kind artifact
```

3. 再写入引用该产物的证据并立即校验。追加命令只负责解析并写入：

```bash
EVIDENCE="ev-$(date -u +%Y%m%d-%H%M%S)-accuracy"
python3 ./.trellis/scripts/hermes/record.py append --task "$TASK" --record-type evidence --json "{\"type\":\"evidence\",\"id\":\"$EVIDENCE\",\"timestamp\":\"$NOW\",\"source\":\"results/accuracy.txt\",\"summary\":\"固定输入得到 0.76 准确率\",\"limits\":\"仅覆盖当前固定输入\",\"artifact_refs\":[\"$ARTIFACT\"],\"command_refs\":[\"cmd-manual-accuracy\"]}"
python3 ./.trellis/scripts/hermes/validate.py --task "$TASK" --kind evidence
```

产物路径校验只接受仓库根目录下的相对字符串，拒绝绝对路径和 `..`（上级目录），并检查文件可读且 `SHA-256`（文件摘要）相符。这是记录一致性检查，不是文件系统隔离：它没有把符号链接解析后的目标限制在仓库内，不应用于不可信目录。

4. 其他常用记录文件包括：

| 记录 | 文件 | 用途 |
| --- | --- | --- |
| 工作代理 | `worker_records.jsonl`（工作代理记录） | 任务卡、心跳、检查点、结果、风险和拒绝 |
| 证据 | `evidence_ledger.jsonl`（证据账本） | 观察、来源和适用限制 |
| 主张 | `claim_ledger.jsonl`（主张账本） | 主张文字、证据编号、范围和状态 |
| 产物 | `artifact_ledger.jsonl`（产物账本） | 文件路径、哈希和运行编号 |
| 来源 | `provenance_ledger.jsonl`（来源账本） | 数据、模型、代码、环境和产物引用 |
| 审计 | `audit_ledger.jsonl`（审计账本） | 安全、外部写入、秘密删改和审批边界 |
| 计划变更 | `plan_change_log.jsonl`（计划变更记录） | 研究计划变化及接受状态 |

5. 发现旧记录错误时，不要改写旧行。追加一条新记录，使用新编号，并用额外的 `supersedes`（替代记录）等字段指向旧编号。

## 预期结果

每行都是一个完整对象，记录编号可相互引用，校验命令返回 `valid`（有效）。长日志留在文件中，记录只保存摘要和引用。

## 失败恢复

- 写入了非法记录：不要删除或改写旧行；追加更正记录，并在评审中说明旧记录无效。
- 缺少必填字段：查看[记录格式](appendix-d-record-schema.md)，补写新的完整记录。
- 引用产物失败：确认产物文件可读、`SHA-256`（文件摘要）正确，且产物编号存在。
- 需要不可篡改审计：使用项目外部的访问控制和不可变存储；当前实现不提供。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.7.1-beta.1`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n "validate_artifact_file|artifact_ref_errors|has_symlink_component" packages/cli/src/templates/trellis/scripts/hermes/runtime.py`（路径与引用边界核对）。
- 结果：示例已改为先创建产物和摘要，再写产物与证据账本；路径检查范围已明示。
- 未验证项：产物路径不是符号链接隔离或操作系统级安全边界。

## 来源

[S7、S8、S12](sources.md)

## 相关页面

- [记录格式](appendix-d-record-schema.md)
- [工作代理与门禁](13-workers-and-gates.md)
- [报告与主张](12-reports-and-claims.md)
