#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古写作系统 v2.0 - 基于V7.5核心精简版
核心功能：
- 12种创作模式
- 四大平台配置
- 五车间流水线
- 素材库生成
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
MODES_DIR = BASE_DIR / "modes"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
WORKSHOPS_DIR = BASE_DIR / "workshops"
PROJECTS_DIR = BASE_DIR / "projects"
PROJECTS_DIR.mkdir(exist_ok=True)

def print_banner():
    print("""
======================================================
               盘古写作系统 v2.0                     
           基于V7.5核心，精简实用版                     
======================================================
    """)

def list_modes():
    """列出所有可用的创作模式"""
    mode_files = sorted(MODES_DIR.glob("*.json"))
    print("\n可用创作模式:")
    print("=======================================")
    for i, mode_file in enumerate(mode_files, 1):
        mode_data = json.loads(mode_file.read_text(encoding='utf-8'))
        print(f"  {i:2d}. {mode_data.get('name', mode_file.stem):20s} - {mode_data.get('description', '')[:50]}...")
    print(f"\n共 {len(mode_files)} 种模式\n")
    return mode_files

def load_platform_configs():
    """加载平台配置"""
    config_file = KNOWLEDGE_DIR / "platform_writing_profiles.json"
    if config_file.exists():
        return json.loads(config_file.read_text(encoding='utf-8'))
    return {}

