#!/usr/bin/env python3
"""mk.py — Read project.yaml and build an iOS IPA with clang + lld + rcodesign (no Xcode required).
Usage: python3 mk.py [project dir] [--clean] [--install] [--check]
  --clean    wipe build/ and rebuild from scratch
  --check    only run the pre-signing preflight (profile/certificate/Bundle ID/devices), no build
  --install  after building and signing, install onto the phone over the Surge loopback and read back to verify (needs real device signing, adhoc will be rejected)
Output: <project>/build/<name>.ipa
Signing: sign.mode = adhoc | p12 in project.yaml
"""
import re, glob, hashlib, os, plistlib, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
import yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import profile as prov

def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.exit(f"❌ command failed: {' '.join(cmd[:4])} ...\n{r.stderr or r.stdout}")
    return r

def need(cond, msg):
    if not cond: sys.exit(f"❌ {msg}")

def resolve_sdk(spec):
    """SDK resolution: use the sdk from project.yaml if set; otherwise default to the highest version in ~/.ios-sdk (iPhoneOS26.x recommended,
    so the linked binary has LC_BUILD_VERSION.sdk=26, which is required to use UIGlassEffect and other new APIs and the new system appearance)."""
    if spec:
        p = os.path.expanduser(spec)
        if not os.path.isdir(p): sys.exit(f"❌ iOS SDK not found: {p}\n   one-shot install: python3 {os.path.dirname(os.path.abspath(__file__))}/install_sdk.py")
        return p
    base = os.path.expanduser("~/.ios-sdk")
    cands = []
    if os.path.isdir(base):
        for d in os.listdir(base):
            m = re.match(r"iPhoneOS(\d+(?:\.\d+)*)\.sdk$", d)
            if m: cands.append((tuple(int(x) for x in m.group(1).split(".")), os.path.join(base, d)))
    if not cands:
        sys.exit(f"❌ no iOS SDK in ~/.ios-sdk\n   one-shot install: python3 {os.path.dirname(os.path.abspath(__file__))}/install_sdk.py")
    cands.sort()
    best = cands[-1]
    if best[0][0] < 26:
        print(f"⚠️  only found SDK {best[0]}, older than 26: iOS 26 APIs such as UIGlassEffect cannot be used. python3 install_sdk.py installs 26.5")
    return best[1]

def preflight(cfg, root, bundle_id, quiet=False):
    """Pre-signing preflight. Returns (profile_dict, summary). Exits if there is an error."""
    sg = cfg.get("sign", {})
    need(sg.get("mode") == "p12", "sign.mode is not p12, there are no signing assets to preflight")
    for k in ("p12", "profile"):
        need(sg.get(k), f"project.yaml does not configure sign.{k}")
    p12 = os.path.expanduser(sg["p12"]); pf = os.path.expanduser(sg["profile"])
    need(os.path.exists(p12), f"p12 not found: {p12}")
    need(os.path.exists(pf), f"provisioning profile not found: {pf}")
    env = sg.get("password_env", "IOSDEV_P12_PASS")
    need(os.environ.get(env), f"environment variable {env} is not set (the p12 password, do not put it in a file)")
    mode = oct(os.stat(p12).st_mode)[-3:]
    if mode[1:] != "00":
        print(f"⚠️  p12 mode is {mode}, consider chmod 600")
    profile = prov.load_profile(pf)
    udid = sg.get("udid")
    errs, warns = prov.check(profile, bundle_id, udid)
    s = prov.summarize(profile)
    if not quiet:
        print(f"📜 provisioning profile: {s['name']} | team {s['team']} | matches `{s['bundle_pattern']}` | "
              f"{'development' if s['development'] else 'non-development'} | {len(s['devices'])} devices | expires {s['expires'].date() if s['expires'] else '?'}")
    for w in warns: print("⚠️ ", w)
    if errs:
        sys.exit("❌ preflight failed:\n  - " + "\n  - ".join(errs))
    return profile, s


def p12_is_pbes2(path):
    """Rough check whether the p12 is PBES2 (AES-256/PBKDF2). rcodesign 0.29 cannot read that."""
    try:
        r = subprocess.run(["openssl", "asn1parse", "-in", path, "-inform", "DER"], capture_output=True, text=True)
        return "1.2.840.113549.1.5.13" in r.stdout or "2A864886F70D010C0A0102" in r.stdout.upper()
    except Exception:
        return False

