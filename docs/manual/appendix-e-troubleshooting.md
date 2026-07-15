# 附录 E 排障

## 目标

用最短路径处理常见安装、初始化、任务、运行和审批失败。

## 适用范围

适用于本手册覆盖的当前测试版。

## 前置条件

保留原始报错，并先运行 `git status --short`（工作区状态）。

## 操作步骤

| 现象 | 处理 |
| --- | --- |
| 初始化提示 Python 不可用 | 确认 `python3 --version`（Python 版本）至少为 3.9，必要时设置 `TRELLIS_PYTHON_CMD`（Python 命令覆盖） |
| 不允许在主目录初始化 | 进入真实项目根目录，不要绕过保护 |
| 任务启动提示缺少会话身份 | 在人工智能会话运行，或设置唯一 `TRELLIS_CONTEXT_ID`（会话标识） |
| 任务启动提示实验无效 | 填完 `experiment.yaml`（实验配置）后单独运行实验校验 |
| 运行命令被拒绝 | 核对允许命令和任务卡，不要扩大为笼统命令 |
| 工作代理记录无效 | 先校验必填字段、唯一任务卡和文件范围 |
| 质量门禁缺少统计字段 | 见[指标与比较](11-metrics-and-comparison.md)中的当前限制 |
| 审批门禁失败 | 等待真实 `human/root`（人工根权限）批准记录 |
| 记忆搜索提示 OpenCode 不可用 | 当前未实现，不是本地故障 |
| 更新有冲突 | 使用 `research-trellis update --create-new`（生成新副本）比较 |

进一步检查：

```bash
research-trellis --version
python3 ./.trellis/scripts/task.py current --source
python3 ./.trellis/scripts/task.py list
```

## 预期结果

能把问题定位到环境、活动任务、实验配置、任务卡、记录或当前未实现功能。

## 失败恢复

仍无法恢复时停止写入，保留日志和差异，从已有 `Git`（版本控制工具）检查点或备份恢复。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.6.0-beta.31`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n -m 1 "quality gate|missing evidence|approval" packages/cli/src/templates/trellis/scripts/hermes packages/cli/test/templates/hermes-runtime.test.ts`（失败关闭分支核对）。
- 结果：质量门禁、缺失证据和审批失败分支都有实现或测试依据。
- 未验证项：本页不包含所有平台主机和网络环境的故障组合。

## 来源

[S3、S4、S6、S8、S11](sources.md)

## 相关页面

- [功能状态](appendix-f-feature-status.md)
- [更新、恢复与卸载](16-update-recovery-and-uninstall.md)
