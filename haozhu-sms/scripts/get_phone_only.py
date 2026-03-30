#!/usr/bin/env python3
"""
豪猪 SMS 快速接码工具
用法：python3 get_phone_only.py <项目 ID> <运营商>
示例：python3 get_phone_only.py 59550 1

运营商参数：1=移动，5=联通，9=电信，14=广电
"""

import requests
import sys
import os

BASE_URL = "https://api.haozhuyun.com/sms/"
TOKEN = os.environ.get("HAOZHU_TOKEN", "12979f4ebab7cfffd5239df6b569d57b6ba4174db474de268754d095fffb40660da9a277a6ad6636f21a80dac7e32f811c921eed962625876572a81c2e15f0b4a7b497091f5fb39ce9dad5e8c5c808a783fe68068a574dcc")
HEADERS = {"User-Agent": "Haozhu-SMS-Fast/1.0"}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        exit(1)
    
    sid, isp = int(sys.argv[1]), int(sys.argv[2])
    
    resp = requests.get(BASE_URL, {
        "_id": sid, "action": "getPhone", "sid": sid, "isp": isp, "token": TOKEN
    }, headers=HEADERS, timeout=30)
    
    result = resp.json()
    
    if result.get("code") == "0":
        print(f"{result['phone']}")  # 纯输出手机号，方便管道使用
        return 0
    else:
        print(f"Error: {result}", file=sys.stderr)
        return -1


if __name__ == "__main__":
    sys.exit(main())
