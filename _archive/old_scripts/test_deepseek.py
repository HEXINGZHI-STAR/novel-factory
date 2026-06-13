#!/usr/bin/env python3
# 测试 DeepSeek API 连接

import requests

api_key = "sk-87adbdb2e95d49caada8bac063a87ff9"
api_base = "https://api.deepseek.com/v1"

# 简单测试
payload = {
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 50,
    "temperature": 0.7
}

try:
    response = requests.post(
        f"{api_base}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=60
    )
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.text[:500]}")
except Exception as e:
    print(f"错误: {e}")