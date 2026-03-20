---
name: github-sync-helper
description: >
  通用 GitHub 基础操作 + GitHub 平台对象（Issues/Labels/Milestones/Releases/Actions）自动化技能（Minis 环境）。当用户提到“GitHub 怎么用、clone、init、remote、branch、commit、push、pull、fetch、merge、rebase、tag、release、issues、actions、labels、milestone、保护分支、fork、PR、同步到上游(upstream)、删除分支、清空目录后恢复、直推 main、一键同步”等任意 Git/GitHub 基础操作与工作流时，必须触发本技能。
compatibility: >
  Requires git, python3. Uses env GITHUB_TOKEN for GitHub API + HTTPS push (non-interactive via GIT_ASKPASS).
---

## 目标

把 GitHub/Git 的“基础操作”与常见协作流程固化为：

1) 清晰的命令速查（解释 + 何时用）
2) 可执行的一键脚本（避免重复手工步骤）
3) 常用输出尽量“带编号”，方便你直接回复编号选择（例如：仓库列表）

## 安全与约束（必须遵守）

| 序号 | 规则 | 原因 |
|---:|---|---|
| 1 | **不要输出 Token**：任何命令都不得把 `$GITHUB_TOKEN` echo/print 到 stdout | 防止泄露 |
| 2 | **危险操作二次确认**：删分支、清空目录、强制覆盖、强推、直推 main | 可逆性差 |
| 3 | 默认用“分支 + PR”协作；只有用户明确要求才“直推 main” | 降低对主分支破坏 |
| 4 | push/pull 前先 `git status` | 防止误提交/误覆盖 |

## 运行方式

- **脚本入口**：`sh /var/minis/skills/github-sync-helper/scripts/gh_sync.sh <command> [options]`

> 脚本在“当前 git 仓库目录”下运行（必须在仓库内）。

## Git/GitHub 基础操作速查（解释 + 对应脚本）

| 序号 | 类别 | 操作 | 一句话解释 | 常用命令 | 脚本支持 |
|---:|---|---|---|---|---|
| 1 | 初始化 | init | 把当前目录变成 git 仓库 | `git init` | `init` |
| 2 | 获取代码 | clone | 从远端下载仓库到本地 | `git clone <url>` | `clone` |
| 3 | 远端 | remote | 管理 origin/upstream 等远端 | `git remote -v/add/set-url/remove` | `remotes/add-remote/add-upstream/set-remote-url/remove-remote` |
| 4 | 分支 | branch | 查看/创建/删除分支 | `git branch -a/-d/-D` | `branches/create-branch/delete-branches` |
| 5 | 切换 | checkout/switch | 切换到某分支 | `git switch <b>` | `checkout` |
| 6 | 查看变更 | status/diff/log | 看工作区改动/差异/历史 | `git status` `git diff` `git log` | `status/diff/log` |
| 7 | 暂存 | add | 把改动加入暂存区 | `git add -A` | `add` |
| 8 | 提交 | commit | 把暂存区打包成一次提交 | `git commit -m "..."` | `commit` |
| 9 | 同步 | fetch/pull/push | 拉取/合并/推送提交 | `git fetch` `git pull` `git push` | `fetch/pull/push/push-main` |
|10| 合并 | merge/rebase | 合并分支历史 | `git merge` `git rebase` | `merge/rebase`（谨慎） |
|11| 暂存栈 | stash | 临时收起未提交改动 | `git stash` | `stash` |
|12| 标签 | tag | 给提交打版本号 | `git tag` | `tag` |
|13| 子模块 | submodule | 管理子仓库依赖 | `git submodule` | `submodule` |
|15| GitHub 平台 | issues/labels/milestones/releases/actions | 通过 GitHub API 管理平台对象 |（API） | `gh-issues-list` 等（见下方） |

> 注：脚本的定位是“把常用基础操作变成可复用命令”。遇到复杂 rebase/冲突，仍建议用交互式终端处理。

## GitHub 平台操作（API）

> 统一要求：需要 env `GITHUB_TOKEN`。

| 序号 | command | 作用 |
|---:|---|---|
| 1 | `gh-issues-list --repo <owner/repo> [--state open|closed|all]` | 列出 Issues |
| 2 | `gh-issue-create --repo <owner/repo> --title <t> [--body <b>]` | 创建 Issue |
| 3 | `gh-issue-close --repo <owner/repo> --number <n>` | 关闭 Issue |
| 4 | `gh-labels-list --repo <owner/repo>` | 列出 labels |
| 5 | `gh-label-create --repo <owner/repo> --name <n> [--color <rrggbb>] [--description <d>]` | 创建 label |
| 6 | `gh-milestones-list --repo <owner/repo> [--state open|closed|all]` | 列出 milestones |
| 7 | `gh-milestone-create --repo <owner/repo> --title <t> [--description <d>] [--due <YYYY-MM-DD>]` | 创建 milestone |
| 8 | `gh-releases-list --repo <owner/repo>` | 列出 releases |
| 9 | `gh-release-create --repo <owner/repo> --tag <vX.Y.Z> --name <n> [--body <b>] [--draft true|false] [--prerelease true|false]` | 创建 release |
|10| `gh-actions-list --repo <owner/repo>` | 列出 workflows |
|11| `gh-actions-dispatch --repo <owner/repo> --workflow <id_or_file> [--ref <branch>] [--inputs <json>]` | 手动触发 workflow_dispatch |

## 脚本命令清单（gh_sync.sh）

