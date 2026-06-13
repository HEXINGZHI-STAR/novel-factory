#!/usr/bin/env python3
# 快速生成并保存章节

import requests
import json

def quick_generate():
    print("=== 快速生成章节 ===")
    
    data = {
        "title": "山村医途",
        "chapter_num": 1,
        "chapter_task": "主角林晓来到云雾山村，遇到神秘老人",
        "mode": "healing_life_v2",
        "word_count": 1500
    }
    
    print(f"正在生成第{data['chapter_num']}章...")
    response = requests.post("http://127.0.0.1:5001/api/v7/generate", json=data, timeout=300)
    result = response.json()
    
    if result.get('success') and 'content' in result:
        content = result['content']
        filename = f"第{data['chapter_num']}章_{data['title']}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"\n✓ 章节已保存到: {filename}")
        clean_content = content.replace('\n', '').replace(' ', '')
        print(f"📝 字数: {len(clean_content)}")
        print(f"\n{content[:500]}...")
        
        return filename
    else:
        print(f"✗ 生成失败: {result.get('reason', '未知')}")
        return None

if __name__ == "__main__":
    quick_generate()
