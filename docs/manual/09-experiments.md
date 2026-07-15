# 09 实验配置

## 目标

为每个科研任务固定问题、假设、数据、被测对象、指标、环境、允许命令和产物目录。

## 适用范围

适用于本地脚本、测试、基准、数据处理和模型评估。纯文档任务仍会生成实验骨架，但启动前也必须把占位字段改成非空内容。

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
sandbox:
  mode: "none"
  required: false
artifact_dir: ".trellis/tasks/任务名/hermes/runs"
```

3. 尽量把 `allowed_commands`（允许命令）写成完整命令前缀，而不是只写 `python3`（Python 3 命令）。当前匹配支持可执行文件名、完整命令或命令前缀，但它不是强安全边界。
4. 选择运行隔离方式：

| 模式 | 当前状态 |
| --- | --- |
| `none`（无隔离） | 已实现且为默认值；直接在本机运行 |
| `container`（容器） | 实验性；需要 `docker`（容器命令）和有效镜像，运行器会挂载仓库 |
| `external`（外部） | 配置可解析，但当前运行器不提供外部沙箱执行，实际运行会失败 |

5. 校验配置：

```bash
python3 ./.trellis/scripts/hermes/experiment.py validate --task "$TASK"
```

## 预期结果

校验输出 `valid`（有效）。之后 `task.py start`（启动任务）和 `runner.py run`（受控运行）都会读取该配置并在不满足要求时停止。

## 失败恢复

- 字段为空或类型错误：按报错修正；指标和允许命令必须是非空列表，随机种子必须是整数。
- `sandbox.required=true`（必须隔离）却使用 `mode: none`（无隔离）：改用可用容器，或停止运行。
- 容器命令不可用：安装并验证 `docker`（容器命令），或在明确接受风险后改回无隔离模式。
- 命令被拒绝：不要扩大到笼统的可执行文件；把确实需要的完整命令前缀加入配置并重新审阅。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.6.0-beta.31`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n -m 1 "allowed_commands|sandbox" packages/cli/src/templates/trellis/scripts/hermes packages/cli/test/templates/hermes-runtime.test.ts`（实现与测试核对）。
- 结果：命令允许列表、隔离模式和对应测试均可定位。
- 未验证项：本轮未启动真实容器或外部隔离环境。

## 来源

[S7、S8、S12](sources.md)

## 相关页面

- [运行与复查](10-runs-and-replay.md)
- [配置参考](appendix-c-configuration-reference.md)
- [排障](appendix-e-troubleshooting.md)
