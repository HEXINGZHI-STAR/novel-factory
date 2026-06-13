#!/usr/bin/env python3
# 检查服务器完整响应

import requests
import os

os.environ['DEEPSEEK_API_KEY'] = 'sk-87adbdb2e95d49caada8bac063a87ff9'

data = {
    "title": "为什么我们越来越难感到幸福",
    "chapter_num": 1,
    "chapter_task": """
生成一篇类似知乎盐选风格的观点类深度文章：

【标题】为什么我们越来越难感到幸福？

【主题】探讨现代社会中幸福感缺失的深层原因

【结构要求】
1. 引言：提出问题，引发共鸣
2. 信息过载与比较焦虑
3. 目标异化与幸福悖论
4. 即时满足与延迟满足的失衡
5. 社交网络的虚幻与现实的落差
6. 结论：回归本质，寻找真实的幸福

【风格要求】观点鲜明，论证有力，语言犀利但有温度
【字数】约1500字
    """,
    "mode": "general",
    "word_count": 1500,
    "quick": True
}

response = requests.post("http://127.0.0.1:5001/api/v7/generate", json=data, timeout=300)
result = response.json()

print("=== 完整响应 ===")
import json
print(json.dumps(result, ensure_ascii=False, indent=2))

# 检查所有可能的输出键
print("\n=== 搜索输出内容 ===")
def search_content(obj, path=""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            new_path = f"{path}.{key}" if path else key
            if isinstance(value, str) and len(value) > 100:
                print(f"找到内容: {new_path} (长度: {len(value)})")
                print(f"预览: {value[:300]}...")
                print()
            elif isinstance(value, (dict, list)):
                search_content(value, new_path)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            search_content(item, f"{path}[{i}]")

search_content(result)