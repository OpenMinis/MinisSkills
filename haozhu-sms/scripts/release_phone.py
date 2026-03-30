#!/usr/bin/env python3
"""
豪猪 SMS 号码释放工具
用法：python3 release_phone.py <手机号>
示例：python3 release_phone.py 18290252747
"""

import requests
import sys
import os

BASE_URL = "https://api.haozhuyun.com/sms/"
TOKEN = os.environ.get("HAOZHU_TOKEN", "12979f4ebab7cfffd5239df6b569d57b6ba4174db474de268754d095fffb40660da9a277a6ad6636f21a80dac7e32f811c921eed962625876572a81c2e15f0b4a7b497091f5fb39ce9dad5e8c5c808a783fe68068a574dcc")
HEADERS = {"User-Agent": "Haozhu-SMS-Release/1.0"}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        exit(1)
    
    phone = sys.argv[1]
    
    resp = requests.get(BASE_URL, {
        "action": "cancelRecv", "phone": phone, "token": TOKEN
    }, headers=HEADERS, timeout=30)
    
    result = resp.json()
    
    if result.get("code") == "0":
        print(f"✅ 成功释放号码：{phone}")
        return 0
    else:
        print(f"❌ 释放失败：{result}")
        return -1


if __name__ == "__main__":
    sys.exit(main())
