#!/bin/sh
# Launch an app on the secondary display and confirm it is really in the foreground there: run-app.sh <package>
# Outputs JSON: {"ok":true,"display":N,"top":"<package/Activity>"}; on failure {"ok":false,...} and non-zero exit
. "$(dirname "$0")/common.sh"
[ -z "$1" ] && { echo '{"ok":false,"error":"Missing package name"}'; exit 2; }
ID=$(cat "$STATE/display" 2>/dev/null)
S=$(agent "/status" 2>/dev/null); echo "$S" | grep -q '"ready":true' || { echo '{"ok":false,"error":"Virtual display not ready","hint":"Run start.sh first"}'; exit 1; }
# Launch via the app (it always answers ok; success is judged by the foreground poll below).
agent "/start?pkg=$1" >/dev/null 2>&1
# Wait for the app to become the top activity ON THE DEVICE, polling every 100 ms (one adb call, returns as soon as it is there).
# The same call first checks the package is installed, so a wrong package name fails in ~150 ms instead of after the full wait.
TOP=$(T=20 adbx shell "pm path $1 >/dev/null 2>&1 || { echo NOTINSTALLED; exit 0; }; i=0; while [ \$i -lt 80 ]; do t=\$(dumpsys activity activities | grep -A12 '^Display #$ID ' | grep -m1 topResumedActivity | sed 's/.*u0 //;s/ .*//'); case \"\$t\" in $1*) echo \"\$t\"; exit 0;; esac; i=\$((i+1)); sleep 0.1; done; echo \"\$t\"" | tr -d '\r' | tail -1)
[ "$TOP" = NOTINSTALLED ] && { echo "{\"ok\":false,\"error\":\"Package not installed: $1\"}"; exit 1; }
case "$TOP" in $1*) echo "{\"ok\":true,\"display\":$ID,\"top\":\"$TOP\"}"; exit 0;; esac
echo "{\"ok\":false,\"error\":\"Launch sent, but $1 did not reach the foreground on display $ID\",\"top\":\"$TOP\",\"hint\":\"The app may be blocked by the OS, require sign-in, or be slow to start; inspect with agent.sh shot\",\"upgrade\":\"If errors persist, update to the latest skill/APK first\"}"; exit 1
