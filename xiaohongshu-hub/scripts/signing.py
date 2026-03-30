"""
Main API signing for edith.xiaohongshu.com
纯标准库实现，无第三方依赖。

改造来源：jackwener/xiaohongshu-cli
https://github.com/jackwener/xiaohongshu-cli/blob/main/xhs_cli/signing.py
"""

import base64
import hashlib
import json
import os
import random
import struct
import time
from typing import Any
from urllib.parse import quote

from .constants import APP_ID, PLATFORM, SDK_VERSION, USER_AGENT

# ─── Custom Base64 alphabets ─────────────────────────────────────────────────

STANDARD_B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
CUSTOM_B64   = "ZmserbBoHQtNP+wOcza/LpngG8yJq42KWYj0DSfdikx3VT16IlUAFM97hECvuRX5"
X3_B64       = "MfgqrsbcyzPQRStuvC7mn501HIJBo2DEFTKdeNOwxWXYZap89+/A4UVLhijkl63G"

_custom_tbl = str.maketrans(STANDARD_B64, CUSTOM_B64)
_x3_tbl     = str.maketrans(STANDARD_B64, X3_B64)

# ─── Static constants ─────────────────────────────────────────────────────────

HEX_KEY = (
    "71a302257793271ddd273bcee3e4b98d9d7935e1da33f5765e2ea8afb6dc77a5"
    "1a499d23b67c20660025860cbf13d4540d92497f58686c574e508f46e1956344"
    "f39139bf4faf22a3eef120b79258145b2feb5193b6478669961298e79bedca64"
    "6e1a693a926154a5a7a1bd1cf0dedb742f917a747a1e388b234f2277516db711"
    "6035439730fa61e9822a0eca7bff72d8"
)

VERSION_BYTES  = [121, 104, 96, 41]
PAYLOAD_LEN    = 144
ENV_TABLE      = [115, 248, 83, 102, 103, 201, 181, 131, 99, 94, 4, 68, 250, 132, 21]
ENV_DEF        = [0, 1, 18, 1, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0]
A3_PREFIX      = [2, 97, 51, 16]
HASH_IV        = (1831565813, 461845907, 2246822507, 3266489909)
MAX32          = 0xFFFFFFFF
X3_PREFIX      = "mns0301_"
XYS_PREFIX     = "XYS_"
B1_KEY         = "xhswebmplfbt"

XSCOMMON_TPL = {
    "s0": 5, "s1": "", "x0": "1", "x1": SDK_VERSION,
    "x2": PLATFORM, "x3": APP_ID, "x4": "4.86.0",
    "x5": "", "x6": "", "x7": "", "x8": "", "x9": -596800761,
    "x10": 0, "x11": "normal",
}

SIG_TPL = {"x0": SDK_VERSION, "x1": APP_ID, "x2": PLATFORM, "x3": "", "x4": ""}

GPU_VENDORS = [
    "Apple|Apple M1", "Apple|Apple M1 Pro", "Apple|Apple M1 Max",
    "Apple|Apple M2", "Apple|Apple M2 Pro", "Apple|Apple M3", "Apple|Apple M3 Pro",
    "Google Inc. (Intel)|ANGLE (Intel, Intel(R) Iris(TM) Plus Graphics 655 OpenGL Engine)",
    "Google Inc. (Intel)|ANGLE (Intel, Intel(R) UHD Graphics 630 OpenGL Engine)",
    "Google Inc. (AMD)|ANGLE (AMD, AMD Radeon Pro 5500M OpenGL Engine)",
]
SCREEN_RES = [
    ("2560;1600", 0.30), ("3024;1964", 0.15), ("3456;2234", 0.10),
    ("2560;1440", 0.15), ("1920;1080", 0.10), ("1440;900", 0.10),
    ("2880;1800", 0.05), ("5120;2880", 0.05),
]
PLUGINS = (
    "PDF Viewer::Portable Document Format::application/pdf~pdf,text/pdf~pdf;"
    "Chrome PDF Viewer::Portable Document Format::application/pdf~pdf,text/pdf~pdf;"
    "Chromium PDF Viewer::Portable Document Format::application/pdf~pdf,text/pdf~pdf;"
    "Microsoft Edge PDF Viewer::Portable Document Format::application/pdf~pdf,text/pdf~pdf;"
    "WebKit built-in PDF::Portable Document Format::application/pdf~pdf,text/pdf~pdf"
)
FONTS = (
    "Arial,Arial Black,Arial Narrow,Book Antiqua,Bookman Old Style,"
    "Calibri,Cambria,Cambria Math,Century,Century Gothic,Century Schoolbook,"
    "Comic Sans MS,Consolas,Courier,Courier New,Georgia,Helvetica,Impact,"
    "Lucida Bright,Lucida Calligraphy,Lucida Console,Lucida Fax,Lucida Handwriting,"
    "Lucida Sans,Lucida Sans Typewriter,Lucida Sans Unicode,Microsoft Sans Serif,"
    "Monotype Corsiva,MS Gothic,MS PGothic,MS Reference Sans Serif,MS Sans Serif,"
    "MS Serif,Palatino Linotype,Segoe Print,Segoe Script,Segoe UI,Segoe UI Light,"
    "Segoe UI Semibold,Segoe UI Symbol,Tahoma,Times,Times New Roman,Trebuchet MS,"
    "Verdana,Wingdings,Wingdings 3"
)

