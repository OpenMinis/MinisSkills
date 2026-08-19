#!/bin/sh
# ============================================================================
# yt-download.sh — YouTube downloader for Minis (running inside iSH on iOS)
# ============================================================================
#
# WHAT THIS DOES
#   Downloads a YouTube video or extracts audio, names the file after the
#   video title, remuxes to an iOS-compatible container, and moves it to the
#   user's iOS Files folder (if mounted).
#
# WHY THIS IS NON-STANDARD
#   This script runs inside iSH — a Linux usermode emulator on iOS. Two things
#   that work fine on a normal Linux machine are broken here:
#
#   1. yt-dlp's built-in video+audio merger fails in iSH.
#      When downloading DASH formats (1080p, 1440p), YouTube serves video and
#      audio as separate files. yt-dlp normally merges them itself — but that
#      merge step crashes in iSH ("Error opening input files"). We work around
#      this by passing -k (keep video) so the separate files survive the crash,
#      then we merge them ourselves with a direct ffmpeg call.
#
#   2. YouTube's MP4 files use the "mp42" major brand, which iOS sometimes
#      treats as audio-only (video track is ignored). We remux everything with
#      ffmpeg and the correct container: H.264 → M4V (Apple's video container),
#      AV1/VP9 → standard mp4 with +faststart.
#
# USAGE
#   sh yt-download.sh "<url>" [quality] [save_mode]
#
#   Quality:  audio, 360p, 720p, 1080p, 1440p, best
#   Save mode (optional, overrides config):
#     files   — move to iOS Files mount (Downloads folder)
#     photos  — save to iOS Photos album "YouTube Downloads" via apple-photos
#     minis   — keep in /var/minis/attachments/
#
#   Default quality and save mode come from ../config.json
#
# OUTPUTS
#   SUCCESS: <path> (<size>)
#   SAVED_TO_FILES: <path>      — moved to iOS Files mount
#   SAVED_TO_PHOTOS: <path>     — saved to iOS Photos album
#   KEPT_IN_ATTACHMENTS: <path> — kept in sandbox
#
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/../config.json"

URL="$1"

# ── Load user config ──────────────────────────────────────────────────────────
DEFAULT_QUALITY="1080p"
DEFAULT_SAVE_MODE="files"
SAVE_LOCATION=""

if [ -f "$CONFIG_FILE" ]; then
  CFG=$(cat "$CONFIG_FILE")
  DEFAULT_QUALITY=$(echo "$CFG" | sed -nE 's/.*"quality"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/p')
  DEFAULT_SAVE_MODE=$(echo "$CFG" | sed -nE 's/.*"save_mode"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/p')
  SAVE_LOCATION=$(echo "$CFG" | sed -nE 's/.*"save_location"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/p')
  # Backward compat: old config had "save_to_files": "true" → treat as "files"
  if [ -z "$DEFAULT_SAVE_MODE" ]; then
    OLD_FLAG=$(echo "$CFG" | sed -nE 's/.*"save_to_files"[[:space:]]*:[[:space:]]*"?([^",}]*)"?.*/\1/p')
    [ "$OLD_FLAG" = "true" ] && DEFAULT_SAVE_MODE="files"
  fi
  [ -z "$DEFAULT_QUALITY" ] && DEFAULT_QUALITY="1080p"
  [ -z "$DEFAULT_SAVE_MODE" ] && DEFAULT_SAVE_MODE="files"
fi

QUALITY="${2:-$DEFAULT_QUALITY}"
SAVE_MODE="${3:-$DEFAULT_SAVE_MODE}"
OUTDIR="/var/minis/attachments"

[ -z "$URL" ] && { echo "ERROR: No URL provided" >&2; echo "Usage: yt-download.sh <url> [quality] [files|photos|minis]" >&2; exit 1; }
mkdir -p "$OUTDIR"

# ── Get the video title for a human-readable filename ─────────────────────────
# yt-dlp --get-title fetches the title from YouTube's API.
# If that fails (network error, JS runtime warning), fall back to the video ID.
TITLE=$(yt-dlp --get-title --no-playlist "$URL" 2>/dev/null | tail -1)
if [ -z "$TITLE" ]; then
  TITLE=$(echo "$URL" | grep -oE 'v=[A-Za-z0-9_-]{11}' | head -1 | cut -d= -f2)
  [ -z "$TITLE" ] && TITLE=$(echo "$URL" | grep -oE 'youtu\.be/[A-Za-z0-9_-]{11}' | head -1 | cut -d/ -f2)
  [ -z "$TITLE" ] && TITLE=$(echo "$URL" | grep -oE 'shorts/[A-Za-z0-9_-]{11}' | head -1 | cut -d/ -f2)
  [ -z "$TITLE" ] && TITLE="video_$(date +%s)"
