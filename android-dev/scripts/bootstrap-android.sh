#!/bin/sh
set -eu

SDK=${ANDROID_SDK_ROOT:-/opt/android-sdk}
CACHE=${ANDROID_BOOTSTRAP_CACHE:-/var/cache/minis-android}
PLATFORM_URL=https://dl.google.com/android/repository/platform-34-ext7_r03.zip
PLATFORM_SHA1=1f2e9478d6a7601425ceaa553311dc43191f103d
PLATFORM_SHA256=16fdb74c55e59ae3ef52def135aec713508467bd56d7dabcd8c9be31fa8b20f3
TOOLS_URL=https://dl.google.com/android/repository/build-tools_r35_linux.zip
TOOLS_SHA1=2cfaa0bbb2336e9ec18ed3ecea84fa2e2af607bc
TOOLS_SHA256=bd3a4966912eb8b30ed0d00b0cda6b6543b949d5ffe00bea54c04c81e1561d88
AAPT2_COMMIT=00b3f95e6858517f1fa1b7aa9b76509cbca027dc
AAPT2_URL="https://raw.githubusercontent.com/Sou6900/aapt2---linux-arm64/$AAPT2_COMMIT/arm64-v8/aapt2"
AAPT2_SHA256=b7410d29c2925daf7fb82f701fdd10cf87397687801137385b01b958ada52e5f

log() { printf '[android-bootstrap] %s\n' "$*"; }
die() { printf '[android-bootstrap] ERROR: %s\n' "$*" >&2; exit 1; }

[ "$(uname -m)" = aarch64 ] || die 'This bootstrap supports only aarch64 Alpine PRoot.'
command -v apk >/dev/null 2>&1 || die 'apk not found; expected Alpine Linux.'
[ "$(id -u)" -eq 0 ] || die 'Run inside the Minis PRoot root environment.'
FREE_KB=$(df -Pk /opt | awk 'NR==2 {print $4}')
[ "${FREE_KB:-0}" -ge 1572864 ] || die 'Need at least 1.5 GiB free under /opt.'

NEED_BASE=0
for C in wget unzip zip file readelf sha1sum sha256sum; do command -v "$C" >/dev/null 2>&1 || NEED_BASE=1; done
[ -x /usr/lib/jvm/java-17-openjdk/bin/java ] || NEED_BASE=1
command -v gradle >/dev/null 2>&1 || NEED_BASE=1
if [ "$NEED_BASE" -eq 1 ]; then
  log 'Installing OpenJDK 17, Gradle, and inspection tools.'
  apk update
  apk add --no-cache openjdk17-jdk gradle unzip zip wget file binutils
fi
if ! command -v adb >/dev/null 2>&1; then
  log 'Installing Alpine ARM64 ADB (optional for builds).'
  apk add --no-cache android-tools || log 'ADB install failed; APK builds can continue.'
fi

export JAVA_HOME=/usr/lib/jvm/java-17-openjdk
export PATH="$JAVA_HOME/bin:$PATH"
java -version >/dev/null 2>&1 || die 'OpenJDK 17 cannot start (possible W^X restriction).'
gradle --version >/dev/null 2>&1 || die 'Gradle cannot start with OpenJDK 17.'
mkdir -p "$SDK/platforms" "$SDK/build-tools" "$CACHE"

fetch_verified() {
  URL=$1; OUT=$2; EXPECTED_SHA1=$3; EXPECTED_SHA256=$4
  if [ -s "$OUT" ] && [ "$(sha1sum "$OUT" | awk '{print $1}')" = "$EXPECTED_SHA1" ] && [ "$(sha256sum "$OUT" | awk '{print $1}')" = "$EXPECTED_SHA256" ]; then return 0; fi
  rm -f "$OUT.part"
  log "Downloading $(basename "$OUT")"
  wget -T 30 -t 2 -O "$OUT.part" "$URL"
  [ "$(sha1sum "$OUT.part" | awk '{print $1}')" = "$EXPECTED_SHA1" ] && [ "$(sha256sum "$OUT.part" | awk '{print $1}')" = "$EXPECTED_SHA256" ] || { rm -f "$OUT.part"; die "Checksum mismatch for $URL"; }
  mv "$OUT.part" "$OUT"
}

fetch_sha256() {
  URL=$1; OUT=$2; EXPECTED=$3
  if [ -s "$OUT" ] && [ "$(sha256sum "$OUT" | awk '{print $1}')" = "$EXPECTED" ]; then return 0; fi
  rm -f "$OUT.part"
  log "Downloading pinned $(basename "$OUT")"
  wget -T 30 -t 2 -O "$OUT.part" "$URL"
  [ "$(sha256sum "$OUT.part" | awk '{print $1}')" = "$EXPECTED" ] || { rm -f "$OUT.part"; die "Checksum mismatch for $URL"; }
  mv "$OUT.part" "$OUT"
}

