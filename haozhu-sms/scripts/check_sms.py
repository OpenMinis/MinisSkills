#!/usr/bin/env python3
"""
豪猪 SMS 短信查询工具
用法：python3 check_sms.py <项目 ID> <手机号>
示例：python3 check_sms.py 59550 18290252747
"""

import requests
import sys
import os
import re

BASE_URL = "https://api.haozhuyun.com/sms/"
TOKEN = os.environ.get("HAOZHU_TOKEN", "12979f4ebab7cfffd5239df6b569d57b6ba4174db474de268754d095fffb40660da9a277a6ad6636f21a80dac7e32f811c921eed962625876572a81c2e15f0b4a7b497091f5fb39ce9dad5e8c5c808a783fe68068a574dcc")
HEADERS = {"User-Agent": "Haozhu-SMS-Check/1.0"}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        exit(1)
    
    sid, phone = int(sys.argv[1]), sys.argv[2]
    
    resp = requests.get(BASE_URL, {
        "_id": sid, "action": "getMessage", "sid": sid, "phone": phone, "token": TOKEN
    }, headers=HEADERS, timeout=30)
    
    result = resp.json()
    
    if result.get("code") == "0":
        sms_content = result.get("sms", "")
        print(f"\n📱 原始短信内容:\n{sms_content}\n")
        
        # 提取数字码
        numbers_6 = re.findall(r'\d{6}', sms_content)
        numbers_4_5 = re.findall(r'\b\d{4,5}\b', sms_content)
        
        if numbers_6:
            print(f"🎯 6 位验证码：{numbers_6[0]}")
        elif numbers_4_5:
            print(f"📞 4-5 位代码：{numbers_4_5[0]}")
        
        return 0
    else:
        print(f"❌ 查询失败：{result}")
        return -1


if __name__ == "__main__":
    sys.exit(main())
