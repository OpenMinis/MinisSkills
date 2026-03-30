---
name: xiaohongshu-hub
description: >
  使用 Python + UV 读写小红书（XHS）数据的技能，仅依赖 httpx + pycryptodome，
  通过 browser_use get_cookies 自动获取 Cookie 完成认证，无需手动复制。
  支持搜索笔记/用户/话题、读取笔记详情与评论、推荐 Feed、热门榜单、
  社交操作（关注/收藏）、互动（点赞/评论/回复）、通知查询、创作者笔记管理等。
  当用户提到"小红书"、"XHS"、"抓取小红书"、"搜索小红书笔记"、"小红书评论"、
  "xiaohongshu-hub"、"读取小红书数据"、"小红书 Cookie"，
  或任何需要以编程方式读写小红书内容的场景，必须触发本技能。
---

# xiaohongshu-hub

> **改造来源**：[jackwener/xiaohongshu-cli](https://github.com/jackwener/xiaohongshu-cli)（Apache-2.0）
>
> 本技能在原仓库基础上做了以下简化与改造：
> - 移除 `browser-cookie3` / `click` / `rich` / `PyYAML` / `qrcode` 依赖
> - Cookie 认证改为直接传入 `dict` 或从环境变量读取，不做浏览器自动提取
> - 移除 CLI 层（commands/）和 QR 登录模块（qr_login.py）
> - `signing.py` 保留完整逆向签名算法，纯标准库实现（无第三方依赖）
> - `creator_signing.py` 保留 AES-128-CBC 签名（依赖 pycryptodome）
> - 在 Minis 环境中，Cookie 通过 `browser_use get_cookies` 自动获取

---

## 文件结构

```
/var/minis/skills/xiaohongshu-hub/
├── SKILL.md
├── pyproject.toml          # UV 项目配置（仅 httpx + pycryptodome）
└── scripts/
    ├── __init__.py
    ├── constants.py        # 常量（Host、UA、SDK 版本等）
    ├── exceptions.py       # 结构化异常（6 种错误类型）
    ├── signing.py          # 主 API 签名（x-s / x-s-common / x-t）纯标准库
    ├── creator_signing.py  # 创作者 API 签名（AES-128-CBC）
    └── client.py           # XhsClient 核心类（全部 API 方法）
```

---

## 认证方式

小红书 Web API 使用三个关键 Cookie：

| Cookie | 说明 |
|--------|------|
| `a1` | 用户身份标识，签名算法核心参数（必填） |
| `web_session` | 登录 Session（必填） |
| `webId` | 设备 ID（建议填写） |

### 方法一：browser_use 自动获取（Minis 环境首选）

在 Minis 中可直接用 `browser_use` 工具导航到小红书，再用 `get_cookies` 自动读取，
**Cookie 原始值不会出现在对话中**，通过 offload env 文件安全传递。

操作步骤：
1. `browser_use navigate` 打开 `https://www.xiaohongshu.com`，确认已登录
2. `browser_use get_cookies` 分别获取 `a1`、`web_session`、`webId`
   - 工具返回 offload env 文件路径（如 `/var/minis/offloads/env_cookies_xxx.sh`）
   - Cookie 原始值不出现在对话上下文中
3. 加载 env 文件后使用：

```bash
. /var/minis/offloads/env_cookies_xxx.sh
# 文件内已导出 COOKIE_A1 / COOKIE_WEB_SESSION / COOKIE_WEBID 等变量
export XHS_A1="$COOKIE_A1"
export XHS_WEB_SESSION="$COOKIE_WEB_SESSION"
export XHS_WEBID="$COOKIE_WEBID"
```

> **注意**：`get_cookies` 仅对当前页面域名生效，需先 navigate 到 `https://www.xiaohongshu.com` 再调用。

### 方法二：手动从浏览器 DevTools 获取

1. 登录小红书，打开 DevTools → Application → Cookies → `https://www.xiaohongshu.com`
2. 找到 `a1`、`web_session`、`webId` 的值
3. 存入 Minis 环境变量（Settings → Environments）：`XHS_A1` / `XHS_WEB_SESSION` / `XHS_WEBID`

### Cookie 传入方式（三种，优先级从高到低）

1. **环境变量**：`XHS_A1` + `XHS_WEB_SESSION` + `XHS_WEBID`（推荐）
2. **代码直接传入**：`XhsClient({"a1": ..., "web_session": ..., "webId": ...})`
3. **脚本参数**：通过 `-a1` / `--web-session` 等参数传入

---

## 快速开始

### 环境准备

```bash
cd /var/minis/skills/xiaohongshu-hub
uv sync
```

### 作为 Python 库调用（推荐）

```python
import os, json, sys
sys.path.insert(0, "/var/minis/skills/xiaohongshu-hub")
from scripts.client import XhsClient

# 方式一：从环境变量构建（推荐）
client = XhsClient.from_env()

# 方式二：直接传入 Cookie dict
client = XhsClient({
    "a1":          os.environ["XHS_A1"],
    "web_session": os.environ["XHS_WEB_SESSION"],
    "webId":       os.environ["XHS_WEBID"],
})

with client:
    # 当前用户信息
    me = client.get_self_info()
    print("用户：", me.get("nickname"))

    # 搜索笔记
    results = client.search_notes("美食", page=1)
    for item in results.get("items", [])[:5]:
        note = item.get("note_card", {})
        print(f"  - {note.get('display_title', '')}")

    # 推荐 Feed
    feed = client.get_home_feed()
    print(f"推荐 Feed：{len(feed.get('items', []))} 条")

    # 热门笔记（旅行）
    hot = client.get_hot_feed("homefeed.travel_v3")
    print(f"热门旅行：{len(hot.get('items', []))} 条")
```

### 通过脚本调用（shell 环境）

```bash
# 搜索笔记，输出 JSON
cd /var/minis/skills/xiaohongshu-hub
uv run python -c "
import os, json, sys
sys.path.insert(0, '.')
from scripts.client import XhsClient
with XhsClient.from_env() as c:
    r = c.search_notes('旅行', page=1)
    print(json.dumps(r, ensure_ascii=False, indent=2))
"

# 获取当前用户信息
uv run python -c "
import os, json, sys
sys.path.insert(0, '.')
from scripts.client import XhsClient
with XhsClient.from_env() as c:
    print(json.dumps(c.get_self_info(), ensure_ascii=False, indent=2))
"
```

---

## API 方法速查

### 用户

| 方法 | 说明 |
|------|------|
| `get_self_info()` | 获取当前登录用户信息 |
| `get_user_info(user_id)` | 获取指定用户主页信息 |
| `get_user_notes(user_id, cursor="")` | 获取用户发布的笔记列表 |

### 搜索

| 方法 | 说明 |
|------|------|
| `search_notes(keyword, page=1, sort="general", note_type=0)` | 搜索笔记 |
| `search_users(keyword, page=1)` | 搜索用户 |
| `search_topics(keyword)` | 搜索话题/标签 |

`sort` 可选：`"general"` / `"popularity_descending"` / `"time_descending"`
`note_type` 可选：`0`=全部 / `1`=视频 / `2`=图文

### 笔记

| 方法 | 说明 |
|------|------|
| `get_note_by_id(note_id, xsec_token="")` | 获取笔记详情 |
| `get_comments(note_id, cursor="", xsec_token="")` | 获取评论（单页） |
| `get_all_comments(note_id, xsec_token="", max_pages=20)` | 自动翻页获取全部评论 |
| `get_sub_comments(note_id, comment_id, cursor="", xsec_token="")` | 获取评论回复 |

### Feed / 发现

| 方法 | 说明 |
|------|------|
| `get_home_feed(category="homefeed_recommend")` | 推荐 Feed |
| `get_hot_feed(category="homefeed.food_v3")` | 热门笔记（按分类） |

热门分类：`fashion_v3` / `food_v3` / `cosmetics_v3` / `movie_and_tv_v3` /
`career_v3` / `love_v3` / `household_product_v3` / `gaming_v3` / `travel_v3` / `fitness_v3`

### 社交

| 方法 | 说明 |
|------|------|
| `follow_user(user_id)` | 关注用户 |
| `unfollow_user(user_id)` | 取消关注 |
| `get_user_favorites(user_id, cursor="")` | 获取用户收藏夹 |

### 互动

| 方法 | 说明 |
|------|------|
| `like_note(note_id, xsec_token="")` | 点赞 |
| `unlike_note(note_id, xsec_token="")` | 取消点赞 |
| `collect_note(note_id, xsec_token="")` | 收藏 |
| `uncollect_note(note_id, xsec_token="")` | 取消收藏 |
| `post_comment(note_id, content, xsec_token="")` | 发表评论 |
| `reply_comment(note_id, comment_id, content, xsec_token="")` | 回复评论 |
| `delete_comment(note_id, comment_id)` | 删除自己的评论 |

### 通知

| 方法 | 说明 |
|------|------|
| `get_unread_count()` | 未读通知数 |
| `get_notifications_mentions(cursor="")` | 评论 / @ 通知 |
| `get_notifications_likes(cursor="")` | 点赞 / 收藏通知 |
| `get_notifications_connections(cursor="")` | 新增关注通知 |

### 创作者

| 方法 | 说明 |
|------|------|
| `get_my_notes(page=0)` | 获取自己发布的笔记列表 |
| `delete_note(note_id)` | 删除笔记（实验性） |

---

## 错误处理

```python
from scripts.exceptions import (
    NeedVerifyError,    # 触发验证码（HTTP 461/471）
    SessionExpiredError, # Cookie 过期（code -100）
    IpBlockedError,     # IP 被封（code 300012）
    SignatureError,     # 签名失败（code 300015）
    XhsApiError,        # 其他 API 错误（基类）
)

try:
    result = client.search_notes("美食")
except NeedVerifyError:
    print("触发验证码，请在浏览器完成验证后重试")
except SessionExpiredError:
    print("Cookie 已过期，请重新获取")
except IpBlockedError:
    print("IP 被封，请更换网络")
except XhsApiError as e:
    print(f"API 错误：{e}（code={e.code}）")
```

---

## 反风控机制

本技能继承原仓库的完整反风控实现：

- **高斯抖动**：请求间隔使用截断高斯分布（非固定间隔），模拟真实浏览节奏
- **随机长停顿**：约 5% 的请求额外等待 2~5 秒，模拟阅读行为
- **指数退避**：HTTP 429/5xx 自动重试（最多 3 次）
- **验证码冷却**：触发验证码后自动等待 5→10→20→30 秒，并永久加倍请求间隔
- **浏览器指纹一致性**：macOS Chrome UA、session 级 GPU/分辨率/CPU 固定
- **完整签名**：`x-s` / `x-s-common` / `x-t` 签名（逆向自 Web 客户端）

---

## 注意事项

- Cookie 有效期通常为数天至数周，过期后需重新通过 `browser_use get_cookies` 获取
- 建议使用专用账号，避免主账号被风控
- 写操作（评论、点赞等）风控风险高于读操作，请酌情使用
- `get_all_comments` 默认最多翻 20 页，可通过 `max_pages` 调整
