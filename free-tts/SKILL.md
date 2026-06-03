---
name: free-tts
version: 1.0.0
description: >
  免费语音合成（edge-tts），无需 API Key 无需注册。将文本转为 mp3 音频文件。
  当用户说"朗读""语音合成""文字转语音""TTS""生成音频""读一下"
  "读出来""念一下""听一下"或任何需要将文本转为语音播放的场景时触发。
---

# Free TTS Skill

使用 `edge-tts`（Python 库）将文本转为语音 mp3 文件。底层调用微软 Edge 浏览器在线 TTS 接口，**完全免费、零注册、零配置、不限次数、国内直连**。

## 环境依赖

```sh
pip install edge-tts
```

无需任何 API Key、账号或 Token。

## 中文音色完整列表

| # | 音色 ID | 名称 | 性别 | 语言/风格 |
|:-:|---------|------|:----:|-----------|
| 1 | `zh-CN-XiaoxiaoNeural` | 晓晓 ⭐ | 女 | 普通话·温暖自然 |
| 2 | `zh-CN-XiaoyiNeural` | 晓伊 | 女 | 普通话·活泼俏皮 |
| 3 | `zh-CN-YunxiNeural` | 云希 | 男 | 普通话·阳光活力 |
| 4 | `zh-CN-YunjianNeural` | 云健 | 男 | 普通话·激情有力 |
| 5 | `zh-CN-YunyangNeural` | 云扬 | 男 | 普通话·专业可靠 |
| 6 | `zh-CN-YunxiaNeural` | 云夏 | 男 | 普通话·可爱萌系 |
| 7 | `zh-CN-liaoning-XiaobeiNeural` | 小蓓 | 女 | 东北话·幽默亲切 |
| 8 | `zh-CN-shaanxi-XiaoniNeural` | 小妮 | 女 | 陕西话·明亮爽朗 |
| 9 | `zh-HK-HiuGaaiNeural` | HiuGaai | 女 | 粤语·友好 |
|10 | `zh-HK-HiuMaanNeural` | HiuMaan | 女 | 粤语·友好 |
|11 | `zh-HK-WanLungNeural` | WanLung | 男 | 粤语·友好 |
|12 | `zh-TW-HsiaoChenNeural` | HsiaoChen | 女 | 台普·友好 |
|13 | `zh-TW-HsiaoYuNeural` | HsiaoYu | 女 | 台普·友好 |
|14 | `zh-TW-YunJheNeural` | YunJhe | 男 | 台普·友好 |

完整多语言音色列表请运行 `edge-tts --list-voices`。

## 调用方式

```sh
# 默认音色（晓晓）
edge-tts --text "你好，欢迎使用免费语音合成。" --write-media /var/minis/workspace/output.mp3

# 指定音色
edge-tts --voice zh-CN-XiaoyiNeural --text "今天天气真好" --write-media /var/minis/workspace/output.mp3

# 调节语速和音量（百分比，-50 ~ +100）
edge-tts --voice zh-CN-XiaoxiaoNeural --rate=+20% --volume=+50% \
  --text "欢迎收听今天的新闻" --write-media /var/minis/workspace/output.mp3
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|-------|
| `--text` | 要合成的文本（必填） | — |
| `--write-media` | 输出 mp3 文件路径（必填） | — |
| `--voice` | 音色 ID | `zh-CN-XiaoxiaoNeural` |
| `--rate` | 语速调整百分比 | `0%` |
| `--volume` | 音量调整百分比 | `0%` |
| `--pitch` | 音调调整 | `0Hz` |

## 输出格式

返回 mp3 文件链接供用户点击播放，格式：
```
![音频](minis://workspace/free_tts_<timestamp>.mp3)
```

## 快捷指令

| 用户输入 | 行为 |
|----------|------|
| "读一下" / "朗读" | 默认音色（晓晓）合成并播放 |
| "用男声" | 切换为 YunJhe（台普男声） |
| "换一个" | 按列表轮换到下一个音色 |
| "换方言" | 切换为 Xiaoni（陕西话） |
| "换粤语" / "讲广东话" | 切换为 WanLung（粤语） |
| "恢复默认" | 回到晓晓 |

## 完整工作流

1. 用户提出需要朗读文本，或说"读一下"
2. 确定目标音色（用户指定或使用当前默认）
3. 调用 `edge-tts` 合成 mp3 到 `/var/minis/workspace/free_tts_<timestamp>.mp3`
4. 返回音频链接供用户播放

## 注意事项

- **合成速度**：一句话约 1-2 秒
- **需联网**：云端合成，走微软 Edge TTS 在线接口
- **零成本**：无需任何账号或付费
- **输出格式**：24kHz 160kbps MP3
- 英文等其他语言音色也可以说中文，但口音不标准，不推荐
