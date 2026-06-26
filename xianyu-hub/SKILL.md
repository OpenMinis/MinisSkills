---
name: xianyu-hub
description: >
  闲鱼（咸鱼/goofish）二手商品搜索与查询技能。通过在已登录的浏览器页面内调用
  mtop API，无需 Cookie/签名即可搜索商品、查询价格行情、筛选城市/价格区间/排序。
  支持输出网页链接和 fleamarket:// APP 直达链接。
  当用户提到「闲鱼」「咸鱼」「二手」「goofish」「搜一下xx多少钱」「找一下xx的商品」，
  或任何需要查询闲鱼商品价格/搜索二手商品的场景，必须触发本技能。
---

# 闲鱼搜索技能 (xianyu-hub)

## 核心原理

在已登录闲鱼的浏览器 tab 内通过 `minis-browser-use execute_js` 调用 `window.lib.mtop.request()`，
天然复用登录态，无需签名或 Cookie 管理。

## 启动流程（每次使用前执行）

全程用 `minis-browser-use` CLI。

### Step 1：确保浏览器有闲鱼 tab

```sh
minis-browser-use list_tabs --compact -q  # 看有没有 goofish.com
# 没有则：
minis-browser-use navigate --url "https://www.goofish.com"
```

### Step 2：检查登录状态

```sh
minis-browser-use execute_js --tab-id <id> \
  --script 'return window.location.href.includes("passport") ? "not_login" : (window.lib && window.lib.mtop ? "ok" : "loading")' \
  --compact -q
```

- `"ok"` → 已登录，执行操作
- 其他 → 未登录，执行：
  ```sh
  minis-open https://www.goofish.com
  ```
  并告知用户：「闲鱼尚未登录，已打开内置浏览器，请完成登录后告诉我 🐟」

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
