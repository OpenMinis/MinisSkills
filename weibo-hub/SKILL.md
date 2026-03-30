---
name: weibo-hub
description: >
  使用 Python + UV 读写微博（Weibo）数据的技能，仅依赖 httpx，通过 browser_use get_cookies
  自动获取 Cookie 完成认证，无需手动复制。支持热搜榜、热门 Feed、关注 Feed、关键词搜索、
  微博详情/评论/转发、用户资料/微博/关注/粉丝列表等。
  当用户提到"微博"、"weibo"、"weibo-hub"、"微博热搜"、"抓取微博"、"搜索微博"、
  "微博评论"、"微博用户"，或任何需要以编程方式读写微博数据的场景，必须触发本技能。
---

# weibo-hub

> **改造来源**：[jackwener/weibo-cli](https://github.com/jackwener/weibo-cli)（Apache-2.0）
>
> 本技能在原仓库基础上做了以下精简：
> - **移除** `click` / `rich` / `browser-cookie3` / `qrcode` / `pyyaml` 依赖
> - **仅保留** `httpx` 一个第三方依赖
> - **移除** CLI 层，所有功能封装为同步 Python API
> - **认证改为** `browser_use get_cookies` 提取 → 调用 `setup_credential()` 保存
> - 数据目录改为 `/var/minis/workspace/weibo-hub/`

---

## 文件结构

```
/var/minis/skills/weibo-hub/
├── SKILL.md
├── pyproject.toml          # 仅 httpx
└── scripts/
    ├── __init__.py
    ├── constants.py        # API 端点、Headers、路径常量
    ├── exceptions.py       # WeiboError 异常体系
    ├── auth.py             # Credential 持久化（无 browser-cookie3）
    └── client.py           # WeiboClient 核心类（全部 API）
```

---

## 认证流程（每次使用前检查）

weibo-hub 使用 **浏览器 Cookie 认证**，通过 `browser_use get_cookies` 从 weibo.com 提取，
无需 `browser-cookie3`，无需 QR 扫码。

### Step 1：用 browser_use 提取 Cookie

```python
# 在 agent 中调用：
browser_use(action="navigate", url="https://weibo.com")
# 确保已登录后：
browser_use(action="get_cookies", url="https://weibo.com")
# 将返回的 offload env 文件路径记录下来
```

### Step 2：从 env 文件读取并保存凭证

```python
import sys, os, subprocess, json

# 加载 Cookie 环境变量（路径来自 get_cookies 返回的 offload 文件）
env_file = "/var/minis/offloads/env_cookies_xxx.sh"   # 替换为实际路径
result = subprocess.run(
    f". {env_file} && python3 -c \"import os,json; print(json.dumps(dict(os.environ)))\"",
    shell=True, capture_output=True, text=True
)
env = json.loads(result.stdout)

# 解析出 Cookie 字典（COOKIE_ 前缀变量）
cookies = {
    k[len("COOKIE_"):]: v
    for k, v in env.items()
    if k.startswith("COOKIE_")
}

# 保存凭证
sys.path.insert(0, "/var/minis/skills/weibo-hub")
from scripts.client import WeiboClient
WeiboClient.setup_credential(cookies)
```

> **关键 Cookie**：`SUB`、`SUBP`（必须），其余越多越好。
> 凭证保存到 `/var/minis/workspace/weibo-hub/credential.json`，有效期 7 天，到期自动提示。

---

## 环境准备

```bash
cd /var/minis/skills/weibo-hub
uv sync
```

---

## 快速使用

```python
import sys
sys.path.insert(0, "/var/minis/skills/weibo-hub")
from scripts.client import WeiboClient

with WeiboClient() as client:

    # ── 热搜 / 趋势（无需登录）──────────────────────────────
    topics = client.hot_search()          # 热搜榜（~52 条）
    for t in topics[:10]:
        print(f"#{t.get('realtime_hot_show_label','')} {t.get('word','')}")

    band = client.hot_band()              # 完整热搜榜
    trends = client.trending()            # 实时搜索推荐词

    # ── Feed（热门无需登录，关注需登录）─────────────────────
    hot = client.hot_feed(count=10)       # 热门时间线
    home = client.home_feed(count=20)     # 关注者时间线

    # ── 搜索（移动端 API）────────────────────────────────────
    results = client.search("人工智能", page=1)
    for w in results[:5]:
        print(w.get("text", "")[:80])

    # ── 微博详情 / 评论 / 转发（需要登录）──────────────────
    wb = client.detail("Qw06Kd98p")
    cmt = client.comments("微博ID", count=20)
    rep = client.reposts("微博ID", count=10)

    # ── 用户（需要登录）─────────────────────────────────────
    me = client.me()                      # 当前登录用户
    user = client.profile("1699432410")   # 指定用户资料
    weibos = client.user_weibos("1699432410", page=1)
    following = client.following("1699432410", page=1)
    followers = client.followers("1699432410", page=1)
```

---

## API 速查

### 无需登录（公开接口）

| 方法 | 说明 |
|------|------|
| `hot_search()` | 热搜榜 sidebar（~52 条） |
| `hot_band()` | 完整热搜榜 |
| `trending()` | 实时搜索推荐词 |
| `hot_feed(count, max_id)` | 热门时间线 |
| `search(keyword, page)` | 关键词搜索微博 |

### 需要登录（Cookie 认证）

| 方法 | 说明 |
|------|------|
| `me()` | 当前登录用户信息 |
| `home_feed(count, max_id)` | 关注者时间线 |
| `detail(mblogid)` | 单条微博详情 |
| `comments(weibo_id, count, max_id)` | 微博评论列表 |
| `reposts(weibo_id, page, count)` | 微博转发列表 |
| `profile(uid)` | 用户资料 |
| `user_weibos(uid, page, count)` | 用户微博列表 |
| `following(uid, page)` | 用户关注列表 |
| `followers(uid, page)` | 用户粉丝列表 |

### 认证

| 方法 | 说明 |
|------|------|
| `WeiboClient.setup_credential(cookies)` | 保存 Cookie 凭证（静态方法） |

---

## 反风控说明

与上游 weibo-cli 保持一致：
- **Gaussian 抖动**：每次请求间隔 = `request_delay + gauss(0.3, 0.15)`，约 1s
- **5% 长停顿**：随机触发 2–5s 额外延迟，模拟阅读行为
- **指数退避**：HTTP 429/5xx 最多重试 3 次，等待时间 2^n 秒
- **Chrome 145 UA**：桌面端 User-Agent，与浏览器指纹一致

---

## 注意事项

- 首次使用必须先调用 `WeiboClient.setup_credential(cookies)` 保存凭证
- 凭证文件：`/var/minis/workspace/weibo-hub/credential.json`，权限 0600
- 必要 Cookie：`SUB` + `SUBP`，缺失时 `setup_credential()` 会抛出 `ValueError`
- Cookie 7 天后自动提示过期，需重新提取
- 热搜/热门 Feed/搜索无需登录，profile/detail/home_feed 等需要有效 Cookie
- `search()` 使用移动端 API（`m.weibo.cn`），结果格式略有不同
