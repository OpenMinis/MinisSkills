---
name: youtube-downloader
description: >
  Download YouTube videos or extract audio using yt-dlp + ffmpeg in the Linux shell.
  Trigger when the user shares a YouTube URL and wants to download, save, rip,
  extract, or convert it — to video or audio (MP3/M4A). Also trigger for phrases
  like "download this video", "save this YouTube", "rip audio from", "grab this
  video", or when a YouTube link is shared with intent to save it locally.
  Works with youtube.com/watch, youtu.be/, and youtube.com/shorts/ URLs.
compatibility: requires yt-dlp, ffmpeg
---

# YouTube Downloader

Download YouTube videos or extract audio. Files are named after the video title, saved to the user's preferred location, and remuxed to play correctly as video on iOS.

## How This Skill Works

This skill runs yt-dlp + ffmpeg inside the Minis Linux sandbox (iSH). Two iSH-specific workarounds are required:

1. **Manual DASH merge:** yt-dlp's built-in video+audio merger crashes in iSH. For high-quality formats (1080p, 1440p), the script downloads video and audio separately using `-k` (keep video), lets the merger fail, then merges them with a direct ffmpeg call.

2. **iOS container fix:** YouTube's MP4 files use the `mp42` brand, which iOS may treat as audio-only. The script remuxes to M4V (for H.264) or standard mp4 (for AV1/VP9) with `+faststart` so iOS Files plays them as video.

## First Run — Onboarding

On the FIRST time this skill triggers, run onboarding before downloading anything.

### Step 1: Check status

```bash
sh /var/minis/skills/youtube-downloader/scripts/yt-config.sh status
```

If `onboarded: true`, skip to Normal Operation. If `onboarded: false` (or config doesn't exist), continue onboarding.

### Step 2: Install dependencies

If `yt-dlp: no` or `ffmpeg: no` in the status output, install them:

```bash
apk add yt-dlp ffmpeg py3-pip
pip install --upgrade --break-system-packages yt-dlp
```

The pip upgrade is essential — Alpine's yt-dlp package is stale and YouTube's player changes frequently. This takes ~30 seconds.

### Step 3: Ask the user two questions

Present as a friendly numbered list. Wait for answers.

**Question 1 — Quality preference:**
> What quality do you want by default?
> 1. **1080p video** — Full HD, best balance of quality and size (default)
> 2. **1440p video** — 2K, highest quality, large files (~300 MB per 10 min)
> 3. **720p video** — HD, smaller file size
> 4. **Audio only** — best for music/podcasts, smallest file
> 5. **Ask me every time** — no default, I'll pick per video

**Question 2 — Where to save:**
> Where should I save your downloads?
> 1. **iOS Files app (Downloads folder)** — appears in Files → Downloads
> 2. **iOS Photos (YouTube Downloads album)** — appears in Photos
> 3. **Keep in Minis** — stays in the app's attachments folder

### Step 4: Set up Files mount (if user chose option 1)

Check if the Downloads mount already exists via the status command. If `downloads_mount: yes`, skip. If `downloads_mount: no`, tell the user:

> To save videos to your Files app, I need you to mount your Downloads folder:
> 1. Tap this link: [Mount External Folders](minis://settings/mount-external)
> 2. Tap "Add Mount"
> 3. Navigate to the folder you want (e.g., iCloud Drive → Downloads, or On My iPhone → Downloads)
> 4. Name it "Downloads"
> 5. Come back here and tell me when you're done

After the user confirms, re-run the status check to verify `downloads_mount: yes`.

### Step 5: Save config

```bash
sh /var/minis/skills/youtube-downloader/scripts/yt-config.sh set quality "<chosen_quality>"
sh /var/minis/skills/youtube-downloader/scripts/yt-config.sh set save_mode "<chosen_save_mode>"
sh /var/minis/skills/youtube-downloader/scripts/yt-config.sh complete
```

- Quality: "1080p", "1440p", "720p", "360p", "audio", or "" (empty string for "ask every time")
- save_mode: "files", "photos", or "minis"

### Step 6: Offer a test download

Tell the user setup is complete. Offer to download a short test video at 360p so they can verify the flow:

```bash
sh /var/minis/skills/youtube-downloader/scripts/yt-download.sh "https://www.youtube.com/watch?v=aqz-KE-bpKQ" 360p <save_mode>
```

Replace `<save_mode>` with whatever the user chose (files, photos, or minis). 360p is used for the test because it's the most reliable quality — higher quality works the same way once configured.

Confirm the file appeared where they expected. Then proceed with whatever they originally asked for.

---

## Normal Operation

```bash
sh /var/minis/skills/youtube-downloader/scripts/yt-download.sh "<URL>" [quality] [save_mode]
```

- Quality is optional — if omitted, uses the saved default from config
- save_mode is optional — if omitted, uses the saved default from config (files, photos, or minis)
- If the user specified a quality in their message ("just the audio", "1440p", etc.), use that
- If the user specified where to save ("save to photos", "put it in files"), pass that as save_mode

### After download, report to the user

The script prints one of three status lines. Read it and tell the user:
- If `SAVED_TO_FILES`: "Saved to your Files app → Downloads folder. Pull to refresh if you don't see it yet."
- If `SAVED_TO_PHOTOS`: "Saved to the 'YouTube Downloads' album in your Photos app."
- If `KEPT_IN_ATTACHMENTS`: The file is at `/var/minis/attachments/<filename>`. Display it inline and tell the user it's available in Minis.
- Always include the video title and file size.

---

## Quality Reference

| Quality | Format | Approx size (10-min video) | Reliability |
|---------|--------|---------------------------|------------|
| 1080p | DASH H.264 + AAC, manually merged | ~256 MB | ✅ Works (M4V container) |
| 1440p | DASH AV1 or VP9 + AAC, manually merged | ~300-460 MB | ✅ Works (mp4 container) |
| 720p | MP4 pre-merged (format 22) | ~80 MB | ✅ Always works |
| 360p | MP4 pre-merged (format 18) | ~27 MB | ✅ Always works |
| audio | M4A 128kbps (format 140) | ~10 MB | ✅ Always works |

DASH formats (1080p, 1440p) download video and audio separately, then merge with ffmpeg (yt-dlp's built-in merger fails in iSH). H.264 streams go into the Apple M4V container; AV1/VP9 streams go into standard mp4. Both play as video on iOS. All video downloads are remuxed with `+faststart` and the correct container brand.

---

## Troubleshooting

**403 Forbidden on DASH streams**: YouTube transiently blocks DASH downloads when using the android vr client fallback (no JS runtime available). Retry — it usually works within 1-2 attempts. Pre-merged formats (360p, 720p) bypass this entirely.

**"No supported JavaScript runtime"**: iSH has no Deno/Node, so yt-dlp can't do YouTube's nsig extraction. Pre-merged formats (18, 22) and audio (140) work without JS. DASH formats work via the android vr client fallback but may intermittently 403.

**yt-dlp out of date**: YouTube breaks extraction often. Run `pip install --upgrade --break-system-packages yt-dlp`.

**Downloads mount disappears**: The mount may disconnect if iCloud sync state changes. Run `yt-config.sh status` to check. If broken, guide the user to re-mount via [Mount External Folders](minis://settings/mount-external).

**Large files**: 1440p files can exceed 450 MB. If the app crashes or becomes unstable, stick to 1080p or lower.