def convert_to_legacy(p12_path, password, out_path):
    """Convert a PBES2 p12 to the legacy format (readable by rcodesign). Decrypt with openssl, then re-export."""
    r = subprocess.run(["openssl", "pkcs12", "-in", p12_path, "-passin", "pass:" + password,
                        "-nodes", "-out", out_path + ".pem"], capture_output=True, text=True)
    if r.returncode != 0:
        return False, (r.stderr or "").strip().splitlines()[-1:] or ["openssl decryption failed"]
    r2 = subprocess.run(["openssl", "pkcs12", "-export", "-in", out_path + ".pem",
                         "-certpbe", "PBE-SHA1-3DES", "-keypbe", "PBE-SHA1-3DES", "-macalg", "sha1",
                         "-out", out_path, "-passout", "pass:" + password], capture_output=True, text=True)
    try: os.remove(out_path + ".pem")
    except OSError: pass
    if r2.returncode != 0:
        return False, ["failed to re-export in the legacy format"]
    return True, []

def sign_p12(cfg, sg, root, app, bundle_id):
    profile, s = preflight(cfg, root, bundle_id)
    shutil.copyfile(os.path.expanduser(sg["profile"]), os.path.join(app, "embedded.mobileprovision"))   # copy2's utime fails on iSH
    # entitlements: unless the user explicitly provides a file, generate the minimal set from the provisioning profile
    if sg.get("entitlements"):
        ent_path = os.path.join(root, sg["entitlements"])
    else:
        ent_path = os.path.join(root, "build", "entitlements.auto.plist")
        open(ent_path, "wb").write(prov.entitlements_xml(prov.entitlements_for(profile, bundle_id)))
    env = sg.get("password_env", "IOSDEV_P12_PASS")
    # rcodesign cannot read the password from /dev/stdin; use a 0600 temp file, delete it immediately afterwards, and keep it off the command line (ps can see that)
    import tempfile
    fd, pwf = tempfile.mkstemp(prefix=".pw", dir=os.path.join(root, "build")); os.chmod(pwf, 0o600)
    try:
        with os.fdopen(fd, "w") as f: f.write(os.environ[env])
        p12_path = os.path.expanduser(sg["p12"])
        cmd = ["rcodesign", "sign", "--p12-file", p12_path,
               "--p12-password-file", pwf, "--entitlements-xml-file", ent_path, app]
        r = subprocess.run(cmd, capture_output=True, text=True)
        # Apple's timestamp server is occasionally unavailable (network flakiness/TSP 502); development signing does not need a trusted timestamp, so retry without it
        if r.returncode != 0 and "Time-Stamp Protocol" in (r.stderr or r.stdout or ""):
            print("⚠️  Apple timestamp service is misbehaving, retrying without a timestamp (development builds install fine)")
            cmd = cmd[:2] + ["--timestamp-url", "none"] + cmd[2:]
            r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 and "incorrect password" in (r.stderr or r.stdout or "") \
                and p12_is_pbes2(os.path.expanduser(sg["p12"])):
            legacy = os.path.join(root, "build", "signing.legacy.p12")
            if convert_to_legacy(os.path.expanduser(sg["p12"]), os.environ[env], legacy):
                print("🔁 the p12 is PBES2 (AES-256), converted it to the legacy format (3DES) and re-signed")
                cmd = ["rcodesign", "sign", "--p12-file", legacy, "--p12-password-file", pwf,
                       "--entitlements-xml-file", ent_path, app]
                r = subprocess.run(cmd, capture_output=True, text=True)

    finally:
        try: os.remove(pwf)
        except OSError: pass
    if r.returncode != 0:
        msg = r.stderr or r.stdout
        if "incorrect password" in msg:
            msg += ("\n💡 Also check the password itself: the \"password.txt\" provided by the signing service often includes the label "
                    "(e.g. the file contains `Password: 1` while the real password is `1`), and whether the p12 is PBES2 (AES-256) — "
                    "the script tries to convert it automatically, but conversion is impossible if the password is wrong.")
            msg += ("\n💡 The password may actually be correct: rcodesign 0.29 cannot read a p12 in OpenSSL 3's default format (AES-256/PBKDF2), "
                    "yet it reports 'wrong password'. If you already have a p12, convert it with the legacy algorithm and retry (see references/signing.md):\n"
                    "   openssl pkcs12 -in my.p12 -nodes -out /tmp/all.pem\n"
                    "   openssl pkcs12 -export -legacy -in /tmp/all.pem -out my.legacy.p12 && rm -f /tmp/all.pem\n"
                    "   then point sign.p12 in project.yaml at my.legacy.p12;\n"
                    "   (if you have key.pem + cert.pem instead: openssl pkcs12 -export -legacy -inkey key.pem -in cert.pem -out dev.p12)")
        sys.exit(f"❌ rcodesign signing failed:\n{msg}")
    print(f"✍️  signed with p12 | entitlements: {', '.join(sorted(plistlib.load(open(ent_path,'rb')).keys()))}")

