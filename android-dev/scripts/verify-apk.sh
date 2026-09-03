#!/bin/sh
set -eu

APK=${1:-}
EXPECTED_PACKAGE=${2:-}
SDK=${ANDROID_SDK_ROOT:-${ANDROID_HOME:-/opt/android-sdk}}
BT="$SDK/build-tools/35.0.0"
JAVA_HOME=${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk}
export JAVA_HOME PATH="$JAVA_HOME/bin:$PATH"

[ -n "$APK" ] || { echo 'Usage: verify-apk.sh APK [EXPECTED_PACKAGE]' >&2; exit 2; }
[ -s "$APK" ] || { echo "ERROR: APK missing or empty: $APK" >&2; exit 1; }
[ -x "$BT/aapt2" ] || { echo 'ERROR: aapt2 missing' >&2; exit 1; }

BADGING=$($BT/aapt2 dump badging "$APK")
printf '%s\n' "$BADGING" | sed -n '1,12p'
if [ -n "$EXPECTED_PACKAGE" ]; then
  ACTUAL=$(printf '%s\n' "$BADGING" | sed -n "s/^package: name='\([^']*\)'.*/\1/p" | head -1)
  [ "$ACTUAL" = "$EXPECTED_PACKAGE" ] || { echo "ERROR: package mismatch: $ACTUAL" >&2; exit 1; }
fi
printf '%s\n' "$BADGING" | grep -q '^launchable-activity:' || { echo 'ERROR: no launchable activity' >&2; exit 1; }
unzip -t "$APK" >/dev/null || { echo 'ERROR: ZIP integrity failed' >&2; exit 1; }
if [ -x "$BT/apksigner" ]; then
  "$BT/apksigner" verify --verbose --print-certs "$APK"
else
  echo 'ERROR: apksigner missing; signature not verified' >&2
  exit 1
fi
HASH=$(sha256sum "$APK" | awk '{print $1}')
SIZE=$(wc -c < "$APK" | tr -d ' ')
printf 'APK_SHA256=%s\nAPK_BYTES=%s\nSTATUS=VERIFIED\n' "$HASH" "$SIZE"
