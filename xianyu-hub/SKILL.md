---
name: xianyu-hub
description: >
  闲鱼（咸鱼/goofish）二手商品搜索与查询技能。支持搜索商品、查询价格行情、
  筛选城市/价格区间/排序、查看商品详情、管理收藏、查询订单和已发布商品。
  支持输出网页链接和 fleamarket:// APP 直达链接。
  内置「关键字增强」：当搜索结果为空或极少时，自动补充同类别替代关键字重试，
  大幅提升搜索命中率。
  当用户提到「闲鱼」「咸鱼」「二手」「goofish」「搜一下xx多少钱」「找一下xx的商品」
  「搜不到」，或任何需要查询闲鱼商品价格/搜索二手商品的场景，必须触发本技能。
---

# 闲鱼搜索技能 (xianyu-hub)

## 核心原理

在已登录闲鱼的浏览器 tab 内通过 `minis-browser-use execute_js` 调用闲鱼内部 API，
需要用户先在内置浏览器中完成闲鱼登录。

## 启动流程（每次使用前执行）

所有脚本都会**自动调用 `ensure_tab.sh`** 完成以下步骤，**无需手动传 `--tab-id`**。

### ensure_tab.sh 自动处理逻辑

1. **扫描所有 tab** — 解析 `list_tabs` 文本，找含 `goofish.com` 的 tab
2. **检查登录态** — 执行 JS 判断当前页是否已登录
3. **已登录** → 直接输出 tab_id，脚本继续执行
4. **未登录** → 自动执行：
   - `navigate` 跳转到闲鱼首页
   - `minis-open` 弹出内置浏览器供用户登录
   - **每 5 秒轮询登录状态，最多等 120 秒**，登录成功自动继续

> 若需手动指定 tab，可传 `--tab-id <id>`，脚本仍会验证登录态。

## 脚本一览

所有脚本位于 `/var/minis/skills/xianyu-hub/scripts/`，用 `sh` 执行。

### 1. 搜索商品 — search.sh

```sh
sh scripts/search.sh -k <关键词> [选项]

# 选项：
#   -k <词>        关键词（必填）
#   -n <数>        每页数量（默认20，最大30）
#   -p <页>        页码（默认1）
#   -s <排序>      default | price_asc | price_desc | time | reduce
#   --min-price <元>  最低价
#   --max-price <元>  最高价
#   --city <城市>     城市过滤
#   --personal-only   仅个人闲置
#   -j              输出 JSON

# 示例
sh scripts/search.sh -k "MacBook Air" -s price_asc --min-price 2000 -n 10
sh scripts/search.sh -k "iPhone15" --city 上海 -s time
```

### 2. 商品详情 — detail.sh

```sh
sh scripts/detail.sh <商品ID>

# 返回：标题、价格、描述、浏览/想要/收藏数、卖家信息（好评率、回复率、售出数）
```

### 3. 收藏管理 — favorites.sh

```sh
sh scripts/favorites.sh list [-n 数量] [-p 页码]   # 查看收藏列表
sh scripts/favorites.sh add <商品ID>               # 收藏商品
sh scripts/favorites.sh remove <商品ID>            # 取消收藏
```

### 4. 订单查询 — orders.sh

```sh
sh scripts/orders.sh [-n 数量] [-p 页码] [-t 类型]

# 类型: all | wait_pay | wait_send | wait_receive | refund
```

### 5. 我发布的 — my_items.sh

```sh
sh scripts/my_items.sh [-n 数量] [-p 页码]
```

---

## 🔎 关键字增强模块

> 当直接搜索结果为空或极少（< 3 条）时，**自动启用关键字增强**，不要直接放弃。

### 核心机制

部分商品在平台上用词各有不同，卖家习惯使用行业通用简称、别称或缩写。
本模块通过 [SearchSharp.com](https://search-sharp.com) 的开放 API，
自动获取该商品的全平台常用别称列表（由用户社区众包维护、按热度排序），
逐一重试搜索，提升命中率。

### 6. 智能关键字搜索 — smart_search.sh ⭐推荐

**结果不足时首选，自动完成：直搜 → 补充别称 → 重试**

```sh
sh scripts/smart_search.sh -k <关键词> [其他 search.sh 参数]

# 示例
sh scripts/smart_search.sh -k "GTA"
sh scripts/smart_search.sh -k "Netflix会员" --max-price 50
sh scripts/smart_search.sh -k "gpt plus"
```

**执行流程：**
1. 用原始关键字搜一遍闲鱼
2. 若结果 < 3 条，调用 SearchSharp API 查询该词的常用别称
3. 按社区热度排序，逐一用别称重试搜索（最多 3 个）
4. 输出全部结果

### 7. 别称查询 — alt_keywords.sh

**仅查询关键字别称，不搜闲鱼，用于了解某商品的常见叫法**

```sh
# 查询某词的常用别称
sh scripts/alt_keywords.sh -q <关键词>

# 列出热门商品别称汇总（约 20 条）
sh scripts/alt_keywords.sh --list

# 查某商品全部别称（用 ID，从 --list 结果里找）
sh scripts/alt_keywords.sh --id <商品ID>

# JSON 输出
sh scripts/alt_keywords.sh -q "gpt" -j
```

### 使用规则

| 情况 | 操作 |
|------|------|
| 搜索结果 ≥ 3 条 | 直接展示，无需增强 |
| 搜索结果 < 3 条 | 自动运行 `smart_search.sh` 补充别称重试 |

### SearchSharp API

| 接口 | 说明 |
|------|------|
| `GET /api/products` | 热门商品列表 |
| `GET /api/products?q=<词>` | 按关键字查商品及别称 |
| `GET /api/products/<id>` | 单商品完整别称列表 |

- 无需认证，直接 curl 调用
- `keywords` 数组按社区净票数排序，热度越高越靠前

---

## 打开商品

```sh
apple-open "fleamarket://item?id=<商品ID>"    # 跳转闲鱼 APP
```

对话中用 Markdown 链接：`[在闲鱼APP中打开](fleamarket://item?id=xxx)`

## URL 规则

| 用途 | 格式 |
|---|---|
| 网页 | `https://www.goofish.com/item?id=<id>` |
| APP | `fleamarket://item?id=<id>` |
| 订单 | `fleamarket://order_detail?id=<orderId>` |

## 注意事项

- `price_asc` 排序服务端可能返回低价垃圾数据，建议配合 `--min-price` 过滤
- 城市/价格区间为客户端过滤
- `--personal-only` 按评价数判断（>10条视为店铺），不绝对准确
- 敏感词被平台屏蔽时返回空结果，属正常现象
- `ensure_tab.sh` 依赖 `list_tabs` 返回文本格式（`Tab N: 标题 — URL`），格式变更需同步更新解析逻辑
- 未登录时 `ensure_tab.sh` 会自动轮询等待，**无需用户手动确认登录**，等待期间脚本会阻塞（最多 120 秒）
