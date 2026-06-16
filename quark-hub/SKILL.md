---
name: quark-hub
version: 1.3.0
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
| 标准库 | Python 内置 | asyncio / json / re / urllib 等 |

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
| `save <url> [fid]` | 🔒 需要 | 转存分享文件到网盘 |
| `dl <url> [dir]` | 🔒 需要 | 下载自己分享的文件到本地 |
| `mkdir <name> [fid]` | 🔒 需要 | 创建网盘目录 |

## 登录流程（agent 执行）

**脚本本身不驱动浏览器。** 当脚本以 **exit code 10** 退出时，表示需要登录。
agent 按以下步骤完成登录：

### 步骤 1：给用户一个可点击的登录链接

在 chat 中输出 Markdown 链接让用户点击打开夸克登录页：

```markdown
请先登录夸克网盘：[点击登录夸克网盘](https://pan.quark.cn)
登录完成后告诉我～
```

### 步骤 2：用户确认登录后，提取 Cookie 并保存

**关键：必须先 navigate 打开夸克页面刷新一次，让 WebView 与服务器交换最新 Cookie，然后再 get_cookies。**

最简方式——直接调用封装好的脚本：

```bash
sh /var/minis/skills/quark-hub/scripts/refresh_cookie.sh
```

该脚本内部执行：navigate → sleep 3 → get_cookies → source env → 写入 `~/.quark_hub_cookie`。

### 步骤 3：验证登录成功

```bash
python3 /var/minis/skills/quark-hub/quark_hub.py info
```

### 完整伪代码

```
1. 运行命令 → exit code 10？
2. YES → 输出可点击链接：[点击登录夸克网盘](https://pan.quark.cn)
3. 用户确认已登录 →
     a. browser_use navigate https://pan.quark.cn （刷新 Cookie）
     b. 等待几秒
     c. browser_use get_cookies → 提取 env 文件路径 → source → 写文件
4. 验证 info → 重新运行原命令
```

## 使用示例

```bash
S=/var/minis/skills/quark-hub/quark_hub.py

# 🔓 无需登录
python3 $S ls-share   "https://pan.quark.cn/s/6095134522b4"
python3 $S tree-share "https://pan.quark.cn/s/6095134522b4"

# 🔒 需要登录（Cookie 有效时直接执行，无效时 exit 10）
python3 $S info
python3 $S ls
python3 $S ls <fid>
python3 $S save "https://pan.quark.cn/s/xxxxxxxx"
python3 $S save "https://pan.quark.cn/s/xxxxxxxx?pwd=1234" <目标fid>
python3 $S dl   "https://pan.quark.cn/s/xxxxxxxx" /var/minis/workspace/
python3 $S mkdir 我的电影
```

## 注意事项

- `dl` 只能下载**自己网盘**的文件（夸克接口限制），他人分享需先 `save` 转存
- Cookie 有效期约 7–30 天，失效后重新登录即可
- 下载 URL 指向阿里云 OSS，headers 中不能带 `Content-Type: application/json`（已在代码中处理）
- 严禁用于非法用途，本工具仅调用夸克官方 API
