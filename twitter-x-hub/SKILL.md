---
name: twitter-x-hub
description: >
  使用 Python + UV 读写 Twitter/X 数据的技能，零第三方依赖（纯标准库），通过直接传入
  auth_token + ct0 Cookie 完成认证。在 Minis 环境中，Cookie 可通过 browser_use 工具
  导航到 x.com 后用 get_cookies 动作自动获取，无需手动复制。支持抓取主页时间线、关注列表、
  书签、搜索、用户资料、用户推文、点赞、推文详情、List 时间线、粉丝/关注列表，以及发推、
  删推、点赞、转推、收藏等写操作。当用户提到"抓取 Twitter 数据"、"获取 X 推文"、
  "Twitter 时间线"、"X 书签"、"搜索推文"、"twitter-x-hub"、"用 Cookie 请求 Twitter"、
  "Twitter GraphQL"，或任何需要以编程方式读写 Twitter/X 数据的场景，必须触发本技能。
---

# twitter-x-hub

> **改造来源**：[jackwener/twitter-cli](https://github.com/jackwener/twitter-cli)
> 本技能对原仓库做了以下简化：移除 `browser-cookie3`/`rich`/`click`/`PyYAML` 依赖，
> 改为纯标准库实现；认证方式改为直接传入 Cookie，不做浏览器自动提取。

---

## 文件结构

```
/var/minis/skills/twitter-x-hub/
├── SKILL.md
├── pyproject.toml              # UV 项目配置（零第三方依赖）
└── scripts/
    ├── __init__.py
    ├── models.py               # 数据模型（Tweet, Author, Metrics, UserProfile…）
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
2. `browser_use get_cookies` 过滤 `auth_token`，再过滤 `ct0`
   - 工具会返回一个 offload env 文件路径（如 `/var/minis/offloads/env_cookies_xxx.sh`）
   - **Cookie 原始值不会出现在对话中**，通过 `. <env_file>` 加载到 shell 环境变量
3. 加载后即可直接使用环境变量调用脚本：
```bash
. /var/minis/offloads/env_cookies_xxx.sh
# 文件内已导出 COOKIE_AUTH_TOKEN / COOKIE_CT0 等变量，按实际变量名使用
export TWITTER_AUTH_TOKEN="$COOKIE_AUTH_TOKEN"
export TWITTER_CT0="$COOKIE_CT0"
```

> **注意**：`get_cookies` 仅对当前页面的域名生效，需先 navigate 到 `https://x.com` 再调用。

### 方法二：手动从浏览器 DevTools 获取

1. 登录 x.com，打开 DevTools → Application → Cookies → `https://x.com`
2. 找到 `auth_token` 和 `ct0` 的值，复制后存入 Minis 环境变量（Settings → Environments）

### 传入方式（三种，优先级从高到低）

1. 环境变量：`TWITTER_AUTH_TOKEN` + `TWITTER_CT0`（推荐，避免明文出现在命令行）
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
uv run python -m scripts.cli feed \
  --auth-token <auth_token> --ct0 <ct0>

# 抓取 Following 时间线，50条，JSON 输出
uv run python -m scripts.cli feed --type following --max 50 --json \
  --auth-token <auth_token> --ct0 <ct0>

# 搜索推文（Top/Latest/Photos/Videos）
uv run python -m scripts.cli search "Claude Code" --tab Latest --max 30 \
  --auth-token <auth_token> --ct0 <ct0>

# 书签
uv run python -m scripts.cli bookmarks --max 50 \
  --auth-token <auth_token> --ct0 <ct0>

# 用户资料
uv run python -m scripts.cli user elonmusk \
  --auth-token <auth_token> --ct0 <ct0>

# 用户推文
uv run python -m scripts.cli user-posts elonmusk --max 20 \
  --auth-token <auth_token> --ct0 <ct0>

# 推文详情（含回复线程）
uv run python -m scripts.cli tweet 1234567890 \
  --auth-token <auth_token> --ct0 <ct0>

# List 时间线
uv run python -m scripts.cli list 1539453138322673664 \
  --auth-token <auth_token> --ct0 <ct0>

# 粉丝 / 关注列表（需先用 user 命令获取 user_id）
uv run python -m scripts.cli followers <user_id> --max 50 \
  --auth-token <auth_token> --ct0 <ct0>

# 发推 / 回复
uv run python -m scripts.cli post "Hello from twitter-fetch!" \
  --auth-token <auth_token> --ct0 <ct0>
uv run python -m scripts.cli post "reply text" --reply-to 1234567890 \
  --auth-token <auth_token> --ct0 <ct0>

# 点赞 / 转推 / 收藏
uv run python -m scripts.cli like 1234567890 --auth-token <auth_token> --ct0 <ct0>
uv run python -m scripts.cli retweet 1234567890 --auth-token <auth_token> --ct0 <ct0>
uv run python -m scripts.cli bookmark 1234567890 --auth-token <auth_token> --ct0 <ct0>
```

### 用环境变量省去每次传参

```bash
export TWITTER_AUTH_TOKEN="xxxx"
export TWITTER_CT0="yyyy"

uv run python -m scripts.cli feed --max 30 --json
```

### 作为 Python 库调用

```python
import os, json
from scripts.client import TwitterClient

client = TwitterClient(
    auth_token=os.environ["TWITTER_AUTH_TOKEN"],
    ct0=os.environ["TWITTER_CT0"],
)

# 抓取首页时间线
tweets = client.fetch_home_timeline(count=20)
for t in tweets:
    print(f"@{t.author.screen_name}: {t.text[:80]}")
    print(f"  ❤️ {t.metrics.likes}  🔁 {t.metrics.retweets}  👁 {t.metrics.views}")

# 搜索
results = client.fetch_search("AI agent", count=10, product="Latest")

# 用户资料
user = client.fetch_user("elonmusk")
print(user.followers_count)

# JSON 序列化（dataclass → dict）
import dataclasses
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

### 分页 & 限流
- 每次响应携带 `cursor`，自动翻页直到达到 `count` 上限
- 请求间隔默认 1.5 秒，HTTP 429 / error code 88 触发指数退避重试

---

## CLI 子命令速查

| 子命令 | 说明 | 关键参数 |
|--------|------|----------|
| `feed` | 主页时间线 | `--type for-you\|following`, `--max`, `--json` |
| `bookmarks` | 书签 | `--max`, `--json` |
| `search` | 搜索 | `query`, `--tab Top\|Latest\|Photos\|Videos`, `--max`, `--json` |
| `user` | 用户资料 | `screen_name`, `--json` |
| `user-posts` | 用户推文 | `screen_name`, `--max`, `--json` |
| `user-likes` | 用户点赞 | `screen_name`, `--max`, `--json` |
| `tweet` | 推文详情+回复 | `tweet_id`, `--max`, `--json` |
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

## 生成 CLI 脚本

如果 `scripts/cli.py` 尚未创建，执行以下步骤让 AI 生成：

1. 确认 `client.py` 和 `models.py` 已存在于 `/var/minis/skills/twitter-x-hub/scripts/`
2. 告知 AI："请根据 twitter-x-fetch skill 的 CLI 速查表，生成 `cli.py`（使用 argparse，支持从环境变量读取 auth_token/ct0）"

---

## 注意事项

- Cookie 有效期通常数周至数月，过期后需重新从浏览器获取
- 建议使用专用小号，避免主账号被风控
- 写操作（发推、点赞等）风控风险高于读操作，请酌情使用
- `max_count` 硬上限为 500，防止意外大量请求
