# 05 项目初始化

## 目标

根据项目结构和人工智能平台选择初始化参数，并在不覆盖已有文件的前提下检查生成内容。

## 适用范围

适用于首次初始化、已有 `Trellis`（上游工作流）项目补充平台，以及单仓库和多包仓库。

## 前置条件

- 已建立可恢复的 `Git`（版本控制工具）检查点。
- 已决定要接入的平台。
- 当前目录不是用户主目录；命令默认拒绝在主目录初始化。

## 操作步骤

1. 先查看当前版本支持的平台参数：

```bash
research-trellis init --help
```

2. 单仓库、非交互初始化示例：

```bash
research-trellis init -y -u "$USER" --codex --no-monorepo
```

`-y`（自动确认）在冲突时采用跳过模式；只有显式 `--force`（强制覆盖）才会覆盖已有文件。

规范模板的下载失败行为取决于调用方式：

| 调用方式 | 失败行为 |
| --- | --- |
| `-y`（自动确认）且不指定模板源 | 不访问网络，直接使用内置空白规范 |
| 默认交互选择 | 默认索引不可用时提示后继续使用空白规范 |
| 显式 `--template <id>`（模板编号） | 索引或模板下载失败时提示重试命令，然后继续使用空白规范 |
| 交互自定义 `--registry`（模板源） | `index.json`（索引）确认不存在时尝试直接下载；暂时网络错误会返回选择界面，不会误当成直接源 |
| `-y --registry`（非交互自定义源） | 多模板市场要求再给 `--template`；索引暂时不可达时终止初始化；只有明确 `404`（不存在）才尝试直接下载，直接下载失败后才退回空白规范 |

3. 多包仓库可以让命令自动检测，也可以显式要求检测：

```bash
research-trellis init -u "$USER" --codex --monorepo
```

当前实现会识别 `pnpm-workspace.yaml`（pnpm 工作区配置）、`package.json`（Node 包配置）、`Cargo.toml`（Rust 工作区配置）、`go.work`（Go 工作区配置）、`pyproject.toml`（Python 项目配置）、子模块和并列仓库。检测成功后，包信息写入 `.trellis/config.yaml`（项目配置）。

4. 已经存在 `.trellis/`（工作流目录）时，增加平台或开发者身份：

```bash
research-trellis init --claude
research-trellis init -u "$USER"
```

5. 完成后检查：

```bash
git status --short
python3 ./.trellis/scripts/get_developer.py
python3 ./.trellis/scripts/task.py list
```

首次创建项目会生成 `00-bootstrap-guidelines`（规范启动任务）；已有项目的新开发者会生成 `00-join-<name>`（入项任务）。

## 预期结果

项目拥有 `.trellis/`（工作流目录）、至少一个平台目录、开发者身份、规范模板、科研模板和启动或入项任务。多包模式还会按包创建规范目录。

## 失败恢复

- 项目类型识别不合适：使用 `--no-monorepo`（关闭多包模式），或修正 `.trellis/config.yaml`（项目配置）。
- Python 检测失败：设置 `TRELLIS_PYTHON_CMD`（Python 命令覆盖变量）；`TRELLIS_SKIP_PYTHON_CHECK=1`（跳过检查）只应用于已确认环境正确的情况。
- 网络模板下载失败：先按上表确认是继续、返回选择还是终止；不要假定所有分支都会退回空白规范。
- 冲突文件很多：停止使用 `--force`（强制覆盖），先比较已有文件，再选择跳过或追加。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.7.0-beta.0`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`rg -n "options.yes|registry|selectedTemplate" packages/cli/src/commands/init.ts packages/cli/test/commands/init.integration.test.ts`（分支核对）。
- 结果：默认、交互、指定模板、自定义源和 `-y`（自动确认）的失败行为已分开记录。
- 未验证项：本轮未连接真实外部模板源注入网络故障。

## 来源

[S3、S4、S5、S9、S12](sources.md)

## 相关页面

- [目录参考](appendix-b-directory-reference.md)
- [配置参考](appendix-c-configuration-reference.md)
- [工作流与平台](14-workflows-and-platforms.md)
