#!/usr/bin/env python3
# 调试 API 返回数据

import requests
import json

def debug_api_response():
    test_data = {
        "title": "山村医途",
        "chapter_num": 1,
        "chapter_task": "主角林晓来到云雾山村，村口遇到一位神秘的白发老人",
        "mode": "healing_life_v2",
        "platform": "qimao",
        "word_count": 1000,
        "cold_storage": "治愈系故事"
    }
    
    response = requests.post("http://127.0.0.1:5001/api/v7/generate", json=test_data, timeout=120)
    print(f"状态码: {response.status_code}")
    print(f"\n响应内容:")
    result = response.json()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    # 检查所有键
    print(f"\n所有键: {list(result.keys())}")

if __name__ == "__main__":
    debug_api_response()