install_tree() {
  ZIP=$1; TOP=$2; DEST=$3
  STAGE="$DEST.new.$$"
  rm -rf "$STAGE" "$STAGE.unpack"
  mkdir -p "$STAGE.unpack"
  unzip -q "$ZIP" -d "$STAGE.unpack"
  [ -d "$STAGE.unpack/$TOP" ] || die "Expected directory $TOP missing from $ZIP"
  mv "$STAGE.unpack/$TOP" "$STAGE"
  rm -rf "$STAGE.unpack"
  if [ -e "$DEST" ]; then mv "$DEST" "$DEST.backup.$(date +%Y%m%d%H%M%S)"; fi
  mv "$STAGE" "$DEST"
}

PLATFORM_ZIP="$CACHE/platform-34-ext7_r03.zip"
TOOLS_ZIP="$CACHE/build-tools_r35_linux.zip"
AAPT2_CACHE="$CACHE/aapt2-arm64-$AAPT2_COMMIT"
fetch_sha256 "$AAPT2_URL" "$AAPT2_CACHE" "$AAPT2_SHA256"
chmod 755 "$AAPT2_CACHE"
file "$AAPT2_CACHE" | grep -q 'ARM aarch64' || die 'Pinned AAPT2 is not AArch64.'

if [ ! -s "$SDK/platforms/android-34/android.jar" ] || ! "$AAPT2_CACHE" dump resources "$SDK/platforms/android-34/android.jar" >/dev/null 2>&1; then
  fetch_verified "$PLATFORM_URL" "$PLATFORM_ZIP" "$PLATFORM_SHA1" "$PLATFORM_SHA256"
  install_tree "$PLATFORM_ZIP" android-34 "$SDK/platforms/android-34"
fi
"$AAPT2_CACHE" dump resources "$SDK/platforms/android-34/android.jar" >/dev/null 2>&1 || die 'Pinned AAPT2 cannot parse installed Android 34.'

if [ ! -s "$SDK/build-tools/35.0.0/lib/d8.jar" ] || [ ! -s "$SDK/build-tools/35.0.0/lib/apksigner.jar" ] || [ ! -x "$SDK/build-tools/35.0.0/apksigner" ]; then
  fetch_verified "$TOOLS_URL" "$TOOLS_ZIP" "$TOOLS_SHA1" "$TOOLS_SHA256"
  install_tree "$TOOLS_ZIP" android-15 "$SDK/build-tools/35.0.0"
fi

AAPT="$SDK/build-tools/35.0.0/aapt2"
if [ ! -x "$AAPT" ] || [ "$(sha256sum "$AAPT" 2>/dev/null | awk '{print $1}')" != "$AAPT2_SHA256" ]; then
  [ ! -e "$AAPT" ] || mv "$AAPT" "$AAPT.previous.$(date +%Y%m%d%H%M%S)"
  install -m 755 "$AAPT2_CACHE" "$AAPT.new"
  "$AAPT.new" dump resources "$SDK/platforms/android-34/android.jar" >/dev/null 2>&1 || die 'Staged AAPT2 verification failed.'
  mv "$AAPT.new" "$AAPT"
fi

if [ "$SDK" = /opt/android-sdk ]; then
  mkdir -p /etc/profile.d
  PROFILE_TMP=/etc/profile.d/android-sdk.sh.new.$$
  cat > "$PROFILE_TMP" <<EOF
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk
export ANDROID_HOME=/opt/android-sdk
export ANDROID_SDK_ROOT=/opt/android-sdk
export PATH=\"\$JAVA_HOME/bin:\$PATH\"
EOF
  chmod 644 "$PROFILE_TMP"
  mv "$PROFILE_TMP" /etc/profile.d/android-sdk.sh
else
  log "Non-default SDK root; not changing global profile: $SDK"
fi

"$AAPT" dump resources "$SDK/platforms/android-34/android.jar" >/dev/null 2>&1 || die 'Final AAPT2/platform verification failed.'
[ -s "$SDK/build-tools/35.0.0/lib/d8.jar" ] || die 'D8 is missing.'
[ -s "$SDK/build-tools/35.0.0/lib/apksigner.jar" ] || die 'apksigner.jar is missing.'
log 'STATUS=READY'
log "JAVA_HOME=$JAVA_HOME"
log "ANDROID_SDK_ROOT=$SDK"
log 'COMPILE_SDK=34'
log 'BUILD_TOOLS=35.0.0'
