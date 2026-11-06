#!/bin/sh
# Shared helpers: locate the skill dir, adb wrapper with timeout and self-healing. Sourced by other scripts.
SK_DIR=$(cd "$(dirname "$0")/.." && pwd)
PKG=app.openminis.vdisplay
DEV=/data/local/tmp/sc
AGENT_PORT=${AGENT_PORT:-28080}
STATE=${SKILLED_STATE:-$HOME/.android-vdisplay}; mkdir -p "$STATE"

# adb target: SERIAL env var first; else the only online device; else try ADB_CONNECT (default localhost:5555)
adbx() {
  if [ -n "$SERIAL" ]; then timeout ${T:-30} adb -s "$SERIAL" "$@"; else timeout ${T:-30} adb "$@"; fi
}
# The adb server occasionally hangs (commands unresponsive). If detected, restart it on a different local port. The port is stored in $STATE/adbport.
adb_heal() {
  P=${ANDROID_ADB_SERVER_PORT:-$(cat "$STATE/adbport" 2>/dev/null || echo 5037)}
  export ANDROID_ADB_SERVER_PORT=$P
  if ! timeout 8 adb devices >/dev/null 2>&1; then
    P=$((P<5400?5400:P+1)); echo $P > "$STATE/adbport"; export ANDROID_ADB_SERVER_PORT=$P
    (adb start-server >/dev/null 2>&1 &); sleep 4
    [ -n "$ADB_CONNECT" ] && timeout 15 adb connect "$ADB_CONNECT" >/dev/null 2>&1
  fi
}
ensure_adb() {
  command -v adb >/dev/null 2>&1 || { echo "ERR: 找不到 adb（Alpine: apk add android-tools）"; return 2; }
  adb_heal
  if ! adbx devices 2>/dev/null | grep -q 'device$'; then
    adb start-server >/dev/null 2>&1
    if [ -n "$ADB_CONNECT" ] || [ -z "$SERIAL" ]; then timeout 15 adb connect "${ADB_CONNECT:-localhost:5555}" >/dev/null 2>&1; fi
  fi
  N=$(timeout 8 adb devices 2>/dev/null | grep -c 'device$')
  if [ "$N" = "0" ]; then echo "ERR: 无在线设备。请先开启开发者选项 → 无线调试并 adb pair/connect，见 references/setup.md"; return 3; fi
  if [ "$N" -gt 1 ] && [ -z "$SERIAL" ]; then echo "ERR: 多个设备，请设置 SERIAL=<序列号>"; adb devices; return 4; fi
  return 0
}
# Host calls the on-device agent API via adb forward; the local port is saved in $STATE/fport and the forward is recreated if lost
fwd() {
  FP=$(cat "$STATE/fport" 2>/dev/null || echo 28090)
  if ! timeout 4 curl -s "http://127.0.0.1:$FP/status" >/dev/null 2>&1; then
    adbx forward --remove "tcp:$FP" >/dev/null 2>&1
    while ! adbx forward "tcp:$FP" "tcp:$AGENT_PORT" >/dev/null 2>&1; do FP=$((FP+1)); [ $FP -gt 28190 ] && return 1; done
    echo $FP > "$STATE/fport"
  fi
}

# Fast path: call the agent straight through the existing forward; only if that fails, run the (slower) adb health check / forward repair.
# This removes `adb devices` and the /status probe from every successful call (they cost ~150–400 ms each time).
agent() {
  FP=$(cat "$STATE/fport" 2>/dev/null || echo 28090)
  R=$(timeout ${CT:-15} curl -s -m ${CT:-15} "http://127.0.0.1:$FP$1" 2>/dev/null) && [ -n "$R" ] && { printf '%s\n' "$R"; return 0; }
  ensure_adb || return $?
  fwd || { echo '{"ok":false,"error":"forward failed"}'; return 1; }
  timeout ${CT:-15} curl -s "http://127.0.0.1:$FP$1"
}
agent_to() {
  FP=$(cat "$STATE/fport" 2>/dev/null || echo 28090)
  timeout 20 curl -s -m 20 "http://127.0.0.1:$FP$1" -o "$2" 2>/dev/null && [ -s "$2" ] && return 0
  ensure_adb || return $?
  fwd || return 1; timeout 20 curl -s "http://127.0.0.1:$FP$1" -o "$2"
}

# Upgrade hint appended to all errors: update to the latest version and retry
SK_VERSION=$(cat "$SK_DIR/assets/VERSION" 2>/dev/null)
upgrade_hint() { echo "hint: 本 skill 版本 ${SK_VERSION:-?}。出错请先更新到最新版（重新安装本 skill 包，再运行 start.sh 会自动升级设备上的 APK），再试一次是否解决。详见 CHANGELOG.md"; }
# Read the APK version on the device: prints JSON (device_version/skill_version/match)
version_info() {
  HAVE=$(adbx shell "dumpsys package $PKG 2>/dev/null | grep -m1 versionName | sed 's/.*=//'" 2>/dev/null | tr -d '\r ')
  M=false; [ "$HAVE" = "$SK_VERSION" ] && M=true
  echo "{\"skill\":\"${SK_VERSION}\",\"apk\":\"${HAVE:-not-installed}\",\"match\":$M}"
}

