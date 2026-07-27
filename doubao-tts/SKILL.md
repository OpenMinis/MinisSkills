---
name: doubao-tts
version: 2.1.0
description: Use Doubao Text-to-Speech (Volcengine TTS) to convert text into audio files. When a user mentions "Doubao TTS," "Doubao Text-to-Speech," "doubao tts," "Volcengine TTS," "volcengine tts," "speech synthesis," "text-to-speech," "TTS," "generate audio," "read text aloud," or any scenario requiring the Doubao/Volcengine Text-to-Speech API, this skill must be triggered.
---

# Doubao TTS Skill (V3)

Use the Volcengine Doubao Text-to-Speech **V3 HTTP SSE unidirectional streaming API** to convert text into audio files.

## Get an API Key (Recommended, New Console)

1. Log in to the [Volcengine Console](https://console.volcengine.com/speech/app)
2. Go to **Doubao Voice → Text-to-Speech Large Model → Application Management**
3. Create an application or use an existing one
4. On the [API Key Management](https://console.volcengine.com/speech/new/setting/apikeys?projectName=default) page, get the API Key → corresponding to `DOUBAO_TTS_API_KEY`

> If you have not enabled the service yet, enable it first on the [Text-to-Speech Large Model](https://console.volcengine.com/speech/service/10) page.

### Legacy Console (AppID + Token)

At the bottom of the application details page in the legacy console, you can find:
- **APP ID** → `DOUBAO_TTS_APPID`
- **Access Token** → `DOUBAO_TTS_TOKEN`

## Environment Variables

| Variable Name | Description | Recommended |
|---|---|---|
| `DOUBAO_TTS_API_KEY` | API Key (new console, `X-Api-Key`) | ✅ |
| `DOUBAO_TTS_APPID` | AppID (legacy console, `X-Api-App-Id`) | |
| `DOUBAO_TTS_TOKEN` | Access Token (legacy console, `X-Api-Access-Key`) | |
| `DOUBAO_TTS_RESOURCE_ID` | Resource ID; leave blank to use the default `seed-tts-2.0` | |

Check whether they are configured:
```sh
[ -n "$DOUBAO_TTS_API_KEY" ] && echo "API_KEY: set" || echo "API_KEY: not set"
[ -n "$DOUBAO_TTS_APPID" ] && echo "APPID: set" || echo "APPID: not set"
[ -n "$DOUBAO_TTS_TOKEN" ] && echo "TOKEN: set" || echo "TOKEN: not set"
```

If they are not configured, tell the user to set them (prefer API Key):
[Set DOUBAO_TTS_API_KEY](minis://settings/environments?create_key=DOUBAO_TTS_API_KEY&create_value=) | [Set DOUBAO_TTS_RESOURCE_ID](minis://settings/environments?create_key=DOUBAO_TTS_RESOURCE_ID&create_value=seed-tts-2.0)

Legacy console (AppID + Token):
[Set DOUBAO_TTS_APPID](minis://settings/environments?create_key=DOUBAO_TTS_APPID&create_value=) | [Set DOUBAO_TTS_TOKEN](minis://settings/environments?create_key=DOUBAO_TTS_TOKEN&create_value=)

## Usage

Call the script: `/var/minis/skills/doubao-tts/scripts/tts.py`

```sh
# Basic usage
uv run --script --cache-dir /root/.cache/uv \
  /var/minis/skills/doubao-tts/scripts/tts.py \
  --text "Hello, and welcome to Doubao Text-to-Speech." \
  --output /var/minis/workspace/output.mp3

# Specify voice and speech rate
uv run --script --cache-dir /root/.cache/uv \
  /var/minis/skills/doubao-tts/scripts/tts.py \
  --text "The weather is really nice today." \
  --speaker zh_female_cancan_uranus_bigtts \
  --speech-rate 10 \
  --output /var/minis/workspace/output.mp3

# English
uv run --script --cache-dir /root/.cache/uv \
  /var/minis/skills/doubao-tts/scripts/tts.py \
  --text "Hello! Nice to meet you." \
  --speaker en_female_dacey_uranus_bigtts \
  --output /var/minis/workspace/output.mp3
```

## API Description

- **Endpoint**: `https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse` (SSE streaming)
- **Authentication** (choose one):
  - New console: Header `X-Api-Key` (API Key)
  - Legacy console: Header `X-Api-App-Id` + `X-Api-Access-Key` (AppID + Token)
- **Resource ID**: Specifies the model version to call (see the table below)
- **Usage response**: The script includes `X-Control-Require-Usage-Tokens-Return: text_words` by default, which returns the number of billable characters (`text_words`) when synthesis ends

| Resource ID | Description |
|---|---|
| `seed-tts-1.0` | Doubao Text-to-Speech Model 1.0 character version (default, compatible with all `BV*_streaming` voices) |
| `seed-tts-1.0-concurr` | Doubao Text-to-Speech Model 1.0 concurrency version |
| `seed-tts-2.0` | Doubao Text-to-Speech Model 2.0 (supports only 2.0 voices) |

## Parameters

| Parameter | Description |
|---|---|
| `--text` | Text to synthesize (required) |
| `--output` | Output file path (required) |
| `--api-key` | API Key (new console, takes precedence over APPID/TOKEN) |
| `--appid` | AppID (legacy console) |
| `--token` | Access Token (legacy console) |
| `--speaker` | Voice, default `zh_female_shuangkuaisisi_uranus_bigtts` (Shuangkuai Sisi 2.0) |
| `--encoding` | Format: `mp3`/`pcm`/`ogg_opus`, default `mp3` |
| `--speech-rate` | Speech rate [-50, 100], where 0 is the default and 100 is 2x speed |
| `--loudness` | Volume [-50, 100], where 0 is the default |
| `--sample-rate` | Sample rate, default 24000 |
| `--emotion` | Emotion, such as `happy`/`sad`/`angry`/`narrator` |
| `--emotion-scale` | Emotion intensity [1, 5] (used with `--emotion`) |
| `--resource-id` | Resource ID (overrides the environment variable) |
| `--json` | Output result in JSON format |

## Quick Reference for Common Voices

### Doubao Text-to-Speech Model 2.0 (`seed-tts-2.0`, recommended)

| speaker | Name | Scenario |
|---|---|---|
| `zh_female_shuangkuaisisi_uranus_bigtts` | Shuangkuai Sisi 2.0 ⭐ Default | General |
| `zh_female_cancan_uranus_bigtts` | Zhixing Cancan 2.0 | Role-playing |
| `zh_female_tianmeixiaoyuan_uranus_bigtts` | Tianmei Xiaoyuan 2.0 | General |
| `zh_female_vv_uranus_bigtts` | Vivi 2.0 | General, Chinese/Japanese/Indonesian/Mexican Spanish, Sichuan/Shaanxi/Northeastern dialects |
| `zh_female_xiaohe_uranus_bigtts` | Xiaohe 2.0 | General |
| `zh_male_m191_uranus_bigtts` | Yunzhou 2.0 | General |
| `zh_male_taocheng_uranus_bigtts` | Xiaotian 2.0 | General |
| `zh_female_kefunvsheng_uranus_bigtts` | Nuanyang Female Voice 2.0 | Customer service |
| `en_female_dacey_uranus_bigtts` | Dacey | Multilingual (English) |
| `en_male_tim_uranus_bigtts` | Tim | Multilingual (English) |

### Doubao Text-to-Speech Model 1.0 (`seed-tts-1.0`, requires changing `--resource-id`)

| speaker | Name | Scenario |
|---|---|---|
| `BV700_streaming` | Cancan | General, supports 22 emotions |
| `BV001_streaming` | General Female Voice | General |
| `BV002_streaming` | General Male Voice | General |
| `BV701_streaming` | Qingcang | Audiobook |
| `BV503_streaming` | Energetic Female Voice-Ariana | English |

> ⚠️ 1.0 and 2.0 voices cannot be mixed. `seed-tts-2.0` supports only voices ending in `*_uranus_bigtts`.

## Common Emotion Values

`pleased` (pleased) / `sorry` (sorry) / `happy` (happy) / `sad` (sad) / `angry` (angry) / `scare` (scared) / `surprise` (surprised) / `hate` (disgust) / `tear` (tearful voice) / `narrator` (narrator) / `storytelling` (storytelling)

## Complete Workflow

1. Check whether environment variables are configured (first `DOUBAO_TTS_API_KEY`, then `DOUBAO_TTS_APPID` + `DOUBAO_TTS_TOKEN`)
2. Call the `tts.py` script to generate an audio file in `/var/minis/workspace/`
3. Return it to the user as a `minis://workspace/xxx.mp3` link, which they can click to play directly.
