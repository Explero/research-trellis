# 附录 D 记录格式

## 目标

汇总最常用 `JSONL`（逐行 JSON）记录的必填字段。

## 适用范围

适用于手工写记录、排查校验错误和审阅代理结果。

## 前置条件

每行使用唯一编号和 `UTC`（协调世界时）时间，旧行不改写。

## 操作步骤

| 类型 | 必填字段摘要 |
| --- | --- |
| `task_card`（任务卡） | `type,id,timestamp,job_id,role,worktree_id,status,allowed_files,forbidden_files,heartbeat_interval,timeout_at,checkpoint,resume_from,record_uri,evidence_refs,risk_flags`；`profile`（模式）可省略，正式质量、证据、主张和统计复核还要有 `parent_job_id`（父工作编号） |
| `heartbeat`（心跳） | `type,id,timestamp,job_id,status,checkpoint,summary,next_check_at` |
| `checkpoint`（检查点） | `type,id,timestamp,job_id,checkpoint,resume_from,evidence_refs,open_items` |
| `result`（结果） | `type,id,timestamp,job_id,status,summary,changed_files,evidence_refs,risk_flags,handoff` |
| `evidence`（证据） | `type,id,timestamp,source,summary,limits` |
| `claim`（主张） | `type,id,timestamp,text,evidence_ids,scope,limits,state` |
| `artifact`（产物） | `type,id,path,hash,run_id,command_ref,summary` |
| `provenance`（来源） | `type,id,timestamp,dataset,model,code,env,artifact` |
| `compare`（比较） | `type,id,timestamp,metric,direction,threshold,baseline,new,delta,passed,evidence_refs,claim_refs,conclusion_state` |
| `human_approval`（人工批准） | `type,id,timestamp,claim_id,approver,decision,notes` |
| `plan_change`（计划变更） | `type,id,timestamp,plan_ref,change_summary,reason,requested_by,decision_state,evidence_refs,supersedes` |

正式角色还有两种 JSON 文件，不是 `JSONL`（逐行 JSON）：

| 文件 | 关键字段 |
| --- | --- |
| `<job>.dispatch.json`（派发文件） | `schema,schema_version,job_id,task_id,task_revision,hermes_revision,role,profile,work_package,parent_job_id,objective,refs,allowed_files,forbidden_files,status,body,audit` |
| `<job>.result.json`（净化结果） | `schema,schema_version,job_id,task_revision,role,profile,parent_job_id,status,conclusion,uncertainties,changed_files,evidence_refs,artifact_refs,run_refs,risk_flags,next_action,audit` |

派发最多 3 个引用，正文最多 2000 字符；结果结论最多 1200 字符。`runner`（运行代理）结果的 `evidence_refs`（证据引用）必须为空，`reviewer:evidence/claim`（证据或主张复核）只能写 proposed judgment（提议判断）。raw trace（原始跟踪）位于 `.trellis/.runtime/hermes-traces/`（本地运行目录），不属于任务记录或发布包。

通用校验命令：

```bash
python3 ./.trellis/scripts/hermes/validate.py --task "$TASK" --kind worker
python3 ./.trellis/scripts/hermes/validate.py --task "$TASK" --kind evidence
python3 ./.trellis/scripts/hermes/validate.py --task "$TASK" --kind claim
```

`run_manifest`（运行清单）不是普通类型记录，至少要有命令、工作目录、环境摘要、输入、输出、退出码、开始时间和结束时间。

新任务卡的 `role`（角色）只允许 `planner`（规划代理）、`researcher`（检索代理）、`coder`（编码代理）、`runner`（运行代理）和 `reviewer`（复核代理）。`profile`（模式）必须属于对应角色。旧名称在读取时会规范化并提示弃用，历史文件不会被自动重写。

## 预期结果

逐行对象可解析，必填字段完整，引用的证据、产物和批准对象存在。

## 失败恢复

记录错误时追加带新编号的更正记录；需要查看协议说明时使用全局模板路径 `.trellis/hermes/records/recordbus.md`（记录总线说明）。任务数据存在 `.trellis/tasks/<task>/hermes/`（任务科研记录），不存在该全局协议目录。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.7.1-beta.1`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n -m 1 "REQUIRED_FIELDS|PLAN_CHANGE_DECISION_STATES" packages/cli/src/templates/trellis/scripts/hermes/runtime.py`（记录结构核对）。
- 结果：必填字段表和计划变更决定值与运行时定义一致；`recordbus.md`（记录总线说明）已标为全局协议路径。
- 未验证项：自定义扩展字段不在本页的必填字段清单中。

## 来源

[S7、S8](sources.md)

## 相关页面

- [Hermes 记录](08-hermes-records.md)
- [报告与主张](12-reports-and-claims.md)
