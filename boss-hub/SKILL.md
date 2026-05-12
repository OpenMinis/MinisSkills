---
name: boss-cli
description: >
  使用 boss-cli 操作 BOSS 直聘 — 搜索职位、查看推荐、管理投递、沟通过 Boss、给 HR 打招呼。
  当用户提到"BOSS 直聘"、"找工作"、"投简历"、"看职位"、"搜岗位"、"boss"、"打招呼"，
  或任何需要操作 BOSS 直聘的场景，必须触发本技能。
---

# boss-cli

> **来源**：[jackwener/boss-cli](https://github.com/jackwener/boss-cli)
> 本技能修改：移除 `browser-cookie3` 依赖，改为从环境变量读取 Cookie。

---

## 文件结构

```
/var/minis/skills/boss-cli/
├── SKILL.md
├── pyproject.toml
└── boss_cli/
    ├── __init__.py
    ├── cli.py          # Click 入口
    ├── client.py       # API 客户端（限速、重试）
    ├── auth.py         # 认证（环境变量 / QR 登录）
    ├── constants.py    # API 端点、过滤器代码
    ├── exceptions.py    # 异常类
    └── commands/       # 子命令
```

---

## 认证方式

### 方法一：环境变量传入 Cookie（推荐）

BOSS 直聘使用两个 Cookie：`wt2` 和 `wbg`。

设置方式：
1. 用 `browser_use` 工具打开 `https://www.zhipin.com` 并登录
2. 用 `get_cookies` 获取 `wt2` 和 `wbg` 的值
3. 存入 Minis 环境变量：
   - `BOSS_COOKIE`: 完整 cookie 字符串 `"wt2=xxx;wbg=xxx"`
   - 或 `BOSS_WT2` + `BOSS_WBG`: 分别设置

```bash
# 方式1：完整 cookie
export BOSS_COOKIE="wt2=xxxx;wbg=xxxx"

# 方式2：分开设置
export BOSS_WT2="xxxx"
export BOSS_WBG="xxxx"
```

### 方法二：QR 码登录

```bash
cd /var/minis/skills/boss-cli
uv run python -m boss_cli.cli login
```

---

## 快速使用

### 基本命令

```bash
cd /var/minis/skills/boss-cli

# 搜索职位
uv run python -m boss_cli.cli search "Python" --city 深圳

# 按薪资筛选
uv run python -m boss_cli.cli search "golang" --salary 20-30K

# 按经验筛选
uv run python -m boss_cli.cli search "前端" --exp 3-5年

# 按行业+规模筛选
uv run python -m boss_cli.cli search "后端" --industry 互联网 --scale 1000-9999人

# 查看推荐职位
uv run python -m boss_cli.cli recommend

# 按编号查看详情（3 = 上次搜索第3个结果）
uv run python -m boss_cli.cli show 3

# 查看职位详情
uv run python -m boss_cli.cli detail <securityId>

# 导出为 CSV
uv run python -m boss_cli.cli export "Python" -n 50 -o jobs.csv

# 导出为 JSON
uv run python -m boss_cli.cli export "golang" --format json -o jobs.json

# 查看已投递
uv run python -m boss_cli.cli applied

# 查看面试邀请
uv run python -m boss_cli.cli interviews

# 查看沟通过的 Boss
uv run python -m boss_cli.cli chat

# 打招呼
uv run python -m boss_cli.cli greet <securityId>

# 批量打招呼（自动 1.5s 延迟防风控）
uv run python -m boss_cli.cli batch-greet "golang" --city 杭州 -n 5

# 查看个人资料
uv run python -m boss_cli.cli me

# 查看支持的城市
uv run python -m boss_cli.cli cities
```

### 带环境变量的完整示例

```bash
# 设置 cookie 后搜索
export BOSS_WT2="你的wt2值"
export BOSS_WBG="你的wbg值"

cd /var/minis/skills/boss-cli
uv run python -m boss_cli.cli search "AI" --city 上海 --salary 30-50K
```

---

## 常用过滤器

| 参数 | 说明 | 示例 |
|------|------|------|
| `--city` | 城市 | `--city 深圳` |
| `--salary` | 薪资范围 | `--salary 20-30K` |
| `--exp` | 工作经验 | `--exp 3-5年` |
| `--degree` | 学历 | `--degree 本科` |
| `--industry` | 行业 | `--industry 互联网` |
| `--scale` | 公司规模 | `--scale 1000-9999人` |
| `--stage` | 融资阶段 | `--stage 已上市` |
| `--job-type` | 工作类型 | `--job-type 全职` |
| `-p` | 页码 | `-p 2` |
| `-n` | 数量（导出用） | `-n 50` |

---

## 子命令速查

| 命令 | 说明 |
|------|------|
| `search <keyword>` | 搜索职位 |
| `recommend` | 个性化推荐 |
| `show <index>` | 按编号查看详情 |
| `detail <securityId>` | 按 ID 查看详情 |
| `export <keyword>` | 导出搜索结果 |
| `applied` | 已投递列表 |
| `interviews` | 面试邀请 |
| `history` | 浏览历史 |
| `chat` | 沟通过的 Boss |
| `greet <securityId>` | 打招呼 |
| `batch-greet <keyword>` | 批量打招呼 |
| `me` | 个人资料 |
| `login` | 扫码登录 |
| `logout` | 清除凭证 |
| `status` | 登录状态 |
| `cities` | 支持的城市列表 |

---

## 注意事项

- Cookie 有效期约 7 天，过期后需重新获取
- 批量打招呼有 1.5s 延迟防风控
- 写操作（打招呼、投递）风险高于读操作
- 部分功能需要完善求职期望才可用
