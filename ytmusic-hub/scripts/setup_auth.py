"""
setup_auth.py
Generate ytmusicapi Browser auth file from environment variables
exported by browser_use get_cookies.

Usage:
    . /var/minis/offloads/env_cookies_youtube_com_xxx.sh
    python3 /var/minis/skills/ytmusic-hub/scripts/setup_auth.py
"""

import os
import hashlib
import time
from ytmusicapi import setup

AUTH_FILE = "/var/minis/workspace/ytmusic_headers.json"

COOKIE_KEYS = [
    ("__Secure-YNID",            "COOKIE___SECURE_YNID"),
    ("VISITOR_INFO1_LIVE",       "COOKIE_VISITOR_INFO1_LIVE"),
    ("VISITOR_PRIVACY_METADATA", "COOKIE_VISITOR_PRIVACY_METADATA"),
    ("_gcl_au",                  "COOKIE__GCL_AU"),
    ("PREF",                     "COOKIE_PREF"),
    ("__Secure-1PSIDTS",         "COOKIE___SECURE_1PSIDTS"),
    ("__Secure-3PSIDTS",         "COOKIE___SECURE_3PSIDTS"),
    ("HSID",                     "COOKIE_HSID"),
    ("SSID",                     "COOKIE_SSID"),
    ("APISID",                   "COOKIE_APISID"),
    ("SAPISID",                  "COOKIE_SAPISID"),
    ("__Secure-1PAPISID",        "COOKIE___SECURE_1PAPISID"),
    ("__Secure-3PAPISID",        "COOKIE___SECURE_3PAPISID"),
    ("SID",                      "COOKIE_SID"),
    ("__Secure-1PSID",           "COOKIE___SECURE_1PSID"),
    ("__Secure-3PSID",           "COOKIE___SECURE_3PSID"),
    ("SIDCC",                    "COOKIE_SIDCC"),
    ("__Secure-1PSIDCC",         "COOKIE___SECURE_1PSIDCC"),
    ("__Secure-3PSIDCC",         "COOKIE___SECURE_3PSIDCC"),
    ("LOGIN_INFO",               "COOKIE_LOGIN_INFO"),
    ("YSC",                      "COOKIE_YSC"),
    ("__Secure-ROLLOUT_TOKEN",   "COOKIE___SECURE_ROLLOUT_TOKEN"),
]


def setup_auth(auth_file=AUTH_FILE):
    cookie_str = "; ".join(
        f"{k}={os.environ[env]}"
        for k, env in COOKIE_KEYS if os.environ.get(env)
    )
    if not cookie_str:
        raise RuntimeError("No Cookie env vars found. Please load the env file first.")

    sapisid = os.environ.get("COOKIE_SAPISID", "")
    ts = str(int(time.time()))
    sha1 = hashlib.sha1(f"{ts} {sapisid} https://music.youtube.com".encode()).hexdigest()

    setup(
        filepath=auth_file,
        headers_raw="\n".join([
            f"cookie: {cookie_str}",
            f"authorization: SAPISIDHASH {ts}_{sha1}",
            "x-goog-authuser: 0",
            "x-origin: https://music.youtube.com",
        ])
    )
    print(f"✅ Auth file written: {auth_file}")


if __name__ == "__main__":
    setup_auth()
