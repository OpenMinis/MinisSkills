#!/bin/sh
# Stop the secondary display (server/bridge/floating window). The virtual display is destroyed with the server; its apps fall back to the main screen.
. "$(dirname "$0")/common.sh"; ensure_adb >/dev/null 2>&1 || exit 0
[ "$1" = quiet ] || save_logs >/dev/null 2>&1   # keep evidence: the next start overwrites server.log/bridge.log
adbx shell "am stopservice $PKG/.PipService >/dev/null 2>&1; am force-stop $PKG"
# Only kill OUR server/bridge (identified by our scid). A user's own scrcpy server (different scid) must survive.
SCID=$(cat "$STATE/scid" 2>/dev/null || echo "${VDISPLAY_SCID:-76646973}")
PIDS=$(adbx shell "ps -A -o PID,ARGS" | grep -E "scrcpy\.Server .*scid=$SCID|vdisplay\.Bridge $SCID" | grep -v grep | awk '{print $1}')
for p in $PIDS; do adbx shell "kill $p" >/dev/null 2>&1; done
rm -f "$STATE/display" "$STATE/port" "$STATE/scid" "$STATE/ui_blocked" "$STATE/ui_heal_ts"
[ "$1" = quiet ] || echo stopped
