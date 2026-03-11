---
name: bilibili-hub
description: >
  使用 Python + UV 读写哔哩哔哩（B 站）数据的技能，依赖 bilibili-api-python + aiohttp，
  通过 browser_use get_cookies 自动获取 Cookie 完成认证，无需手动复制。
  支持视频详情/字幕/AI总结/评论、用户主页、搜索、热门/排行榜、关注动态 Feed、
  收藏夹、稍后再看、观看历史、互动操作（点赞/投币/三连）、动态发布与删除等。
  当用户提到"B站"、"哔哩哔哩"、"bilibili"、"B站视频"、"B站热门"、"bilibili-hub"、
  "获取B站数据"、"B站字幕"、"B站评论"、"B站收藏"、"B站动态"，
  或任何需要以编程方式读写 B 站内容的场景，必须触发本技能。
---

# bilibili-hub

> **改造来源**：[jackwener/bilibili-cli](https://github.com/jackwener/bilibili-cli)（Apache-2.0）
>
> 本技能在原仓库基础上做了以下简化与改造：
> - 移除 `browser-cookie3` / `click` / `rich` / `PyYAML` / `qrcode` 依赖
> - Cookie 认证改为直接传入 `dict` 或从环境变量读取，不做浏览器自动提取
> - 移除 CLI 层（commands/）、QR 登录、formatter 等
> - 保留全部 API 方法，统一封装为同步接口（`asyncio.run`）
> - 核心依赖 `bilibili-api-python`（逆向工程 B 站 API 的第三方 SDK）
> - 在 Minis 环境中，Cookie 通过 `browser_use get_cookies` 自动获取

---

## 文件结构

```
/var/minis/skills/bilibili-hub/
├── SKILL.md
├── pyproject.toml          # bilibili-api-python + aiohttp
└── scripts/
    ├── __init__.py
    ├── exceptions.py       # 6 种结构化异常
    ├── payloads.py         # 数据结构规范化（normalize_* 函数）
    └── client.py           # BiliClient 核心类（全部 API 方法）
```

---

## 认证方式

B 站 Web API 使用三个关键 Cookie：

| Cookie | 说明 |
|--------|------|
| `SESSDATA` | 用户 Session（必填，读操作） |
| `bili_jct` | CSRF Token（写操作必填：点赞/投币/发动态等） |
| `DedeUserID` | 用户 ID（建议填写） |
| `buvid3` | 设备 ID（建议填写，降低风控概率） |

### 方法一：browser_use 自动获取（Minis 环境首选）

1. `browser_use navigate` 打开 `https://www.bilibili.com`，确认已登录
2. `browser_use get_cookies` 获取 Cookie（原始值不出现在对话中）
3. 加载 offload env 文件：

```bash
. /var/minis/offloads/env_cookies_www_bilibili_com_xxx.sh
export BILI_SESSDATA="$COOKIE_SESSDATA"
export BILI_JCT="$COOKIE_BILI_JCT"
export BILI_USERID="$COOKIE_DEDEUSERID"
export BILI_BUVID3="$COOKIE_BUVID3"
```

> **注意**：`get_cookies` 仅对当前页面域名生效，需先 navigate 到 `https://www.bilibili.com` 再调用。

### 方法二：手动从浏览器 DevTools 获取

1. 登录 B 站，打开 DevTools → Application → Cookies → `https://www.bilibili.com`
2. 找到 `SESSDATA`、`bili_jct`、`DedeUserID` 的值
3. 存入 Minis 环境变量：`BILI_SESSDATA` / `BILI_JCT` / `BILI_USERID`

### Cookie 传入方式（三种）

```python
# 方式一：从环境变量（推荐）
client = BiliClient.from_env()

# 方式二：直接传入 dict
client = BiliClient({
    "SESSDATA":   os.environ["BILI_SESSDATA"],
    "bili_jct":   os.environ["BILI_JCT"],
    "DedeUserID": os.environ["BILI_USERID"],
})

# 方式三：仅读操作（无需写权限）
client = BiliClient({"SESSDATA": os.environ["BILI_SESSDATA"]})
```

---

## 快速开始

### 环境准备

```bash
cd /var/minis/skills/bilibili-hub
uv sync
```

### 作为 Python 库调用

```python
import os, json, sys
sys.path.insert(0, "/var/minis/skills/bilibili-hub")
from scripts.client import BiliClient

client = BiliClient.from_env()

# 当前用户信息
me = client.whoami()
print("用户：", me.get("name"), "UID:", me.get("mid"))

# 搜索视频
videos = client.search_videos("Python 教程", count=5)
for v in videos:
    print(f"  {v['bvid']} {v['title']} ({v['duration']})")

# 获取视频详情（含字幕）
detail = client.get_video("BV1xx411c7mD", subtitle=True)
print(detail["video"]["title"])
print(detail["subtitle"]["text"][:200])

# 热门视频
hot = client.get_hot(count=10)
for v in hot:
    print(f"  {v['bvid']} {v['title']} 👁{v['stats']['view']}")
```

---

## API 方法速查

### 账号

| 方法 | 说明 |
|------|------|
| `whoami()` | 获取当前登录用户信息 |

### 视频

| 方法 | 说明 |
|------|------|
| `get_video(bvid, *, subtitle, subtitle_timeline, ai_summary, comments, related)` | 获取视频详情（可选字幕/AI总结/评论/相关） |

`bvid` 支持 BV 号或完整 URL，自动提取。

### 用户

| 方法 | 说明 |
|------|------|
| `get_user(uid)` | 获取用户主页信息 + 关注/粉丝数 |
| `get_user_videos(uid, count=20)` | 获取用户发布的视频 |

### 搜索

| 方法 | 说明 |
|------|------|
| `search_videos(keyword, page=1, count=20)` | 搜索视频 |
| `search_users(keyword, page=1)` | 搜索用户 |

### 发现

| 方法 | 说明 |
|------|------|
| `get_hot(page=1, count=20)` | 全站热门视频 |
| `get_rank(day=3, count=50)` | 全站排行榜（day: 1/3/7） |
| `get_feed(offset=0)` | 关注动态 Feed（需登录） |
| `get_my_dynamics(offset=0)` | 我发布的动态（需登录） |
| `post_dynamic(text)` | 发布文字动态（需登录+bili_jct） |
| `delete_dynamic(dynamic_id)` | 删除动态（需登录+bili_jct） |

### 收藏 / 历史

| 方法 | 说明 |
|------|------|
| `get_favorites()` | 获取收藏夹列表（需登录） |
| `get_favorites(folder_id)` | 获取收藏夹内视频 |
| `get_following(page=1)` | 获取关注列表（需登录） |
| `get_watch_later()` | 稍后再看列表（需登录） |
| `get_history()` | 观看历史（需登录） |

### 下载

| 方法 | 说明 |
|------|------|
| `download_video(bvid, output_dir, filename=None)` | 下载完整视频（mp4），自动处理 DASH 合并 |
| `download_audio(bvid, output_dir, filename=None)` | 仅下载音频流（m4a），适合 ASR 转写 |

**下载流程**：
- DASH 流（主流）：分别下载视频流 + 音频流 → ffmpeg copy 合并 → 失败则保留无声视频
- FLV/MP4 流（少见）：直接下载，无需合并
- 未登录可下最高 480P；登录后可下 1080P（大会员可下更高画质）

| 方法 | 说明 |
|------|------|
| `like(bvid)` / `like(bvid, undo=True)` | 点赞 / 取消点赞（需bili_jct） |
| `coin(bvid, num=1)` | 投币 1 或 2 枚（需bili_jct） |
| `triple(bvid)` | 一键三连（需bili_jct） |
| `unfollow(uid)` | 取消关注用户（需bili_jct） |

---

## 错误处理

```python
from scripts.exceptions import (
    AuthenticationError,  # Cookie 缺失或过期
    RateLimitError,       # 触发风控（412）
    NotFoundError,        # 视频/用户不存在
    NetworkError,         # 网络/超时错误
    InvalidBvidError,     # BV 号格式错误
    BiliError,            # 其他 API 错误（基类）
)

try:
    detail = client.get_video("BV1xx411c7mD")
except AuthenticationError:
    print("Cookie 已过期，请重新获取")
except RateLimitError:
    print("触发风控，稍后重试")
except NotFoundError:
    print("视频不存在")
except BiliError as e:
    print(f"API 错误：{e}")
```

---

## 注意事项

- `SESSDATA` 是读操作的最低要求；写操作（点赞/投币/发动态）还需要 `bili_jct`
- Cookie 有效期通常数天至数周，过期后需重新通过 `browser_use get_cookies` 获取
- B 站对高频请求有风控（HTTP 412），建议操作间隔 ≥1 秒
- `bilibili-api-python` 是社区维护的逆向工程项目，接口可能随 B 站更新失效
- 写操作（投币/三连等）不可逆，请谨慎调用
