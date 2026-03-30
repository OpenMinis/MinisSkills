#!/usr/bin/env python3
"""
豪猪 SMS 全功能客户端
- 自动获取可用号码
- 轮询接收验证码（带限流保护）
- 支持自定义重试次数和延迟
"""

import requests
import time
import sys
import os

# ==================== 配置区 ===================
BASE_URL = "https://api.haozhuyun.com/sms/"
TOKEN = os.environ.get("HAOZHU_TOKEN", "12979f4ebab7cfffd5239df6b569d57b6ba4174db474de268754d095fffb40660da9a277a6ad6636f21a80dac7e32f811c921eed962625876572a81c2e15f0b4a7b497091f5fb39ce9dad5e8c5c808a783fe68068a574dcc")
API_KEY = os.environ.get("HAOZHU_API_KEY", "3a216c7fff1b1894fd7ff19f904813ca1f1f56006cf5e9f5af83e5d46ebd17bf")
HEADERS = {"User-Agent": "Haozhu-SMS-Agent/1.0"}


def make_request(params: dict, is_idempotent=False) -> dict:
    """发送请求并返回 JSON 结果"""
    params["token"] = TOKEN
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
    return resp.json()


def get_phone(sid: int, isp: int, max_retries=3) -> str:
    """
    获取指定项目和运营商的电话号码
    
    Args:
        sid: 项目 ID (如 59550)
        isp: 运营商参数 (1=移动，5=联通，9=电信，14=广电)
        max_retries: API 限流时最大重试次数
    
    Returns:
        手机号的字符串
    """
    for attempt in range(max_retries):
        result = make_request({"_id": sid, "action": "getPhone", "sid": sid, "isp": isp})
        
        if result.get("code") == "0":
            phone = result.get("phone")
            print(f"\n✅ [Attempt {attempt + 1}/{max_retries}]: 成功获取号码 → {phone}")
            return phone
        elif "code" in result and result["code"] == -101:
            # API 限流
            wait_time = (30 << attempt)
            print(f"⚠️ 触发 API 限流，等待 {wait_time} 秒后重试...")
            time.sleep(wait_time)
            continue
        else:
            print(f"\n❌ 获取失败：{result}", file=sys.stderr)
            return None
    return None


def get_message(phone: str, sid: int, check_interval: float = 5) -> str:
    """
    查询手机号码收到的短信内容
    
    Args:
        phone: 11 位手机号
        sid: 项目 ID
        check_interval: 每次检查间隔时间（秒）
    
    Returns:
        提取出的 6 位数字验证码，或完整的短信内容
    """
    for _ in range(12):  # 最多等待 60 秒
        result = make_request({
            "_id": sid,
            "action": "getMessage",
            "sid": sid,
            "phone": phone
        })
        
        if isinstance(result, dict) and result.get("code") == "0":
            sms_content = result.get("sms", "")
            import re
            
            numbers = re.findall(r'\d{6}', sms_content)
            if numbers:
                code = numbers[0]
                print(f"🎯 发现 6 位数字码：{code}")
                return code
            
            numbers_short = re.findall(r'\d{4,5}\b', sms_content)
            if numbers_short:
                code = numbers_short[0]
                print(f"📱 发现 4-5 位数代码：{code}")
                return code
        
        print("⏳ 尚未收到短信，请前往目标网站点击【获取验证码】...")
        time.sleep(check_interval)
    
    return None


def cancel_recv(phone: str) -> bool:
    """释放已租用的号码"""
    result = make_request({"action": "cancelRecv", "phone": phone})
    return result.get("code") == "0"


if __name__ == "__main__":
    try:
        if len(sys.argv) < 3:
            print(__doc__)
            exit(-1)
        
        target_sid = int(sys.argv[1])
        target_isp = int(sys.argv[2])
        
        print(f"🎯 任务开始：获取项目 [{target_sid}] [{target_isp}]\n")
        
        phone_number = get_phone(target_sid, target_isp)
        if not phone_number:
            print("❌ 无法获取可用号码", file=sys.stderr)
            exit(1)
        
        print(f"\n📞 当前测试号码：[{phone_number}]")
        print("=" * 60 + "\n")
        answer_code = get_message(phone_number, target_sid)
        
        if not answer_code:
            print(f"\n⏳ 请在目标网站输入手机号 [{phone_number}] 并发送验证码\n")
            time.sleep(5)
            answer_code = get_message(phone_number, target_sid)
            
            if not answer_code:
                print("\n⏳ 再次输入手机号并请求验证码...", file=sys.stderr)
                time.sleep(5)
                answer_code = get_message(phone_number, target_sid)
    except KeyboardInterrupt:
        print("\n⛏️ 用户中断", file=sys.stderr)
        if 'phone_number':
            cancel_recv(phone_number)
    except Exception as e:
        print(f"❗ 程序异常：{type(e).__name__}: {e}", file=sys.stderr)
