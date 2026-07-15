# 03 第一个科研任务

## 目标

在一个可回滚项目中完成初始化、创建科研任务、填写实验配置并进入执行阶段。

## 适用范围

适合第一次试跑。示例使用 `Codex`（代码代理平台）；其他平台请替换初始化参数，并参考[工作流与平台](14-workflows-and-platforms.md)。

## 前置条件

- 已按[安装](02-installation.md)准备命令。
- 当前目录是低风险科研项目，不是用户主目录。
- 已确认 `git status --short`（工作区状态）并保留可恢复的提交或备份。

## 操作步骤

1. 在目标项目根目录初始化。该命令会写入 `.trellis/`（工作流目录）、`.codex/`（Codex 配置目录）、`.agents/`（共享技能目录）和 `AGENTS.md`（代理说明文件）。

```bash
git status --short
trellis init -y -u "$USER" --codex --no-monorepo
```

2. 检查生成结果和启动任务：

```bash
python3 ./.trellis/scripts/task.py list
find .trellis/hermes -maxdepth 2 -type f -print
```

3. 创建一个范围很小的科研任务。日期前缀由脚本自动添加：

```bash
python3 ./.trellis/scripts/task.py create "比较两种文本清洗方法" --slug compare-cleaning --priority P2 --description "在固定样例上比较两种本地文本清洗方法"
TASK="$(find .trellis/tasks -maxdepth 1 -type d -name '*-compare-cleaning' -printf '%f\n' | sort | tail -n 1)"
printf '%s\n' "$TASK"
```

4. 先填写以下两个文件，不要保留模板占位文字：

- `.trellis/tasks/$TASK/prd.md`（任务需求）；
- `.trellis/tasks/$TASK/hermes/experiment.yaml`（实验配置）。

实验配置至少要给出问题、假设、数据、被测对象、指标、随机种子、环境、允许命令和产物目录。完成后校验：

```bash
python3 ./.trellis/scripts/hermes/experiment.py validate --task "$TASK"
python3 ./.trellis/scripts/task.py validate "$TASK"
```

5. 在人工智能会话内通常会自动获得会话身份；普通终端试跑可显式设置一个临时身份，然后启动任务：

```bash
export TRELLIS_CONTEXT_ID=manual-first-task
python3 ./.trellis/scripts/task.py start "$TASK"
python3 ./.trellis/scripts/task.py current --source
```

6. 在已配置的平台中用自然语言要求代理按 `Hermes`（科研工作流）执行该任务，并先审阅任务卡、允许文件和证据标准。任务进入运行后，继续阅读[实验配置](09-experiments.md)和[运行与复查](10-runs-and-replay.md)。

## 预期结果

- 任务目录包含 `task.json`（任务元数据）、`prd.md`（需求）、`implement.jsonl`（实现上下文）、`check.jsonl`（检查上下文）以及 `hermes/`（科研记录目录）。
- 实验校验输出 `valid`（有效）。
- 启动后任务状态从 `planning`（规划中）变为 `in_progress`（进行中），当前任务命令显示会话来源。

## 失败恢复

- 初始化中断：修正报错后再次运行同一命令；已存在文件默认不会因 `-y`（自动确认）而被覆盖。
- 实验校验失败：按报错补齐字段；`task.py start`（启动任务）也会先校验实验并在失败时停止。
- 缺少会话身份：在人工智能会话中重试，或设置唯一的 `TRELLIS_CONTEXT_ID`（会话标识）。
- 生成内容不适合项目：先查看 `git diff`（文件差异），再用项目原有回滚方式恢复；不要立即运行卸载。

## 验证记录

- 日期：2026-07-14。
- 版本：`0.6.0-beta.30`（测试版）。
- 基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`（当前基准）。
- 命令：`rg -n "experiment.py|task.py start|--codex" packages/cli/src packages/cli/test`（实现与测试核对）。
- 结果：初始化、任务创建、实验校验和启动步骤与当前入口一致。
- 未验证项：本轮未在新建的外部科研项目中手工执行整组示例。

## 来源

[S3、S4、S5、S6、S7](sources.md)

## 相关页面

- [项目初始化](05-project-setup.md)
- [任务与规划](06-tasks-and-planning.md)
- [实验配置](09-experiments.md)
