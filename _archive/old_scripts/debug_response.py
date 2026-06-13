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
print("Status:", response.status_code)
result = response.json()
print("Success:", result.get('success'))
print("Keys:", list(result.keys()))
if 'content' in result:
    print("Content length:", len(result['content']))
    print("Content preview:", result['content'][:200])
elif 'reason' in result:
    print("Reason:", result['reason'])