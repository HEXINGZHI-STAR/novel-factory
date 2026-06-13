#!/usr/bin/env python3
# 简单测试五车间流水线

import requests

def simple_test():
    print("=== 简单测试五车间流水线 ===")
    
    # 健康检查
    response = requests.get("http://127.0.0.1:5001/api/v7/health")
    print(f"健康检查: {response.status_code}")
    
    # 测试生成
    data = {
        "title": "测试小说",
        "chapter_num": 1,
        "chapter_task": "主角来到一个神秘的小镇",
        "mode": "general",
        "word_count": 500
    }
    
    print("\n正在生成章节...")
    response = requests.post("http://127.0.0.1:5001/api/v7/generate", json=data, timeout=180)
    result = response.json()
    
    print(f"成功: {result.get('success')}")
    
    if result.get('success') and 'content' in result:
        content = result['content']
        clean_content = content.replace('\n', '')
        print(f"\n生成内容 ({len(clean_content)}字):")
        print("-" * 50)
        print(content)
        print("-" * 50)
        
        # 保存文件
        with open("测试章节.txt", 'w', encoding='utf-8') as f:
            f.write(content)
        print("\n✓ 章节已保存到: 测试章节.txt")

if __name__ == "__main__":
    simple_test()