# Preserve evidence before anything restarts the display: copies server.log, bridge.log and the app's logcat into
# $STATE/logs/<timestamp>/ (last 5 sets kept). Prints the directory (empty if the device is unreachable).
save_logs() {
  _d="$STATE/logs/$(date +%Y%m%d-%H%M%S)"; mkdir -p "$_d" || return 0
  adbx shell "cat $DEV/server.log" > "$_d/server.log" 2>/dev/null
  adbx shell "cat $DEV/bridge.log" > "$_d/bridge.log" 2>/dev/null
  T=20 adbx shell "logcat -d -t 300" 2>/dev/null | grep -E "SKILLED|vdisplay|scrcpy|MediaCodec|ACodec|Codec2" > "$_d/logcat.txt"
  adbx shell "dumpsys package $PKG | grep -m2 versionName" > "$_d/version.txt" 2>/dev/null
  for _o in $(ls -1d "$STATE"/logs/*/ 2>/dev/null | sort -r | tail -n +6); do rm -rf "$_o"; done
  echo "$_d"
}

# Enable our read-only accessibility service (needed by /ui). APPENDS to enabled_accessibility_services (never overwrites other services)
# and is idempotent. Needs WRITE_SECURE_SETTINGS, which the adb shell user has on tested phones. `am force-stop $PKG` (used by start/stop)
# makes Android drop OUR entry only, so this must run after every start. Prints nothing; returns 0 when the service is in the list.
UI_SVC=$PKG/$PKG.UiService
ensure_ui() {
  _cur=$(adbx shell "settings get secure enabled_accessibility_services" 2>/dev/null | tr -d '\r')
  case ":$_cur:" in *":$UI_SVC:"*) ;; *)
    case "$_cur" in null|"") _new=$UI_SVC;; *) _new="$_cur:$UI_SVC";; esac
    adbx shell "settings put secure enabled_accessibility_services '$_new'; settings put secure accessibility_enabled 1" >/dev/null 2>&1 ;;
  esac
  adbx shell "settings get secure enabled_accessibility_services" 2>/dev/null | grep -q "$UI_SVC" || return 1
  # binding takes up to ~3 s after the setting changes: wait until the app reports serviceConnected (max 6 s) so the first /ui works
  _i=0; while [ $_i -lt 30 ]; do agent /status 2>/dev/null | grep -q '"serviceConnected":true' && return 0; _i=$((_i+1)); sleep 0.2; done
  return 0
}
# Heal a LOST accessibility service in the middle of a session (user toggled it off, settings reset, force-stop dropped the entry...).
# Rules, so we never fight the user or loop:
#  - only inside a session WE started ($STATE/display exists; stop.sh removes it) - outside a session we never touch the setting;
#  - at most one attempt per 60 s (if it is switched off again right away, someone means it: stop re-enabling);
#  - if the system refuses the write (some vendor ROMs block `settings put secure`), remember it ($STATE/ui_blocked) and stop trying.
# Returns 0 when the service is enabled again, 1 otherwise. Prints one explanatory line on stderr.
ui_heal() {
  [ -f "$STATE/display" ] || return 1
  [ -f "$STATE/ui_blocked" ] && return 1
  _now=$(date +%s); _last=$(cat "$STATE/ui_heal_ts" 2>/dev/null || echo 0)
  [ $((_now - _last)) -lt 60 ] && return 1
  echo "$_now" > "$STATE/ui_heal_ts"
  if ensure_ui >/dev/null 2>&1; then echo "note: the accessibility service was off; re-enabled it (append-only, other services untouched)" >&2; return 0; fi
  : > "$STATE/ui_blocked"
  echo "note: could not re-enable the accessibility service (the system refused the settings write); use 'agent.sh shot' instead of 'ui'" >&2
  return 1
}
# Remove only OUR entry (other services untouched).
disable_ui() {
  _cur=$(adbx shell "settings get secure enabled_accessibility_services" 2>/dev/null | tr -d '\r')
  _new=$(printf %s "$_cur" | tr ':' '\n' | grep -vx "$UI_SVC" | grep -v '^null$' | paste -sd: -)
  [ "$_new" = "$_cur" ] && return 0
  if [ -z "$_new" ]; then adbx shell "settings delete secure enabled_accessibility_services" >/dev/null 2>&1
  else adbx shell "settings put secure enabled_accessibility_services '$_new'" >/dev/null 2>&1; fi
}
