---
name: douyin-downloader
description: Download Douyin (TikTok) videos from share links. Parse Douyin share text and links, download watermark-free videos, and transcribe audio to text using Volcano Engine ASR (Doubao Speech). Uses Python for iSH compatibility.
---

# Douyin Video Downloader

Parse Douyin share links and download videos without watermarks.

> **Note**: The original version used Node.js. Because of iSH environment limitations, it has been converted to Python.

## Dependencies

- Python 3
- requests library (`pip3 install requests`)

### Environment Variables (Transcription Feature)

- `VOLC_APP_KEY` - Volcano Engine App Key
- `VOLC_ACCESS_KEY` - Volcano Engine Access Key

## Workflow

### 1. Parse Share Link

When the user provides Douyin share text or a link, extract the video metadata:

```bash
python3 scripts/parse_douyin.py "<share text or link>"
```

**Input examples:**
- Full share text: `7.43 FuL:/ You know what? It really is pretty nice. https://v.douyin.com/iFDbjn2M/ Copy this link...`
- Just the URL: `https://v.douyin.com/iFDbjn2M/`

**Output (JSON):**
```json
{
  "video_id": "7445842287652441376",
  "title": "You_know_what_It_really_is_pretty_nice",
  "download_url": "https://...play.../video/...",
  "raw_url": "https://...playwm.../video/...",
  "share_url": "https://v.douyin.com/iFDbjn2M/",
  "redirected_url": "https://www.iesdouyin.com/share/video/7445842287652441376",
  "iesdouyin_url": "https://www.iesdouyin.com/share/video/7445842287652441376"
}
```

**Key fields:**
- `download_url` - Watermark-free version (`playwm` to `play`)
- `title` - Sanitized video description, safe for filenames
- `video_id` - Unique video identifier

### 2. Download Video

Use the `download_url` from step 1:

```bash
python3 scripts/download_video.py "<download_url>" "<output_path>"
```

**Example:**
```bash
python3 scripts/download_video.py "https://aweme.snssdk.com/aweme/v1/play/?video_id=..." "./downloads/You_know_what_It_really_is_pretty_nice.mp4"
```

**Output:**
```json
{
  "status": "success",
  "path": "./downloads/You_know_what_It_really_is_pretty_nice.mp4"
}
```

Progress is written to stderr during download.

### 3. Transcribe Audio

Transcribe audio or video to text using Volcano Engine ASR (Doubao Speech):

```bash
python3 scripts/transcribe_audio.py "<audio_or_video_file>" --app-key "$VOLC_APP_KEY" --access-key "$VOLC_ACCESS_KEY"
```

**Parameters:**
- `--app-key` - Volcano Engine App Key (required, or set the `VOLC_APP_KEY` environment variable)
- `--access-key` - Volcano Engine Access Key (required, or set the `VOLC_ACCESS_KEY` environment variable)
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
  "result_text": "When you feel that fate has been unfair to you, you might want to listen to what Tong Guowei said to Long Keduo...",
  "result": { ... }
}
```

**Getting API credentials:**
1. Visit the [Volcano Engine Console](https://console.volcengine.com/speech/new/overview)
2. Create a speech recognition (ASR) application
3. Get the App Key and Access Key from the application settings

## Complete Example

```bash
# Step 1: Parse
result=$(python3 scripts/parse_douyin.py "7.43 FuL:/ You know what? It really is pretty nice. https://v.douyin.com/iFDbjn2M/")

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
- **Mobile UA required**: Uses an iPhone user agent for compatibility
- **Timeout**: 60 seconds per download
- **Progress**: Displays progress every 10% on stderr
- **Filename length**: Use short filenames (English or pinyin) for saved files. Long filenames with URL encoding may break `minis://` preview links.

### Examples

- Bad: `High_Definition_Lens_41_years_old_Qi_Xi_How_is_her_condition_The_Role_of_Film_Beijing_Premiere.mp4`
- Good: `qixi_short.mp4`

## Error Handling

Common errors:
- `No valid share link found` - Invalid or missing URL in input
- `Failed to access the share link` - Network error or blocked request
- `Failed to parse video information from HTML` - Page structure changed (script needs an update)
- `Download timed out` - Network timeout (try again)

When errors occur, scripts return JSON with `{ "status": "error", "error": "<message>" }` on stderr and exit with code 1.
