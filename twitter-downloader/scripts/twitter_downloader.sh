#!/usr/bin/env sh
set -e

usage() {
  echo "Usage: $0 <tweet_url> [--dir DIR] [--images] [--video] [--fallback]" >&2
  exit 1
}

[ $# -lt 1 ] && usage

URL="$1"; shift || true
DIR="/var/minis/workspace/tweet_media"
DL_IMAGES=0
DL_VIDEO=0
FALLBACK=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dir) DIR="$2"; shift 2 ;;
    --images) DL_IMAGES=1; shift ;;
    --video) DL_VIDEO=1; shift ;;
    --fallback) FALLBACK=1; shift ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done

# Ensure deps
need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing $1. Installing..."; apk add --no-cache "$1" >/dev/null; }; }
need curl
need jq

mkdir -p "$DIR"

# Normalize URL
CLEAN="${URL%%[?#]*}"
CLEAN="${CLEAN%/}"
# Extract username and id using sed (POSIX)
USERNAME=$(printf %s "$CLEAN" | sed -nE 's#.*(twitter\.com|x\.com)/([^/]+)/status/([0-9]+).*#\2#p')
TWEET_ID=$(printf %s "$CLEAN" | sed -nE 's#.*status/([0-9]+).*#\1#p')

if [ -z "$USERNAME" ] || [ -z "$TWEET_ID" ]; then
  echo "Failed to parse username or tweet id from URL: $URL" >&2
  exit 2
fi

API_HOST="api.fxtwitter.com"
[ "$FALLBACK" -eq 1 ] && API_HOST="api.vxtwitter.com"
API_URL="https://$API_HOST/$USERNAME/status/$TWEET_ID"
OUT_JSON="$DIR/${TWEET_ID}.json"

# Fetch JSON
if ! curl -fsSL "$API_URL" -o "$OUT_JSON"; then
  if [ "$FALLBACK" -eq 0 ]; then
    echo "Primary API failed. Retrying with fallback api.vxtwitter.com..." >&2
    API_HOST="api.vxtwitter.com"
    API_URL="https://$API_HOST/$USERNAME/status/$TWEET_ID"
    curl -fsSL "$API_URL" -o "$OUT_JSON"
  else
    echo "Failed to fetch tweet data from $API_URL" >&2
    exit 3
  fi
fi

# Summarize via Python (more robust than jq on Alpine builds)
SUMMARY="$DIR/${TWEET_ID}_summary.txt"
need python3
python3 - <<'PY' "$OUT_JSON" "$SUMMARY"
import sys, json
inp, outp = sys.argv[1], sys.argv[2]
with open(inp, 'r', encoding='utf-8') as f:
    data = json.load(f)

t = data.get('tweet', {})
lines = []
author = t.get('author', {})
lines.append(f"Author: {author.get('name','unknown')} (@{author.get('screen_name','')})")
lines.append(f"Text: {t.get('text','(no text)')}")
lines.append(f"Created: {t.get('creation_date','')}" )
lines.append(f"Sensitive: {t.get('possibly_sensitive', False)}")
lines.append("Media:")
media_all = (t.get('media') or {}).get('all') or []
for m in media_all:
    mtype = m.get('type')
    if mtype == 'photo':
        url = m.get('url')
        if url:
            lines.append(f"  photo {url}")
    elif mtype == 'video':
        # choose best bitrate variant if available
        url = m.get('url')
        variants = m.get('variants') or []
        if variants:
            try:
                url = max(variants, key=lambda v: v.get('bitrate', 0)).get('url') or url
            except Exception:
                url = url
        if url:
            lines.append(f"  video {url}")
        thumb = m.get('thumbnail_url')
        if thumb:
            lines.append(f"  thumb {thumb}")
    elif mtype == 'gif':
        url = m.get('url')
        if url:
            lines.append(f"  gif {url}")
        thumb = m.get('thumbnail_url')
        if thumb:
            lines.append(f"  thumb {thumb}")
with open(outp, 'w', encoding='utf-8') as f:
    f.write("\n".join(lines) + "\n")
print(outp)
PY

# Optional downloads
if [ "$DL_IMAGES" -eq 1 ] || [ "$DL_VIDEO" -eq 1 ]; then
  mkdir -p "$DIR/$TWEET_ID"
  IMGS_DOWN=0
  VIDS_DOWN=0
  # Photos
  if [ "$DL_IMAGES" -eq 1 ]; then
    for url in $(jq -r '.tweet.media.all[]? | select(.type=="photo") | .url' "$OUT_JSON"); do
      fname="$DIR/$TWEET_ID/$(basename "$url" | cut -d'?' -f1)"
      curl -fsSL "$url" -o "$fname" && IMGS_DOWN=$((IMGS_DOWN+1))
    done
    # Thumbnails for video/gif
    for url in $(jq -r '.tweet.media.all[]? | select(.type=="video" or .type=="gif") | .thumbnail_url // empty' "$OUT_JSON"); do
      fname="$DIR/$TWEET_ID/thumb_$(basename "$url" | cut -d'?' -f1)"
      curl -fsSL "$url" -o "$fname" && IMGS_DOWN=$((IMGS_DOWN+1))
    done
  fi
  # Video best quality
  if [ "$DL_VIDEO" -eq 1 ]; then
    for url in $(jq -r '.tweet.media.all[]? | select(.type=="video") | (if (.variants // null) then (.variants | max_by(.bitrate).url) else .url end)' "$OUT_JSON"); do
      base="$(basename "$url" | cut -d'?' -f1)"; [ -z "$base" ] && base="${TWEET_ID}.mp4"
      fname="$DIR/$TWEET_ID/$base"
      curl -fsSL "$url" -o "$fname" && VIDS_DOWN=$((VIDS_DOWN+1))
    done
  fi
  echo "Downloaded images: $IMGS_DOWN, videos: $VIDS_DOWN" >> "$SUMMARY"
fi

echo "OK: $SUMMARY"
