#!/bin/sh
# Launch an app on the secondary display and confirm it is really in the foreground there: run-app.sh <package>
# Outputs JSON: {"ok":true,"display":N,"top":"<package/Activity>"}; on failure {"ok":false,...} and non-zero exit
. "$(dirname "$0")/common.sh"
[ -z "$1" ] && { echo '{"ok":false,"error":"缺少包名"}'; exit 2; }
ID=$(cat "$STATE/display" 2>/dev/null)
S=$(agent "/status" 2>/dev/null); echo "$S" | grep -q '"ready":true' || { echo '{"ok":false,"error":"副屏未就绪","hint":"先运行 start.sh"}'; exit 1; }
# Launch via the app (it always answers ok; success is judged by the foreground poll below).
agent "/start?pkg=$1" >/dev/null 2>&1
# Wait for the app to become the top activity ON THE DEVICE, polling every 100 ms (one adb call, returns as soon as it is there).
# The same call first checks the package is installed, so a wrong package name fails in ~150 ms instead of after the full wait.
TOP=$(T=20 adbx shell "pm path $1 >/dev/null 2>&1 || { echo NOTINSTALLED; exit 0; }; i=0; while [ \$i -lt 80 ]; do t=\$(dumpsys activity activities | grep -A12 '^Display #$ID ' | grep -m1 topResumedActivity | sed 's/.*u0 //;s/ .*//'); case \"\$t\" in $1*) echo \"\$t\"; exit 0;; esac; i=\$((i+1)); sleep 0.1; done; echo \"\$t\"" | tr -d '\r' | tail -1)
[ "$TOP" = NOTINSTALLED ] && { echo "{\"ok\":false,\"error\":\"未安装 $1\"}"; exit 1; }
case "$TOP" in $1*) echo "{\"ok\":true,\"display\":$ID,\"top\":\"$TOP\"}"; exit 0;; esac
echo "{\"ok\":false,\"error\":\"命令已发送，但 $1 没有出现在副屏 $ID 前台\",\"top\":\"$TOP\",\"hint\":\"可能 App 被系统拦截/需要登录/启动慢；用 agent.sh shot 看画面\",\"upgrade\":\"仍失败请先更新到最新版 skill/APK 再试\"}"; exit 1
