# clash-controller (skill)

通过 Clash / mihomo RESTful API 实时监控和控制 Clash（含 Clash.Meta / mihomo 内核）。提供状态/连接/流量/规则查询、节点与策略组切换、节点测速、DNS 查询、配置重载等命令，对标 `surge-cli` 的常用操作。

## 适用场景

当用户提到 Clash、mihomo、切换节点、查看连接、实时流量、规则匹配、节点测速、Clash 控制器时使用。需要 Clash 正在运行且 `external-controller` 已开启（默认 `127.0.0.1:9090`）。

## Layout

| File | Purpose |
| --- | --- |
| `SKILL.md` | 技能主体：命令速查、写操作边界、安全注意事项 |
| `scripts/clash-cli` | Python3 脚本，封装 Clash RESTful API，纯标准库无依赖 |
| `references/api-reference.md` | mihomo RESTful API 端点参考（含 SSE 兼容说明） |
| `references/surge-mapping.md` | `surge-cli` ↔ `clash-cli` 命令对照表 |

## 安装

```sh
# 从 GitHub 安装（让 Minis 助手粘贴本 SKILL.md 的 URL，或用 git）
git clone https://github.com/openminis/MinisSkills ~/.config/minis-skills
ln -s ~/.config/minis-skills/clash-controller ~/.minis/skills/clash-controller

# 或仅取本技能目录后解压到技能库
unzip clash-controller.zip -d ~/.minis/skills/
```

## 快速使用

```bash
clash-cli status            # 概览：版本/模式/内存/策略组
clash-cli connections       # 实时连接
clash-cli traffic 5         # 5 秒实时流量
clash-cli proxy set PROXY "节点名"   # 切换节点
clash-cli test PROXY        # 测延迟
```

环境变量：`CLASH_API`（默认 `http://127.0.0.1:9090`）、`CLASH_SECRET`、`CLASH_TIMEOUT`（默认 8 秒）。
