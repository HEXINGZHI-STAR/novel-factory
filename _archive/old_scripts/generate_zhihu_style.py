#!/usr/bin/env python3
# 生成知乎盐选风格的观点类短文

import requests
import os

# 设置环境变量
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
5. 特点：引用数据或现象，有独特视角

请从以下角度分析：
- 信息过载与比较焦虑
- 目标异化与幸福悖论
- 即时满足与延迟满足的失衡
- 社交网络的虚幻与现实的落差
    """,
    "mode": "general",
    "word_count": 1500
}

print("正在生成知乎盐选风格短文...")
response = requests.post("http://127.0.0.1:5001/api/v7/generate", json=data, timeout=300)

if response.status_code == 200:
    result = response.json()
    if result.get('success'):
        content = result.get('results', {}).get('W4', '')
        if content:
            # 保存文件
            with open('知乎盐选风格短文.txt', 'w', encoding='utf-8') as f:
                f.write(content)
            print("✓ 生成成功！文件已保存为: 知乎盐选风格短文.txt")
            print("\n--- 内容预览 ---")
            print(content[:800] + "...")
        else:
            print("✗ 生成内容为空")
    else:
        print(f"✗ 生成失败: {result.get('error', '未知错误')}")
else:
    print(f"✗ 请求失败: {response.status_code}")