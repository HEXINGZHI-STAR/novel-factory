import requests
import json

data = {
    "title": "山村医途",
    "chapter_num": 1,
    "chapter_task": "主角林晓来到云雾山村，遇到神秘老人",
    "mode": "healing_life_v2",
    "word_count": 1500
}

response = requests.post("http://127.0.0.1:5001/api/v7/generate", json=data, timeout=300)
result = response.json()

if result.get('success'):
    # 内容在 results 字段中
    results = result.get('results', {})
    content = results.get('w4_final_chapter', results.get('content', ''))
    
    if content:
        filename = "第1章_山村医途.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print("文件已保存到:", filename)
        print("字数:", len(content.replace('\n', '').replace(' ', '')))
        print("\n内容预览:")
        print(content[:500] + "...")
    else:
        print("没有找到内容字段")
        print("results 字段:", list(results.keys()))
else:
    print("生成失败:", result.get('reason'))