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
# Requires python3 for structured JSON updates and validation (no jq).
# Writes use a same-directory temporary file and atomic replacement.
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
  JSON="$1" KEY="$2"
  if printf '%s' "$JSON" | grep -qE "\"$KEY\"[[:space:]]*:[[:space:]]*\""; then
    printf '%s' "$JSON" | sed -nE "s/.*\"$KEY\"[[:space:]]*:[[:space:]]*\"([^\"]*)\".*/\1/p"
  else
    printf '%s' "$JSON" | sed -nE "s/.*\"$KEY\"[[:space:]]*:[[:space:]]*([^,}[:space:]]+).*/\1/p"
  fi
}

# --- Structured setter; output stays compatible with existing sed readers ---
# Strings cannot contain controls, quotes or backslashes. Python decodes old
# JSON before validating this domain and emits a single line with literal Unicode.
set_field() {
  JSON="$1" KEY="$2" VAL="$3"

  # 1. Strict key whitelist to prevent schema injection
  case "$KEY" in
    onboarded|quality|save_location|save_mode) ;;
    *)
      echo "ERROR: Invalid config key '$KEY'. Allowed keys: onboarded, quality, save_location, save_mode" >&2
      return 1
      ;;
  esac

  # 1b. onboarded is a boolean field — accept only true or false
  if [ "$KEY" = "onboarded" ] && { [ "$VAL" != "true" ] && [ "$VAL" != "false" ]; }; then
    echo "ERROR: 'onboarded' only accepts true or false (got '$VAL')" >&2
    return 1
  fi

  # 2. Reject control characters, double quotes, and backslashes
  case "$VAL" in
    *[[:cntrl:]]*)
      echo "ERROR: Value for '$KEY' contains invalid control characters" >&2
      return 1
      ;;
    *\"* | *\\*)
      echo "ERROR: Value for '$KEY' must not contain double quotes or backslashes" >&2
      return 1
      ;;
  esac

  if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is required for structured configuration updates" >&2
    return 1
  fi

  RES=$(python3 -c '
import json, sys
raw_json = sys.argv[1]
key = sys.argv[2]
val = sys.argv[3]
try:
    def unique_object(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError("duplicate config key")
            result[k] = v
        return result
    data = json.loads(raw_json, object_pairs_hook=unique_object)
    if not isinstance(data, dict):
        sys.exit(2)
    allowed_keys = {"onboarded", "quality", "save_location", "save_mode"}
    for k, v in data.items():
        if k not in allowed_keys:
            sys.exit(3)
        if k == "onboarded":
            if not isinstance(v, bool):
                sys.exit(4)
        else:
            if not isinstance(v, str) or any(ord(c) < 32 or ord(c) == 127 for c in v) or "\"" in v or "\\" in v:
                sys.exit(5)

    if key == "onboarded":
        data[key] = (val.lower() == "true")
    else:
        data[key] = val
    print(json.dumps(data, ensure_ascii=False))
except Exception:
    sys.exit(1)
' "$JSON" "$KEY" "$VAL")

  if [ $? -ne 0 ] || [ -z "$RES" ]; then
    echo "ERROR: Config transformation or validation failed for '$KEY'" >&2
    return 1
  fi

  # 3. Confirm the update actually took effect
  if [ "$(get_field "$RES" "$KEY")" != "$VAL" ]; then
    echo "ERROR: Field '$KEY' was not updated (no match in config)" >&2
    return 1
  fi

  printf '%s' "$RES"
}

# --- Safe atomic config persistence ---
save_config() {
  NEW_CONTENT="$1"

  if [ -z "$NEW_CONTENT" ]; then
    echo "ERROR: Refusing to write empty configuration" >&2
    return 1
  fi

  if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is required for config validation" >&2
    return 1
  fi

  # Validate before creating the temporary file.
  if ! printf '%s' "$NEW_CONTENT" | python3 -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null; then
    echo "ERROR: Generated config is not valid JSON, keeping existing config" >&2
    return 1
  fi

  TMP_FILE=$(mktemp "${CONFIG_FILE}.XXXXXX") || {
    echo "ERROR: Failed to create temporary config file" >&2
    return 1
  }

  printf '%s\n' "$NEW_CONTENT" > "$TMP_FILE" || {
    echo "ERROR: Failed to write temporary config file" >&2
    rm -f "$TMP_FILE"
    return 1
  }

  if [ ! -s "$TMP_FILE" ]; then
    echo "ERROR: Generated config validation failed, keeping existing config" >&2
    rm -f "$TMP_FILE"
    return 1
  fi

  mv -f "$TMP_FILE" "$CONFIG_FILE" || {
    echo "ERROR: Failed to atomically replace $CONFIG_FILE" >&2
    rm -f "$TMP_FILE"
    return 1
  }
}

case "$1" in
  init)
    save_config "$DEFAULT_CONFIG" || exit 1
    echo "Config initialized at $CONFIG_FILE"
    ;;

  status)
    [ ! -f "$CONFIG_FILE" ] && { save_config "$DEFAULT_CONFIG" || exit 1; }
    CONFIG=$(cat "$CONFIG_FILE") || { echo "ERROR: Failed to read $CONFIG_FILE" >&2; exit 1; }

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
    [ "$#" -lt 3 ] && { echo "ERROR: set requires a value argument (use an explicit empty string for empty)" >&2; echo "Usage: yt-config.sh set <key> <val>" >&2; exit 1; }
    if [ ! -f "$CONFIG_FILE" ]; then save_config "$DEFAULT_CONFIG" || exit 1; fi
    CONFIG=$(cat "$CONFIG_FILE") || { echo "ERROR: Failed to read $CONFIG_FILE" >&2; exit 1; }
    NEW_CONFIG=$(set_field "$CONFIG" "$2" "$3") || exit 1
    save_config "$NEW_CONFIG" || exit 1
    echo "Set $2 = $3"
    ;;

  complete)
    if [ ! -f "$CONFIG_FILE" ]; then save_config "$DEFAULT_CONFIG" || exit 1; fi
    CONFIG=$(cat "$CONFIG_FILE") || { echo "ERROR: Failed to read $CONFIG_FILE" >&2; exit 1; }
    NEW_CONFIG=$(set_field "$CONFIG" "onboarded" "true") || exit 1
    save_config "$NEW_CONFIG" || exit 1
    echo "Onboarding marked complete"
    ;;

  *)
    echo "Usage: yt-config.sh {status|init|set <key> <val>|complete}"
    exit 1
    ;;
esac