fi

# Sanitize: strip characters iOS doesn't allow in filenames, trim, cap at 80 chars
SAFE_TITLE=$(echo "$TITLE" | sed 's/[/\\:*?"<>|]/_/g' | sed 's/  */ /g' | sed 's/^ *//;s/ *$//' | cut -c1-80)
[ -z "$SAFE_TITLE" ] && SAFE_TITLE="video_$(date +%s)"

# ── Format selection ──────────────────────────────────────────────────────────
#
# YouTube serves video in two ways:
#   - Pre-merged: video + audio in a single file (format 18 = 360p, format 22 = 720p)
#   - DASH: video and audio as separate files, must be merged afterward
#
# DASH formats offer higher quality (1080p, 1440p) but require the merge workaround.
# Format fallback chains (e.g., "299+140/22/18") mean: try 299+140 first, if that
# fails try format 22, if that fails try format 18. This way a 1080p request still
# gets *something* even if the DASH stream is unavailable.

case "$QUALITY" in
  audio)
    # Format 140 = 128kbps AAC audio. --fixup never skips yt-dlp's container
    # repair step which also crashes in iSH. The raw download plays fine.
    EXT="m4a"; FMT="140/139/bestaudio[ext=m4a]/bestaudio"; MODE="direct"
    ;;
  360p)
    # Format 18 = 360p H.264 + AAC, pre-merged. Most reliable format in iSH.
    EXT="mp4"; FMT="18"; MODE="direct"
    ;;
  720p)
    # Format 22 = 720p H.264 + AAC, pre-merged. Falls back to 360p if unavailable.
    EXT="mp4"; FMT="22/18"; MODE="direct"
    ;;
  1080p)
    # Format 299 = 1080p60 H.264 (video only) + format 140 = AAC audio.
    # Falls back to 720p pre-merged, then 360p.
    EXT="mp4"; FMT="299+140/22/18"; MODE="dash"
    ;;
  1440p)
    # Format 400 = 1440p60 AV1 (video only). AV1 is the only 1440p option.
    # Falls back to VP9 (308), then 1080p H.264 (299), then pre-merged formats.
    EXT="mp4"; FMT="400+140/308+251/299+140/22/18"; MODE="dash"
    ;;
  best)
    EXT="mp4"; FMT="bestvideo[ext=mp4]+bestaudio[ext=m4a]/22/18"; MODE="dash"
    ;;
  *)
    echo "ERROR: Unknown quality '$QUALITY'" >&2
    echo "Valid: audio, 360p, 720p, 1080p, 1440p, best" >&2
    exit 1
    ;;
esac

OUTFILE="$OUTDIR/${SAFE_TITLE}.${EXT}"
TMPDIR="/tmp/yt-dl-$$"
mkdir -p "$TMPDIR"

# ── Download ──────────────────────────────────────────────────────────────────

