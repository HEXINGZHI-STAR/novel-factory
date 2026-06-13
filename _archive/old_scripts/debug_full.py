#!/usr/bin/env python3
# 调试服务器响应

import requests

data = {
    "title": "山村医途",
    "chapter_num": 1,
    "chapter_task": "主角林晓来到云雾山村，遇到神秘老人",
    "mode": "healing_life_v2",
    "word_count": 1500
}

response = requests.post("http://127.0.0.1:5001/api/v7/generate", json=data, timeout=300)
print("状态码:", response.status_code)
result = response.json()

print("\n=== 响应结构 ===")
print("success:", result.get('success'))
print("keys:", list(result.keys()))

if 'results' in result:
    results = result['results']
    print("\n=== results 字段 ===")
    for key, value in results.items():
        print(f"{key}: {type(value).__name__}")
        if isinstance(value, str):
            print(f"  长度: {len(value)}")
            if len(value) > 0:
                print(f"  预览: {value[:100]}...")

if 'logs' in result:
    print("\n=== 日志 ===")
    for log in result['logs']:
        print(f"[{log['stage']}] {log['message']}")