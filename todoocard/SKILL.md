---
name: todoocard
version: 1.2.0
description: >
  TodooCard（土豆片 / NEWSTONE）六色电子纸技能族。用户提到土豆片、TodooCard、电子纸推送，
  或要在卡上显示内容时使用。当前子技能 today-eats（今天吃点啥：附近随机外卖并推送）。
  后续可扩展天气卡、任意图推送等子技能。
compatibility: >
  Minis iOS with apple-bluetooth; py3-pillow; font-noto-cjk.
  Sub-skills may need apple-location / apple-maps / apple-weather.
---

# todoocard

TodooCard / 土豆片的**父技能**。

- 设备绑定与公共配置
- 共享传输层（六色转换 + BLE 整帧发送）
- 路由到子技能

## 子技能

| 子技能 | 目录 | 触发示例 |
|--------|------|----------|
| 今天吃点啥 | `today-eats/` | 今天吃点啥、中午吃啥、随机外卖、附近吃什么 |

匹配子技能意图时，**先加载该子技能的 `SKILL.md`**，再执行其流程。  
推屏与编码统一用本目录 `scripts/` 与 `references/protocol.md`。

## 设备命令

```bash
ROOT=/var/minis/skills/todoocard
CLI="python3 $ROOT/today-eats/scripts/cli.py"

$CLI scan
$CLI probe --device-id <UUID> --save
$CLI config --show
```

```bash
mkdir -p /var/minis/shared/todoocard
cp $ROOT/config.example.json /var/minis/shared/todoocard/config.json
```

## 新增子技能

1. 在 `todoocard/` 下新建目录（如 `weather/`）
2. 编写 `SKILL.md`（name + description + 流程）
3. 脚本放 `scripts/`；需要推屏时引用父级 `../scripts/`（即 `todoocard/scripts`）
4. 更新本文件子技能表

## 依赖

- `apple-bluetooth`、`py3-pillow`、`font-noto-cjk`
- 可选 macOS：`scripts/build_native_sender.sh`

协议：`references/protocol.md`
