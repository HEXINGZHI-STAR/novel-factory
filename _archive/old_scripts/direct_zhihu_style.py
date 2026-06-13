#!/usr/bin/env python3
# 直接生成知乎盐选风格的观点类短文

import requests
import os

api_key = "sk-87adbdb2e95d49caada8bac063a87ff9"
api_base = "https://api.deepseek.com/v1"

prompt = """
请生成一篇类似知乎盐选风格的观点类深度文章：

【标题】为什么我们越来越难感到幸福？

【主题】探讨现代社会中幸福感缺失的深层原因

【结构要求】
1. 引言：提出问题，引发共鸣
2. 第一部分：信息过载与比较焦虑
   - 社交媒体带来的"别人家的生活"
   - 算法推荐制造的信息茧房
   - 数据支撑：相关研究或调查结果
   
3. 第二部分：目标异化与幸福悖论
   - 追逐目标本身成为目的
   - 达成目标后的空虚感
   - 案例分析

4. 第三部分：即时满足与延迟满足的失衡
   - 短视频、游戏等即时刺激的影响
   - 深度体验能力的退化
   
5. 第四部分：社交网络的虚幻与现实的落差
   - 精心包装的虚拟形象
   - 真实社交能力的弱化

6. 结论：回归本质，寻找真实的幸福

【风格要求】
- 观点鲜明，论证有力
- 语言犀利但有温度
- 引用数据或研究支撑论点
- 引发读者反思

【字数】约1500字
"""

payload = {
    "model": "deepseek-chat",
    "messages": [
        {"role": "system", "content": "你是一位资深的知乎盐选专栏作者，擅长撰写深度观点类文章。你的文章结构清晰、论证有力、语言犀利且富有洞察力。"},
        {"role": "user", "content": prompt}
    ],
    "max_tokens": 2000,
    "temperature": 0.7
}

print("正在生成知乎盐选风格短文...")
response = requests.post(
    f"{api_base}/chat/completions",
    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    json=payload,
    timeout=180
)

if response.status_code == 200:
    result = response.json()
    content = result["choices"][0]["message"]["content"]
    
    with open('知乎盐选风格短文.txt', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✓ 生成成功！文件已保存为: 知乎盐选风格短文.txt")
    print("\n--- 内容预览 ---")
    print(content[:1500] + "...")
else:
    print(f"✗ 请求失败: {response.status_code}")
    print(response.text)