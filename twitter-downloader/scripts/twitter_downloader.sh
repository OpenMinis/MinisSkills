#!/usr/bin/env sh
set -e

usage() {
  echo "Usage: $0 <tweet_url> [--dir DIR] [--images] [--video] [--all] [--no-download] [--json-only]" >&2
  exit 1
}

[ $# -lt 1 ] && usage

URL="$1"; shift || true
DIR="/var/minis/workspace/tweet_media"
DL_IMAGES=0
DL_VIDEO=0
NO_DOWNLOAD=0
JSON_ONLY=0
MEDIA_FLAG_SET=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dir) DIR="$2"; shift 2 ;;
    --images) DL_IMAGES=1; MEDIA_FLAG_SET=1; shift ;;
    --video) DL_VIDEO=1; MEDIA_FLAG_SET=1; shift ;;
    --all) DL_IMAGES=1; DL_VIDEO=1; MEDIA_FLAG_SET=1; shift ;;
    --no-download) NO_DOWNLOAD=1; MEDIA_FLAG_SET=1; shift ;;
    --json-only) JSON_ONLY=1; NO_DOWNLOAD=1; MEDIA_FLAG_SET=1; shift ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done

if [ "$MEDIA_FLAG_SET" -eq 0 ]; then
  DL_IMAGES=1
  DL_VIDEO=1
fi

if [ "$NO_DOWNLOAD" -eq 1 ]; then
  DL_IMAGES=0
  DL_VIDEO=0
fi

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing $1. Installing..." >&2; apk add --no-cache "$1" >/dev/null; }
}
need curl
need jq
need python3

mkdir -p "$DIR"

CLEAN="${URL%%[?#]*}"
CLEAN="${CLEAN%/}"
USERNAME=$(printf %s "$CLEAN" | sed -nE 's#.*(twitter\.com|x\.com)/([^/]+)/status/([0-9]+).*#\2#p')
TWEET_ID=$(printf %s "$CLEAN" | sed -nE 's#.*status/([0-9]+).*#\1#p')

if [ -z "$USERNAME" ] || [ -z "$TWEET_ID" ]; then
  echo "Failed to parse username or tweet id from URL: $URL" >&2
  exit 2
fi

OUT_JSON="$DIR/${TWEET_ID}.json"
SUMMARY="$DIR/${TWEET_ID}_summary.txt"
MEDIA_DIR="$DIR/$TWEET_ID"

fetch_json() {
  host="$1"
  api_url="https://$host/$USERNAME/status/$TWEET_ID"
  curl -fsSL "$api_url" -o "$OUT_JSON"
}

if ! fetch_json "api.fxtwitter.com"; then
  echo "Primary API failed. Retrying with fallback api.vxtwitter.com..." >&2
  fetch_json "api.vxtwitter.com" || { echo "Failed to fetch tweet data. It may be private/deleted or API is unavailable." >&2; exit 3; }
fi

if [ "$JSON_ONLY" -eq 1 ]; then
  cat "$OUT_JSON"
  exit 0
fi

python3 /var/minis/skills/twitter-downloader/scripts/summarize_tweet.py "$OUT_JSON" "$SUMMARY"

if [ "$DL_IMAGES" -eq 1 ] || [ "$DL_VIDEO" -eq 1 ]; then
  mkdir -p "$MEDIA_DIR"
  IMGS_DOWN=0
  VIDS_DOWN=0

  if [ "$DL_IMAGES" -eq 1 ]; then
    for media_url in $(jq -r '.tweet.media.all[]? | select(.type=="photo") | .url // empty' "$OUT_JSON"); do
      fname="$MEDIA_DIR/$(basename "$media_url" | cut -d'?' -f1)"
      curl -fsSL "$media_url" -o "$fname" && IMGS_DOWN=$((IMGS_DOWN+1)) || true
    done
    for media_url in $(jq -r '.tweet.media.all[]? | select(.type=="video" or .type=="gif") | .thumbnail_url // empty' "$OUT_JSON"); do
      fname="$MEDIA_DIR/thumb_$(basename "$media_url" | cut -d'?' -f1)"
      curl -fsSL "$media_url" -o "$fname" && IMGS_DOWN=$((IMGS_DOWN+1)) || true
    done
  fi

  if [ "$DL_VIDEO" -eq 1 ]; then
    for media_url in $(jq -r '.tweet.media.all[]? | select(.type=="video" or .type=="gif") | (if ((.variants // []) | length) > 0 then (.variants | max_by(.bitrate // 0).url) else .url end) // empty' "$OUT_JSON"); do
      base="$(basename "$media_url" | cut -d'?' -f1)"
      [ -z "$base" ] && base="${TWEET_ID}.mp4"
      fname="$MEDIA_DIR/$base"
      curl -fsSL "$media_url" -o "$fname" && VIDS_DOWN=$((VIDS_DOWN+1)) || true
    done
  fi

  echo "Downloaded images: $IMGS_DOWN, videos: $VIDS_DOWN" >> "$SUMMARY"
fi

encode_path() {
  python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1]))' "$1"
}

minis_url_for() {
  p="$1"
  case "$p" in
    /var/minis/workspace/*)
      rel="${p#/var/minis/workspace/}"
      printf 'minis://workspace/%s' "$(encode_path "$rel")"
      ;;
    /var/minis/attachments/*)
      rel="${p#/var/minis/attachments/}"
      printf 'minis://attachments/%s' "$(encode_path "$rel")"
      ;;
    /var/minis/shared/*)
      rel="${p#/var/minis/shared/}"
      printf 'minis://shared/%s' "$(encode_path "$rel")"
      ;;
    *)
      printf '%s' "$p"
      ;;
  esac
}

link_for() {
  p="$1"
  name="$(basename "$p")"
  url="$(minis_url_for "$p")"
  printf '[%s](%s)' "$name" "$url"
}

media_for() {
  p="$1"
  name="$(basename "$p")"
  url="$(minis_url_for "$p")"
  printf '![%s](%s)' "$name" "$url"
}

printf '## 推文摘要\n\n'
if [ -f "$SUMMARY" ]; then
  sed 's/^/- /' "$SUMMARY"
else
  printf -- '- 未生成摘要文件\n'
fi

printf '\n## 文件链接\n\n'
[ -f "$SUMMARY" ] && printf -- '- %s\n' "$(link_for "$SUMMARY")"
[ -f "$OUT_JSON" ] && printf -- '- %s\n' "$(link_for "$OUT_JSON")"

printf '\n## 媒体\n\n'
if [ -d "$MEDIA_DIR" ] && [ "$(find "$MEDIA_DIR" -type f | wc -l | tr -d ' ')" -gt 0 ]; then
  find "$MEDIA_DIR" -type f | sort | while IFS= read -r f; do
    ext="$(printf '%s' "${f##*.}" | tr '[:upper:]' '[:lower:]')"
    case "$ext" in
      jpg|jpeg|png|webp|gif|mp4|mov|m4v|webm)
        printf '%s\n\n' "$(media_for "$f")"
        ;;
      *)
        printf -- '- %s\n' "$(link_for "$f")"
        ;;
    esac
  done
else
  printf -- '- 没有下载到媒体文件，可能该推文无媒体，或使用了 --no-download。\n'
fi