# ─── Base64 ──────────────────────────────────────────────────────────────────

def _cb64(data: bytes | str) -> str:
    if isinstance(data, str): data = data.encode()
    return base64.b64encode(data).decode().translate(_custom_tbl)

def _x3b64(data: bytes) -> str:
    return base64.b64encode(data).decode().translate(_x3_tbl)

# ─── Math ─────────────────────────────────────────────────────────────────────

def _rot32(v: int, n: int) -> int:
    return ((v << n) | (v >> (32 - n))) & MAX32

def _le4(v: int) -> list[int]:
    return list(struct.pack("<I", v & MAX32))

def _le8(v: int) -> list[int]:
    return list(struct.pack("<Q", v & 0xFFFFFFFFFFFFFFFF))

# ─── Custom hash (A3 segment) ─────────────────────────────────────────────────

def _chash(inp: list[int]) -> list[int]:
    s0, s1, s2, s3 = HASH_IV
    n = len(inp)
    s0 = (s0 ^ n) & MAX32
    s1 = (s1 ^ ((n << 8) & MAX32)) & MAX32
    s2 = (s2 ^ ((n << 16) & MAX32)) & MAX32
    s3 = (s3 ^ ((n << 24) & MAX32)) & MAX32
    buf = bytes(inp)
    for i in range(len(buf) // 8):
        v0 = struct.unpack_from("<I", buf, i * 8)[0]
        v1 = struct.unpack_from("<I", buf, i * 8 + 4)[0]
        s0 = _rot32(((s0 + v0) & MAX32) ^ s2, 7)
        s1 = _rot32(((v0 ^ s1) + s3) & MAX32, 11)
        s2 = _rot32(((s2 + v1) & MAX32) ^ s0, 13)
        s3 = _rot32(((s3 ^ v1) + s1) & MAX32, 17)
    t0=(s0^n)&MAX32; t1=(s1^t0)&MAX32; t2=(s2+t1)&MAX32; t3=(s3^t2)&MAX32
    r0=_rot32(t0,9); r1=_rot32(t1,13); r2=_rot32(t2,17); r3=_rot32(t3,19)
    s0=(r0+r2)&MAX32; s1=(r1^r3)&MAX32; s2=(r2+s0)&MAX32; s3=(r3^s1)&MAX32
    out: list[int] = []
    for s in [s0, s1, s2, s3]: out.extend(_le4(s))
    return out

# ─── CRC32 (JS-compatible) ───────────────────────────────────────────────────

_CRC_POLY = 0xEDB88320
_crc_tbl: list[int] | None = None

def _crc32(data: str) -> int:
    global _crc_tbl
    if _crc_tbl is None:
        t = [0] * 256
        for d in range(256):
            r = d
            for _ in range(8):
                r = (r >> 1) ^ _CRC_POLY if r & 1 else r >> 1
            t[d] = r & MAX32
        _crc_tbl = t
    c = 0xFFFFFFFF
    for ch in data:
        b = ord(ch) & 0xFF
        c = (_crc_tbl[(c & 0xFF) ^ b] ^ (c >> 8)) & MAX32
    u = (0xFFFFFFFF ^ c ^ _CRC_POLY) & MAX32
    return u - 0x100000000 if u > 0x7FFFFFFF else u

# ─── RC4 ─────────────────────────────────────────────────────────────────────

def _rc4(key: str, data: str) -> bytes:
    kb = key.encode(); db = data.encode()
    S = list(range(256)); j = 0
    for i in range(256):
        j = (j + S[i] + kb[i % len(kb)]) & 0xFF
        S[i], S[j] = S[j], S[i]
    out = bytearray(len(db)); i2 = j2 = 0
    for k in range(len(db)):
        i2 = (i2 + 1) & 0xFF
        j2 = (j2 + S[i2]) & 0xFF
        S[i2], S[j2] = S[j2], S[i2]
        out[k] = db[k] ^ S[(S[i2] + S[j2]) & 0xFF]
    return bytes(out)

# ─── Fingerprint ─────────────────────────────────────────────────────────────

def _fingerprint(cookies: dict[str, str]) -> dict[str, Any]:
    cstr = "; ".join(f"{k}={v}" for k, v in cookies.items())
    gpu  = random.choice(GPU_VENDORS)
    vendor, renderer = gpu.split("|")
    res, wts = zip(*SCREEN_RES)
    scr  = random.choices(list(res), weights=list(wts), k=1)[0]
    w, h = (int(x) for x in scr.split(";"))
    aw   = w - random.choice([0, 30, 60, 80]) if random.random() > 0.5 else w
    ah   = h - random.choice([30, 60, 80, 100]) if random.random() > 0.5 else h
    cd   = random.choices([16, 24, 30, 32], [0.05, 0.6, 0.05, 0.3])[0]
    dm   = random.choices([1, 2, 4, 8, 12, 16], [0.1, 0.25, 0.4, 0.2, 0.03, 0.01])[0]
    co   = random.choices([2, 4, 6, 8, 12, 16], [0.1, 0.4, 0.2, 0.15, 0.08, 0.07])[0]
    wh   = hashlib.md5(os.urandom(32)).hexdigest()
    inc  = "true" if random.random() > 0.95 else "false"
    x78y = random.randint(2350, 2450)
    return {
        "x1": USER_AGENT, "x2": "false", "x3": "zh-CN",
        "x4": str(cd), "x5": str(dm), "x6": "24",
        "x7": f"{vendor},{renderer}", "x8": str(co),
        "x9": f"{w};{h}", "x10": f"{aw};{ah}",
        "x11": "-480", "x12": "Asia/Shanghai",
        "x13": inc, "x14": inc, "x15": inc,
        "x16": "false", "x17": "false", "x18": "un", "x19": "MacIntel",
        "x20": "", "x21": PLUGINS, "x22": wh,
        "x23": "false", "x24": "false", "x25": "false",
        "x26": "false", "x27": "false", "x28": "0,false,false",
        "x29": "4,7,8", "x30": "swf object not loaded",
        "x33": "0", "x34": "0", "x35": "0",
        "x36": str(int(time.time() * 1000 - random.randint(5000, 30000))),
        "x37": "0", "x38": "0", "x39": 0, "x40": "0", "x41": "0",
        "x42": "3.4.4", "x43": "742cc32c",
        "x44": str(int(time.time() * 1000)),
        "x45": "__SEC_CAV__1-1-1-1-1|__SEC_WSA__|",
        "x46": "false", "x47": "1|0|0|0|0|0", "x48": "",
        "x49": "{list:[],type:}", "x50": "", "x51": "", "x52": "",
        "x55": "380,380,360,400,380,400,420,380,400,400,360,360,440,420",
        "x56": f"{vendor}|{renderer}|{wh}|35",
        "x57": cstr, "x58": "180", "x59": "2", "x60": "63",
        "x61": "1291", "x62": "2047", "x63": "0", "x64": "0", "x65": "0",
        "x66": {"referer": "", "location": "https://www.xiaohongshu.com/explore", "frame": 0},
        "x67": "1|0", "x68": "0", "x69": "326|1292|30",
        "x70": ["location"], "x71": "true", "x72": "complete",
        "x73": "1191", "x74": "0|0|0", "x75": "Apple Inc.", "x76": "true",
        "x77": "1|1|1|1|1|1|1|1|1|1",
        "x78": {"x": 0, "y": x78y, "left": 0, "right": 290.828125,
                "bottom": x78y + 18, "height": 18, "top": x78y,
                "width": 290.828125, "font": FONTS},
        "x82": "_0x17a2|_0x1954", "x31": "124.04347527516074",
        "x79": "144|599565058866",
        "x53": hashlib.md5(os.urandom(32)).hexdigest(),
        "x54": "10311144241322244122",
        "x80": "1|[object FileSystemDirectoryHandle]",
    }

def _b1(fp: dict[str, Any]) -> str:
    keys = ["x33","x34","x35","x36","x37","x38","x39","x42","x43","x44",
            "x45","x46","x48","x49","x50","x51","x52","x82"]
    j = json.dumps({k: fp[k] for k in keys}, separators=(",", ":"))
    ct = _rc4(B1_KEY, j)
    enc = quote(ct.decode("latin1"), safe="!'()*~._-")
    rb = bytearray()
    i = 0
    while i < len(enc):
        if enc[i] == "%" and i + 2 < len(enc):
            rb.append(int(enc[i+1:i+3], 16)); i += 3
        else:
            rb.append(ord(enc[i])); i += 1
    return _cb64(bytes(rb))

# ─── Session fingerprint cache ────────────────────────────────────────────────

_fp_cache: dict[str, tuple[dict, str, int]] = {}

def _session_fp(cookies: dict[str, str]) -> tuple[dict, str, int]:
    a1 = cookies.get("a1", "")
    if a1 in _fp_cache:
        fp, b1v, x9 = _fp_cache[a1]
        fp["x44"] = str(int(time.time() * 1000))
        return fp, b1v, x9
    fp = _fingerprint(cookies)
    b1v = _b1(fp)
    x9  = _crc32(b1v)
    _fp_cache[a1] = (fp, b1v, x9)
    return fp, b1v, x9

# ─── Payload builder ─────────────────────────────────────────────────────────

def _api_path(uri: str) -> str:
    for ch in ["{", "?"]:
        p = uri.find(ch)
        if p != -1: uri = uri[:p]
    return uri

def _build_payload(hex_d: str, a1: str, content: str, ts: float) -> list[int]:
    p: list[int] = []
    p.extend(VERSION_BYTES)
    seed = struct.unpack("<I", os.urandom(4))[0]
    sb = _le4(seed); s0 = sb[0]; p.extend(sb)
    tsms = int(ts * 1000); tsb = _le8(tsms); p.extend(tsb)
    p.extend(_le8(int((ts - random.randint(10, 50)) * 1000)))
    p.extend(_le4(random.randint(15, 50)))
    p.extend(_le4(random.randint(1000, 1200)))
    p.extend(_le4(len(content.encode())))
    md5b = bytes.fromhex(hex_d)
    for i in range(8): p.append(md5b[i] ^ s0)
    p.append(52)
    a1b = a1.encode()
    for i in range(52): p.append(a1b[i] if i < len(a1b) else 0)
    p.append(10)
    src = APP_ID.encode()
    for i in range(10): p.append(src[i] if i < len(src) else 0)
    p.append(1); p.append(s0 ^ ENV_TABLE[0])
    for i in range(1, 15): p.append(ENV_TABLE[i] ^ ENV_DEF[i])
    apm = hashlib.md5(_api_path(content).encode()).hexdigest()
    apb = [int(apm[i:i+2], 16) for i in range(0, 32, 2)]
    ho  = _chash(list(tsb) + apb)
    p.extend(A3_PREFIX)
    for b in ho: p.append(b ^ s0)
    return p

def _xor(src: list[int]) -> bytes:
    key = bytes.fromhex(HEX_KEY)
    return bytes((src[i] ^ key[i]) & 0xFF if i < len(key) else src[i] & 0xFF
                 for i in range(len(src)))

# ─── URI helpers ─────────────────────────────────────────────────────────────

def build_get_uri(uri: str, params: dict | None = None) -> str:
    if not params: return uri
    parts = []
    for k, v in params.items():
        sv = ",".join(v) if isinstance(v, list) else str(v)
        parts.append(f"{k}={quote(sv, safe='')}")
    return f"{uri}?{'&'.join(parts)}"

def extract_uri(url: str) -> str:
    from urllib.parse import urlparse
    try: return urlparse(url).path
    except Exception: return url.split("?")[0]

# ─── Trace IDs ───────────────────────────────────────────────────────────────

def _b3() -> str: return os.urandom(8).hex()

def _xray(ts: int | None = None) -> str:
    t = ts if ts is not None else int(time.time() * 1000)
    return format((t << 23) | random.randint(0, 8388607), "016x") + os.urandom(8).hex()

# ─── Public API ───────────────────────────────────────────────────────────────

def sign_main_api(
    method: str,
    uri: str,
    cookies: dict[str, str],
    params: dict | None = None,
    payload: dict | None = None,
    timestamp: float | None = None,
) -> dict[str, str]:
    """生成 edith.xiaohongshu.com 请求所需签名 headers。"""
    a1 = cookies.get("a1", "")
    if not a1: raise ValueError("cookies 缺少 'a1' 字段")
    ts   = timestamp or time.time()
    tsms = int(ts * 1000)
    upath = extract_uri(uri)
    full  = build_get_uri(upath, params) if method == "GET" else upath
    content = (upath + (json.dumps(payload, separators=(",", ":")) if payload else "")
               if method == "POST" else full)
    hex_d = hashlib.md5(content.encode()).hexdigest()
    arr   = _build_payload(hex_d, a1, content, ts)
    xored = _xor(arr)
    x3s   = _x3b64(xored[:PAYLOAD_LEN])
    xs    = XYS_PREFIX + _cb64(json.dumps({**SIG_TPL, "x3": X3_PREFIX + x3s}, separators=(",", ":")))
    _, b1v, x9 = _session_fp(cookies)
    xsc   = _cb64(json.dumps({**XSCOMMON_TPL, "x5": a1, "x8": b1v, "x9": x9}, separators=(",", ":")))
    return {"x-s": xs, "x-s-common": xsc, "x-t": str(tsms),
            "x-b3-traceid": _b3(), "x-xray-traceid": _xray(tsms)}
