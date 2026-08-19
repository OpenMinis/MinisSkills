---
name: today-eats
version: 1.1.0
description: >
  附近随机外卖「今天吃点啥」并推送到 TodooCard（土豆片）。父技能为 todoocard。
  用于用户说今天吃点啥、中午吃啥、晚饭吃什么、随机外卖、附近吃什么时。
---

# today-eats · 今天吃点啥

**父技能：** `todoocard`

附近随机一家外卖 →「今天吃点啥」卡片 → 推送到土豆片。

## 何时使用

- 「今天吃点啥」「中午吃啥」「晚饭吃什么」
- 「随机外卖」「附近吃什么」

## 命令

```bash
CLI="python3 /var/minis/skills/todoocard/today-eats/scripts/cli.py"

$CLI eat
$CLI 今天吃点啥
$CLI eat --prepare-only
```

设备未绑定时，用同一 CLI 的 `scan` / `probe --save`。

## 流程

1. 确认父技能配置中有 `device_id`
2. 定位 + 附近餐饮搜索 → 随机 1 家
3. `meal_template.py` 渲染卡片
4. 父目录 `scripts/`：转换 + **整帧** BLE 推送（禁止 resume）

## 依赖

- 父技能 `todoocard` 的 `scripts/` 与协议
- `apple-location` `apple-maps`
