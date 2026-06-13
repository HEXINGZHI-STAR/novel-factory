#!/usr/bin/env python3
# 测试五车间流水线 API

import requests
import json

data = {
    "title": "测试小说",
    "chapter_num": 1,
    "chapter_task": "主角来到一个神秘的小镇",
    "mode": "healing_life_v2",
    "platform": "qimao"
}

try:
    response = requests.post(
        "http://127.0.0.1:5001/api/v7/generate",
        json=data,
        timeout=60
    )
    print(f"状态码: {response.status_code}")
    result = response.json()
    print("\n响应:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
except Exception as e:
    print(f"错误: {e}")
