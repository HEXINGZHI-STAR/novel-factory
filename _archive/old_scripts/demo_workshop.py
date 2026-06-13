#!/usr/bin/env python3
# 五车间流水线演示脚本

import requests
import json
import time

def print_title(text):
    """打印标题"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def print_step(step, text):
    """打印步骤"""
    print(f"\n[{step}] {text}")

def demo_workshop_pipeline():
    print_title("五车间流水线完整演示")
    
    # 1. 健康检查
    print_step("1", "健康检查")
    response = requests.get("http://127.0.0.1:5001/api/v7/health")
    print(f"   状态: {response.status_code}")
    result = response.json()
    print(f"   服务: {'正常' if result.get('status') == 'healthy' else '异常'}")
    
    # 2. 获取模式列表
    print_step("2", "获取可用模式")
    response = requests.get("http://127.0.0.1:5001/api/v7/modes")
    modes = response.json()
    # modes 可能是列表或字典
    if isinstance(modes, dict):
        mode_list = list(modes.keys())
    else:
        mode_list = modes
    print(f"   可用模式 ({len(mode_list)}种):")
    for mode in mode_list[:5]:
        print(f"     - {mode}")
    if len(mode_list) > 5:
        print(f"     ... (还有 {len(mode_list) - 5} 种)")
    
    # 3. 准备测试数据
    print_step("3", "准备测试数据")
    test_data = {
        "title": "山村医途",
        "chapter_num": 1,
        "chapter_task": "主角林晓是一位年轻医生，来到偏远的云雾山村支援医疗，在村口遇到一位神秘的白发老人",
        "mode": "healing_life_v2",
        "platform": "qimao",
        "word_count": 1500,
        "cold_storage": "这是一个关于治愈与成长的故事。主角林晓从繁华都市来到偏远山村，在与村民的相处中，逐渐找到了人生的意义。"
    }
    print(f"   标题: {test_data['title']}")
    print(f"   章节: 第{test_data['chapter_num']}章")
    print(f"   模式: {test_data['mode']}")
    print(f"   任务: {test_data['chapter_task']}")
    
    # 4. 调用五车间流水线
    print_step("4", "启动五车间流水线")
    print("   W0→W1→W2→W3→W4 正在执行...")
    
    start_time = time.time()
    response = requests.post("http://127.0.0.1:5001/api/v7/generate", json=test_data, timeout=300)
    end_time = time.time()
    
    result = response.json()
    duration = end_time - start_time
    
    print(f"\n   执行完成！耗时: {duration:.1f}秒")
    print(f"   成功: {result.get('success', False)}")
    
    # 5. 展示流水线日志
    print_step("5", "流水线执行日志")
    if 'logs' in result:
        for log in result['logs']:
            print(f"   [{log['time']}] [{log['stage']}] {log['message']}")
    
    # 6. 展示各车间输出
    print_step("6", "各车间输出概览")
    
    # W0 主旨锚定
    if 'w0_structured' in result and result['w0_structured']:
        w0 = result['w0_structured']
        print("\n   【W0 主旨锚定】")
        print(f"     一句话主旨: {w0.get('thesis', '')}")
        print(f"     不可替换性: {w0.get('irreplaceability_score', '?')}/10")
        print(f"     情绪锚点: {w0.get('anchor_scene', '')}")
    
    # W1 设定预处理
    if 'w1_hot_storage' in result:
        print("\n   【W1 设定预处理】")
        print(f"     热库内容预览:\n     {result['w1_hot_storage'][:150]}...")
    
    # W2 正文初稿
    if 'w2_draft' in result:
        print("\n   【W2 正文初稿】")
        draft = result['w2_draft']
        clean_draft = draft.replace('\n', '').replace(' ', '')
        print(f"     字数: {len(clean_draft)}")
        print(f"     内容预览:\n     {draft[:150]}...")
    
    # W3 逻辑质检
    if 'w3_report' in result:
        w3 = result['w3_report']
        print("\n   【W3 逻辑质检】")
        print(f"     一致性评分: {w3.get('consistency_score', '?')}")
        print(f"     情绪一致性: {w3.get('emotion_consistency', '?')}")
        if isinstance(w3.get('suggestions'), list) and w3['suggestions']:
            print(f"     改进建议: {w3['suggestions'][0]}")
    
    # W4 文笔精修成品
    if 'content' in result:
        content = result['content']
        print("\n   【W4 文笔精修成品】")
        clean_content = content.replace('\n', '').replace(' ', '')
        print(f"     字数: {len(clean_content)}")
        print("\n" + "-"*50)
        print(content)
        print("-"*50)
        
        # 保存文件
        filename = f"第{test_data['chapter_num']}章_{test_data['title']}_演示版.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\n     ✓ 章节已保存到: {filename}")
    
    # 7. 展示监控数据
    print_step("7", "监控数据")
    response = requests.get("http://127.0.0.1:5001/api/v7/dashboard")
    dashboard = response.json()
    
    llm_stats = dashboard.get('llm_stats', {})
    health = dashboard.get('health', {})
    
    print("\n   LLM 调用统计:")
    print(f"     总调用: {llm_stats.get('total_calls', 0)}")
    print(f"     成功: {llm_stats.get('success_calls', 0)}")
    print(f"     失败: {llm_stats.get('failed_calls', 0)}")
    
    print("\n   系统健康状态:")
    print(f"     状态: {health.get('status', 'unknown')}")
    print(f"     请求成功率: {health.get('request_success_rate', 0):.1f}%")
    
    print_title("演示完成！")
    print("\n🎉 五车间流水线运行成功！")
    print("\n📝 使用方式:")
    print("   1. CLI: python pangu_optimized.py → 选择项目 → 输入 3")
    print("   2. API: POST /api/v7/generate")
    print("   3. 监控: GET /api/v7/dashboard")

if __name__ == "__main__":
    demo_workshop_pipeline()