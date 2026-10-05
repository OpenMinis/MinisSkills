---
name: Clash 控制器
description: 通过 Clash / mihomo RESTful API 实时监控和控制 Clash（含 Clash.Meta / mihomo 内核）。支持状态/连接/流量/规则查询、节点与策略组切换、节点测速、DNS 查询、配置重载。当用户提到 Clash、mihomo、切换节点、查看连接、实时流量、规则匹配、节点测速、Clash 控制器时使用。
---

# Clash 控制器（Clash / mihomo RESTful API）

通过 `clash-cli`（封装 Clash RESTful API）在 Minis 内实时监控和控制 Clash / Mihomo。Clash 配置语法请参考官方文档，本文档只管运行态操作。

## 1. 入口授权（前提检查）

- **Clash 必须正在运行**（VPN / 代理开启），`external-controller` 才会监听端口。未启动时 `clash-cli` 报「连接失败」。
- 默认 API 地址 `http://127.0.0.1:9090`（本机 localhost）。
- secret 从环境变量 `CLASH_SECRET` 读取；未设置则免认证直接访问。
- 入口检查：`clash-cli status` 能返回版本、模式、内存、策略组即通过。

```bash
clash-cli status
# mihomo 1.19.32  meta=True
# mode=rule  mixed-port=7890  tun=True stack=gVisor
# 内存 31MB  inuse=0KB
# 策略组 13 个：
#   PROXY → AUTO
```

## 2. 状态检查

| 命令 | 说明 |
|---|---|
| `clash-cli status` | 版本/模式/内存 + 所有策略组当前选择 |
| `clash-cli proxies` | 列全部代理条目（含叶子节点与策略组） |
| `clash-cli proxies <组>` | 查看某策略组当前选择、类型、成员列表 |
| `clash-cli traffic [秒]` | 实时流量 SSE（默认 3 秒，显示瞬时速率+累计） |
| `clash-cli connections [N]` | 活跃连接列表（host→策略组→命中规则→上下行），默认前 20 |
| `clash-cli configs` | 当前运行配置（端口/tun/dns 等） |
| `clash-cli rules [N]` | 规则列表（默认前 10） |

## 3. 常用任务

- **查当前选中节点**：`clash-cli proxy get <组>`（如 `PROXY`）
- **切换节点/策略**：`clash-cli proxy set <组> <节点>`（组内任意成员名，含 DIRECT）
  ```bash
  clash-cli proxy set PROXY DIRECT    # 直连
  clash-cli proxy set PROXY AUTO      # 切回自动测速组
  ```
- **节点测速**：`clash-cli test <节点名> [url] [timeout_ms]`；对组内全部节点测速 `clash-cli grouptest <组名> [url] [timeout_ms]`
- **DNS 查询**：`clash-cli dns query <域名> [type]`（走 mihomo 内部 DNS，返回 Answer 数组）
- **日志**：`clash-cli logs [秒数] [level]`（SSE，默认 3 秒）
- **规则命中分析**：mihomo 无 `rule match` 端点，看每连接命中规则用 `clash-cli connections`（最后一列显示匹配的规则名）

## 4. 影响边界（写操作）

- **写操作**：`proxy set`、`conn close <id|all>`、`reload`、PATCH `/configs` 会改变运行状态，执行前先确认目标名存在（`proxy get`）。
- `conn close all` 会断开全部连接（SSH/下载会被打断）。
- `reload` 重载配置可能导致短暂断线，配置改动应先备份再 reload。
- 若配置文件含节点订阅密码等敏感信息，务必只备份到私有仓库，**绝不推公共仓库**。

## 5. 环境与安全注意事项

