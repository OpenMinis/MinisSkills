"""
Creator platform signing (XYW_ prefix) for creator.xiaohongshu.com

改造来源：jackwener/xiaohongshu-cli
https://github.com/jackwener/xiaohongshu-cli/blob/main/xhs_cli/creator_signing.py
"""

import base64
import hashlib
import json
import time

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

AES_KEY = b"7cc4adla5ay0701v"
AES_IV  = b"4uzjr7mbsibcaldp"


def _aes_encrypt(data: str) -> str:
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return cipher.encrypt(pad(data.encode(), AES.block_size)).hex()


def sign_creator(api: str, data: dict | None, a1: str) -> dict[str, str]:
    """生成 creator.xiaohongshu.com 签名 headers。"""
    content = api + (json.dumps(data, separators=(",", ":")) if data else "")
    x1 = hashlib.md5(content.encode()).hexdigest()
    x4 = int(time.time() * 1000)
    plain = f"x1={x1};x2=0|0|0|1|0|0|1|0|0|0|1|0|0|0|0|1|0|0|0;x3={a1};x4={x4};"
    payload = _aes_encrypt(base64.b64encode(plain.encode()).decode())
    envelope = {"signSvn": "56", "signType": "x2", "appId": "ugc",
                "signVersion": "1", "payload": payload}
    xs = "XYW_" + base64.b64encode(json.dumps(envelope, separators=(",", ":")).encode()).decode()
    return {"x-s": xs, "x-t": str(x4)}
