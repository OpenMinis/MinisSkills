#!/usr/bin/env python3
"""Install the iOS SDK into ~/.ios-sdk/ (default: iPhoneOS26.5.sdk, about 330MB, fetches only headers and .tbd files).
Source: github.com/xybp888/iOS-SDKs (third-party mirror, not an official Apple download, integrity cannot be verified; usage must comply with Apple's SDK terms).
Usage: python3 install_sdk.py [version, e.g. 26.5]
"""
import os, sys, shutil, subprocess, tempfile
if __name__ != "__main__":
    raise ImportError("install_sdk.py is a command-line script, not a library: run it with python3 install_sdk.py")

ver = sys.argv[1] if len(sys.argv) > 1 else "26.5"
name = f"iPhoneOS{ver}.sdk"
dst = os.path.expanduser("~/.ios-sdk"); os.makedirs(dst, exist_ok=True)
if os.path.isdir(os.path.join(dst, name, "System/Library/Frameworks/UIKit.framework")):
    sys.exit(f"✅ already exists: {dst}/{name}")
tmp = tempfile.mkdtemp(prefix="sdkrepo-")
def run(*a, cwd=None): subprocess.run(a, cwd=cwd, check=True)
try:
    run("git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", "https://github.com/xybp888/iOS-SDKs", tmp + "/r")
    run("git", "sparse-checkout", "set", name, cwd=tmp + "/r")
    src = os.path.join(tmp, "r", name)
    if not os.path.isdir(src): sys.exit(f"❌ {name} not found in the repository")
    shutil.move(src, os.path.join(dst, name))
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print(f"✅ installed {dst}/{name}")

# --- tbd target patch (needed for iOS 27+ SDKs) ---------------------------------
# SDKs from iOS 27.0 on list only [ arm64e-ios, arm64e.x1-ios ] in their .tbd stubs:
# the plain arm64 device slice is gone and arm64e.x1 is an architecture LLD < 21 does
# not know, so every link fails with "unknown architecture" / "malformed file".
# A stub only declares symbols, so declaring arm64-ios is enough to link an arm64 app
# (arm64 code runs unchanged on arm64e hardware). This rewrite is idempotent.
import re as _re
_rx = _re.compile(r'^(\s*(?:-\s*)?targets:\s*)\[(.*)\]$')
_files = _lines = 0
for _root, _, _fs in os.walk(os.path.join(dst, name)):
    for _fn in _fs:
        if not _fn.endswith(".tbd"):
            continue
        _p = os.path.join(_root, _fn)
        _s = open(_p, encoding="utf-8", errors="ignore").read()
        if "arm64e.x1" not in _s:
            continue
        _out, _changed = [], False
        for _ln in _s.splitlines(True):
            _m = _rx.match(_ln.rstrip("\n"))
            if _m and "arm64e.x1" in _m.group(2):
                _tg = [t.strip() for t in _m.group(2).split(",") if t.strip() and "x1" not in t]
                if "arm64-ios" not in _tg:
                    _tg.insert(0, "arm64-ios")
                _ln = _m.group(1) + "[ " + ", ".join(_tg) + " ]\n"
                _changed = True
                _lines += 1
            _out.append(_ln)
        if _changed:
            open(_p, "w", encoding="utf-8").write("".join(_out))
            _files += 1
if _files:
    print(f"🔧 patched tbd targets: {_files} files / {_lines} target lists (+arm64-ios, -arm64e.x1)")

