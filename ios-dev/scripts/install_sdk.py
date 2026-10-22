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
