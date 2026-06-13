#!/usr/bin/env python3
# 测试五车间流水线完整流程

import requests
import json

def test_workshop_pipeline():
    print("=== 测试五车间流水线 ===")
    
    # 测试健康检查
    print("\n1. 健康检查")
    response = requests.get("http://127.0.0.1:5001/api/v7/health")
    print(f"   状态: {response.status_code}")
    print(f"   响应: {response.json()}")
    
    # 测试获取模式列表
    print("\n2. 获取模式列表")
    response = requests.get("http://127.0.0.1:5001/api/v7/modes")
    modes = response.json()
    print(f"   可用模式: {', '.join(modes)}")
    
    # 测试 W0 主旨锚定单独调用
    print("\n3. 测试 W0 主旨锚定")
    anchor_data = {
        "title": "测试小说",
        "chapter_task": "主角是一位年轻的医生，来到偏远山村行医，遇到了神秘的老中医",
        "mode": "healing_life_v2"
    }
    response = requests.post("http://127.0.0.1:5001/api/v7/anchor", json=anchor_data)
    result = response.json()
    print(f"   状态: {response.status_code}")
    print(f"   主旨锚定结果: {result.get('anchor', '')[:100]}...")
    
    # 测试完整五车间流水线
    print("\n4. 测试完整五车间流水线")
    generate_data = {
        "title": "山村医途",
        "chapter_num": 1,
        "chapter_task": "主角林晓来到云雾山村，村口遇到一位神秘的白发老人",
        "mode": "healing_life_v2",
        "platform": "qimao"
    }
    
    print(f"   任务: {generate_data['chapter_task']}")
    response = requests.post("http://127.0.0.1:5001/api/v7/generate", json=generate_data, timeout=120)
    result = response.json()
    
    print(f"   状态: {response.status_code}")
    print(f"   成功: {result.get('success', False)}")
    
    # 打印日志
    if 'logs' in result:
        print("\n   流水线日志:")
        for log in result['logs']:
            print(f"     [{log['stage']}] {log['message']}")
    
    # 打印生成的内容
    if result.get('success') and 'content' in result:
        content = result['content']
        print("\n   生成内容（前200字）:")
        print(f"     {content[:200]}...")
        clean_content = content.replace('\n', '').replace(' ', '')
        print(f"\n   字数: {len(clean_content)}")

if __name__ == "__main__":
    test_workshop_pipeline()
