#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=${1:-/var/minis/workspace/android-bootstrap-smoke}
CACHE=${ANDROID_BOOTSTRAP_CACHE:-/var/minis/workspace/android-bootstrap-cache}

[ "$ROOT" != /opt/android-sdk ] || { echo 'Refusing to use production SDK root for smoke test.' >&2; exit 2; }
rm -rf "$ROOT"
mkdir -p "$ROOT"
ANDROID_SDK_ROOT="$ROOT/sdk" ANDROID_BOOTSTRAP_CACHE="$CACHE" "$SCRIPT_DIR/bootstrap-android.sh"
ANDROID_SDK_ROOT="$ROOT/sdk" "$SCRIPT_DIR/doctor.sh"
[ -s "$ROOT/sdk/platforms/android-34/android.jar" ]
[ -x "$ROOT/sdk/build-tools/35.0.0/aapt2" ]
[ -s "$ROOT/sdk/build-tools/35.0.0/lib/d8.jar" ]
printf 'STATUS=SMOKE_OK\nROOT=%s\n' "$ROOT"
