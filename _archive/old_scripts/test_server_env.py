#!/usr/bin/env python3
# 测试服务器中的环境变量

import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")
print(f"DEEPSEEK_API_KEY: {'已设置' if api_key else '未设置'}")
if api_key:
    print(f"API Key 值: {api_key}")
    
# 测试调用
import requests

payload = {
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 50
}

response = requests.post(
    "https://api.deepseek.com/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    json=payload,
    timeout=60
)

print(f"\n测试调用结果:")
print(f"状态码: {response.status_code}")
if response.status_code == 200:
    print("✓ API调用成功")
else:
    print(f"✗ API调用失败: {response.text}")