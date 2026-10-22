"""profile.py — Parse .mobileprovision and validate it before signing. Pure standard library, no Xcode/security dependency.

A mobileprovision is a CMS (PKCS#7) wrapper around a plist. The CMS signature is not verified (the content is only read for preflight checks);
real trust is decided by iOS at install time.
"""
import datetime, plistlib, re, subprocess, os

def _now():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def load_profile(path):
    """Return the plist dict. Try unpacking with openssl cms first; on failure, look for the embedded xml plist in the raw bytes."""
    path = os.path.expanduser(path)
    raw = open(path, "rb").read()
    try:
        r = subprocess.run(["openssl", "smime", "-inform", "DER", "-verify", "-noverify", "-in", path],
                           capture_output=True)
        if r.returncode == 0 and r.stdout.strip():
            return plistlib.loads(r.stdout)
    except FileNotFoundError:
        pass
    m = re.search(rb"<\?xml.*?</plist>", raw, re.S)
    if not m:
        raise ValueError(f"not a valid mobileprovision: {path}")
    return plistlib.loads(m.group(0))


def summarize(p):
    ent = p.get("Entitlements", {})
    appid = ent.get("application-identifier", "")
    team = (p.get("TeamIdentifier") or [""])[0]
    prefix = (p.get("ApplicationIdentifierPrefix") or [team])[0]
    bundle_pattern = appid[len(prefix) + 1:] if appid.startswith(prefix + ".") else appid
    exp = p.get("ExpirationDate")
    return {
        "name": p.get("Name"),
        "team": team,
        "app_id": appid,
        "bundle_pattern": bundle_pattern,          # e.g. "*" or "com.example.app" or "com.example.*"
        "is_wildcard": bundle_pattern.endswith("*"),
        "development": bool(ent.get("get-task-allow")),
        "devices": list(p.get("ProvisionedDevices") or []),
        "all_devices": bool(p.get("ProvisionsAllDevices")),
        "expires": exp,
        "expired": bool(exp and exp.replace(tzinfo=None) < _now()),
        "entitlements": sorted(ent.keys()),
        "cert_count": len(p.get("DeveloperCertificates") or []),
    }


def bundle_matches(pattern, bundle_id):
    """Wildcard rules: '*' matches anything; 'com.a.*' matches anything starting with 'com.a.'; otherwise an exact match is required."""
    if pattern == "*":
        return True
    if pattern.endswith("*"):
        return bundle_id.startswith(pattern[:-1])
    return pattern == bundle_id


def check(profile, bundle_id, udid=None, now=None):
    """Return (errors, warnings). If errors is non-empty you should not continue signing."""
    s = summarize(profile) if "bundle_pattern" not in profile else profile
    errors, warns = [], []
    if s["expired"]:
        errors.append(f"Provisioning profile has expired ({s['expires']})")
    if not bundle_matches(s["bundle_pattern"], bundle_id):
        errors.append(f"Bundle ID `{bundle_id}` does not match provisioning profile `{s['team']}.{s['bundle_pattern']}`")
    if udid and not s["all_devices"] and udid not in s["devices"]:
        errors.append(f"Target device {udid} is not among the {len(s['devices'])} devices in the provisioning profile")
    if not s["development"]:
        warns.append("get-task-allow is not true: this is not a development provisioning profile, it can only be used for AdHoc/release, development installs may be rejected")
    if s["expires"] and not s["expired"]:
        left = (s["expires"].replace(tzinfo=None) - _now()).days
        if left < 14:
            warns.append(f"Provisioning profile expires in {left} days")
    return errors, warns


def entitlements_for(profile, bundle_id):
    """Generate only the minimal entitlements the provisioning profile allows; application-identifier substitutes the real Bundle ID for the wildcard."""
    s = summarize(profile)
    ent = {
        "application-identifier": f"{s['team']}.{bundle_id}",
        "com.apple.developer.team-identifier": s["team"],
    }
    if profile.get("Entitlements", {}).get("get-task-allow") is not None:
        ent["get-task-allow"] = bool(profile["Entitlements"]["get-task-allow"])
    # keychain-access-groups is "<team>.*" in a wildcard provisioning profile; including it lets the app use the keychain
    kag = profile.get("Entitlements", {}).get("keychain-access-groups")
    if kag:
        ent["keychain-access-groups"] = [g.replace("*", bundle_id) if g.endswith(".*") else g for g in kag]
    return ent


def entitlements_xml(ent):
    return plistlib.dumps(ent, fmt=plistlib.FMT_XML)
