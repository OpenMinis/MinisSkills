#!/usr/bin/env bash
set -euo pipefail

# Build the long-lived CoreBluetooth sender on macOS.
# This must run on macOS with Bluetooth permission; iSH/Linux cannot link CoreBluetooth.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="${1:-$script_dir/native_sender}"
mkdir -p "$(dirname "$out")"

command -v swiftc >/dev/null 2>&1 || {
  echo "swiftc is required; run this on macOS, not iSH/Linux." >&2
  exit 69
}

swiftc -O \
  -framework CoreBluetooth \
  -framework Foundation \
  "$script_dir/native_sender.swift" \
  -o "$out"

echo "$out"
