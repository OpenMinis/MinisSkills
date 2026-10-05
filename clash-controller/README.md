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

`clash-cli` 是独立 Python3 脚本（仅标准库依赖），但作为 Minis 技能使用时需放进技能目录才能被自动发现。任选一种：

### ① Minis 内自动安装（推荐）

把本技能的 SKILL.md GitHub URL 直接粘贴到 Minis 对话，智能体会自动拉取安装：

```
https://github.com/openminis/MinisSkills/blob/main/clash-controller/SKILL.md
```

### ② git 克隆 + 软链

```sh
git clone https://github.com/openminis/MinisSkills ~/.minis-skills
ln -s ~/.minis-skills/clash-controller ~/.minis/skills/clash-controller
```

> 技能目录位置：iOS 上为 `/var/minis/skills`；其他平台以 Minis 设置中显示的技能目录为准。

### ③ 手动解压

下载技能目录压缩包后解压到技能目录：

```sh
unzip clash-controller.zip -d ~/.minis/skills/
```

### ④ 仅用脚本（不装技能）

`scripts/clash-cli` 可单独运行，只要本机 Clash 在运行且 `external-controller` 已开启（默认 `127.0.0.1:9090`）：

```sh
chmod +x clash-cli
./clash-cli status
# 远程实例 / 带 secret：
# export CLASH_API=http://<IP>:9090 CLASH_SECRET=<你的secret>
# ./clash-cli status
```

### 验证

```sh
clash-cli status
```

返回版本 / 模式 / 策略组即安装成功；若报「连接失败」，说明 Clash 未运行或 `external-controller` 未监听。

## 快速使用

```bash
clash-cli status            # 概览：版本/模式/内存/策略组
clash-cli connections       # 实时连接
clash-cli traffic 5         # 5 秒实时流量
clash-cli proxy set PROXY "节点名"   # 切换节点
clash-cli test PROXY        # 测延迟
```

环境变量：`CLASH_API`（默认 `http://127.0.0.1:9090`）、`CLASH_SECRET`、`CLASH_TIMEOUT`（默认 8 秒）。
