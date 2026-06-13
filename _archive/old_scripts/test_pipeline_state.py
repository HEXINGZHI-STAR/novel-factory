#!/usr/bin/env python3
# 测试五车间流水线完整流程（包含状态追踪）

import requests
import json

def test_pipeline_with_state():
    print("=== 五车间流水线完整测试（含状态追踪）===")
    
    # 测试数据
    test_data = {
        "title": "山村医途",
        "chapter_num": 1,
        "chapter_task": "主角林晓是一位年轻医生，来到偏远的云雾山村支援医疗，在村口遇到一位神秘的白发老人",
        "mode": "healing_life_v2",
        "platform": "qimao",
        "word_count": 2000,
        "cold_storage": "这是一个关于治愈与成长的故事。主角林晓从繁华都市来到偏远山村，在与村民的相处中，逐渐找到了人生的意义。"
    }
    
    print(f"\n任务: {test_data['chapter_task']}")
    print(f"模式: {test_data['mode']}")
    print(f"平台: {test_data['platform']}")
    
    # 调用五车间流水线
    response = requests.post("http://127.0.0.1:5001/api/v7/generate", json=test_data, timeout=120)
    result = response.json()
    
    print(f"\n状态码: {response.status_code}")
    print(f"成功: {result.get('success', False)}")
    
    # 打印流水线日志
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
        
        # W0 主旨锚定
        if 'w0_structured' in result and result['w0_structured']:
            w0 = result['w0_structured']
            print("\n【W0 主旨锚定】")
            print(f"  一句话主旨: {w0.get('thesis', '')}")
            print(f"  不可替换性: {w0.get('irreplaceability_score', '?')}/10")
            print(f"  情绪锚点: {w0.get('anchor_scene', '')}")
            print(f"  反直觉点: {w0.get('counterintuitive_point', '')}")
        
        # W1 设定预处理
        if 'w1_hot_storage' in result:
            print("\n【W1 设定预处理】")
            print(f"  热库内容:\n{result['w1_hot_storage'][:200]}...")
        
        # W2 正文初稿
        if 'w2_draft' in result:
            print("\n【W2 正文初稿】")
            draft = result['w2_draft']
            clean_draft = draft.replace('\n', '').replace(' ', '')
            print(f"  字数: {len(clean_draft)}")
            print(f"  内容预览:\n{draft[:200]}...")
        
        # W3 逻辑质检
        if 'w3_report' in result:
            w3 = result['w3_report']
            print("\n【W3 逻辑质检】")
            print(f"  一致性评分: {w3.get('consistency_score', '?')}")
            print(f"  情绪一致性: {w3.get('emotion_consistency', '?')}")
            print(f"  人物一致性: {w3.get('character_consistency', '?')}")
            if w3.get('suggestions'):
                print(f"  建议: {', '.join(w3['suggestions'][:3])}")
        
        # W4 文笔精修成品
        if 'content' in result:
            content = result['content']
            clean_content = content.replace('\n', '').replace(' ', '')
            print("\n【W4 文笔精修成品】")
            print(f"  字数: {len(clean_content)}")
            print(f"\n{content}")
        
        # 状态追踪数据
        if 'state_tracker' in result:
            print("\n【状态追踪数据】")
            state = result['state_tracker']
            print(f"  章节状态: {state.get('chapter_state', {}).get('chapter_num', 'N/A')}")
            print(f"  写作统计: {state.get('writing_stats', {}).get('total_words', 0):,} 字")
        
        # 保存生成的章节
        if 'content' in result:
            chapter_file = f"第{test_data['chapter_num']}章_山村医途.txt"
            with open(chapter_file, 'w', encoding='utf-8') as f:
                f.write(result['content'])
            print(f"\n✓ 章节已保存到: {chapter_file}")

if __name__ == "__main__":
    test_pipeline_with_state()
