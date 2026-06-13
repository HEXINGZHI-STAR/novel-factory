#!/usr/bin/env python3
# 调试知乎盐选风格短文生成

import requests
import os

os.environ['DEEPSEEK_API_KEY'] = 'sk-87adbdb2e95d49caada8bac063a87ff9'

data = {
    "title": "知乎盐选风格短文",
    "chapter_num": 1,
    "chapter_task": """
生成一篇类似知乎盐选风格的观点类短文，主题：为什么我们越来越难感到幸福？

要求：
1. 风格：深度分析、观点鲜明、引发思考
2. 结构：提出问题 → 分析原因 → 给出见解
3. 语言：犀利但不刻薄，理性且有温度
4. 字数：约1500字

从以下角度分析：
- 信息过载与比较焦虑
- 目标异化与幸福悖论
- 即时满足与延迟满足的失衡
- 社交网络的虚幻与现实的落差
    """,
    "mode": "general",
    "word_count": 1500
}

response = requests.post("http://127.0.0.1:5001/api/v7/generate", json=data, timeout=300)
print("状态码:", response.status_code)
result = response.json()
print("\n响应结构:")
print("success:", result.get('success'))
print("keys:", list(result.keys()))

if 'results' in result:
    print("\nresults 内容:")
    for key, value in result['results'].items():
        if isinstance(value, str):
            print(f"{key}: {len(value)} 字符")
            if len(value) > 0:
                print(f"  预览: {value[:200]}...")
        else:
            print(f"{key}: {type(value).__name__}")

if 'logs' in result:
    print("\n日志:")
    for log in result['logs']:
        print(f"[{log['stage']}] {log['message']}")