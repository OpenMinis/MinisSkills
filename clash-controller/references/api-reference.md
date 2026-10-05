# mihomo RESTful API 端点参考（实测 1.19.32）

Base URL = `external-controller` 值，默认 `http://127.0.0.1:9090`。
secret 认证：`Authorization: Bearer ${secret}`（无 secret 则免认证）。

## 状态与配置

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/version` | `{"version":"1.19.32","meta":true}` |
| GET | `/configs` | 当前运行配置（port/mixed-port/tun/dns/...） |
| PATCH | `/configs` | 热修改运行配置（如 mode、mixed-port） |
| PUT | `/configs?force=true` | 重载配置（可选 body `{"path":"..."}`） |

## 代理与策略组

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/proxies` | 全部代理条目：叶子节点 + 策略组（Selector/URLTest），`now` 为当前选择 |
| GET | `/proxies/:name` | 单条代理详情（类型、成员、当前选择、历史延迟） |
| PUT | `/proxies/:name` | 切换策略组选择，body `{"name":"目标节点"}` → HTTP 204 |
| GET | `/proxies/:name/delay?url=...&timeout=...` | 测速，返回 `{"delay":ms}` 或 `{"message":"..."}` |

## 连接

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/connections` | 活跃连接：`connections[]`（metadata/chains/download/upload）+ 总量 |
| DELETE | `/connections/:id` | 关闭单个连接 |
| DELETE | `/connections` | 关闭全部连接 |

## 流式（SSE）

⚠️ **mihomo 的 `/traffic` 和 `/memory` 是「类 SSE」：每条消息是裸 JSON 行 + 空行，没有标准 `data:` 前缀**（`/logs` 和 `/events` 则是标准 SSE `data:` 格式）。解析时需兼容两种。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/traffic` | 实时流量流：`{"up":B,"down":B,"upTotal":B,"downTotal":B}` |
| GET | `/memory` | 内存流：`{"inuse":0,"oslimit":0,"footprint":B}`（inuse 恒 0，内存看 footprint） |
| GET | `/logs` | 日志流：`{"type":"level","payload":"msg"}`，默认 info |
| GET | `/events` | 事件流（连接建立/关闭、代理切换等） |

## 规则与 DNS

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/rules` | 规则列表：`rules[]`（type/payload/proxy），`rulesCount` |
| GET | `/dns/query?name=<域名>&type=A` | 走 mihomo DNS 解析，返回 `Answer[]`（TTL/type/data） |
| GET | `/proxies/:name/now` | （部分版本）当前选择 |
| GET | `/chaos` | 调试信息 |

## 与 Surge 能力对照

| 需求 | mihomo | Surge |
|---|---|---|
| 规则命中查询 | 无 `/rule/match` 端点，用 `/connections` 看每连接命中规则 | `surge-cli rule match` |
| 实时流量 | `/traffic` SSE | `monitoring.traffic_statistics` |
| 实时连接 | `/connections` | `surge-cli dump recent` |
| 切换策略组 | `PUT /proxies/:name` | `surge-cli --raw set ProxyGroupSelection` |
| 节点测速 | `/proxies/:name/delay` | `surge-cli test` |
| 配置热改 | `PATCH /configs` | `surge-cli reload` 等 |