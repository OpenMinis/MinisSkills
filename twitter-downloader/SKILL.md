---
name: twitter-downloader
version: 2.0.0
description: "Download Twitter/X tweet text, images, GIFs, and videos via fxtwitter/vxtwitter, then return a tweet summary plus Markdown-formatted Minis links. Trigger when users share twitter.com/x.com links or ask to download/summarize tweet media."
---

# Twitter Downloader Skill

Download and summarize Twitter/X posts, save media into Minis, and return chat-ready Markdown.

## When to Use
- User provides a twitter.com or x.com status URL.
- User asks to download Twitter/X images, GIFs, or videos.
- User asks what a tweet says/contains.
- User wants downloaded media inserted/displayed in chat as Markdown.

## What It Does
1. Parses username and tweet/status ID from Twitter/X URL variants.
2. Fetches structured JSON from `api.fxtwitter.com`, with fallback to `api.vxtwitter.com`.
3. Generates a short summary:
   - author
   - text
   - created time if available
   - sensitive flag
   - original media URLs
4. Downloads images, video thumbnails, and GIF/video files by default.
5. Returns Markdown containing:
   - `## Tweet Summary`
   - summary/raw JSON links
   - inline media syntax for images/thumbnails/videos/GIFs: `![filename](minis://...)`

## Dependencies
- `curl`
- `jq`
- `python3`

The helper script auto-installs missing packages with `apk add --no-cache`.

## Helper Script
Path:
`/var/minis/skills/twitter-downloader/scripts/twitter_downloader.sh`

Usage:
```sh
/var/minis/skills/twitter-downloader/scripts/twitter_downloader.sh "<tweet_url>"
```

Options:
```sh
--dir DIR        Output directory, default /var/minis/workspace/tweet_media
--images         Download images/thumbnails only in addition to summary
--video          Download videos/GIFs only in addition to summary
--all            Download images/thumbnails and videos/GIFs; default when no media flag is provided
--no-download    Only fetch summary/JSON and return Markdown links for those files
--json-only      Fetch and print raw tweet JSON only; no Markdown output
```

Examples:
```sh
# Default: download all available media and output Markdown
/var/minis/skills/twitter-downloader/scripts/twitter_downloader.sh "https://x.com/user/status/123"

# Summary only, no media downloads
/var/minis/skills/twitter-downloader/scripts/twitter_downloader.sh "https://x.com/user/status/123" --no-download

# Custom output directory
/var/minis/skills/twitter-downloader/scripts/twitter_downloader.sh "https://x.com/user/status/123" --dir "/var/minis/workspace/tweet_media"
```

Generated files:
```text
/var/minis/workspace/tweet_media/<tweet_id>.json
/var/minis/workspace/tweet_media/<tweet_id>_summary.txt
/var/minis/workspace/tweet_media/<tweet_id>/<media files>
```

## Agent Workflow
1. Run the helper script with the tweet URL.
2. Paste stdout directly into chat.
3. Do not merely mention the folder path; include generated Markdown links.
4. Keep images, thumbnails, videos, and GIFs as inline media syntax:
   `![filename](minis://...)`
5. Keep JSON/text summary files as normal links:
   `[filename](minis://...)`
6. If `Sensitive: True`, preserve that field and avoid adding explicit extra descriptions unless the user asks.

## Output Format
The helper outputs Markdown similar to:

```md
## Tweet Summary

- Author: ...
- Text: ...
- Created: ...
- Sensitive: false
- Media:
-   photo https://...
- Downloaded images: 1, videos: 1

## File Links

- [summary.txt](minis://workspace/...)
- [raw.json](minis://workspace/...)

## Media

![photo.jpg](minis://workspace/.../photo.jpg)

![video.mp4](minis://workspace/.../video.mp4)
```

## Error Handling
- If URL parsing fails, ask for a valid `twitter.com`/`x.com` status URL.
- If both APIs fail, report that the tweet may be private/deleted or the API may be temporarily unavailable.
- If no media is found, still return the tweet summary and JSON/summary links.

## Notes
- Video/GIF downloads choose the best bitrate variant when available.
- Video/GIF thumbnails are downloaded when image download is enabled.
- Minis URLs are percent-encoded by the helper.
