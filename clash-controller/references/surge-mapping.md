# surge-cli ↔ clash-cli 命令对照表

用户在两者间迁移时的速查表。`clash-cli` 见 `scripts/clash-cli`。

## 状态与概览

| 需求 | surge-cli | clash-cli |
|---|---|---|
| 概览/健康 | `surge-cli state` | `clash-cli status` |
| 版本 | `surge-cli version` | `clash-cli version` |
| 当前配置 | `surge-cli config get` | `clash-cli configs` |

## 代理与节点

| 需求 | surge-cli | clash-cli |
|---|---|---|
| 列出策略组/节点 | `surge-cli --raw dump policy` | `clash-cli proxies` |
| 查某组当前选择 | `surge-cli --raw get Policy` | `clash-cli proxy get <组>` |
| 切换节点 | `surge-cli --raw set ProxyGroupSelection "<组>=<节点>"` | `clash-cli proxy set <组> <节点>` |
| 节点测速 | `surge-cli test <节点>` | `clash-cli test <节点>` |
| 组内全部测速 | — | `clash-cli grouptest <组>` |

## 流量与连接

| 需求 | surge-cli | clash-cli |
|---|---|---|
| 实时流量 | `surge-cli monitoring` 面板 / 面板脚本 | `clash-cli traffic [秒]` |
| 实时连接 | `surge-cli --raw dump recent` | `clash-cli connections [N]` |
| 关连接 | `surge-cli --raw close connection` | `clash-cli conn close <id\|all>` |
| 规则匹配 | `surge-cli rule match <域名>` | `clash-cli connections`（看命中列，无直接 match） |

## DNS 与配置

| 需求 | surge-cli | clash-cli |
|---|---|---|
| DNS 查询 | `surge-cli --raw query DNS <域名>` | `clash-cli dns query <域名>` |
| 日志 | `surge-cli --raw dump log` | `clash-cli logs [秒] [level]` |
| 重载配置 | `surge-cli reload` | `clash-cli reload [路径]` |

## 能力差异说明

- **规则匹配**：Surge 有 `rule match` 命令直接查域名命中；mihomo 无对应端点，只能通过 `/connections` 看已建立连接实际命中的规则名，或手动比对 `/rules` 列表。
- **策略组结构**：Surge 用 `ProxyGroupSelection` 全局键；mihomo 用 `PUT /proxies/:name`，节点名必须与策略组成员**精确匹配**（含空格/特殊字符，如「🇭🇰香港trojan1」）。
- **secret**：Surge external-controller 默认有 secret；mihomo 无 secret 时直接访问，有 secret 走 `Authorization: Bearer`。
- **SSE**：Surge 面板脚本用 `$httpClient`；mihomo 的 `/traffic` `/memory` 是裸 JSON 流（无 `data:` 前缀），解析时需兼容。