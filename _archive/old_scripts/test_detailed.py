#!/usr/bin/env python3
# 详细测试五车间流水线

import requests
import json

def test_full_pipeline_detailed():
    print("=== 五车间流水线详细测试 ===")
    
    generate_data = {
        "title": "山村医途",
        "chapter_num": 1,
        "chapter_task": "主角林晓来到云雾山村，村口遇到一位神秘的白发老人",
        "mode": "healing_life_v2",
        "platform": "qimao"
    }
    
    print(f"\n任务: {generate_data['chapter_task']}")
    response = requests.post("http://127.0.0.1:5001/api/v7/generate", json=generate_data, timeout=120)
    result = response.json()
    
    print(f"\n状态: {response.status_code}")
    print(f"成功: {result.get('success', False)}")
    
    # 打印完整日志
    if 'logs' in result:
        print("\n" + "="*60)
        print("流水线执行日志")
        print("="*60)
        for log in result['logs']:
            print(f"[{log['time']}] [{log['stage']}] {log['message']}")
    
    # 打印各车间输出
    if result.get('success'):
        print("\n" + "="*60)
        print("各车间输出概览")
        print("="*60)
        
        if 'w0_anchor' in result:
            print("\n【W0 主旨锚定】")
            print(f"  一句话主旨: {result.get('w0_structured', {}).get('thesis', '')}")
            print(f"  不可替换性: {result.get('w0_structured', {}).get('irreplaceability_score', '?')}/10")
            print(f"  情绪锚点: {result.get('w0_structured', {}).get('anchor_scene', '')}")
        
        if 'w1_hot_storage' in result:
            print("\n【W1 设定预处理】")
            print(f"  热库内容: {result['w1_hot_storage'][:100]}...")
        
        if 'w2_draft' in result:
            print("\n【W2 正文初稿】")
            print(f"  字数: {result.get('w2_word_count', 0)}")
            print(f"  内容预览:\n{result['w2_draft'][:200]}...")
        
        if 'w3_report' in result:
            print("\n【W3 逻辑质检】")
            w3 = result.get('w3_report', {})
            print(f"  一致性评分: {w3.get('consistency_score', '?')}")
            print(f"  情绪一致性: {w3.get('emotion_consistency', '?')}")
            print(f"  人物一致性: {w3.get('character_consistency', '?')}")
        
        if 'content' in result:
            print("\n【W4 文笔精修成品】")
            content = result['content']
            clean_content = content.replace('\n', '').replace(' ', '')
            print(f"  字数: {len(clean_content)}")
            print(f"\n{content}")

if __name__ == "__main__":
    test_full_pipeline_detailed()
