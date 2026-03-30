---
name: twitter-downloader
version: 1.0.0
description: "Download text, images, GIFs, and videos from Twitter/X posts via fxtwitter API. Trigger when users share any twitter.com or x.com link, or ask to download or see media from a tweet (e.g., '下载推特视频', '把这条推文的图存下来', 'what's in this tweet')."
---

# Twitter Downloader Skill

A compact, reliable workflow to parse Twitter/X URLs, fetch structured JSON via the public fxtwitter API (no auth), summarize the tweet, and download media files to Minis for easy sharing.

## When to Use
- User provides a twitter.com or x.com URL
- User asks to download video/images/GIF from a tweet
- User asks “这条推文里有什么/what’s in this tweet” and you may also need media links/files

## What It Does
1. Parse username and status ID from any Twitter/X URL variant
2. Fetch tweet JSON from api.fxtwitter.com (fallback api.vxtwitter.com)
3. Produce a short summary (author, handle, created time, text, sensitive flag)
4. Extract direct media URLs (best bitrate for videos when available)
5. Optionally download photos, thumbnails, and videos to a local folder and return Minis links

## Dependencies
- curl
- jq

The helper script auto-installs missing packages: `apk add --no-cache curl jq`.

## Helper Script
Path: /var/minis/skills/twitter-downloader/scripts/twitter_downloader.sh

Usage:
- Summarize only
  /var/minis/skills/twitter-downloader/scripts/twitter_downloader.sh "<URL>"
- Download images and/or video to a directory
  /var/minis/skills/twitter-downloader/scripts/twitter_downloader.sh "<URL>" --dir "/var/minis/workspace/tweet_media" --images --video

Outputs:
- JSON: DIR/<tweet_id>.json
- Summary: DIR/<tweet_id>_summary.txt
- Media (if downloaded): DIR/<tweet_id>/...

## Agent Workflow
1) Normalize input URL (accept any twitter.com or x.com format).
2) Run the helper script without downloads to get summary + links.
3) If the user wants files in chat, re-run with --images/--video and show Minis links:
   - Example: [tweet_media/<id>.json](minis://workspace/tweet_media/<id>.json)
   - Example folder: [tweet_media/<id>/](minis://workspace/tweet_media/<id>/)
4) If analysis is requested, pass downloaded image/thumbnail files to vision and describe content.

## Error Handling
- If URL parsing fails: ask for a valid twitter.com/x.com status URL
- If fxtwitter fails: auto-retry with vxtwitter; if both fail, report outage and suggest trying later
- If the tweet is deleted/private: explain that media/text may be unavailable

## Safety
- Respect `possibly_sensitive`; don’t auto-render explicit content; describe neutrally if asked

## Notes
- Videos may include multiple variants; the script picks the highest bitrate when available
- Thumbnails (JPEG) are downloaded for video/GIF if `--images` is set (useful for quick vision analysis)