if [ "$MODE" = "dash" ]; then
  # ── DASH mode: download video + audio separately, merge ourselves ────────────
  #
  # -k (keep video): preserve the separate files even after yt-dlp's merger
  #   crashes. Without -k, yt-dlp deletes them on failure.
  # --no-part: don't write .part files (they cause issues in iSH).
  # || true: yt-dlp's merger will exit with error code 1; don't let that kill
  #   the script (we handle the merge ourselves).
  yt-dlp -f "$FMT" -o "$TMPDIR/v.%(ext)s" --no-playlist -k --no-part "$URL" 2>&1 || true

  # Find the downloaded files. yt-dlp appends format IDs to filenames
  # (e.g., "v.f299.mp4", "v.f140.m4a") for DASH, but falls back to plain
  # "v.mp4" / "v.webm" for pre-merged formats.
  VIDEO_FILE=$(ls "$TMPDIR"/v.f*.mp4 "$TMPDIR"/v.f*.webm "$TMPDIR"/v.mp4 "$TMPDIR"/v.webm "$TMPDIR"/v.mkv 2>/dev/null | grep -v '\.m4a$' | head -1)
  AUDIO_FILE=$(ls "$TMPDIR"/*.m4a 2>/dev/null | head -1)

  if [ -n "$VIDEO_FILE" ] && [ -n "$AUDIO_FILE" ]; then
    # Detect the video codec to choose the right MP4 container.
    # H.264 → M4V container (Apple's brand, best iOS compatibility)
    # AV1/VP9 → standard mp4 container (M4V doesn't support these codecs)
    VCODEC=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$VIDEO_FILE" 2>/dev/null)

    if [ "$VCODEC" = "h264" ]; then
      ffmpeg -y -i "$VIDEO_FILE" -i "$AUDIO_FILE" -c copy -movflags +faststart -f ipod "$OUTFILE" 2>/dev/null
    else
      ffmpeg -y -i "$VIDEO_FILE" -i "$AUDIO_FILE" -c copy -movflags +faststart -f mp4 "$OUTFILE" 2>/dev/null
    fi
  elif [ -n "$VIDEO_FILE" ]; then
    # Fallback: only one file means the format fallback gave us a pre-merged file
    mv "$VIDEO_FILE" "$OUTFILE"
  fi
else
  # ── Direct mode: pre-merged or audio-only ────────────────────────────────────
  EXTRA_OPTS=""
  [ "$QUALITY" = "audio" ] && EXTRA_OPTS="--fixup never"
  yt-dlp -f "$FMT" $EXTRA_OPTS -o "$OUTFILE" --no-playlist "$URL" 2>&1

  # Remux pre-merged video files to iOS-compatible format.
  # YouTube's pre-merged files use the "mp42" brand which iOS may treat as
  # audio-only. Remuxing to M4V brand fixes this. This step is fast (stream copy,
  # no re-encoding) and produces a file iOS reliably plays as video.
  EXT="${OUTFILE##*.}"
  if [ "$EXT" = "mp4" ]; then
    REMUXED="${OUTFILE}.tmp"
    ffmpeg -y -i "$OUTFILE" -c copy -movflags +faststart -f ipod "$REMUXED" 2>/dev/null
    [ -f "$REMUXED" ] && mv "$REMUXED" "$OUTFILE"
  fi
fi

# ── Cleanup temp files ────────────────────────────────────────────────────────
rm -rf "$TMPDIR" 2>/dev/null

# ── Move to destination ───────────────────────────────────────────────────────
if [ -f "$OUTFILE" ]; then
  SIZE=$(ls -lh "$OUTFILE" | awk '{print $5}')
  echo "SUCCESS: $OUTFILE ($SIZE)"

  case "$SAVE_MODE" in
    files)
      # Move to iOS Files app (Downloads folder mount)
      FILES_DIR=""
      if [ -n "$SAVE_LOCATION" ] && [ -d "$SAVE_LOCATION" ] && [ -w "$SAVE_LOCATION" ]; then
        FILES_DIR="$SAVE_LOCATION"
      elif [ -d /var/minis/mounts/Downloads ] && [ -w /var/minis/mounts/Downloads ]; then
        FILES_DIR="/var/minis/mounts/Downloads"
      fi
      if [ -n "$FILES_DIR" ]; then
        mv "$OUTFILE" "$FILES_DIR/"
        echo "SAVED_TO_FILES: $FILES_DIR/$(basename "$OUTFILE")"
      else
        echo "NOTICE: No Files mount available — file kept in attachments"
        echo "KEPT_IN_ATTACHMENTS: $OUTFILE"
      fi
      ;;

    photos)
      # Save to iOS Photos album "YouTube Downloads" via apple-photos CLI.
      # Photos only accepts images and video — audio (.m4a) falls back to attachments.
      EXT="${OUTFILE##*.}"
      if [ "$EXT" = "m4a" ] || [ "$EXT" = "mp3" ]; then
        echo "NOTICE: Photos does not support audio files — keeping in attachments"
        echo "KEPT_IN_ATTACHMENTS: $OUTFILE"
      elif command -v apple-photos >/dev/null 2>&1; then
        apple-photos save --path "$OUTFILE" --album-name "YouTube Downloads" 2>&1
        rm -f "$OUTFILE"
        echo "SAVED_TO_PHOTOS: YouTube Downloads album"
      else
        echo "NOTICE: apple-photos not available — file kept in attachments"
        echo "KEPT_IN_ATTACHMENTS: $OUTFILE"
      fi
      ;;

    minis)
      # Keep in attachments — user can view/play in-chat
      echo "KEPT_IN_ATTACHMENTS: $OUTFILE"
      ;;

    *)
      echo "ERROR: Unknown save mode '$SAVE_MODE'" >&2
      echo "Valid: files, photos, minis" >&2
      echo "File left at: $OUTFILE"
      ;;
  esac
else
  echo "ERROR: Download failed — file not found" >&2
  exit 1
fi