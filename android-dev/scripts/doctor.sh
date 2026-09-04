#!/bin/sh
set -u

SDK=${ANDROID_SDK_ROOT:-${ANDROID_HOME:-/opt/android-sdk}}
JAVA17=${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk}
BT="$SDK/build-tools/35.0.0"
PLATFORM="$SDK/platforms/android-34/android.jar"
READY=1

item() { printf '%s=%s\n' "$1" "$2"; }
missing() { item "$1" missing; READY=0; }

ARCH=$(uname -m 2>/dev/null || echo unknown)
item ARCH "$ARCH"
if [ "$ARCH" != aarch64 ]; then
  item STATUS UNSUPPORTED_ARCH
  exit 20
fi

if [ -x "$JAVA17/bin/java" ] && "$JAVA17/bin/java" -version >/dev/null 2>&1; then
  item JAVA17 ready
else
  missing JAVA17
fi

if command -v gradle >/dev/null 2>&1; then item GRADLE ready; else missing GRADLE; fi
if [ -s "$PLATFORM" ]; then item PLATFORM_34 ready; else missing PLATFORM_34; fi

if [ -x "$BT/aapt2" ]; then
  HASH=$(sha256sum "$BT/aapt2" 2>/dev/null | awk '{print $1}')
  item AAPT2_SHA256 "${HASH:-unknown}"
  if "$BT/aapt2" dump resources "$PLATFORM" >/dev/null 2>&1; then
    item AAPT2_ANDROID34 compatible
  else
    item AAPT2_ANDROID34 incompatible
    READY=0
  fi
else
  missing AAPT2
fi

if [ -s "$BT/lib/d8.jar" ]; then item D8 ready; else missing D8; fi
if [ -x "$BT/apksigner" ]; then item APKSIGNER ready; else missing APKSIGNER; fi
if command -v adb >/dev/null 2>&1; then item ADB ready; else item ADB optional_missing; fi
if [ -d "$SDK/ndk/27.3.13750724" ]; then item NDK_R27D present_unverified; else item NDK_R27D optional_missing; fi

FREE_KB=$(df -Pk /opt 2>/dev/null | awk 'NR==2 {print $4}')
item FREE_KB "${FREE_KB:-unknown}"

if [ "$READY" -eq 1 ]; then
  item STATUS READY
  exit 0
fi
item STATUS NEED_BOOTSTRAP
exit 10
