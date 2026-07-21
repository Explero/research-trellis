# 03 第一个科研任务

## 目标

在一个可回滚项目中完成初始化、适度规划、执行、审计和关闭。

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
research-trellis init -y -u "$USER" --codex --no-monorepo
```

2. 检查生成结果和启动任务。空仓库先处理 `00-bootstrap-guidelines`（项目启动任务）：完成一次研究合同讨论，填写 `.trellis/project/` 中的三份项目资料，再创建下面的首个任务。已有项目先读取 `PROJECT_INDEX.md`（事实索引）列出的原始资料，不把索引当作自动摘要。

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

实验配置至少要给出问题、假设、数据、被测对象、指标、随机种子、环境、允许命令和产物目录。然后把任务目标、范围和完成条件写入 closure（收口计划）。这个简单任务只需要一个工作包：

```bash
python3 ./.trellis/scripts/closure.py plan --task "$TASK" \
  --intent "在固定样例上得到可重复的两种清洗方法比较结果" \
  --in-scope "固定本地样例" \
  --out-of-scope "论文级泛化结论" \
  --done-when "两种方法均运行成功且比较结果经过检查"
python3 ./.trellis/scripts/closure.py validate --task "$TASK"
python3 ./.trellis/scripts/hermes/experiment.py validate --task "$TASK"
python3 ./.trellis/scripts/task.py validate "$TASK"
```

5. 在人工智能会话内通常会自动获得会话身份；普通终端试跑可显式设置一个临时身份，然后启动任务：

```bash
export TRELLIS_CONTEXT_ID=manual-first-task
python3 ./.trellis/scripts/task.py start "$TASK"
python3 ./.trellis/scripts/task.py current --source
python3 ./.trellis/scripts/closure.py capsule --task "$TASK"
```

6. 在已配置的平台中要求代理只处理 capsule（紧凑上下文）里的当前工作包。实际检查通过后登记证据并关闭：

```bash
python3 ./.trellis/scripts/closure.py package-check --task "$TASK"
python3 ./.trellis/scripts/closure.py package-done --task "$TASK" --evidence "比较测试与结果文件"
python3 ./.trellis/scripts/closure.py audit --task "$TASK"
python3 ./.trellis/scripts/closure.py close --task "$TASK"
```

任务进入运行后，继续阅读[实验配置](09-experiments.md)、[运行与复查](10-runs-and-replay.md)和[Lean Research Closure](17-lean-research-closure.md)。

## 预期结果

- 任务目录包含 `task.json`（任务元数据）、`prd.md`（需求）、`implement.jsonl`（实现上下文）、`check.jsonl`（检查上下文）以及 `hermes/`（科研记录目录）。
- 实验校验输出 `valid`（有效）。
- 启动后原版状态从 `planning`（规划中）变为 `in_progress`（进行中），当前工作包变为 `running`（运行中）。
- 关闭后 `closure_state`（收口状态）为 `closed`（已关闭），原版状态才变为 `completed`（已完成）。

## 失败恢复

- 初始化中断：修正报错后再次运行同一命令；已存在文件默认不会因 `-y`（自动确认）而被覆盖。
- 实验校验失败：按报错补齐字段；`task.py start`（启动任务）也会先校验实验并在失败时停止。
- 启动提示 closure 未准备：先运行 `closure.py plan`（规划）和 `closure.py validate`（校验）。
- 关闭提示缺口：按 `audit`（审计）给出的 package、missing 和 action 处理，不要直接修改完成状态。
- 缺少会话身份：在人工智能会话中重试，或设置唯一的 `TRELLIS_CONTEXT_ID`（会话标识）。
- 生成内容不适合项目：先查看 `git diff`（文件差异），再用项目原有回滚方式恢复；不要立即运行卸载。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.7.1-beta.0`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n "experiment.py|task.py start|--codex" packages/cli/src packages/cli/test`（实现与测试核对）。
- 结果：初始化、任务创建、实验校验和启动步骤与当前入口一致。
- 未验证项：本轮未在新建的外部科研项目中手工执行整组示例。

## 来源

[S3、S4、S5、S6、S7](sources.md)

## 相关页面

- [项目初始化](05-project-setup.md)
- [任务与规划](06-tasks-and-planning.md)
- [实验配置](09-experiments.md)
