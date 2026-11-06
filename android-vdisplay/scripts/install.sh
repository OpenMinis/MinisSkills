#!/bin/sh
# Install/update (idempotent): push jars, install APK, grant overlay permission. Outputs JSON; non-zero exit on failure.
. "$(dirname "$0")/common.sh"; ensure_adb || { echo '{"ok":false,"stage":"adb","hint":"Device disconnected or unauthorized; see references/setup.md"}'; exit 3; }
err() { echo "{\"ok\":false,\"stage\":\"$1\",\"hint\":\"$2\"}"; exit 1; }
adbx shell "mkdir -p $DEV" || err push "Cannot write to $DEV"
T=60 adbx push "$SK_DIR/assets/scrcpy-server.jar" $DEV/server.jar >/dev/null 2>&1 || err push "Failed to push server.jar (check storage/authorization)"
T=60 adbx push "$SK_DIR/assets/skilled-shell.jar" $DEV/shell.jar >/dev/null 2>&1 || err push "Failed to push shell.jar"
R=$(T=120 adbx install -r "$SK_DIR/assets/skilled.apk" 2>&1 | tail -1)
case "$R" in *Success*) ;; *) err apk "APK install failed: $R (if signature conflicts, ask the user before uninstalling the old $PKG)";; esac
adbx shell "appops set $PKG SYSTEM_ALERT_WINDOW allow; pm grant $PKG android.permission.POST_NOTIFICATIONS 2>/dev/null; cmd deviceidle whitelist +$PKG >/dev/null 2>&1"
adbx shell "appops get $PKG SYSTEM_ALERT_WINDOW" | grep -qi allow || err permission "Overlay permission not granted; ask the user to enable Display over other apps in Settings -> Apps -> Special app access"
ensure_ui >/dev/null 2>&1   # best effort: enable the read-only /ui accessibility service (appends, idempotent)
echo '{"ok":true}'