def install(cfg, ipa, bundle_id):
    """Install over the Surge loopback and read back via installation_proxy to verify."""
    pairing = os.environ.get("CDTK_PAIRING_FILE", "/root/.cdtk/pairing/new_phone.plist")
    need(os.path.exists(pairing), f"pairing file not found: {pairing}")
    env = dict(os.environ, CDTK_PAIRING_FILE=pairing)
    here = os.path.dirname(os.path.abspath(__file__))
    helper = os.path.join(here, "install_ipa.py")
    need(os.path.exists(helper), f"install script not found: {helper}")
    t = time.time()
    r = subprocess.run([sys.executable, helper, ipa], env=env, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        sys.exit(f"❌ install failed (channel/pairing/signature rejected, see the raw output below):\n{(r.stdout + r.stderr)[-900:]}")
    print(f"📲 install_from_local returned without exceptions in {time.time()-t:.1f}s, reading back to verify…")
    code = (
        f"import asyncio,sys;sys.path.insert(0,{here!r})\n"
        "from session import CoreDeviceSession\n"
        "from pymobiledevice3.services.installation_proxy import InstallationProxyService as S\n"
        "async def m():\n"
        "  async with CoreDeviceSession() as s:\n"
        f"    a=(await S(s.rsd).get_apps(application_type='Any',bundle_identifiers=['{bundle_id}'])).get('{bundle_id}')\n"
        "    print('MISSING' if not a else '|'.join(str(a.get(k)) for k in ('CFBundleDisplayName','CFBundleShortVersionString','CFBundleVersion','SignerIdentity')))\n"
        "asyncio.run(m())\n")
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120)
    out = (r.stdout.strip().splitlines() or ["?"])[-1]
    need(out != "MISSING" and r.returncode == 0, f"install reported success, but {bundle_id} cannot be read on the phone: {(r.stderr or out)[-300:]}")
    n, v, b, sid = (out.split("|") + ["?"] * 4)[:4]
    print(f"✅ confirmed on the phone: {n} {v}({b}) | signed by {sid}")

