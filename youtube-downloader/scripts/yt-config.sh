#!/bin/sh
# ============================================================================
# yt-config.sh — Config and status manager for the YouTube downloader skill
# ============================================================================
#
# This script manages a JSON config file (../config.json) that persists the
# user's onboarding state and preferences across sessions.
#
# It also reports dependency and mount status so the agent can decide what
# to do on first run (install packages, guide the user to mount a folder, etc.).
#
# No external dependencies (no jq). JSON field access is done with sed because
# the config is simple flat key-value pairs, not nested structures.
#
# Usage:
#   yt-config.sh status           Print config + dependency + mount status
#   yt-config.sh init            Write default config (onboarded = false)
#   yt-config.sh set <key> <val>  Update one config field
#   yt-config.sh complete         Mark onboarding as complete
#
# ============================================================================

CONFIG_FILE="$(dirname "$0")/../config.json"

# Default config written on first run.
# quality: the user's default download quality.
# save_mode: where to save downloads — "files" (iOS Files mount), "photos"
#   (iOS Photos album "YouTube Downloads"), or "minis" (keep in attachments).
DEFAULT_CONFIG='{"onboarded": false, "quality": "1080p", "save_location": "", "save_mode": "files"}'

# --- Simple JSON field reader (no jq needed) ---
get_field() {
  echo "$1" | sed -nE "s/.*\"$2\"[[:space:]]*:[[:space:]]*\"?([^\",}]*)\"?.*/\1/p"
}

# --- Simple JSON field setter ---
set_field() {
  JSON="$1" KEY="$2" VAL="$3"
  if echo "$JSON" | grep -q "\"$KEY\""; then
    echo "$JSON" | sed -E "s/(\"$KEY\"[[:space:]]*:[[:space:]]*)(\"?[^\"]*\"?)([,}])/\1\"$VAL\"\3/"
  else
    echo "$JSON" | sed -E "s/}$/, \"$KEY\": \"$VAL\"}/" | sed -E 's/\{,/\{/'
  fi
}

case "$1" in
  init)
    echo "$DEFAULT_CONFIG" > "$CONFIG_FILE"
    echo "Config initialized at $CONFIG_FILE"
    ;;

  status)
    [ ! -f "$CONFIG_FILE" ] && echo "$DEFAULT_CONFIG" > "$CONFIG_FILE"
    CONFIG=$(cat "$CONFIG_FILE")

    # --- Dependency checks ---
    # yt-dlp: the download engine. Alpine's package version is stale —
    #   the onboarding flow upgrades it via pip.
    # ffmpeg: needed to merge DASH streams and remux to iOS-compatible format.
    # pip: needed to upgrade yt-dlp to the latest version.
    YTDLP="no"; [ -x "$(which yt-dlp 2>/dev/null)" ] && YTDLP="yes"
    FFMPEG="no"; [ -x "$(which ffmpeg 2>/dev/null)" ] && FFMPEG="yes"
    PIP="no"; [ -x "$(which pip 2>/dev/null)" ] && PIP="yes"

    # --- Mount checks ---
    # The user mounts an iOS Files folder (e.g., Downloads) so the script can
    # move completed downloads there. Without a mount, files stay in /var/minis/attachments/.
    DOWNLOADS_MOUNT="no"
    if [ -d /var/minis/mounts/Downloads ] && [ -w /var/minis/mounts/Downloads ]; then
      DOWNLOADS_MOUNT="yes"
    fi
    ANY_MOUNT="no"
    if [ -d /var/minis/mounts/ ] && [ "$(ls -A /var/minis/mounts/ 2>/dev/null)" ]; then
      ANY_MOUNT="yes"
    fi
    MOUNTS=""
    if [ -d /var/minis/mounts/ ]; then
      MOUNTS=$(ls /var/minis/mounts/ 2>/dev/null | tr '\n' ',')
    fi

    echo "CONFIG:"
    echo "  onboarded: $(get_field "$CONFIG" "onboarded")"
    echo "  quality: $(get_field "$CONFIG" "quality")"
    echo "  save_mode: $(get_field "$CONFIG" "save_mode")"
    echo "  save_location: $(get_field "$CONFIG" "save_location")"
    echo ""
    echo "DEPENDENCIES:"
    echo "  yt-dlp: $YTDLP"
    echo "  ffmpeg: $FFMPEG"
    echo "  pip: $PIP"
    echo ""
    echo "MOUNTS:"
    echo "  any_mount: $ANY_MOUNT"
    echo "  downloads_mount: $DOWNLOADS_MOUNT"
    [ -n "$MOUNTS" ] && echo "  available_mounts: $MOUNTS"
    ;;

  set)
    [ ! -f "$CONFIG_FILE" ] && echo "$DEFAULT_CONFIG" > "$CONFIG_FILE"
    CONFIG=$(cat "$CONFIG_FILE")
    NEW_CONFIG=$(set_field "$CONFIG" "$2" "$3")
    echo "$NEW_CONFIG" > "$CONFIG_FILE"
    echo "Set $2 = $3"
    ;;

  complete)
    [ ! -f "$CONFIG_FILE" ] && echo "$DEFAULT_CONFIG" > "$CONFIG_FILE"
    CONFIG=$(cat "$CONFIG_FILE")
    NEW_CONFIG=$(set_field "$CONFIG" "onboarded" "true")
    echo "$NEW_CONFIG" > "$CONFIG_FILE"
    echo "Onboarding marked complete"
    ;;

  *)
    echo "Usage: yt-config.sh {status|init|set <key> <val>|complete}"
    exit 1
    ;;
esac