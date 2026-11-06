#!/bin/sh
# Install/update (idempotent): push jars, install APK, grant overlay permission. Outputs JSON; non-zero exit on failure.
. "$(dirname "$0")/common.sh"; ensure_adb || { echo '{"ok":false,"stage":"adb","hint":"设备未连接或未授权"}'; exit 3; }
err() { echo "{\"ok\":false,\"stage\":\"$1\",\"hint\":\"$2\"}"; exit 1; }
adbx shell "mkdir -p $DEV" || err push "无法写 $DEV"
T=60 adbx push "$SK_DIR/assets/scrcpy-server.jar" $DEV/server.jar >/dev/null 2>&1 || err push "推送 server.jar 失败（空间/授权）"
T=60 adbx push "$SK_DIR/assets/skilled-shell.jar" $DEV/shell.jar >/dev/null 2>&1 || err push "推送 shell.jar 失败"
R=$(T=120 adbx install -r "$SK_DIR/assets/skilled.apk" 2>&1 | tail -1)
case "$R" in *Success*) ;; *) err apk "APK 安装失败: $R（签名冲突时需用户确认后卸载旧版 $PKG）";; esac
adbx shell "appops set $PKG SYSTEM_ALERT_WINDOW allow; pm grant $PKG android.permission.POST_NOTIFICATIONS 2>/dev/null; cmd deviceidle whitelist +$PKG >/dev/null 2>&1"
adbx shell "appops get $PKG SYSTEM_ALERT_WINDOW" | grep -qi allow || err permission "悬浮窗权限未授予，请用户在 设置→应用→特殊权限→显示在其他应用上层 手动开启"
ensure_ui >/dev/null 2>&1   # best effort: enable the read-only /ui accessibility service (appends, idempotent)
echo '{"ok":true}'