| 序号 | command | 作用 |
|---:|---|---|
| 2 | `clone --url <url> [--dir <path>]` | clone 仓库到指定目录 |
| 3 | `remotes` | 显示当前 remotes |
| 4 | `add-remote --name <n> --url <url>` | 添加远端 |
| 5 | `set-remote-url --name <n> --url <url>` | 修改远端 URL |
| 6 | `remove-remote --name <n>` | 删除远端 |
| 7 | `add-upstream --upstream <owner/repo>` | 添加 upstream remote |
| 8 | `status` | `git status --porcelain` + 简要提示 |
| 9 | `diff [--staged]` | 查看差异 |
|10| `log [--n <k>]` | 查看最近提交 |
|11| `branches` | 列出本地与远程分支 |
|12| `create-branch --name <b> [--from <ref>]` | 创建分支 |
|13| `checkout --name <b>` | 切换分支 |
|14| `delete-branches --keep <branch>` | 删除除 keep 外的本地/远程分支 |
|15| `add --path <p>` | `git add` |
|16| `commit --message <m>` | `git commit` |
|17| `fetch [--remote <n>]` | 拉取远端更新 |
|18| `pull [--remote <n>] [--branch <b>]` | 拉取并合并 |
|19| `push [--remote <n>] [--branch <b>]` | 推送 |
|20| `push-main` | push 当前 main 到 origin（使用 token 非交互） |
|21| `empty-dir --dir <path>` | 清空仓库内某目录但保留目录（用 .gitkeep） |
|22| `restore-dir --src <path> --dst <path>` | 用本机目录覆盖恢复到仓库目录（会先删除 dst 内容） |
|23| `pr --upstream <owner/repo> --head <owner:branch> --base <branch> --title <t> --body <b>` | 通过 GitHub API 创建 PR |
|24| `gh-issues-list ...` 等 | GitHub 平台对象操作（issues/labels/milestones/releases/actions） |

## 典型工作流（示例）

### 1）直推 main：清空目录 → 恢复目录 → push（你刚刚那套）

```bash
sh /var/minis/skills/github-sync-helper/scripts/gh_sync.sh empty-dir --dir self-improving-agent
sh /var/minis/skills/github-sync-helper/scripts/gh_sync.sh restore-dir --src /var/minis/skills/self-improving-agent --dst self-improving-agent
sh /var/minis/skills/github-sync-helper/scripts/gh_sync.sh commit --message "restore(self-improving-agent): sync from local"
sh /var/minis/skills/github-sync-helper/scripts/gh_sync.sh push-main
```

### 4）仅替换仓库目标文件内容（保留原路径/文件名），然后提交并推送

适用场景：用户要求“只内容替换”“只替换里面的 worker”“保留仓库原文件名/路径”，本意是：**只覆盖目标文件内容，不新增上传源文件名，不改仓库中的目标路径**。

推荐执行顺序：

```bash
# 1. 拉取/刷新仓库
repo_dir=/var/minis/workspace/<repo>
if [ -d "$repo_dir/.git" ]; then
  cd "$repo_dir" && git fetch --all --prune && git reset --hard origin/main
else
  gh repo clone <owner/repo> "$repo_dir"
fi

# 2. 仅内容覆盖：用源文件内容覆盖仓库目标文件
cp <source_file> "$repo_dir/<target_path>"

# 3. 如未配置 Git 身份，优先复用 GitHub 登录名，并使用 GitHub noreply 邮箱
cd "$repo_dir"
git config user.name '<GitHub显示名>'
git config user.email '<login>@users.noreply.github.com'

# 4. 提交并直推 main（仅在用户明确要求提交/推送时执行）
git add <target_path>
git commit -m 'replace <target_path> content'
git push origin main
```

执行要点：
- 用户说“只内容替换”时，统一理解为：**保留仓库中的原文件路径与文件名，仅覆盖内容**。
- 不要把源文件名直接放进仓库；目标仍应是仓库里原本那个文件（例如 `worker.js`）。
- 若目标路径已知，直接覆盖该路径；若未知，先在仓库中定位目标文件再替换。
- 提交前若报 `Author identity unknown`，可在当前仓库写入：
  - `git config user.name '<GitHub显示名>'`
  - `git config user.email '<login>@users.noreply.github.com'`
- 默认先 `git fetch` + `git reset --hard origin/main`，避免在旧工作树上误提交。
- 若用户已经明确要求“提交”“推送”，可直接继续执行，无需重复确认。

### 5）删除除 main 外的所有分支（本地+远程）

```bash
sh /var/minis/skills/github-sync-helper/scripts/gh_sync.sh delete-branches --keep main
```

### 6）不建分支，fork:main → upstream:main 直接开 PR

```bash
sh /var/minis/skills/github-sync-helper/scripts/gh_sync.sh pr \
  --upstream OpenMinis/MinisSkills \
  --head mowenyun:main \
  --base main \
  --title "sync: ..." \
  --body "..."
```

- **仓库列表输出必须使用 Markdown 表格**，并包含 `编号` 列，便于用户直接回复编号选择。
- 字段建议：`编号 | 仓库(owner/repo) | 可见性 | Fork | 默认分支 | 最近更新 | URL`
- 交互建议：表格后提示“回复编号即可继续（clone/pull/提交推送/只内容替换等）”。

> 备注：若用户需要更多字段（description、language、stars），再加 `--json ...` 扩展。

| 序号 | 现象 | 处理 |
|---:|---|---|
| 1 | push 报 `could not read Username` | 需要 env `GITHUB_TOKEN`，脚本会用 `GIT_ASKPASS` 非交互认证 |
| 2 | API 401/403 | token 权限不足（repo/public_repo）或过期 |
| 3 | `not inside a git repo` | 先 `cd` 到仓库目录（或用 `clone`/`init`） |
