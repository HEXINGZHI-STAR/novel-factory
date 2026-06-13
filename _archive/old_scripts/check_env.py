#!/usr/bin/env python3
# 检查环境变量加载

import os

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✓ dotenv 加载成功")
except ImportError:
    print("✗ dotenv 未安装")

print("\n环境变量检查:")
print(f"DEEPSEEK_API_KEY: {'已设置' if os.getenv('DEEPSEEK_API_KEY') else '未设置'}")
print(f"LLM_MODEL: {os.getenv('LLM_MODEL', '未设置')}")

# 测试 API Key 是否正确
api_key = os.getenv('DEEPSEEK_API_KEY')
if api_key:
    print(f"\nAPI Key 前8位: {api_key[:8]}...")
    print(f"API Key 长度: {len(api_key)}")