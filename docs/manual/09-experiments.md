# 09 实验配置

## 目标

为每个科研任务固定问题、假设、数据、被测对象、指标、环境、允许命令和产物目录。运行器直接在当前项目环境执行命令，不提供容器或沙箱运行模式。

## 适用范围

适用于本地脚本、测试、基准、数据处理和模型评估。纯文档任务仍会生成实验骨架，但启动前也必须把占位字段改成非空内容。

数据预检不是通用步骤。只有 Hermes closure（科研闭环）任务属于 exploration（探索），且 `research_change_fields`（研究变化字段）包含 `dataset`（数据集）、`split`（数据切分）或 `preprocessing`（预处理）时才启用；旧版非 closure 任务、普通任务、冻结协议执行和不涉及这三个字段的探索任务都不增加预检。

## 前置条件

- 已创建任务并设置 `TASK`（任务目录名）变量。
- 已决定实验输入、输出和执行命令。
- 对运行环境和秘密信息边界有基本控制。

## 操作步骤

1. 新任务会自动生成配置；旧任务缺少配置时可补建：

```bash
python3 ./.trellis/scripts/hermes/experiment.py init --task "$TASK"
```

该命令不会覆盖已经存在的实验配置。

2. 编辑 `.trellis/tasks/$TASK/hermes/experiment.yaml`（任务实验配置），至少填写：

```yaml
question: "固定数据上的方法是否达到预期指标？"
hypothesis: "新方法比基线至少提高 0.02。"
dataset: "fixtures/eval.jsonl"
model: "scripts/evaluate.py"
metrics:
  - "accuracy"
seed: 42
environment:
  os: "ubuntu-24.04"
  shell: "bash"
allowed_commands:
  - "python3 scripts/evaluate.py"
artifact_dir: ".trellis/tasks/任务名/hermes/runs"
```

3. 对需要数据预检的任务，增加 `data_preflight`（数据预检）：

```yaml
data_preflight:
  source: "公开评估集"
  version: "2026-07"
  input_manifest: "data/eval-manifest.json"
  hash: "sha256:实际文件的64位小写哈希"
  checks_ref: "data/eval-checks.yaml"
```

`input_manifest`（输入清单）与 `data_path`（数据路径）二选一，`hash`（哈希值）必须与所指文件一致。`checks_ref`（检查记录）必须位于仓库内，并把 `schema`（结构）、`missing`（缺失值）、`duplicates`（重复项）和 `split_leakage`（切分泄漏）分别记为 `checked`（已检查）或 `not_applicable`（不适用）。运行时还要用 `runner.py run --input`（声明运行输入）同时传入数据文件和检查记录，二者会带哈希写入运行清单。

4. 尽量把 `allowed_commands`（允许命令）写成完整命令前缀，而不是只写 `python3`（Python 3 命令）。它用于实验复现和任务边界，不是安全隔离。
5. 校验配置：

```bash
python3 ./.trellis/scripts/hermes/experiment.py validate --task "$TASK"
```

## 预期结果

校验输出 `valid`（有效）。之后 `task.py start`（启动任务）和 `runner.py run`（受控运行）都会读取该配置并在不满足要求时停止。

## 失败恢复

- 字段为空或类型错误：按报错修正；指标和允许命令必须是非空列表，随机种子必须是整数。
- 命令被拒绝：不要扩大到笼统的可执行文件；把确实需要的完整命令前缀加入配置并重新审阅。
- 数据预检失败：修正仓库内路径、实际文件哈希或四项检查状态。校验通过前运行器不会执行命令，也不会写入成功运行状态。
- 旧配置中的 `sandbox`（沙箱）字段可以保留，但运行器会忽略它并直接在项目环境执行。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.7.1-beta.1`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n -m 1 "allowed_commands" packages/cli/src/templates/trellis/scripts/hermes packages/cli/test/templates/hermes-runtime.test.ts`（实现与测试核对）。
- 结果：命令允许列表和本地运行记录均可定位。

## 来源

[S7、S8、S12](sources.md)

## 相关页面

- [运行与复查](10-runs-and-replay.md)
- [配置参考](appendix-c-configuration-reference.md)
- [排障](appendix-e-troubleshooting.md)
