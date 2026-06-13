#!/usr/bin/env python3
# 生成《镇妖司：新科状元》前5章，目标签约审核通过

import requests
import os
import json

api_key = "sk-87adbdb2e95d49caada8bac063a87ff9"
os.environ['DEEPSEEK_API_KEY'] = api_key

project_dir = r"d:\study\近思录\小说\盘古AI\projects\镇妖司：新科状元"

# 章节任务列表
chapters = [
    {
        "chapter_num": 1,
        "task": """【第1章：密旨】
沈夜骑马游街，连中三元风光无限，正当他接受万民朝拜时，太监突然传旨：调任镇妖司，任灭妖吏，正九品。
从翰林院的锦绣前程，一脚踩进斩妖除魔的深渊。
结尾钩子：太监转身离开时，沈夜瞥见他的影子在墙上蠕动，嘴角裂到了耳根。"""
    },
    {
        "chapter_num": 2,
        "task": """【第2章：断臂司主】
沈夜踏入镇妖司，看到的是破败的院落和诡异的气氛。断臂女司主苏青棠冷眼打量他，第一句话是："新来的，你活不过三天。"
描写镇妖司的环境，苏青棠的冷酷，以及她断臂处渗血的妖气。
结尾钩子：苏青棠的左臂断口处，有黑色妖气在渗血。"""
    },
    {
        "chapter_num": 3,
        "task": """【第3章：残废同僚】
沈夜认识三位同僚：瘸腿老刘、瞎眼阿七、哑巴小陈。每个人都藏着秘密。
老刘递给他一本《妖物图鉴》，封面沾着干涸的血。
结尾钩子：图鉴翻到最后一页，有人用血写着"沈夜，观世妖宿主"。"""
    },
    {
        "chapter_num": 4,
        "task": """【第4章：兵部灭门案】
第一个任务：兵部尚书满门被杀，现场无凶器无血迹。
沈夜发现死者瞳孔里映着同一个画面——一面铜镜。
结尾钩子：那画面是一面铜镜，镜中映着沈夜自己的脸。"""
    },
    {
        "chapter_num": 5,
        "task": """【第5章：圣贤书推理】
沈夜以《礼记》"视于无形"推理：妖物藏身镜中。
他让人搬来所有铜镜，发现其中一面映不出人影。
小高潮：镜妖现身，沈夜用圣贤书"非礼勿视"四字化作金光，镜妖尖叫碎裂。
结尾钩子：镜妖尸体里掉出一枚黑色妖核，刻着编号"柒叁"。"""
    }
]

# 批量生成章节
for chapter in chapters:
    print(f"\n{'='*60}")
    print(f"正在生成第{chapter['chapter_num']}章...")
    print(f"{'='*60}")
    
    data = {
        "title": "镇妖司：新科状元",
        "chapter_num": chapter['chapter_num'],
        "chapter_task": chapter['task'],
        "mode": "general",
        "word_count": 2000,
        "quick": False
    }
    
    response = requests.post("http://127.0.0.1:5001/api/v7/generate", json=data, timeout=300)
    
    if response.status_code == 200:
        result = response.json()
        if result.get('success'):
            # 获取最终章节内容
            content = result.get('results', {}).get('W4', '')
            if content:
                # 保存章节
                file_path = f"{project_dir}\\正文\\第{chapter['chapter_num']}章_{['密旨', '断臂司主', '残废同僚', '兵部灭门案', '圣贤书推理'][chapter['chapter_num']-1]}.txt"
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"✓ 第{chapter['chapter_num']}章生成成功！")
                print(f"  文件: {file_path}")
                # 预览前200字
                print(f"\n  预览:\n{content[:200]}...")
            else:
                print(f"✗ 第{chapter['chapter_num']}章内容为空")
        else:
            print(f"✗ 第{chapter['chapter_num']}章生成失败: {result.get('message', '未知错误')}")
    else:
        print(f"✗ 请求失败: {response.status_code}")

print(f"\n{'='*60}")
print("批量生成完成！")
print(f"{'='*60}")

# 更新项目状态
state_file = f"{project_dir}\\state.json"
try:
    with open(state_file, 'r', encoding='utf-8') as f:
        state = json.load(f)
except:
    state = {"title": "镇妖司：新科状元", "chapters": {}}

state["current_chapter"] = 5
state["last_updated"] = "2026-06-11"

for i in range(1, 6):
    state["chapters"][str(i)] = {
        "title": ['密旨', '断臂司主', '残废同僚', '兵部灭门案', '圣贤书推理'][i-1],
        "file": f"正文/第{i}章_{['密旨', '断臂司主', '残废同僚', '兵部灭门案', '圣贤书推理'][i-1]}.txt",
        "status": "completed"
    }

with open(state_file, 'w', encoding='utf-8') as f:
    json.dump(state, f, ensure_ascii=False, indent=2)

print(f"\n项目状态已更新: {state_file}")