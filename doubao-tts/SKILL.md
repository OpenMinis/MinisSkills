---
name: doubao-tts
version: 2.0.0
description: 使用豆包语音合成（Volcengine TTS）将文本转为语音文件。当用户提到"豆包TTS"、"豆包语音合成"、"doubao tts"、"火山引擎TTS"、"volcengine tts"、"语音合成"、"文字转语音"、"TTS"、"生成音频"、"朗读文字"，或任何需要调用豆包/火山引擎语音合成 API 的场景，必须触发本技能。
---

# Doubao TTS Skill（V3）

使用火山引擎豆包语音合成 **V3 HTTP SSE 单向流式接口**将文本转为音频文件。

## 获取 AppID 和 Token

1. 登录 [火山引擎控制台](https://console.volcengine.com/speech/app)
2. 进入 **豆包语音 → 语音合成大模型 → 应用管理**
3. 创建应用（或使用已有应用），点击应用名称进入详情
4. 在应用详情页底部可看到：
   - **APP ID** → 对应 `DOUBAO_TTS_APPID`
   - **Access Token** → 对应 `DOUBAO_TTS_TOKEN`

> 若尚未开通服务，需先在 [语音合成大模型](https://console.volcengine.com/speech/service/10) 页面开通后才能创建应用。

## 环境变量

| 变量名 | 说明 |
|---|---|
| `DOUBAO_TTS_APPID` | 控制台申请的 AppID（即 `X-Api-App-Id`） |
| `DOUBAO_TTS_TOKEN` | Access Token（即 `X-Api-Access-Key`） |
| `DOUBAO_TTS_RESOURCE_ID` | 资源 ID，留空由服务端自动匹配，或指定 `seed-tts-2.0` 等 |

检查是否已配置：
```sh
[ -n "$DOUBAO_TTS_APPID" ] && echo "set" || echo "not set"
[ -n "$DOUBAO_TTS_TOKEN" ] && echo "set" || echo "not set"
```

未配置时告知用户设置：
[Set DOUBAO_TTS_APPID](minis://settings/environments?create_key=DOUBAO_TTS_APPID&create_value=) | [Set DOUBAO_TTS_TOKEN](minis://settings/environments?create_key=DOUBAO_TTS_TOKEN&create_value=) | [Set DOUBAO_TTS_RESOURCE_ID](minis://settings/environments?create_key=DOUBAO_TTS_RESOURCE_ID&create_value=seed-tts-1.0)

## 使用方式

调用脚本：`/var/minis/skills/doubao-tts/scripts/tts.py`

```sh
# 基础用法
uv run --script --cache-dir /root/.cache/uv \
  /var/minis/skills/doubao-tts/scripts/tts.py \
  --text "你好，欢迎使用豆包语音合成" \
  --output /var/minis/workspace/output.mp3

# 指定音色和语速
uv run --script --cache-dir /root/.cache/uv \
  /var/minis/skills/doubao-tts/scripts/tts.py \
  --text "今天天气真好" \
  --speaker zh_female_cancan_uranus_bigtts \
  --speech-rate 10 \
  --output /var/minis/workspace/output.mp3

# 英文
uv run --script --cache-dir /root/.cache/uv \
  /var/minis/skills/doubao-tts/scripts/tts.py \
  --text "Hello! Nice to meet you." \
  --speaker en_female_dacey_uranus_bigtts \
  --output /var/minis/workspace/output.mp3
```

## API 说明

- **接口**：`https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse`（SSE 流式）
- **鉴权**：Header `X-Api-App-Id` + `X-Api-Access-Key`（即 AppID + Token，**非** API Key）
- **Resource ID**：指定调用的模型版本（见下表）

| Resource ID | 说明 |
|---|---|
| `seed-tts-1.0` | 豆包语音合成模型 1.0 字符版（默认，兼容所有 `BV*_streaming` 音色） |
| `seed-tts-1.0-concurr` | 豆包语音合成模型 1.0 并发版 |
| `seed-tts-2.0` | 豆包语音合成模型 2.0（仅支持 2.0 音色） |

## 参数说明

| 参数 | 说明 |
|---|---|
| `--text` | 要合成的文本（必填） |
| `--output` | 输出文件路径（必填） |
| `--speaker` | 音色，默认 `BV700_streaming`（灿灿） |
| `--encoding` | 格式：`mp3`/`pcm`/`ogg_opus`，默认 `mp3` |
| `--speech-rate` | 语速 [-50, 100]，0 为默认，100 为 2 倍速 |
| `--loudness` | 音量 [-50, 100]，0 为默认 |
| `--sample-rate` | 采样率，默认 24000 |
| `--emotion` | 情感（如 `happy`/`sad`/`angry`/`narrator` 等） |
| `--emotion-scale` | 情绪强度 [1, 5]（配合 `--emotion` 使用） |
| `--resource-id` | Resource ID（覆盖环境变量） |
| `--json` | JSON 格式输出结果 |

## 常用音色速查

### 豆包语音合成模型 2.0（`seed-tts-2.0`，推荐）

| speaker | 名称 | 场景 |
|---|---|---|
| `zh_female_shuangkuaisisi_uranus_bigtts` | 爽快思思 2.0 ⭐默认 | 通用 |
| `zh_female_cancan_uranus_bigtts` | 知性灿灿 2.0 | 角色扮演 |
| `zh_female_tianmeixiaoyuan_uranus_bigtts` | 甜美小源 2.0 | 通用 |
| `zh_female_vv_uranus_bigtts` | Vivi 2.0 | 通用，支持中/日/印尼/西语 |
| `zh_female_xiaohe_uranus_bigtts` | 小何 2.0 | 通用 |
| `zh_male_m191_uranus_bigtts` | 云舟 2.0 | 通用 |
| `zh_male_taocheng_uranus_bigtts` | 小天 2.0 | 通用 |
| `zh_female_kefunvsheng_uranus_bigtts` | 暖阳女声 2.0 | 客服 |
| `en_female_dacey_uranus_bigtts` | Dacey | 美式英语 |
| `en_male_tim_uranus_bigtts` | Tim | 美式英语 |

### 豆包语音合成模型 1.0（`seed-tts-1.0`，需改 `--resource-id`）

| speaker | 名称 | 场景 |
|---|---|---|
| `BV700_streaming` | 灿灿 | 通用，支持22种情感 |
| `BV001_streaming` | 通用女声 | 通用 |
| `BV002_streaming` | 通用男声 | 通用 |
| `BV701_streaming` | 擎苍 | 有声阅读 |
| `BV503_streaming` | 活力女声-Ariana | 英语 |

> ⚠️ 1.0 和 2.0 音色不能混用，`seed-tts-2.0` 只支持 `*_uranus_bigtts` 结尾的音色

## 常见情感值

`pleased`(愉悦) / `sorry`(抱歉) / `happy`(开心) / `sad`(悲伤) / `angry`(愤怒) / `scare`(害怕) / `surprise`(惊讶) / `hate`(厌恶) / `tear`(哭腔) / `narrator`(旁白) / `storytelling`(讲故事)

## 完整工作流

1. 检查环境变量是否配置（APPID + TOKEN）
2. 调用 `tts.py` 脚本生成音频文件到 `/var/minis/workspace/`
3. 以 `minis://workspace/xxx.mp3` 链接形式返回给用户，可直接点击播放
