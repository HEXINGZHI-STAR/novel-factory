#!/usr/bin/env python3
# 直接生成知乎盐选风格短文（绕过故事性检查）

import requests
import os

os.environ['DEEPSEEK_API_KEY'] = 'sk-87adbdb2e95d49caada8bac063a87ff9'

# 使用快速模式，跳过 W0 主旨锚定检查
data = {
    "title": "为什么我们越来越难感到幸福",
    "chapter_num": 1,
    "chapter_task": """
生成一篇类似知乎盐选风格的观点类深度文章：

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
    """,
    "mode": "general",
    "word_count": 1500,
    "quick": True  # 跳过 W0 和 W3 检查
}

print("正在生成知乎盐选风格短文...")
response = requests.post("http://127.0.0.1:5001/api/v7/generate", json=data, timeout=300)

if response.status_code == 200:
    result = response.json()
    print("success:", result.get('success'))
    
    if 'results' in result:
        # 检查各个车间的输出
        for key in ['W2', 'W4']:
            if key in result['results'] and isinstance(result['results'][key], str) and len(result['results'][key]) > 0:
                content = result['results'][key]
                with open('知乎盐选风格短文.txt', 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"✓ 生成成功！文件已保存为: 知乎盐选风格短文.txt")
                print("\n--- 内容预览 ---")
                print(content[:1000] + "...")
                break
        else:
            print("✗ 所有车间输出均为空")
    
    if 'logs' in result:
        print("\n日志:")
        for log in result['logs']:
            print(f"[{log['stage']}] {log['message']}")
else:
    print(f"✗ 请求失败: {response.status_code}")