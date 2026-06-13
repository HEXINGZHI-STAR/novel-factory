#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json

def load_project(project_name):
    """加载项目信息"""
    project_dir = os.path.join("projects", project_name)
    if not os.path.exists(project_dir):
        print(f"错误：项目 {project_name} 不存在")
        return None
    
    # 读取大纲
    outline_path = os.path.join(project_dir, "大纲", "总大纲.md")
    if os.path.exists(outline_path):
        with open(outline_path, 'r', encoding='utf-8') as f:
            outline = f.read()
    else:
        outline = ""
    
    # 读取状态
    state_path = os.path.join(project_dir, "state.json")
    if os.path.exists(state_path):
        with open(state_path, 'r', encoding='utf-8') as f:
            state = json.load(f)
    else:
        state = {"chapters": {}, "current_chapter": 5}
    
    return {
        "dir": project_dir,
        "name": project_name,
        "outline": outline,
        "state": state
    }

def extract_chapter_outline(outline, chapter_num):
    """从大纲中提取指定章节的大纲"""
    lines = outline.split('\n')
    chapter_lines = []
    capture = False
    
    for i, line in enumerate(lines):
        if f"## 第{chapter_num}章" in line:
            capture = True
            chapter_lines.append(line)
        elif capture and line.startswith('## ') and f"第{chapter_num}章" not in line:
            break
        elif capture:
            chapter_lines.append(line)
    
    return '\n'.join(chapter_lines)

def workshop_pipeline(project, chapter_num, chapter_title, chapter_task):
    """五车间流水线处理"""
    print(f"\n{'='*60}")
    print(f"五车间流水线 - 第{chapter_num}章: {chapter_title}")
    print(f"{'='*60}")
    
    # W0 主旨锚定
    print("\n[W0] 主旨锚定...")
    print(f"任务: {chapter_task}")
    theme = f"第{chapter_num}章《{chapter_title}》核心主旨：{chapter_task}"
    print(f"主旨锁定: {theme}")
    
    # W1 设定预处理
    print("\n[W1] 设定预处理...")
    setting = f"""
【世界观】大燕王朝，妖物横行，镇妖司负责斩妖除魔
【主角】沈夜 - 新科状元，右眼能看见妖的弱点
【女主】苏青棠 - 镇妖司司主，断臂，脸上有妖爪疤痕
【反派】魏忠 - 司礼监掌印太监，妖核黑市主人
【场景】第{chapter_num}章主要场景
【冲突】主角与反派的矛盾激化
    """.strip()
    print("设定加载完成")
    
    # W2 正文初稿
    print("\n[W2] 正文初稿生成...")
    
    # 根据任务生成初稿
    chapter_content = generate_chapter(chapter_num, chapter_title, chapter_task, setting)
    print("初稿生成完成")
    
    # W3 逻辑质检
    print("\n[W3] 逻辑质检...")
    issues = []
    
    # 检查字数
    word_count = len(chapter_content.replace('\n', ''))
    if word_count < 1500:
        issues.append(f"警告：字数不足 ({word_count}字)")
    else:
        print(f"✓ 字数达标: {word_count}字")
    
    # 检查钩子
    if "（本章完）" not in chapter_content:
        issues.append("警告：缺少章节结尾钩子")
    else:
        print("✓ 章节结尾钩子存在")
    
    # 检查人物一致性
    if "沈夜" not in chapter_content:
        issues.append("警告：主角沈夜未出现")
    else:
        print("✓ 主角沈夜出场")
    
    if issues:
        print("\n⚠️ 发现问题:")
        for issue in issues:
            print(f"  - {issue}")
        print("需要人工审核修正")
    else:
        print("\n✓ 逻辑质检通过")
    
    # W4 文笔精修
    print("\n[W4] 文笔精修...")
    refined_content = refine_writing(chapter_content)
    print("文笔精修完成")
    
    # 保存章节
    save_chapter(project, chapter_num, chapter_title, refined_content)
    
    # 更新状态
    update_state(project, chapter_num)
    
    print(f"\n🎉 第{chapter_num}章《{chapter_title}》生成完成！")
    return refined_content

def generate_chapter(chapter_num, chapter_title, chapter_task, setting):
    """根据任务生成章节内容"""
    outlines = {
        6: {
            "title": "妖