#!/bin/sh
# check-drift.sh — compare the vendored converter against an optional reference tree.
#
# This package is the canonical copy of the converter. If you also keep a
# private working tree, a silent divergence between the two is the failure
# mode this script is meant to catch. Point ROOMPLAN_DXF_UPSTREAM at that
# tree (the directory that contains roomplan-to-dxf.js) and run:
#
#   ROOMPLAN_DXF_UPSTREAM=/path/to/reference/scripts sh scripts/check-drift.sh
#
# With no upstream set the script just reports the local checksums and exits
# 0 — it never contacts the network and never writes anything.
#
# Exit: 0 = identical (or no upstream given), 1 = differences or missing files.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
FILES="roomplan-to-dxf.js lib/align.js lib/decode-optimized.js lib/decode-raw.js
       lib/dxf-emit.py lib/dxf-writer.js lib/group-sidecar.js lib/manifest.js lib/model.js lib/story.js
       lib/transform.js"

sha_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d' ' -f1
  else
    shasum -a 256 "$1" | cut -d' ' -f1
  fi
}

if [ -z "${ROOMPLAN_DXF_UPSTREAM:-}" ]; then
  echo "No ROOMPLAN_DXF_UPSTREAM set; local checksums only."
  for f in $FILES; do
    printf '  %-28s %s\n' "$f" "$(sha_of "$HERE/$f")"
  done
  exit 0
fi

same=0; diff=0; missing=0
for f in $FILES; do
  if [ ! -f "$ROOMPLAN_DXF_UPSTREAM/$f" ]; then
    printf '  %-28s MISSING UPSTREAM\n' "$f"; missing=$((missing+1))
  elif [ "$(sha_of "$HERE/$f")" = "$(sha_of "$ROOMPLAN_DXF_UPSTREAM/$f")" ]; then
    printf '  %-28s identical\n' "$f"; same=$((same+1))
  else
    printf '  %-28s DIFFERS\n' "$f"; diff=$((diff+1))
  fi
done

echo
echo "identical: $same | differing: $diff | missing upstream: $missing"
if [ "$diff" -gt 0 ] || [ "$missing" -gt 0 ]; then
  echo
  echo "If the difference is intentional, record why in the commit message;"
  echo "otherwise restore or port the change so both trees stay in sync."
  exit 1
fi
exit 0
