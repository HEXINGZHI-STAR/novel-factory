#!/usr/bin/env python3
# 直接调用LLM生成《镇妖司：新科状元》前5章

import requests
import os
import json

api_key = "sk-87adbdb2e95d49caada8bac063a87ff9"
api_base = "https://api.deepseek.com/v1"

project_dir = r"d:\study\近思录\小说\盘古AI\projects\镇妖司：新科状元"

# 章节任务列表
chapters = [
    {
        "chapter_num": 1,
        "title": "密旨",
        "task": """【第1章：密旨】

沈夜骑马游街，连中三元风光无限。长安街上万人空巷，百姓们争相目睹新科状元的风采。正当他接受万民朝拜时，一名太监突然策马而来，高声宣旨："奉天承运，皇帝诏曰：新科状元沈夜，才高八斗，胆识过人，着即调任镇妖司，任灭妖吏，正九品。钦此。"

从翰林院的锦绣前程，一脚踩进斩妖除魔的深渊。

要求：
1. 描写沈夜的震惊和不解
2. 描写围观百姓的反应
3. 描写太监的诡异之处
4. 结尾钩子：太监转身离开时，沈夜瞥见他的影子在墙上蠕动，嘴角裂到了耳根。

风格：古风悬疑，节奏紧张"""
    },
    {
        "chapter_num": 2,
        "title": "断臂司主",
        "task": """【第2章：断臂司主】

沈夜踏入镇妖司，看到的是破败的院落和诡异的气氛。院子里长满了青苔，墙角挂着生锈的铁链，空气中弥漫着淡淡的血腥味。

断臂女司主苏青棠坐在正厅，冷眼打量他，第一句话是："新来的，你活不过三天。"

要求：
1. 详细描写镇妖司的环境
2. 描写苏青棠的外貌和气质（断左臂，脸上三道妖爪疤痕）
3. 描写苏青棠断臂处渗血的妖气
4. 结尾钩子：苏青棠的左臂断口处，有黑色妖气在渗血。

风格：悬疑惊悚，氛围压抑"""
    },
    {
        "chapter_num": 3,
        "title": "残废同僚",
        "task": """【第3章：残废同僚】

沈夜认识三位同僚：瘸腿老刘、瞎眼阿七、哑巴小陈。每个人都藏着秘密。

老刘是镇妖司的活字典，瘸着腿却行走如飞；阿七双眼失明，却能听见十里外的风吹草动；小陈从不说话，却能用手势传递复杂信息。

老刘递给他一本《妖物图鉴》，封面沾着干涸的血。

要求：
1. 描写三位同僚的特点
2. 描写《妖物图鉴》的诡异之处
3. 结尾钩子：图鉴翻到最后一页，有人用血写着"沈夜，观世妖宿主"。

风格：悬疑，伏笔铺垫"""
    },
    {
        "chapter_num": 4,
        "title": "兵部灭门案",
        "task": """【第4章：兵部灭门案】

第一个任务：兵部尚书满门被杀，现场无凶器无血迹，死者脸上都带着诡异的微笑。

沈夜仔细勘察现场，发现死者瞳孔里映着同一个画面——一面铜镜。

要求：
1. 描写案发现场的诡异景象
2. 描写沈夜的推理过程
3. 结尾钩子：那画面是一面铜镜，镜中映着沈夜自己的脸。

风格：悬疑推理，层层递进"""
    },
    {
        "chapter_num": 5,
        "title": "圣贤书推理",
        "task": """【第5章：圣贤书推理】

沈夜以《礼记》"视于无形"推理：妖物藏身镜中。

他让人搬来所有铜镜，发现其中一面映不出人影。镜妖现身，化作狰狞的怪物扑向沈夜。

小高潮：沈夜翻开《论语》，念出"非礼勿视"四字，金光闪耀，镜妖尖叫碎裂。

要求：
1. 描写沈夜与镜妖的对决
2. 描写圣贤书的力量
3. 结尾钩子：镜妖尸体里掉出一枚黑色妖核，刻着编号"柒叁"。

风格：动作场面，高潮迭起"""
    }
]

# 批量生成章节
for chapter in chapters:
    print(f"\n{'='*60}")
    print(f"正在生成第{chapter['chapter_num']}章：{chapter['title']}")
    print(f"{'='*60}")
    
    prompt = f"""
你是一位资深的网络小说作家，擅长写古风悬疑和玄幻题材。请按照以下要求生成章节：

{chapter['task']}

字数要求：约2000字
语言风格：古风，简练有力，符合武侠/玄幻小说风格
结构要求：有场景描写，有对话，有情节推进
"""
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一位资深的网络小说作家，擅长写古风悬疑和玄幻题材。你的文字风格简练有力，情节紧凑，善于制造悬念和伏笔。"},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 2500,
        "temperature": 0.7
    }
    
    response = requests.post(
        f"{api_base}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=180
    )
    
    if response.status_code == 200:
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        # 保存章节
        file_path = f"{project_dir}\\正文\\第{chapter['chapter_num']}章_{chapter['title']}.txt"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✓ 第{chapter['chapter_num']}章生成成功！")
        print(f"  文件: {file_path}")
        print(f"\n  预览:\n{content[:300]}...")
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

for i, ch in enumerate(chapters, 1):
    state["chapters"][str(i)] = {
        "title": ch["title"],
        "file": f"正文/第{i}章_{ch['title']}.txt",
        "status": "completed"
    }

with open(state_file, 'w', encoding='utf-8') as f:
    json.dump(state, f, ensure_ascii=False, indent=2)

print(f"\n项目状态已更新: {state_file}")