---
name: cloudflare-dns
description: 使用 flarectl 命令行工具管理 Cloudflare DNS 记录，包括列出、添加、更新、删除 DNS 记录，以及查询 Zone 信息。当用户提到"Cloudflare DNS"、"CF DNS"、"添加 DNS 记录"、"删除 DNS 记录"、"更新 DNS"、"查看 DNS 记录"、"cloudflare-dns"、"flarectl"，或任何涉及 Cloudflare DNS 管理的场景，必须触发本技能。
---

# Cloudflare DNS 管理

## 环境准备

### 安装 flarectl

当前环境（Alpine Linux arm64）可直接使用预装版本。若不存在则从 Release 安装：

```bash
if ! which flarectl > /dev/null 2>&1; then
  wget -q https://github.com/wsvn53/flarectl/releases/download/flarectl-v0.1.0-alpine-arm64/flarectl-linux-arm64 \
    -O /usr/local/bin/flarectl && chmod +x /usr/local/bin/flarectl
fi
```

### 认证配置

flarectl 支持两种认证方式（优先使用 API Token）：

**方式一：API Token（推荐）**
```bash
export CF_API_TOKEN=<your_token>
```

**方式二：Global API Key**
```bash
export CF_API_KEY=<your_key>
export CF_API_EMAIL=<your_email>
```

可选：
```bash
export CF_ACCOUNT_ID=<account_id>   # 多账号时指定
```

检查环境变量是否已设置：
```bash
[ -n "$CF_API_TOKEN" ] && echo "Token: set" || echo "Token: NOT SET"
[ -n "$CF_API_KEY" ] && echo "API Key: set" || echo "API Key: NOT SET"
```

若未设置，告知用户需要的变量名并提供设置链接：
- API Token：[设置 CF_API_TOKEN](minis://settings/environments?create_key=CF_API_TOKEN&create_value=)
- API Key：[设置 CF_API_KEY](minis://settings/environments?create_key=CF_API_KEY&create_value=) 和 [设置 CF_API_EMAIL](minis://settings/environments?create_key=CF_API_EMAIL&create_value=)

---

## 常用操作

### 查询 Zone 列表

```bash
flarectl zone list
```

输出示例：
```
ID                               NAME          PLAN   STATUS
abc123...                        example.com   Free   active
```

### 列出 DNS 记录

```bash
# 列出某域名所有记录
flarectl dns list --zone example.com

# 按类型过滤
flarectl dns list --zone example.com --type A

# 按名称过滤
flarectl dns list --zone example.com --name sub.example.com

# JSON 格式输出（便于解析 ID）
flarectl --json dns list --zone example.com
```

### 添加 DNS 记录

```bash
# A 记录
flarectl dns create --zone example.com --type A --name sub.example.com --content 1.2.3.4 --ttl 1

# CNAME 记录（开启橙云代理）
flarectl dns create --zone example.com --type CNAME --name www.example.com --content example.com --proxy

# MX 记录
flarectl dns create --zone example.com --type MX --name example.com --content mail.example.com --priority 10

# TXT 记录
flarectl dns create --zone example.com --type TXT --name _dmarc.example.com --content "v=DMARC1; p=none"

# AAAA 记录（IPv6）
flarectl dns create --zone example.com --type AAAA --name ipv6.example.com --content "2001:db8::1"
```

参数说明：
- `--ttl 1`：自动 TTL（推荐）；其他值单位为秒（如 `--ttl 300`）
- `--proxy`：开启 Cloudflare 橙云代理（仅 A/AAAA/CNAME 支持）

### 更新 DNS 记录

更新需要记录的 `id`，先用 `dns list` 获取：

```bash
# 获取记录 ID
flarectl --json dns list --zone example.com --name sub.example.com | python3 -c "
import sys,json
for r in json.load(sys.stdin):
    print(r['id'], r['type'], r['name'], r['content'])
"

# 更新内容
flarectl dns update --zone example.com --id <record_id> --content 5.6.7.8

# 更新并开启代理
flarectl dns update --zone example.com --id <record_id> --content 5.6.7.8 --proxy
```

### 创建或更新（upsert）

```bash
# 存在则更新，不存在则创建
flarectl dns create-or-update --zone example.com --type A --name sub.example.com --content 1.2.3.4
```

### 删除 DNS 记录

```bash
# 先查出 ID
flarectl --json dns list --zone example.com --name sub.example.com | python3 -c "
import sys,json
for r in json.load(sys.stdin):
    print(r['id'], r['name'], r['type'])
"

# 删除
flarectl dns delete --zone example.com --id <record_id>
```

### 批量删除同名记录

```bash
flarectl --json dns list --zone example.com --name sub.example.com | python3 -c "
import sys,json,subprocess
for r in json.load(sys.stdin):
    subprocess.run(['flarectl','dns','delete','--zone','example.com','--id',r['id']])
    print('Deleted:', r['id'], r['type'], r['content'])
"
```

---

## 工作流程

1. **确认认证**：检查 `CF_API_TOKEN` 或 `CF_API_KEY`+`CF_API_EMAIL` 是否已设置
2. **确认域名**：若用户未指定 zone，先用 `flarectl zone list` 列出可用域名让用户选择
3. **执行操作**：按需执行 list/create/update/delete
4. **结果展示**：操作后用 `flarectl dns list --zone <zone>` 展示最新记录状态

## 注意事项

- 删除操作不可恢复，执行前需向用户确认
- `--proxy` 仅支持 A、AAAA、CNAME 记录类型
- MX 记录必须指定 `--priority`
- TXT 记录内容含空格时需用引号包裹
- `flarectl --json` 全局 flag 必须放在子命令之前
