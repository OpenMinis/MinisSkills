---
name: quark-hub
version: 1.4.0
description: 夸克网盘文件管理工具。支持登录、列目录、转存分享链接、下载文件、创建目录。登录改用 minis-browser-use 替代原项目的 Playwright。当用户提到「夸克网盘」「夸克下载」「夸克转存」「quark」「pan.quark.cn」时触发本技能。
---

# quark-hub

基于 [ihmily/QuarkPanTool](https://github.com/ihmily/QuarkPanTool) (Apache-2.0) 改造的 Minis 版夸克网盘工具。

## 文件路径

| 文件 | 路径 | 说明 |
|------|------|------|
| 主脚本 | `/var/minis/skills/quark-hub/quark_hub.py` | 所有命令入口 |
| 分享查看脚本 | `/var/minis/skills/quark-hub/scripts/quark_share_ls.py` | 独立脚本，无需登录 |
| **Cookie 刷新脚本** | **`/var/minis/skills/quark-hub/scripts/refresh_cookie.sh`** | **一键刷新 Cookie** |
| **Cookie 缓存** | **`~/.quark_hub_cookie`** | 登录态持久化，跨会话复用，权限 600 |

## 依赖

**零 pip 安装**，仅需 Alpine 原生包（iSH 已预装）：

| 包 | 来源 | 用途 |
|---|---|---|
| `aiohttp` | Alpine 原生 (`py3-aiohttp`) | 所有 async HTTP 请求 |
| 标准库 | Python 内置 | asyncio / json / re / urllib / threading 等 |

若 `aiohttp` 不可用：
```bash
apk add py3-aiohttp
```

## 命令速查

| 命令 | 登录 | 说明 |
|------|------|------|
| `ls-share <url>` | 🔓 无需 | 列出分享链接根目录文件 |
| `tree-share <url>` | 🔓 无需 | 递归展开分享链接完整文件树 |
| `info` | 🔒 需要 | 查看账号信息和容量 |
| `ls [fid]` | 🔒 需要 | 列出自己网盘目录（含 fid） |
| `save <url> [fid]` | 🔒 需要 | 转存分享文件到网盘（自动检查是否已存在） |
| `dl <url> [dir]` | 🔒 需要 | 下载自己网盘的文件到本地（后台线程+进度） |
| `mkdir <name> [fid]` | 🔒 需要 | 创建网盘目录 |

## ⚡ 转存 + 下载最佳流程（Agent 必读）

**下载他人分享文件时，按以下顺序执行，避免重复转存：**

```
1. tree-share <url>           # 看清楚分享里有什么
2. ls [to_fid]                # 检查目标网盘目录是否已有同名内容
3a. 已有 → 直接取 fid 下载    # 跳过转存，用现有 fid 调 api_get_download_urls
3b. 没有 → save <url>         # 转存（内部也会自动检查，已有则跳过）
4. ls [to_fid]                # 取得转存后文件的 fid
5. dl（传 extra_fids）         # 后台线程下载，自动打印进度和1min均速
```

**关键：`save` 命令现在会自动检查目标目录是否已有同名文件，有则跳过转存。**
但 agent 仍应在调用 `save` 前先 `ls` 确认，避免不必要的网络请求。

## 下载注意事项

- `dl` / `download_files_bg` 只能下载**自己网盘**内的文件（夸克接口限制）
- 他人分享 → 先 `save` 转存 → 再 `ls` 取 fid → 再 `dl`
- 下载使用**后台线程**，每 10 秒打印进度（已下/总大小/百分比/1min均速）
- 下载 URL 指向阿里云 OSS，headers 不能带 `Content-Type`（已在代码中处理）
- 字幕等文件可通过 `rename_map` 参数在下载时同步重命名（如与视频同名）

## 代码级 API（供脚本 import 使用）

```python
from quark_hub import (
    ensure_cookie,           # 获取/校验 Cookie，失效时 sys.exit(10)
    api_get_download_urls,   # 传 fid 列表 → 返回含 download_url 的 dict 列表
    download_files_bg,       # 后台线程下载，传 items=[{file_name, download_url, save_name?}]
    api_list_all,            # 列出网盘目录
)
```

## 登录流程（agent 执行）

**脚本本身不驱动浏览器。** 当脚本以 **exit code 10** 退出时，表示需要登录。
agent 按以下步骤完成登录：

### 步骤 1：给用户一个可点击的登录链接

```markdown
请先登录夸克网盘：[点击登录夸克网盘](https://pan.quark.cn)
登录完成后告诉我～
```

### 步骤 2：用户确认登录后，提取 Cookie 并保存

```bash
sh /var/minis/skills/quark-hub/scripts/refresh_cookie.sh
```

### 步骤 3：验证登录成功

```bash
python3 /var/minis/skills/quark-hub/quark_hub.py info
```

## 使用示例

```bash
S=/var/minis/skills/quark-hub/quark_hub.py

# 🔓 无需登录
python3 $S ls-share   "https://pan.quark.cn/s/xxxxxxxx"
python3 $S tree-share "https://pan.quark.cn/s/xxxxxxxx"

# 🔒 需要登录
python3 $S info
python3 $S ls
python3 $S ls <fid>
python3 $S save "https://pan.quark.cn/s/xxxxxxxx"         # 自动检查已有 → 跳过或转存
python3 $S save "https://pan.quark.cn/s/xxxxxxxx?pwd=1234" <目标fid>
python3 $S dl   "https://pan.quark.cn/s/xxxxxxxx" /var/minis/workspace/
python3 $S mkdir 我的电影
```

## 注意事项

- Cookie 有效期约 7–30 天，失效后重新登录即可
- 严禁用于非法用途，本工具仅调用夸克官方 API