- `external-controller` 默认绑定 `127.0.0.1` 即可本地访问。
- **勿改 `0.0.0.0` 绑定**（`allow-lan: true` 且无 secret 时，局域网内可被访问，有风险）。如确需远程访问，务必设置 secret。
- 环境变量：`CLASH_API`（默认 `http://127.0.0.1:9090`）、`CLASH_SECRET`、`CLASH_TIMEOUT`（默认 8 秒）。
- 切换节点时节点名必须与策略组成员**精确匹配**（含空格/emoji/特殊字符，如「🇭🇰香港trojan1」）。
- 实测确认：mihomo 的 `/traffic`、`/memory` 是裸 JSON 流（无 `data:` 前缀），`/logs` 为标准 SSE，解析需兼容两种格式。

## 6. 社区 CLI 备选：mihomosh（可选）

`mihomosh` 是社区为 Mihomo 写的命令行工具包（Rust，MIT），可覆盖几乎全部外部控制 API，作为本技能自带 `clash-cli` 脚本的补充/对照实现。

- **安装**：GitHub Release 下载对应平台预编译二进制，解压后放 `PATH`（如 `/usr/local/bin/mihomosh`）。
- **配置**：`~/.local/share/mihomosh/config.yaml`
  - `mihomo-api: http://127.0.0.1:9090`（Clash 控制端口）
  - `mihomo-path: <你的 clash 配置路径>`（Clash 配置副本）
- **常用命令**：
  ```bash
  mihomosh proxy view        # 查看全部节点/策略组
  mihomosh proxy update     # 切换代理
  mihomosh proxy test        # 批量测速
  mihomosh rule view          # 查看规则
  mihomosh connection list    # 实时连接
  mihomosh inspect version    # 内核版本
  ```
- **注意事项**：
  - Clash 未运行时控制端口无监听，mihomosh 报 `Connection refused`，属正常（开着才能用）。
  - 社区 CLI 本质仍是 HTTP API 客户端包装，**能力边界 = API 边界**（如内核禁止的端点，mihomosh 同样做不到）。

## 7. 安装方式

`clash-cli` 是独立 Python3 脚本（仅标准库），但作为 Minis 技能使用时需放进技能目录才能被自动发现。按环境选一种：

**① Minis 内自动安装（推荐）**
把本技能的 SKILL.md 的 GitHub URL 粘贴到 Minis 对话，智能体会自动拉取安装：
```
https://github.com/openminis/MinisSkills/blob/main/clash-controller/SKILL.md
```

**② git 克隆 + 软链（Minis 技能目录）**
```sh
git clone https://github.com/openminis/MinisSkills ~/.minis-skills
ln -s ~/.minis-skills/clash-controller ~/.minis/skills/clash-controller
```
> iOS 上 Minis 技能目录实际为 `/var/minis/skills`；macOS/其他环境可能是 `~/.minis/skills` 或对应配置路径，以 Minis 设置中显示的技能目录为准。

**③ 手动解压**
下载本技能目录（zip）后解压到技能目录：
```sh
unzip clash-controller.zip -d ~/.minis/skills/
```

**④ 仅用脚本（不装技能，任何有 Python3 的机器）**
`scripts/clash-cli` 可单独使用，只需本机运行着 Clash 且 `external-controller` 在监听：
```sh
chmod +x clash-cli
./clash-cli status
# 远程/带 secret：
# export CLASH_API=http://<IP>:9090 CLASH_SECRET=<你的secret>
# ./clash-cli status
```

**验证安装**
```sh
clash-cli status   # 返回版本/模式/策略组即成功；报「连接失败」说明 Clash 未运行或端口未开
```

## 参考资料（来源）

- mihomo（MetaCubeX）GitHub：https://github.com/MetaCubeX/mihomo
- mihomo Wiki：https://wiki.metacubex.one/
- Clash 原始 RESTful API 文档：https://clash.gitbook.io/doc/restful-api
- mihomosh（SamuNatsu）GitHub：https://github.com/SamuNatsu/mihomosh
- 校验：`clash-cli` 通过 `python3 -m py_compile`，核心命令实测通过（status/traffic/connections/rules/proxy get/set/test/dns）
