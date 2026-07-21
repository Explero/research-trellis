# 07 规范与上下文

## 目标

把项目真实约定写入规范目录，并只向工作代理传入当前任务需要的材料。

## 适用范围

适用于初始化后的规范补全、任务规划以及实现代理和检查代理的上下文整理。

## 前置条件

- 已阅读项目现有的贡献说明、代理说明和真实代码示例。
- 已创建任务目录。
- 引用的文件已经存在于项目中。

## 操作步骤

1. 补全 `.trellis/spec/`（项目规范目录）。单仓库通常包含 `backend/`（后端规范）、`frontend/`（前端规范）、`guides/`（通用指南）和 `languages/`（语言书写规范）；多包仓库按包名组织。`guides/general-code-guidelines.md`（通用代码规范）是科研代码任务的默认候选基线，规定范围、测试、安全和可复现性；项目已有规范和语言工具配置优先。`languages/` 预置 TypeScript/JavaScript、Python、Go、Rust、C++ 和 Shell/Bash 规范，任务只显式加入当前改动涉及的文件。为保持最小上下文，通用规范和语言规范都不会自动加入每个任务；代码任务缺少更具体规范时，再显式加入实现或检查清单。
2. 规范应描述项目当前真实做法，并引用真实示例。初始化模板中的空白内容不是完成的规范。
3. 主代理启动时只收到 `.trellis/project/`（项目资料目录）内项目背景、研究方案和项目约束的文档地址与用途。它在判断请求、讨论方案和拆分任务前按需读取；正文不会自动进入会话。派发时，任务明确引用优先，剩余位置才按角色补最小项目资料：代码角色默认拿项目约束，运行角色拿研究方案或约束，证据类审核拿研究方案和约束。代码规范、接口规范和实验材料仍由主代理明确加入派发包。

4. 查看可用包和当前上下文：

```bash
python3 ./.trellis/scripts/get_context.py --mode packages
python3 ./.trellis/scripts/task.py list-context "$TASK"
python3 ./.trellis/scripts/closure.py capsule --task "$TASK"
```

新任务每轮优先使用 capsule（紧凑上下文）：目标、范围、当前工作包、完成条件、下一动作、阻塞项和最多 3 个相关引用。完整 PRD、报告、事件、证据账本、历史任务和非当前规范只在需要时读取。这个优化不删除原始文件。

5. 向实现和检查清单追加需要的规范或研究材料：

```bash
python3 ./.trellis/scripts/task.py add-context "$TASK" implement .trellis/spec/backend/quality-guidelines.md "实现时遵守项目质量规则"
python3 ./.trellis/scripts/task.py add-context "$TASK" check .trellis/spec/backend/quality-guidelines.md "检查时核对项目质量规则"
python3 ./.trellis/scripts/task.py validate "$TASK"
```

每行真实条目格式为：

```json
{"file":".trellis/spec/backend/quality-guidelines.md","reason":"实现时遵守项目质量规则"}
```

目录条目会额外写入 `"type":"directory"`（目录类型）。创建任务时的 `_example`（示例）行不会被当作真实上下文；加入真实条目后可以删除该示例行。

6. 不要把源码路径当作规范上下文堆进清单。源码由代理按任务范围读取；这里主要放规范和研究材料。

## 预期结果

上下文校验显示两个清单均有效，代理只加载当前工作包需要的规范和研究材料，规划文档和完整历史仍保留在任务目录中。

## 失败恢复

- `Path not found`（路径不存在）：使用仓库根目录相对路径，并先确认文件存在。
- 重复条目：命令会给出警告并跳过，无需手工再追加。
- 规范与代码不一致：先修正规范；不要让代理按理想化、尚未实现的规则工作。
- 清单损坏：每行必须是一个完整 `JSON`（结构化数据）对象，修正后重新运行 `task.py validate`（任务校验）。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.7.1-beta.0`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n "implement.jsonl|check.jsonl|context" packages/cli/src/templates/trellis/scripts packages/cli/test`（上下文实现核对）。
- 结果：上下文清单、重复检查和平台读取路径与当前模板一致。
- 未验证项：各平台主机对注入内容的实际消费情况。

## 来源

[S5、S6、S9](sources.md)

## 相关页面

- [任务与规划](06-tasks-and-planning.md)
- [工作代理与门禁](13-workers-and-gates.md)
- [目录参考](appendix-b-directory-reference.md)
