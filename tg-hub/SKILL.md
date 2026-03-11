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
本地 SQLite  /var/minis/workspace/tg-hub/messages.db
    ↓  search / today / recent / filter（离线）
结构化数据
```

- **读操作**（search/today/recent）：查本地 SQLite，**不联网**，毫秒级响应
- **写操作**（sync/refresh）：连接 Telegram 拉取新消息，增量写入 SQLite
- Session 文件：`/var/minis/workspace/tg-hub/tg_hub.session`

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

```
1. 打开 Terminal
2. cd /var/minis/skills/tg-hub
3. uv run python -c "
   import sys; sys.path.insert(0,'.')
   from scripts.client import TGClient
   me = TGClient().login()
   print('登录成功：', me)
   "
4. 按提示输入手机号（+86XXXXXXXXXX 格式）
5. 输入 Telegram App 收到的验证码
6. 登录成功后 session 自动保存，后续免登录
```

> **注意**：使用内置的 Telegram Desktop 公共凭证（`api_id=2040`），无需自己申请 API。
> 如需使用自己的凭证，设置环境变量 `TG_API_ID` 和 `TG_API_HASH`。

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
result = client.refresh()
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
| `sync_all(limit_per_chat=5000)` | 同步所有群 |
| `refresh(limit_per_chat=500)` | 快速增量刷新（推荐日常使用） |

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
| `TG_API_ID` | `2040`（Telegram Desktop） | 自定义 API ID |
| `TG_API_HASH` | 内置 | 自定义 API Hash |
| `TG_SESSION_NAME` | `tg_hub` | Session 文件名 |
| `TG_DATA_DIR` | `/var/minis/workspace/tg-hub` | 数据目录 |
| `TG_DB_PATH` | `{TG_DATA_DIR}/messages.db` | SQLite 路径 |

---

## 注意事项

- 首次登录必须在交互式 terminal 中完成（需要输入验证码）
- Session 文件保存在 `/var/minis/workspace/tg-hub/tg_hub.session`，妥善保管
- `sync_all` 首次运行时间较长（取决于群数量和历史消息量）
- 建议用 `refresh()` 做日常增量更新，用 `sync(chat, limit=10000)` 做首次全量同步
- Telegram 对 API 请求有频率限制，大量同步时 telethon 会自动处理 flood wait
