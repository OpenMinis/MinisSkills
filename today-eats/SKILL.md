---
name: today-eats
version: 1.1.0
description: >
  附近随机外卖「今天吃点啥」并推送到 TodooCard（土豆片）六色电子纸。
  用于用户说今天吃点啥、中午吃啥、晚饭吃什么、随机外卖、附近吃什么、推到土豆片时。
compatibility: >
  Minis on iOS with apple-bluetooth, apple-location, apple-maps; py3-pillow; font-noto-cjk.
  Optional macOS native_sender via scripts/build_native_sender.sh.
---

# today-eats · 今天吃点啥

附近随机一家外卖，生成卡片并推送到 TodooCard / 土豆片（528×792 六色电子纸）。

## 何时使用

- 「今天吃点啥」「中午吃啥」「晚饭吃什么」
- 「随机外卖」「附近吃什么」
- 「推到土豆片 / TodooCard」（在要推荐吃什么的语境下）

## 命令

```bash
CLI="python3 /var/minis/skills/today-eats/scripts/cli.py"

# 首次绑定设备
$CLI scan
$CLI probe --device-id <UUID> --save

# 今天吃点啥
$CLI eat
$CLI 今天吃点啥

# 只出图不发送
$CLI eat --prepare-only
```

配置写入本地（勿提交）：

```bash
mkdir -p /var/minis/shared/todoocard
cp /var/minis/skills/today-eats/config.example.json /var/minis/shared/todoocard/config.json
```

## 流程

1. 确认 `device_id`（`scan` / `probe --save`）
2. 用 `apple-location` 定位，用 `apple-maps` 多品类搜索附近餐饮，随机选 1 家
3. 用 `meal_template.py` 渲染「今天吃点啥」卡片
4. 用 `image_to_payload.py` 做六色转换，再用 `safe_send.py` **整帧** BLE 推送  
   （失败即中止；禁止半帧 resume，避免花屏）

## 依赖

- Minis：`apple-bluetooth` `apple-location` `apple-maps`
- `apk add py3-pillow font-noto-cjk`
- 可选 macOS 加速：`scripts/build_native_sender.sh`

协议细节：`references/protocol.md`
