# 02 安装

## 目标

安装当前测试版命令，并确认 `Node.js`（JavaScript 运行时）、`Python`（脚本运行时）和 `Git`（版本控制工具）满足要求。

## 适用范围

适用于 `Ubuntu 24.04`（Ubuntu 24.04 操作系统）和相近的本地开发环境。新包发布前应从源码运行；发布后可从 `npm`（Node 包平台）安装。

## 前置条件

- `Node.js >= 18.17.0`（Node.js 18.17.0 或更高版本）。
- `Python >= 3.9`（Python 3.9 或更高版本）。
- 可用的 `Git`（版本控制工具）。
- 能访问 `npm`（Node 包平台）；源码方式还需要 `pnpm 10.32.1`（包管理器）。

## 操作步骤

先检查环境：

```bash
node --version
python3 --version
git --version
```

新包发布后，推荐固定安装本手册对应的测试版：

```bash
npm install --global research-trellis@0.7.1-beta.0
research-trellis --version
research-trellis --help
```

如不希望全局安装，可临时执行：

```bash
npm exec --yes --package research-trellis@0.7.1-beta.0 -- research-trellis --version
```

已经安装旧包时，先卸载旧名称，再安装新包：

```bash
npm uninstall --global trellis-hermes
npm install --global research-trellis@0.7.1-beta.0
research-trellis --version
```

需要核对或修改源码时，使用源码方式：

```bash
git clone https://github.com/Explero/research-trellis.git
cd research-trellis
corepack enable
pnpm install --frozen-lockfile
pnpm build
node packages/cli/bin/trellis.js --version
```

源码命令不会自动变成全局 `research-trellis`（命令）；后续应继续使用 `node /绝对路径/packages/cli/bin/trellis.js`（源码入口），或在新包发布后另行全局安装。

## 预期结果

版本命令输出 `0.7.1-beta.0`，帮助中能看到 `init`（初始化）、`update`（更新）、`workflow`（工作流）、`channel`（协作频道）和 `mem`（会话记忆）等命令。

## 失败恢复

- `node`（Node.js 命令）版本过低：先升级运行时，不要绕过包的版本要求。
- 找不到 `python3`（Python 3 命令）：安装 Python 3.9 以上版本，或在初始化前设置 `TRELLIS_PYTHON_CMD`（Python 命令覆盖变量）。
- 全局安装没有写权限：修正用户级 `npm`（Node 包管理器）目录，不建议直接使用 `sudo`（管理员执行）。
- 只想确认包可用：使用上面的 `npm exec`（临时执行）命令，不会安装全局命令。

## 验证记录

- 日期：2026-07-15。
- 版本：`0.7.1-beta.0`（测试版）。
- 更名前基准提交：`9f7dc8497b4782878d6fa7ac3b63eba5bde507df`。
- 命令：`node -p "require('./packages/cli/package.json').version"`（包版本核对）。
- 结果：源码包版本为 `0.7.1-beta.0`（测试版），运行时要求与包配置一致。
- 未验证项：本轮未重新进行全局安装，也未实时查询 `npm`（Node 包平台）标签。

## 来源

[S1、S2、S3](sources.md)

## 相关页面

- [第一个科研任务](03-first-research-task.md)
- [命令参考](appendix-a-cli-reference.md)
- [排障](appendix-e-troubleshooting.md)
