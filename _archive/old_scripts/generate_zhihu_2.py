#!/usr/bin/env python3
# 生成知乎盐选风格文章 - 职场成长主题

import requests
import os
import json

api_key = "sk-87adbdb2e95d49caada8bac063a87ff9"
api_base = "https://api.deepseek.com/v1"

prompt = """
请生成一篇类似知乎盐选风格的观点类深度文章：

【标题】为什么你越努力，越容易陷入"无效内卷"？

【主题】探讨职场中努力与产出不成正比的深层原因，以及如何跳出内卷陷阱

【结构要求】
1. 引言：提出问题——为什么很多人努力工作却得不到相应回报？
2. 第一部分：努力的假象——忙碌不等于产出
   - 时间管理的误区：把忙碌当作效率
   - 任务选择的偏差：做紧急的事而非重要的事
   - 数据支撑：相关研究或调查结果
   
3. 第二部分：内卷的本质——零和博弈的困境
   - 内卷的定义和特征
   - 企业管理中的"伪KPI"现象
   - 案例分析：某大厂的996文化反思

4. 第三部分：破局之道——从"努力"到"有效努力"
   - 建立个人护城河：不可替代性
   - 学会拒绝：精力管理的艺术
   - 杠杆思维：用更少的努力获得更大的成果
   
5. 第四部分：重新定义成功——工作与生活的平衡
   - 金钱之外的价值追求
   - 长期主义 vs 短期利益
   - 真正的成长：能力的复利效应

6. 结论：跳出内卷，找到属于自己的节奏

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

print("正在生成第二篇知乎盐选风格文章...")
response = requests.post(
    f"{api_base}/chat/completions",
    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    json=payload,
    timeout=180
)

if response.status_code == 200:
    result = response.json()
    content = result["choices"][0]["message"]["content"]
    
    # 保存文章
    file_path = r"d:\study\近思录\小说\盘古AI\projects\知乎盐选\观点文章\为什么你越努力越容易陷入无效内卷.txt"
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # 更新状态文件
    state_file = r"d:\study\近思录\小说\盘古AI\projects\知乎盐选\state.json"
    with open(state_file, 'r', encoding='utf-8') as f:
        state = json.load(f)
    
    state["articles"]["观点文章"].append({
        "title": "为什么你越努力，越容易陷入\"无效内卷\"？",
        "file": "观点文章/为什么你越努力越容易陷入无效内卷.txt",
        "word_count": 1500,
        "category": "职场成长",
        "status": "completed"
    })
    state["last_updated"] = "2026-06-11"
    
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 生成成功！文件已保存为: {file_path}")
    print("\n--- 内容预览 ---")
    print(content[:1000] + "...")
else:
    print(f"✗ 请求失败: {response.status_code}")
    print(response.text)