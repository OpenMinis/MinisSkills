---
name: douyin-downloader
description: Download Douyin (抖音) videos from share links. Parse Douyin share text/links, download watermark-free videos, and transcribe audio to text using Volcano Engine ASR (Doubao Speech). Uses Python for iSH compatibility.
---

# Douyin Video Downloader

Parse Douyin share links and download videos without watermarks.

> **注意**：原版使用 Node.js，由于 iSH 环境限制，已转换为 Python 版本。

## 依赖

- Python 3
- requests 库 (`pip3 install requests`)

### 环境变量（转录功能）

- `VOLC_APP_KEY` - 火山引擎 App Key
- `VOLC_ACCESS_KEY` - 火山引擎 Access Key

## Workflow

### 1. Parse Share Link

When the user provides a Douyin share text or link, extract video metadata:

```bash
python3 scripts/parse_douyin.py "<分享文本或链接>"
```

**Input examples:**
- Full share text: `7.43 FuL:/ 你别说，真挺好看的 https://v.douyin.com/iFDbjn2M/ 复制此链接...`
- Just the URL: `https://v.douyin.com/iFDbjn2M/`

**Output (JSON):**
```json
{
  "video_id": "7445842287652441376",
  "title": "你别说_真挺好看的",
  "download_url": "https://...play.../video/...",
  "raw_url": "https://...playwm.../video/...",
  "share_url": "https://v.douyin.com/iFDbjn2M/",
  "redirected_url": "https://www.iesdouyin.com/share/video/7445842287652441376",
  "iesdouyin_url": "https://www.iesdouyin.com/share/video/7445842287652441376"
}
```

**Key fields:**
- `download_url` - No watermark version (playwm → play)
- `title` - Sanitized video description (safe for filenames)
- `video_id` - Unique video identifier

### 2. Download Video

Use the `download_url` from step 1:

```bash
python3 scripts/download_video.py "<download_url>" "<output_path>"
```

**Example:**
```bash
python3 scripts/download_video.py "https://aweme.snssdk.com/aweme/v1/play/?video_id=..." "./downloads/你别说_真挺好看的.mp4"
```

**Output:**
```json
{
  "status": "success",
  "path": "./downloads/你别说_真挺好看的.mp4"
}
```

Progress is written to stderr during download.

### 3. Transcribe Audio

Transcribe audio/video to text using Volcano Engine ASR (Doubao Speech):

```bash
python3 scripts/transcribe_audio.py "<audio_or_video_file>" --app-key "$VOLC_APP_KEY" --access-key "$VOLC_ACCESS_KEY"
```

**Parameters:**
- `--app-key` - Volcano Engine App Key (required, or set `VOLC_APP_KEY` env var)
- `--access-key` - Volcano Engine Access Key (required, or set `VOLC_ACCESS_KEY` env var)
- `--resource-id` - Resource ID: `volc.bigasr.auc_turbo` (flash) or `volc.seedasr.auc` (standard)
- `--mode` - Mode: `auto` | `flash` | `standard` (default: `auto`)
- `--out` - Output JSON file path (optional)
- `--text-out` - Output text file path (optional)

**Example:**
```bash
# Using env vars
export VOLC_APP_KEY="your_app_key"
export VOLC_ACCESS_KEY="your_access_key"
python3 scripts/transcribe_audio.py "./downloads/video.mp4" --mode flash

# Or inline
python3 scripts/transcribe_audio.py "./downloads/video.mp4" \
  --app-key "your_app_key" \
  --access-key "your_access_key" \
  --resource-id "volc.bigasr.auc_turbo" \
  --mode flash \
  --text-out "./downloads/transcript.txt"
```

**Output (JSON):**
```json
{
  "status": "success",
  "mode": "flash",
  "result_text": "当你感到命运对你不公时，不妨听听佟国维对隆科多说的话...",
  "result": { ... }
}
```

**Getting API credentials:**
1. Visit [Volcano Engine Console](https://console.volcengine.com/speech/new/overview)
2. Create a speech recognition (ASR) application
3. Get App Key and Access Key from application settings

## Complete Example

```bash
# Step 1: Parse
result=$(python3 scripts/parse_douyin.py "7.43 FuL:/ 你别说，真挺好看的 https://v.douyin.com/iFDbjn2M/")

# Step 2: Extract fields
download_url=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin)['download_url'])")
title=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin)['title'])")

# Step 3: Download
python3 scripts/download_video.py "$download_url" "./downloads/${title}.mp4"
```

## Notes

- **Watermark removal**: The script automatically converts `playwm` URLs to `play` URLs
- **Title sanitization**: Removes invalid filename characters (`\/:*?"<>|`)
- **Both video and note**: Supports both `/video/` and `/note/` URLs
- **Mobile UA required**: Uses iPhone user agent for compatibility
- **Timeout**: 60 seconds per download
- **Progress**: Displays progress every 10% on stderr
- **Filename length**: Use SHORT filenames (English/pinyin) for the saved files. Long Chinese filenames with URL encoding may break the minis:// preview links.

### Examples
- ❌ Bad: `高清镜头41岁的_齐溪_状态如何_电影用武之地_电影用武之地北京首映礼.mp4`
- ✅ Good: `qixi_short.mp4`

## Error Handling

Common errors:
- `未找到有效的分享链接` - Invalid or missing URL in input
- `访问分享链接失败` - Network error or blocked request
- `从HTML中解析视频信息失败` - Page structure changed (script needs update)
- `下载超时` - Network timeout (try again)

When errors occur, scripts return JSON with `{ "status": "error", "error": "<message>" }` on stderr and exit with code 1.