---
name: twitter-x-hub
description: >
  使用 Python + UV 读写 Twitter/X 数据的技能，零第三方依赖（纯标准库），通过直接传入
  auth_token + ct0 Cookie 完成认证。在 Minis 环境中，Cookie 可通过 browser_use 工具
  导航到 x.com 后用 get_cookies 动作自动获取，无需手动复制。支持抓取主页时间线、关注列表、
  书签（含书签文件夹）、搜索、用户资料、用户推文、点赞、推文详情（单条/含回复）、List 时间线、
  粉丝/关注列表，以及发推、删推、点赞、转推、收藏等写操作。当用户提到"抓取 Twitter 数据"、
  "获取 X 推文"、"Twitter 时间线"、"X 书签"、"搜索推文"、"twitter-x-hub"、
  "用 Cookie 请求 Twitter"、"Twitter GraphQL"，或任何需要以编程方式读写 Twitter/X
  数据的场景，必须触发本技能。
---

# twitter-x-hub

> **改造来源**：[public-clis/twitter-cli](https://github.com/public-clis/twitter-cli)（原 jackwener/twitter-cli）
> 本技能对原仓库做了以下简化：移除 `browser-cookie3`/`rich`/`click`/`PyYAML`/`curl_cffi`/
> `xclienttransaction`/`beautifulsoup4` 依赖，改为纯标准库实现；认证方式改为直接传入 Cookie，
> 不做浏览器自动提取；移除 Twitter Article 渲染和图片上传功能。

---

## 文件结构

```
/var/minis/skills/twitter-x-hub/
├── SKILL.md
├── pyproject.toml              # UV 项目配置（零第三方依赖）
└── scripts/
    ├── __init__.py
    ├── models.py               # 数据模型（Tweet, Author, Metrics, UserProfile, BookmarkFolder）
    ├── parser.py               # GraphQL 响应解析（从 client.py 拆出，同步自上游 v0.8.6）
    ├── client.py               # GraphQL 客户端（核心逻辑）
    └── cli.py                  # 命令行入口（argparse）
```

---

## 认证方式

Twitter/X 内部 GraphQL API 使用两个 Cookie 做认证：

| Cookie | 说明 |
|--------|------|
| `auth_token` | 用户登录凭证（OAuth Session Token） |
| `ct0` | CSRF Token，同时作为 `X-Csrf-Token` 请求头 |

### 方法一：browser_use 工具自动获取（推荐，Minis 环境首选）

在 Minis 中可直接用 `browser_use` 工具导航到 x.com，再用 `get_cookies` 动作读取 Cookie，
无需手动复制。**获取后应立即存入环境变量**，避免明文出现在对话上下文中。

操作步骤：
1. `browser_use navigate` 打开 `https://x.com`，确认已登录
2. `browser_use get_cookies` 获取所有 cookie
   - 工具返回 offload env 文件路径（如 `/var/minis/offloads/env_cookies_xxx.sh`）
   - **Cookie 原始值不会出现在对话中**
3. 加载后即可使用：
```bash
. /var/minis/offloads/env_cookies_xxx.sh
export TWITTER_AUTH_TOKEN="$COOKIE_AUTH_TOKEN"
export TWITTER_CT0="$COOKIE_CT0"
```

### 方法二：手动设置环境变量

从浏览器 DevTools → Application → Cookies → `https://x.com` 复制 `auth_token` 和 `ct0`，
存入 Minis 环境变量（Settings → Environments）：`TWITTER_AUTH_TOKEN` + `TWITTER_CT0`

### 传入方式（三种，优先级从高到低）

1. 环境变量：`TWITTER_AUTH_TOKEN` + `TWITTER_CT0`（推荐）
2. CLI 参数：`--auth-token <value> --ct0 <value>`
3. 代码直接传入：`TwitterClient(auth_token=..., ct0=...)`

---

## 快速使用

### 环境准备

```bash
# 确认 UV 可用
which uv || pip install uv

# 进入 skill 目录
cd /var/minis/skills/twitter-x-hub
```

### CLI 用法

```bash
# 抓取首页 For-You 时间线（默认20条）
uv run python -m scripts.cli feed

# 抓取 Following 时间线，30条，JSON 输出
uv run python -m scripts.cli feed --type following --max 30 --json

# 搜索推文（Top/Latest/Photos/Videos）
uv run python -m scripts.cli search "Claude Code" --tab Latest --max 20

# 书签
uv run python -m scripts.cli bookmarks --max 50

# 书签文件夹列表（新增）
uv run python -m scripts.cli bookmark-folders

# 用户资料
uv run python -m scripts.cli user elonmusk

# 用户推文
uv run python -m scripts.cli user-posts elonmusk --max 20

# 用户点赞
uv run python -m scripts.cli user-likes elonmusk --max 20

# 推文详情（含回复线程）
uv run python -m scripts.cli tweet 1234567890

# 单条推文快速获取（新增，比 tweet 命令快）
uv run python -m scripts.cli tweet-by-id 1234567890

# List 时间线
uv run python -m scripts.cli list 1539453138322673664

# 粉丝 / 关注列表（需先用 user 命令获取 user_id）
uv run python -m scripts.cli followers <user_id> --max 50
uv run python -m scripts.cli following <user_id> --max 50

# 发推 / 回复
uv run python -m scripts.cli post "Hello from twitter-x-hub!"
uv run python -m scripts.cli post "reply text" --reply-to 1234567890

# 点赞 / 转推 / 收藏
uv run python -m scripts.cli like 1234567890
uv run python -m scripts.cli retweet 1234567890
uv run python -m scripts.cli bookmark 1234567890
```

### 用环境变量省去每次传参

```bash
export TWITTER_AUTH_TOKEN="xxxx"
export TWITTER_CT0="yyyy"

uv run python -m scripts.cli feed --max 30 --json
```

### 作为 Python 库调用

```python
import os, json, dataclasses
from scripts.client import TwitterClient

client = TwitterClient(
    auth_token=os.environ["TWITTER_AUTH_TOKEN"],
    ct0=os.environ["TWITTER_CT0"],
)

# 抓取首页时间线
tweets = client.fetch_home_timeline(count=20)
for t in tweets:
    print(f"@{t.author.screen_name}: {t.text[:80]}")
    print(f"  ❤️ {t.metrics.likes}  🔁 {t.metrics.retweets}  👁 {t.metrics.views}  🔖 {t.metrics.bookmarks}")

# 搜索（Latest tab）
results = client.fetch_search("AI agent", count=10, product="Latest")

# 单条推文（快速，无回复）
tweet = client.fetch_tweet_by_id("1234567890")

# 书签文件夹
folders = client.fetch_bookmark_folders()

# 用户资料
user = client.fetch_user("elonmusk")
print(user.id, user.followers_count)

# JSON 序列化
data = [dataclasses.asdict(t) for t in tweets]
print(json.dumps(data, ensure_ascii=False, indent=2))
```

---

## 核心实现原理

### 认证机制
使用浏览器 Cookie（`auth_token` + `ct0`）+ 硬编码公共 Bearer Token，
伪装成 Chrome 浏览器请求 Twitter 内部 GraphQL API。

### QueryId 三级解析（自动应对接口变动）
```
1. 内存缓存（最快）
2. 硬编码 FALLBACK_QUERY_IDS（常量兜底）
   → 若 404，说明 queryId 已过期，进入下一级
3. 从 github.com/fa0311/twitter-openapi 拉取最新 queryId
   → 还没有则扫描 x.com JS Bundle 用正则提取
```

### URL 优化（同步自上游 v0.8）
- features 字典中值为 `False` 的 key 不发送，避免 URL 过长（414 错误）

### 分页 & 限流
- 每次响应携带 `cursor`，自动翻页直到达到 `count` 上限
- 请求间隔默认 1.5 秒 + ±30% 随机抖动，HTTP 429 触发指数退避重试
- 写操作延迟 1.5~4 秒随机

### 解析器拆分（同步自上游 v0.7+）
- `parser.py` 从 `client.py` 拆出，包含 `parse_tweet_result`、`parse_timeline_response`、
  `parse_user_result` 等独立函数，便于单元测试和复用

---

## CLI 子命令速查

| 子命令 | 说明 | 关键参数 |
|--------|------|----------|
| `feed` | 主页时间线 | `--type for-you\|following`, `--max`, `--json` |
| `bookmarks` | 书签 | `--max`, `--json` |
| `bookmark-folders` | 书签文件夹列表 ⭐新增 | `--json` |
| `search` | 搜索 | `query`, `--tab Top\|Latest\|Photos\|Videos`, `--max`, `--json` |
| `user` | 用户资料 | `screen_name`, `--json` |
| `user-posts` | 用户推文 | `screen_name`, `--max`, `--json` |
| `user-likes` | 用户点赞 | `screen_name`, `--max`, `--json` |
| `tweet` | 推文详情+回复 | `tweet_id`, `--max`, `--json` |
| `tweet-by-id` | 单条推文（快速）⭐新增 | `tweet_id`, `--json` |
| `list` | List 时间线 | `list_id`, `--max`, `--json` |
| `followers` | 粉丝列表 | `user_id`, `--max`, `--json` |
| `following` | 关注列表 | `user_id`, `--max`, `--json` |
| `post` | 发推 | `text`, `--reply-to` |
| `delete` | 删推 | `tweet_id` |
| `like` / `unlike` | 点赞/取消 | `tweet_id` |
| `retweet` / `unretweet` | 转推/取消 | `tweet_id` |
| `bookmark` / `unbookmark` | 收藏/取消 | `tweet_id` |

所有子命令均支持 `--auth-token` / `--ct0` 参数，也可通过环境变量替代。

---

## 变更日志（同步自上游）

### v0.8.6 同步（2026-04-08）
- **QueryId 全量更新**：从 x.com JS bundle（main.0e98bc8a.js）实时扫描，更新了
  HomeTimeline、HomeLatestTimeline、UserTweets、SearchTimeline、Likes、TweetDetail、
  TweetResultByRestId、ListLatestTweetsTimeline、Followers、Following、CreateTweet 等全部 ID
- **新增 QueryId**：`TweetResultByRestId`、`BookmarkFoldersSlice`、`BookmarkFolderTimeline`
- **新增命令**：`tweet-by-id`（单条推文快速获取）、`bookmark-folders`（书签文件夹）
- **models.py**：`Metrics` 新增 `bookmarks` 字段；`Tweet` 新增 `article_title`、
  `article_text`、`is_subscriber_only` 字段；新增 `BookmarkFolder` dataclass
- **parser.py**：从 `client.py` 拆出为独立模块；修复新 API 结构（`core.name`/`core.screen_name`）；
  `parse_tweet_result` 支持 `note_tweet` 全文（长推文"显示更多"）；
  新增 `_unwrap_visibility` 处理 `TweetWithVisibilityResults`；
  `parse_user_result` 修复 `joined` 日期从 `core.created_at` 读取
- **URL 优化**：features 中 False 值不发送，避免 414 错误
- **SearchTimeline 限制**：X 从 2025 年底开始要求 `x-client-transaction-id` header，
  该 header 由 `xclienttransaction`（C 扩展）生成，在 iSH/Alpine 环境无法安装，
  因此 `search` 命令在本环境暂不可用；替代方案：用 `browser_use` 导航到搜索页面提取 DOM

---

## 注意事项

- Cookie 有效期通常数周至数月，过期后需重新从浏览器获取
- 建议使用专用小号，避免主账号被风控
- 写操作（发推、点赞等）风控风险高于读操作，请酌情使用
- `max_count` 硬上限为 500，防止意外大量请求
- 上游依赖 `curl_cffi` 做 TLS 指纹伪装，本 skill 使用 stdlib `urllib` 替代，
  遇到风控时可尝试通过 `cookie_string` 参数传入完整 Cookie 字符串增强指纹