def main():
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print(__doc__); return
    _known = {"--clean", "--install", "--check", "--config"}
    _bad = [a for a in sys.argv[1:] if a.startswith("-") and a not in _known]
    if _bad:
        sys.exit(f"unknown option: {' '.join(_bad)}\n" + __doc__)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    root = os.path.abspath(args[0] if args else ".")
    _py = os.path.join(root, "project.yaml")
    if "--config" in sys.argv:
        _i = sys.argv.index("--config")
        if _i + 1 >= len(sys.argv):
            sys.exit("❌ --config must be followed by a yaml path")
        _c = sys.argv[_i + 1]
        _py = _c if os.path.isabs(_c) else os.path.join(root, _c)
        # the --config value is not a positional argument
        args = [a for a in args if a != _c]
    if not os.path.exists(_py):
        sys.exit(f"❌ there is no project.yaml in {root}.\n"
                 "   New project: cp -r assets/hello <dir>, then edit project.yaml as described in references/signing.md.")
    cfg = yaml.safe_load(open(_py))
    name = cfg["name"]
    bundle_id = cfg["bundle_id"]
    if "--check" in sys.argv:
        preflight(cfg, root, bundle_id); print("✅ preflight passed"); return
    min_ios = str(cfg.get("min_ios", "14.0"))
    sdk = resolve_sdk(cfg.get("sdk"))
    sub = os.path.join(sdk, "System/Library/SubFrameworks")   # iOS 26 SDK: UIKit headers reference <UIUtilities/...>
    print(f"🧰 SDK: {os.path.basename(sdk)}")
    build = os.path.join(root, "build")
    if "--clean" in sys.argv:
        shutil.rmtree(build, ignore_errors=True)
    obj = os.path.join(build, "obj"); os.makedirs(obj, exist_ok=True)
    t0 = time.time()

    base = ["clang", "-target", f"arm64-apple-ios{min_ios}", "-isysroot", sdk,
            "-fobjc-arc", "-Wno-everything", "-I", os.path.join(root, "src")]
    if os.path.isdir(sub): base += ["-F", sub]
    base += cfg.get("cflags", [])

    # 1. source files
    srcs = []
    for pat in cfg.get("sources", ["src/*.m", "src/*.c"]):
        srcs += sorted(glob.glob(os.path.join(root, pat)))
    if not srcs:
        sys.exit("❌ no source files found")

    # 2. PCH (cached by content + flags)
    pch_flags, tag = [], ""
    if cfg.get("pch"):
        h = hashlib.sha1((cfg["pch"] + " ".join(base) + sdk).encode()).hexdigest()[:10]
        hdr = os.path.join(build, "pch.h"); pch = os.path.join(build, f"pch-{h}.pch")
        open(hdr, "w").write(cfg["pch"] + "\n")
        if not os.path.exists(pch):
            t = time.time()
            sh(base + ["-x", "objective-c-header", hdr, "-o", pch])
            print(f"⚙️  generated PCH in {time.time()-t:.1f}s")
        else:
            tag = "(PCH cache hit)"
        pch_flags = ["-include-pch", pch]

    # 3. parallel compilation with incremental checks
    def compile_one(src):
        o = os.path.join(obj, os.path.relpath(src, root).replace("/", "_") + ".o")
        hdrs = glob.glob(os.path.join(root, "src", "*.h"))
        newest = max([os.path.getmtime(src)] + [os.path.getmtime(x) for x in hdrs])
        if os.path.exists(o) and os.path.getmtime(o) >= newest and not pch_flags_changed:
            return o, False
        flags = pch_flags if src.endswith(".m") else []   # the PCH is only used for ObjC
        sh(base + flags + ["-c", src, "-o", o])
        return o, True
    pch_flags_changed = False
    t = time.time()
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as ex:
        res = list(ex.map(compile_one, srcs))
    objs = [r[0] for r in res]
    print(f"🔨 compiled {sum(r[1] for r in res)}/{len(srcs)} files in {time.time()-t:.1f}s {tag}")

    # 4. link
    app = os.path.join(build, "Payload", f"{name}.app")
    shutil.rmtree(os.path.join(build, "Payload"), ignore_errors=True)
    os.makedirs(app)
    fw = []
    for f in cfg.get("frameworks", ["UIKit", "Foundation"]):
        fw += ["-framework", f]
    t = time.time()
    sh(base + ["-fuse-ld=lld"] + fw + objs + ["-o", os.path.join(app, name)])
    print(f"🔗 linked in {time.time()-t:.1f}s")

    # 5. Info.plist
    info = {
        "CFBundleExecutable": name, "CFBundleIdentifier": bundle_id,
        "CFBundleName": name, "CFBundleDisplayName": cfg.get("display_name", name),
        "CFBundleShortVersionString": str(cfg.get("version", "1.0")),
        "CFBundleVersion": str(cfg.get("build", "1")),
        "CFBundlePackageType": "APPL", "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleSupportedPlatforms": ["iPhoneOS"], "MinimumOSVersion": min_ios,
        "UIDeviceFamily": cfg.get("device_family", [1]), "LSRequiresIPhoneOS": True,
        "UIRequiredDeviceCapabilities": ["arm64"],
        "UISupportedInterfaceOrientations": ["UIInterfaceOrientationPortrait"],
    }
    info.update(cfg.get("info", {}))
    with open(os.path.join(app, "Info.plist"), "wb") as f:
        plistlib.dump(info, f)

    # 6. resources
    for r in cfg.get("resources", []):
        for p in glob.glob(os.path.join(root, r)):
            dst = os.path.join(app, os.path.basename(p.rstrip("/")))
            shutil.copytree(p, dst) if os.path.isdir(p) else shutil.copy2(p, dst)

    # 7. signing
    sg = cfg.get("sign", {"mode": "adhoc"})
    if sg.get("mode") == "p12":
        sign_p12(cfg, sg, root, app, bundle_id)
    else:
        sh(["rcodesign", "sign", app])
        print("✍️  ad-hoc signed (for structural validation only, a real device rejects the install; a real device needs sign.mode: p12)")

    # 8. package the IPA
    ipa = os.path.join(build, f"{name}.ipa")
    if os.path.exists(ipa): os.remove(ipa)
    sh(["zip", "-qry", ipa, "Payload"], cwd=build)
    print(f"📦 {ipa}  ({os.path.getsize(ipa)/1024:.1f} KB)  total {time.time()-t0:.1f}s")
    if "--install" in sys.argv:
        need(cfg.get("sign", {}).get("mode") == "p12", "--install requires sign.mode: p12 (an ad-hoc build cannot be installed on a real device)")
        install(cfg, ipa, bundle_id)

if __name__ == "__main__":
    main()