def create_project():
    """创建新项目"""
    print("\n创建新项目")
    print("=======================================")
    
    title = input("书名: ").strip()
    if not title:
        print("书名不能为空！")
        return None
    
    print("\n选择平台:")
    platforms = ["fanqie", "qidian", "qimao", "jinjiang"]
    for i, p in enumerate(platforms, 1):
        print(f"  {i}. {p}")
    platform_choice = input("平台 (1-4, 默认1): ").strip() or "1"
    platform = platforms[int(platform_choice)-1]
    
    mode_files = list_modes()
    mode_choice = input("选择模式 (1-N, 默认1): ").strip() or "1"
    mode_file = mode_files[int(mode_choice)-1]
    mode = mode_file.stem
    
    words = input("目标字数 (默认30000): ").strip() or "30000"
    chapters = input("目标章节数 (默认20): ").strip() or "20"
    
    # 创建项目目录
    project_slug = title.replace(" ", "_").replace("/", "_")
    project_dir = PROJECTS_DIR / project_slug
    project_dir.mkdir(exist_ok=True)
    (project_dir / "大纲").mkdir(exist_ok=True)
    (project_dir / "正文").mkdir(exist_ok=True)
    (project_dir / "设定集").mkdir(exist_ok=True)
    
    # 创建state.json
    state = {
        "project_info": {
            "title": title,
            "genre": mode,
            "platform": platform,
            "target_words": int(words),
            "target_chapters": int(chapters),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "progress": {"current_chapter": 0, "total_words": 0},
        "chapter_meta": {}
    }
    
    with open(project_dir / "state.json", 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    
    # 创建大纲模板
    outline_template = f"""# {title} 总大纲

## 一句话核心概念
[填写一句话概括你的小说]

## 核心卖点
1. [卖点1]
2. [卖点2]
3. [卖点3]

## 主要人物
### 主角
- 姓名: [名字]
- 核心创伤/执念: [填写]
- 核心目标: [填写]

### 反派
- 姓名: [名字]
- 核心动机: [填写]
- 与主角的冲突点: [填写]

## 章节规划
"""
    with open(project_dir / "大纲" / "总大纲.md", 'w', encoding='utf-8') as f:
        f.write(outline_template)
    
    print(f"\n项目创建成功！")
    print(f"  路径: {project_dir}")
    print(f"  书名: {title}")
    print(f"  模式: {mode}")
    print(f"  平台: {platform}")
    return project_dir

def write_chapter(project_dir):
    """写新章节"""
    state_file = project_dir / "state.json"
    if not state_file.exists():
        print("不是有效的项目目录！")
        return
    
    state = json.loads(state_file.read_text(encoding='utf-8'))
    current_chapter = state["progress"]["current_chapter"] + 1
    
    print(f"\n准备写第 {current_chapter} 章")
    print("=======================================")
    
    chapter_task = input("\n这章要写什么? 简要描述: ").strip()
    word_count = input("目标字数 (默认3000): ").strip() or "3000"
    
    mode = state["project_info"]["genre"]
    platform = state["project_info"]["platform"]
    
    # 加载模式配置
    mode_config = {}
    mode_file = MODES_DIR / f"{mode}.json"
    if mode_file.exists():
        mode_config = json.loads(mode_file.read_text(encoding='utf-8'))
    
    # 加载平台配置
    platform_configs = load_platform_configs()
    platform_config = platform_configs.get("profiles", {}).get(platform, {})
    
    print(f"\n配置信息:")
    print(f"  模式: {mode_config.get('name', mode)}")
    print(f"  平台: {platform_config.get('name', platform)}")
    print(f"  任务: {chapter_task}")
    print(f"  字数: {word_count}")
    
    print("""
提示：
当前使用模拟模式（未配置LLM API Key）
你可以：
1. 直接根据提示手动写
2. 或者复制下面的提示词给AI（Claude/DeepSeek等）

提示词模板：
""")
    
    # 生成完整的写作提示词
    w1_prompt_path = WORKSHOPS_DIR / "workshop_1_setup" / "system_prompt.txt"
    w1_prompt = w1_prompt_path.read_text(encoding='utf-8') if w1_prompt_path.exists() else "设定预处理"
    
    w2_prompt_path = WORKSHOPS_DIR / "workshop_2_draft" / "system_prompt.txt"
    w2_prompt = w2_prompt_path.read_text(encoding='utf-8') if w2_prompt_path.exists() else "正文初稿"
    
    prompt = f"""# 写作任务

## 书名
{state["project_info"]["title"]}

## 本章任务
{chapter_task}

## 创作模式
{json.dumps(mode_config, ensure_ascii=False, indent=2)}

## 平台要求
{json.dumps(platform_config, ensure_ascii=False, indent=2)}

## 字数要求
{word_count} 字

## 请按照五车间流程写：
1. 先设定本章的核心设定
2. 写正文初稿
3. 质检逻辑
4. 精修文笔

---
请直接输出正文！
"""
    
    print(prompt)
    
    print("\n或者你可以手动写，写好后保存到项目目录的 正文/ 文件夹")
    
    # 更新状态
    state["progress"]["current_chapter"] = current_chapter
    state["chapter_meta"][f"chapter_{current_chapter}"] = {
        "task": chapter_task,
        "target_words": int(word_count),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def generate_library_template():
    """生成三库模板"""
    print("\n生成三库模板")
    print("=======================================")
    
    title = input("项目/小说名: ").strip()
    if not title:
        print("项目名不能为空！")
        return
    
    lib_dir = PROJECTS_DIR / title.replace(" ", "_") / "三库"
    lib_dir.mkdir(exist_ok=True, parents=True)
    
    character_atlas = {
        "characters": [
            {
                "name": "[主角名]",
                "role": "protagonist",
                "native_trauma": "[原生创伤]",
                "obsession": "[执念/核心驱动力]",
                "bottom_line": "[底线]",
                "hidden_quirk": "[隐性怪癖]",
                "growth_arc": "初登场 -> 中期蜕变 -> 结局蜕变"
            },
            {
                "name": "[反派名]",
                "role": "antagonist",
                "motivation": "[核心动机]",
                "conflict_point": "[与主角的核心冲突]"
            }
        ]
    }
    
    event_plot_atlas = {
        "unit_events": [
            "[事件1 - 表面冲突 + 深层隐藏 + 触发人物内核 + 反常识设定]"
        ],
        "foreshadowing_threads": [
            "[伏笔线1]"
        ]
    }
    
    exclusive_materials = {
        "world_settings": [
            "[世界观设定1 - 小众地理/奇特法则/特殊文明]"
        ],
        "items": [
            "[道具/能力1 - 有副作用/有故事]"
        ],
        "environment": [
            "[环境1 - 有情绪功能]"
        ],
        "anti_routine": [
            "[反套路转折素材]"
        ]
    }
    
    with open(lib_dir / "character_atlas.json", 'w', encoding='utf-8') as f:
        json.dump(character_atlas, f, ensure_ascii=False, indent=2)
    
    with open(lib_dir / "event_plot_atlas.json", 'w', encoding='utf-8') as f:
        json.dump(event_plot_atlas, f, ensure_ascii=False, indent=2)
    
    with open(lib_dir / "exclusive_materials.json", 'w', encoding='utf-8') as f:
        json.dump(exclusive_materials, f, ensure_ascii=False, indent=2)
    
    print(f"\n三库模板已生成！")
    print(f"  路径: {lib_dir}")

def check_project(project_dir):
    """检查项目状态"""
    state_file = project_dir / "state.json"
    if not state_file.exists():
        print("不是有效的项目目录！")
        return
    
    state = json.loads(state_file.read_text(encoding='utf-8'))
    info = state.get("project_info", {})
    progress = state.get("progress", {})
    
    print("\n项目状态")
    print("=======================================")
    print(f"  书名: {info.get('title', 'N/A')}")
    print(f"  模式: {info.get('genre', 'N/A')}")
    print(f"  平台: {info.get('platform', 'N/A')}")
    print(f"  进度: 第 {progress.get('current_chapter', 0)} 章 / {info.get('target_chapters', '?')}")
    print(f"  字数: {progress.get('total_words', 0)} / {info.get('target_words', '?')}")
    print(f"  创建: {info.get('created_at', 'N/A')}")

def show_help():
    print("""
盘古写作系统 v2.0 - 使用帮助

命令列表:
  pangu.py new                - 创建新项目
  pangu.py list               - 列出所有创作模式
  pangu.py write <项目名>     - 写新章节
  pangu.py status <项目名>    - 查看项目状态
  pangu.py library <项目名>   - 生成三库模板
  pangu.py platforms          - 列出平台配置
  pangu.py help               - 显示帮助

快速开始:
  1. 先运行 pangu.py new 创建项目
  2. 再运行 pangu.py write <项目名> 写章节

创作模式:
  - general          - 通用网文
  - healing_life     - 治愈生活流
  - urban_power      - 都市职业异能
  - female_solo      - 无CP大女主
  - history_scholar  - 历史考据流
  - folk_horror      - 中式民俗悬疑
  - rule_mystery     - 规则怪谈
  - romance          - 言情
  - crazy_lit        - 发疯文学
  - reality_revenge  - 现实复仇
  - retro_life       - 年代文
""")

def main():
    print_banner()
    
    if len(sys.argv) < 2:
        show_help()
        return
    
    cmd = sys.argv[1].lower()
    
    if cmd == "new" or cmd == "init":
        create_project()
    elif cmd == "list" or cmd == "modes":
        list_modes()
    elif cmd == "write":
        if len(sys.argv) < 3:
            print("请提供项目名！")
            print("用法: pangu.py write <项目名>")
        else:
            project_name = sys.argv[2]
            project_dir = PROJECTS_DIR / project_name.replace(" ", "_")
            if project_dir.exists():
                write_chapter(project_dir)
            else:
                print(f"项目 '{project_name}' 不存在！")
    elif cmd == "status":
        if len(sys.argv) < 3:
            print("请提供项目名！")
        else:
            project_name = sys.argv[2]
            project_dir = PROJECTS_DIR / project_name.replace(" ", "_")
            check_project(project_dir)
    elif cmd == "library":
        generate_library_template()
    elif cmd == "platforms":
        configs = load_platform_configs()
        print("\n平台配置:")
        print("=======================================")
        for p_key, p_data in configs.get("profiles", {}).items():
            print(f"  {p_data.get('name', p_key):15s} - {p_data.get('core_logic', '')}")
    elif cmd == "help" or cmd == "-h" or cmd == "--help":
        show_help()
    else:
        print(f"未知命令: {cmd}")
        show_help()

if __name__ == "__main__":
    main()
