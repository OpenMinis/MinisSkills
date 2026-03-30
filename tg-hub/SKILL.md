---
name: tg-hub
description: >
  使用 Python + UV 读写 Telegram 数据的技能，仅依赖 telethon，本地优先架构（消息同步到
  SQLite 后离线查询）。首次使用需在 terminal 中完成手机号验证码登录，之后 session 持久化免登录。
  支持同步群/频道消息到本地、关键词搜索、多关键词过滤、今日消息、最近消息、发言排行、时间线统计等。
  当用户提到"Telegram"、"TG"、"电报"、"tg-hub"、"同步 Telegram 消息"、"搜索 TG 群"、
  "Telegram 关键词"、"获取 TG 消息"，或任何需要以编程方式读写 Telegram 数据的场景，必须触发本技能。
---

# tg-hub

> **改造来源**：[jackwener/tg-cli](https://github.com/jackwener/tg-cli)（Apache-2.0）
>
> 本技能在原仓库基础上做了以下简化：
> - 移除 `click` / `rich` / `python-dotenv` / `pyyaml` 依赖
> - 仅保留 `telethon` 一个第三方依赖
> - 移除 CLI 层，所有功能封装为同步 Python API
> - 默认 session/db 路径改为 `/var/minis/workspace/tg-hub/`
> - 配置改为直接读取环境变量，无需 `.env` 文件

---

## 架构特点：本地优先（Local-First）

```
Telegram MTProto（telethon）
    ↓  sync / refresh（增量）
本地 SQLite  ~/.tg-hub/messages.db
    ↓  search / today / recent / filter（离线）
结构化数据
```

- **读操作**（search/today/recent）：查本地 SQLite，**不联网**，毫秒级响应
- **写操作**（sync/refresh）：连接 Telegram 拉取新消息，增量写入 SQLite
- Session 文件：`~/.tg-hub/tg_hub.session`

---

## 文件结构

```
/var/minis/skills/tg-hub/
├── SKILL.md
├── pyproject.toml          # 仅 telethon
└── scripts/
    ├── __init__.py
    ├── config.py           # 配置（环境变量 / 默认路径）
    ├── db.py               # SQLite 消息存储
    ├── exceptions.py       # 结构化异常
    └── client.py           # TGClient 核心类（全部 API）
```

---

## 首次登录（必须在 Terminal 中操作）

tg-hub 使用 **MTProto 协议**（非 Bot API），需要用你的 Telegram 账号登录。

> **建议**：优先使用你自己的 `TG_API_ID` / `TG_API_HASH`。
> 我已按上游 tg-cli 的反风控实现同步：使用 Telegram Desktop 5.x 指纹，并在继续使用默认 `api_id=2040` 时给出 warning。公共 APP ID 仅作兜底，长期仍建议使用自有凭证。

```
1. 打开 Terminal
2. （推荐）先设置自己的 TG_API_ID / TG_API_HASH
3. cd /var/minis/skills/tg-hub
4. uv run python -c "
   import sys; sys.path.insert(0,'.')
   from scripts.client import TGClient
   me = TGClient().login()
   print('登录成功：', me)
   "
5. 按提示输入手机号（+86XXXXXXXXXX 格式）
6. 输入 Telegram App 收到的验证码
7. 登录成功后 session 自动保存，后续免登录
```

> 如暂时没有自己的凭证，可先用内置公共凭证登录；如遇登录/拉取异常，优先切换为自己的 APP ID。

[打开 Terminal 登录](minis://open_terminal?init_command=cd%20%2Fvar%2Fminis%2Fskills%2Ftg-hub%20%26%26%20uv%20run%20python%20-c%20%22import%20sys%3B%20sys.path.insert(0%2C'.')%3B%20from%20scripts.client%20import%20TGClient%3B%20TGClient().login()%22)

---

## 快速使用

### 环境准备

```bash
cd /var/minis/skills/tg-hub
uv sync
```

### Python 调用

```python
import sys
sys.path.insert(0, "/var/minis/skills/tg-hub")
from scripts.client import TGClient

client = TGClient()

# 查看当前账号
me = client.whoami()
print(me["name"], me["phone"])

# 列出所有对话（实时从 TG 获取）
chats = client.list_chats()
for c in chats[:10]:
    print(f"  [{c['type']}] {c['name']}  未读: {c['unread']}")

# 增量同步单个群
n = client.sync("群名或用户名", limit=1000)
print(f"新增 {n} 条消息")

# 快速刷新所有群（每群最多 500 条新消息）
# 默认带轻微节流；也可以限制本轮只刷前 30 个 chat
result = client.refresh(delay=1.0, max_chats=30)
for name, count in result.items():
    if count > 0:
        print(f"  {name}: +{count}")

# 搜索关键词
msgs = client.search("Python", hours=48)
for m in msgs:
    print(f"[{m['chat_name']}] {m['sender_name']}: {m['content'][:80]}")

# 多关键词过滤（OR 逻辑）
msgs = client.filter("招聘,remote,兼职", hours=24)

# 今日消息
msgs = client.today()

# 最近 12 小时消息
msgs = client.recent(hours=12, limit=200)

# 发言排行
top = client.top_senders(hours=24)
for t in top[:5]:
    print(f"  {t['sender_name']}: {t['msg_count']} 条")

# 时间线统计
tl = client.timeline(granularity="hour", hours=48)

# 本地数据库统计
stats = client.stats()
print(f"本地共 {stats['total']} 条消息，{len(stats['chats'])} 个群")
```

---

## API 速查

### 认证

| 方法 | 说明 |
|------|------|
| `login()` | 交互式登录（首次，需 terminal） |
| `whoami()` | 获取当前账号信息 |

### 同步（联网）

| 方法 | 说明 |
|------|------|
| `list_chats(chat_type=None)` | 列出所有对话（实时） |
| `sync(chat, limit=5000)` | 同步单个群到本地 SQLite |
| `sync_all(limit_per_chat=5000, delay=1.0, max_chats=None)` | 同步所有群（带节流/数量限制） |
| `refresh(limit_per_chat=500, delay=1.0, max_chats=None)` | 快速增量刷新（推荐日常使用） |

### 查询（本地，不联网）

| 方法 | 说明 |
|------|------|
| `search(keyword, *, chat, sender, hours, regex, limit)` | 关键词/正则搜索 |
| `filter(keywords, *, chat, hours)` | 多关键词 OR 过滤 |
| `today(chat=None)` | 今日消息 |
| `recent(hours=24, *, chat, sender, limit)` | 最近 N 小时消息 |
| `top_senders(chat, hours, limit)` | 发言排行 |
| `timeline(chat, hours, granularity)` | 时间线统计 |
| `stats()` | 数据库统计 |
| `local_chats()` | 本地已同步的群列表 |
| `delete_chat(chat)` | 删除某群的本地消息 |

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TG_API_ID` | `2040`（仅兜底） | **推荐改为你自己的** API ID |
| `TG_API_HASH` | 内置（仅兜底） | **推荐改为你自己的** API Hash |
| `TG_SESSION_NAME` | `tg_hub` | Session 文件名 |
| `TG_DATA_DIR` | `~/.tg-hub` | 数据目录 |
| `TG_DB_PATH` | `{TG_DATA_DIR}/messages.db` | SQLite 路径 |
| `TG_DEVICE_MODEL` | `Desktop` | Telethon 客户端设备型号 |
| `TG_SYSTEM_VERSION` | `macOS 15.3` | Telethon 客户端系统版本 |
| `TG_APP_VERSION` | `5.12.1` | Telethon 客户端版本 |
| `TG_LANG_CODE` | `en` | 客户端语言代码 |
| `TG_SYSTEM_LANG_CODE` | `en-US` | 系统语言代码 |

---

## 账号安全建议

1. **优先使用自己的 API 凭证**：前往 `https://my.telegram.org` 创建应用后设置 `TG_API_ID` / `TG_API_HASH`。
2. **控制同步频率**：避免高频反复执行 `refresh()`。
3. **使用 `delay` 和 `max_chats`**：建议日常增量刷新时限制每轮同步数量，并保留 chat 之间的间隔。
4. **首次全量同步不要太激进**：tg-hub 已对首次同步 chat 自动限制更低的抓取量。
5. **优先读操作**：搜索/统计等本地查询不联网，风险远低于频繁同步。

---

## 注意事项

- 首次登录必须在交互式 terminal 中完成（需要输入验证码）
- **强烈建议优先使用自己的 `TG_API_ID` / `TG_API_HASH`**，避免公共 APP ID 被滥用带来的风控问题
- tg-hub 已对齐上游 tg-cli 的 Telegram Desktop 5.x 客户端指纹，并保留环境变量覆盖能力，用于降低异常指纹风险
- 若仍使用默认 `api_id=2040`，连接时会打印 warning，提醒改用自己的 `TG_API_ID` / `TG_API_HASH`
- Session 文件保存在 `/var/minis/workspace/tg-hub/tg_hub.session`，妥善保管
- `sync_all` 首次运行时间较长（取决于群数量和历史消息量）
- 建议用 `refresh()` 做日常增量更新，用 `sync(chat, limit=10000)` 做首次全量同步
- Telegram 对 API 请求有频率限制，大量同步时 telethon 会自动处理 flood wait
