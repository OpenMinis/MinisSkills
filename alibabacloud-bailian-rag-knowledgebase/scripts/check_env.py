#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
环境检查脚本：验证阿里云凭证、SDK 安装情况以及 API 连通性。
"""

import os
import sys
import json

def check_environment():
    print("=" * 50)
    print("阿里云百炼知识库服务 - 环境检查")
    print("=" * 50)
    
    # 1. 检查凭证
    ak = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_ID')
    sk = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
    
    cred_ok = bool(ak and sk)
    cred_icon = "✅" if cred_ok else "❌"
    ak_display = f"{ak[:5]}{'*'*(len(ak)-9)}{ak[-4:]}" if ak else "未设置"
    
    print(f"\n[凭证配置] {cred_icon}")
    print(f"  AccessKey ID: {ak_display}")
    if sk: print("  AccessKey Secret: [已配置]")
    if not ak or not sk:
        print("  ⚠️  未检测到完整的凭证环境变量！")
        print("     请在 Minis 设置中配置：")
        print("     - ALIBABA_CLOUD_ACCESS_KEY_ID")
        print("     - ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        return False
        
    # 2. 检查默认工作空间和知识库配置
    ws_id = os.getenv('DEFAULT_WORKSPACE_ID')
    idx_id = os.getenv('DEFAULT_INDEX_ID')
    
    ws_ok = bool(ws_id)
    idx_ok = bool(idx_id)
    
    ws_icon = "✅" if ws_ok else "⚠️"
    idx_icon = "✅" if idx_ok else "⚠️"
    ws_display = ws_id if ws_ok else "未设置"
    idx_display = idx_id if idx_ok else "未设置"
    
    print(f"\n[默认配置]")
    print(f"  DEFAULT_WORKSPACE_ID  {ws_icon}  {ws_display}")
    print(f"  DEFAULT_INDEX_ID      {idx_icon}  {idx_display}")
    if not ws_ok or not idx_ok:
        print("  💡 提示：使用 quick_retrieve.py 时可直接传参 workspace_id 和 index_id")
        
    # 3. 检查 SDK 安装
    sdk_checks = [
        ("alibabacloud_bailian20231229", "百炼 SDK"),
        ("alibabacloud_credentials", "凭证库"),
        ("alibabacloud_tea_util", "Tea 工具包"),
    ]
    
    for module_name, label in sdk_checks:
        try:
            mod = __import__(module_name)
            ver = getattr(mod, '__version__', 'unknown')
            print(f"[{label}] ✅ v{ver}")
        except ImportError:
            print(f"[{label}] ❌ 未安装或导入失败")
            return False
            
    # 3. 尝试创建客户端（连通性检查）
    try:
        from alibabacloud_bailian20231229.client import Client as BaiLianClient
        from alibabacloud_tea_openapi.models import Config
        
        config = Config(
            access_key_id=ak,
            access_key_secret=sk,
            endpoint="bailian.cn-beijing.aliyuncs.com",
            read_timeout=10000,
            connect_timeout=10000
        )
        client = BaiLianClient(config)
        print("\n[API 连通] ✅ SDK 初始化成功，连接正常")
        print("=" * 50)
        print("环境检查通过！你可以通过以下命令开始使用：")
        print("  python3 scripts/list_indices.py <id>    # 列出知识库")
        print("  python3 scripts/retrieve.py <id> <id>   # 检索内容")
        return True
    except Exception as e:
        print(f"\n[API 连通] ❌ 连接失败: {type(e).__name__}: {e}")
        return False

if __name__ == '__main__':
    success = check_environment()
    sys.exit(0 if success else 1)
