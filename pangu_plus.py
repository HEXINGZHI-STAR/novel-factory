#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古参考库浏览器 (Database Browser)

定位: 4,466本参考书的浏览/搜索/分析工具。不是写作入口。
写作入口: pangu_workshop.py / pangu_workshop_smart.py

主要功能:
  - 按题材/平台/评分浏览参考书
  - 查看书籍章节和分析结果
  - 生成参考提示词
  - 数据库统计
"""

import os
import sys
import json
import time
import re
from pathlib import Path
from datetime import datetime

# 尝试导入requests
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# 尝试导入dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 添加knowledge目录到路径
sys.path.insert(0, str(Path(__file__).parent / 'knowledge'))
try:
    from db_manager import NovelReferenceDB
    from chapter_analyzer import ChapterAnalyzer
    from reference_prompt import ReferencePromptGenerator
except ImportError:
    print("警告：未找到模块，部分功能将不可用")
    NovelReferenceDB = None
    ChapterAnalyzer = None
    ReferencePromptGenerator = None

BASE_DIR = Path(__file__).resolve().parent
MODES_DIR = BASE_DIR / "modes"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
WORKSHOPS_DIR = BASE_DIR / "workshops"
PROJECTS_DIR = BASE_DIR / "projects"
CONFIG_FILE = BASE_DIR / ".env"
PROJECTS_DIR.mkdir(exist_ok=True)


def load_config():
    """加载配置"""
    config = {
        "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
        "base_url": os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1"),
        "model": os.getenv("AI_MODEL", "deepseek-chat"),
        "temperature": 0.7,
        "max_tokens": 4000,
        "timeout": 120,
        "retry_times": 3,
    }
    
    if not config["api_key"]:
        print("⚠️  警告: 未设置 DEEPSEEK_API_KEY 环境变量")
        print("   Windows 命令行: set DEEPSEEK_API_KEY=你的key")
        print("   PowerShell: $env:DEEPSEEK_API_KEY='你的key'")
        print("   或者在 .env 文件中设置")
    
    return config


CONFIG = load_config()


def print_banner():
    print("""
====================================================================
                      盘古写作系统 Plus
              基于V7.5核心 + 146本经典参考库
====================================================================
    """)


def init_db():
    """初始化数据库连接"""
    if NovelReferenceDB is None:
        return None
    try:
        db = NovelReferenceDB()
        return db
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None


def show_db_stats():
    """显示数据库统计"""
    db = init_db()
    if db is None:
        return
    
    stats = db.get_stats()
    print("\n" + "="*60)
    print("参考库统计")
    print("="*60)
    print(f"  总书籍数: {stats['total_books']} 本")
    print(f"  参考书籍: {stats['reference_books']} 本")
    print(f"  总章节数: {stats['total_chapters']} 章")
    
    if stats.get('by_genre'):
        print("\n  按题材分布:")
        for genre, cnt in stats['by_genre'].items():
            if genre:
                print(f"    - {genre}: {cnt} 本")
    
    print("="*60)


def list_modes():
    """列出所有可用的创作模式"""
    mode_files = sorted(MODES_DIR.glob("*.json"))
    print("\n可用创作模式:")
    print("="*60)
    for i, mode_file in enumerate(mode_files, 1):
        try:
            mode_data = json.loads(mode_file.read_text(encoding='utf-8'))
            name = mode_data.get('name', mode_file.stem)
            desc = mode_data.get('description', '')
            print(f"  {i:2d}. {name:25s}")
            if desc:
                print(f"      {desc[:60]}...")
        except:
            print(f"  {i:2d}. {mode_file.stem}")
    print(f"\n共 {len(mode_files)} 种模式")
    return mode_files


def search_reference_books():
    """搜索参考小说"""
    db = init_db()
    if db is None:
        print("数据库不可用")
        return
    
    print("\n搜索参考小说")
    print("="*60)
    
    print("\n请选择:")
    print("  1. 按题材查找")
    print("  2. 按平台查找")
    print("  3. 列出所有有章节的参考小说")
    print("  4. 随机推荐3本")
    
    choice = input("\n请选择 (1-4, 直接回车返回): ").strip()
    
    if not choice:
        return
    
    if choice == '1':
        print("\n可选题材:")
        books = db.list_books(only_reference=True)
        genres = set(b['genre'] for b in books if b['genre'])
        for i, genre in enumerate(sorted(genres), 1):
            print(f"  {i}. {genre}")
        genre_choice = input("\n选择题材编号: ").strip()
        if genre_choice.isdigit():
            genre_list = sorted(genres)
            if 1 <= int(genre_choice) <= len(genre_list):
                display_books_by_genre(db, genre_list[int(genre_choice)-1])
    
    elif choice == '2':
        display_books_by_platform(db)
    
    elif choice == '3':
        display_books_with_chapters(db)
    
    elif choice == '4':
        display_random_recommendations(db)


def display_books_by_genre(db, genre):
    """按题材显示书籍"""
    print(f"\n{genre} 题材参考小说:")
    print("="*60)
    books = db.list_books(genre=genre, only_reference=True)
    
    for i, book in enumerate(books[:15], 1):
        chapters = db.get_chapters(book['id'])
        has_content = len(chapters) > 0
        status = "[OK]" if has_content else "[--]"
        print(f"  {status} {book['id']:3d}. {book['title']}")
        print(f"      作者: {book['author'] or '未知'}")
        
        if has_content:
            print(f"      章节数: {len(chapters)}")
            total_words = sum(c['word_count'] or 0 for c in chapters)
            print(f"      总字数: {total_words:,} 字")
        print()


def display_books_by_platform(db):
    """按平台显示书籍"""
    stats = db.get_stats()
    print("\n按平台:")
    if stats.get('by_platform'):
        for i, (platform, cnt) in enumerate(stats['by_platform'].items(), 1):
            print(f"  {i}. {platform} ({cnt}本)")


def display_books_with_chapters(db):
    """显示有章节的书籍"""
    books = db.list_books(only_reference=True)
    print("\n有章节内容的参考小说:")
    print("="*60)
    count = 0
    for book in books:
        chapters = db.get_chapters(book['id'])
        if chapters:
            count += 1
            total_words = sum(c['word_count'] or 0 for c in chapters)
            print(f"  {count:2d}. {book['title']}")
            print(f"      作者: {book['author'] or '未知'}")
            print(f"      题材: {book['genre'] or '未知'}")
            print(f"      章节: {len(chapters)}章 / {total_words:,}字\n")
    
    if count == 0:
        print("  暂无比对完整内容的小说")


def display_random_recommendations(db):
    """随机推荐书籍"""
    import random
    books = db.list_books(only_reference=True)
    books_with_content = [b for b in books if db.get_chapters(b['id'])]
    
    if not books_with_content:
        print("  暂无可推荐的书籍")
        return
    
    print("\n随机推荐:")
    print("="*60)
    recommendations = random.sample(books_with_content, min(3, len(books_with_content)))
    
    for book in recommendations:
        chapters = db.get_chapters(book['id'])
        total_words = sum(c['word_count'] or 0 for c in chapters)
        print(f"\n{book['title']}")
        print(f"   作者: {book['author'] or '未知'}")
        print(f"   题材: {book['genre'] or '未知'}")
        print(f"   字数: {total_words:,} 字")
        
        if chapters:
            first_chapter = chapters[0]
            preview = first_chapter['content'][:100] if first_chapter['content'] else ""
            print(f"\n   开篇预览:")
            print(f"   {'-'*50}")
            print(f"   {preview}...")


def analyze_chapter(db, book_id, chapter_idx):
    """分析指定章节"""
    book = db.get_book(book_id)
    chapters = db.get_chapters(book_id)
    
    if not chapters or chapter_idx < 0 or chapter_idx >= len(chapters):
        print("无效的章节索引")
        return
    
    chap = chapters[chapter_idx]
    chapter_title = chap.get('title', f"第{chap['chapter_num']}章")
    chapter_content = chap.get('content', '')
    
    if not chapter_content:
        print("该章节无内容可分析")
        return
    
    if ChapterAnalyzer is None:
        print("分析器不可用")
        return
    
    analyzer = ChapterAnalyzer()
    analysis = analyzer.full_analysis(chapter_content, book.get('title', ''), chapter_title)
    report = analyzer.generate_analysis_report(analysis)
    print(report)


def generate_reference_prompt(db, book_id, chapter_idx=0, mode_name="通用", platform="番茄"):
    """生成参考提示词"""
    book = db.get_book(book_id)
    chapters = db.get_chapters(book_id)
    
    if not chapters or chapter_idx < 0 or chapter_idx >= len(chapters):
        print("无效的章节索引")
        return
    
    chap = chapters[chapter_idx]
    chapter_content = chap.get('content', '')
    
    if not chapter_content:
        print("该章节无内容")
        return
    
    if ReferencePromptGenerator is None:
        print("提示词生成器不可用")
        return
    
    generator = ReferencePromptGenerator()
    prompt = generator.generate_full_prompt(
        book_title=book.get('title', ''),
        genre=book.get('genre', ''),
        author=book.get('author', ''),
        chapter_content=chapter_content,
        mode_name=mode_name,
        platform=platform
    )
    
    print("="*70)
    print("📝 生成的写作提示词")
    print("="*70)
    print(prompt)
    print("="*70)
    
    return prompt


def view_reference_book():
    """查看参考小说内容"""
    db = init_db()
    if db is None:
        print("数据库不可用")
        return
    
    book_id = input("\n请输入参考小说ID (输入0返回): ").strip()
    if not book_id or book_id == '0':
        return
    
    try:
        book_id = int(book_id)
    except:
        print("无效的ID")
        return
    
    book = db.get_book(book_id)
    if not book:
        print(f"找不到ID为 {book_id} 的小说")
        return
    
    chapters = db.get_chapters(book_id)
    
    print(f"\n{'='*60}")
    print(f"{book['title']}")
    print(f"{'='*60}")
    print(f"作者: {book['author'] or '未知'}")
    print(f"题材: {book['genre'] or '未知'}")
    print(f"平台: {book['platform'] or '未知'}")
    if chapters:
        total_words = sum(c['word_count'] or 0 for c in chapters)
        print(f"章节: {len(chapters)} 章 / {total_words:,} 字")
    print(f"{'='*60}")
    
    if chapters:
        print("\n章节列表:")
        for i, chap in enumerate(chapters, 1):
            title = chap.get('title')
            if not title:
                title = f"第{chap['chapter_num']}章"
            print(f"  {i}. {title}")
        
        print("\n请选择:")
        print("  [章节编号] - 查看该章节内容")
        print("  A [章节编号] - 分析该章节")
        print("  0 - 返回")
        
        choice = input("\n请选择: ").strip()
        if choice == '0':
            return
        
        # 分析模式
        if choice.upper().startswith('A'):
            parts = choice[1:].strip()
            if not parts:
                # 直接A，分析第1章
                idx = 0
            else:
                try:
                    idx = int(parts) - 1
                except:
                    print("无效选择")
                    return
            
            if idx < 0 or idx >= len(chapters):
                print("无效选择")
                return
            
            analyze_chapter(db, book_id, idx)
            return
        
        # 查看内容模式
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(chapters):
                print("无效选择")
                return
        except:
            print("无效选择")
            return
        
        chap = chapters[idx]
        print(f"\n{'='*60}")
        title = chap.get('title')
        if not title:
            title = f"第{chap['chapter_num']}章"
        print(f"{title}")
        print(f"{'='*60}")
        if chap.get('content'):
            print(chap['content'])
        else:
            print("  (无内容)")
        print(f"\n{'='*60}")
        
        # 询问是否分析
        analyze_choice = input("\n是否分析该章节? (y/n, 默认n): ").strip().lower()
        if analyze_choice == 'y':
            analyze_chapter(db, book_id, idx)


def generate_outline_ai(title, concept, mode, platform, target_chapters, reference_info=""):
    """用AI生成大纲"""
    prompt = f"""你是一位专业的网文创作助手。请根据以下信息，生成一份完整的小说大纲。

# 书名
{title}

# 一句话核心概念
{concept}

# 创作模式
{mode}

# 发布平台
{platform}

# 目标章节数
{target_chapters}章（每章约2000字）

{reference_info}

请按以下格式输出，只输出Markdown内容，不要其他文字：

# {title} 总大纲

## 一句话核心概念
（重复或提炼）

## 核心卖点
1. 
2. 
3. 

## 主要人物
### 主角
- 姓名: 
- 性格: 
- 核心目标: 
- 核心创伤/执念: 

### 关键配角
- 角色名: 简要描述
- 角色名: 简要描述

{reference_info}

## 详细章节规划（每章2000字）

逐章规划，包括：
- 第1章: 开篇钩子，主要人物登场，第一个冲突/悬念
- 第2章: 
- 第3章: 
...
- 第{target_chapters}章: 高潮+收尾

每章请写清楚本章的核心任务、主要事件、钩子/爽点。
"""
    
    return call_ai(prompt)


def create_project():
    """创建新项目"""
    print("\n创建新项目")
    print("="*60)
    
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
    mode_choice = input("\n选择模式 (1-N, 默认1): ").strip() or "1"
    mode_file = mode_files[int(mode_choice)-1]
    mode = mode_file.stem
    
    # 选择小说类型
    print("\n选择小说类型:")
    print("  1. 短篇 (3-10章，约6000-20000字)")
    print("  2. 中篇 (10-30章，约20000-60000字)")
    print("  3. 长篇 (30章以上，约60000字+)")
    type_choice = input("类型 (1-3, 默认2中篇): ").strip() or "2"
    
    if type_choice == '1':
        default_words = 10000
        default_chapters = 5
        type_name = "短篇"
    elif type_choice == '3':
        default_words = 100000
        default_chapters = 50
        type_name = "长篇"
    else:
        default_words = 40000
        default_chapters = 20
        type_name = "中篇"
    
    print(f"\n你选择了: {type_name}小说")
    print(f"  推荐字数: {default_words}字")
    print(f"  推荐章节: {default_chapters}章 (每章2000字)")
    
    words = input(f"\n目标总字数 (默认{default_words}): ").strip() or str(default_words)
    chapters = input(f"目标章节数 (默认{default_chapters}): ").strip() or str(default_chapters)
    
    # 一句话简介（用于AI生成大纲）
    concept = input("\n一句话简介（AI生成大纲用）: ").strip()
    
    # 选择参考小说
    ref_ids = []
    ref_choice = input("\n是否选择参考小说? (y/n, 默认y): ").strip().lower()
    if ref_choice != 'n':
        db = init_db()
        if db:
            print("\n以下是有完整章节内容的参考小说（推荐选择同题材的）:")
            books = db.list_books(only_reference=True)
            valid_books = []
            for book in books:
                chaps = db.get_chapters(book['id'])
                if chaps and chaps[0].get('content', ''):
                    valid_books.append(book)
            
            if valid_books:
                for i, book in enumerate(valid_books[:20], 1):
                    print(f"  {i}. [{book['id']}] {book['title'][:40]} ({book.get('genre', 'N/A')})")
                
                print("\n选择方式:")
                print("  - 输入单个ID (如 774)")
                print("  - 输入多个ID用逗号分隔 (如 774,775,776)")
                print("  - 直接回车跳过")
                
                ref_input = input("选择参考小说ID: ").strip()
                if ref_input:
                    try:
                        ref_ids = [int(x.strip()) for x in ref_input.replace('，', ',').split(',') if x.strip()]
                    except:
                        print("输入格式有误，跳过参考")
    
    # 创建项目目录
    project_slug = title.replace(" ", "_").replace("/", "_")
    project_dir = PROJECTS_DIR / project_slug
    project_dir.mkdir(exist_ok=True)
    (project_dir / "大纲").mkdir(exist_ok=True)
    (project_dir / "正文").mkdir(exist_ok=True)
    (project_dir / "设定集").mkdir(exist_ok=True)
    
    # 生成参考分析（如果选了参考）
    reference_info = ""
    if ref_ids:
        db = init_db()
        if db:
            print("\n正在分析参考小说...")
            ref_books = []
            for rid in ref_ids:
                book = db.get_book(rid)
                if book:
                    chaps = db.get_chapters(rid)
                    if chaps and chaps[0].get('content', ''):
                        ref_books.append(book)
            
            if ref_books:
                reference_info = "## 参考书目分析\n\n"
                for book in ref_books:
                    reference_info += f"- {book['title']} ({book.get('author', 'N/A')})\n"
                
                # 分析第一本的章节
                book = ref_books[0]
                chaps = db.get_chapters(book['id'])
                if ChapterAnalyzer:
                    content = chaps[0].get('content', '')
                    analyzer = ChapterAnalyzer()
                    analysis = analyzer.full_analysis(content, book['title'])
                    hooks = analysis.get('hooks', [])
                    if hooks:
                        reference_info += "\n### 参考作品钩子类型:\n"
                        for h in hooks[:5]:
                            reference_info += f"- {h['type']} ({h['count']}次)\n"
                
                reference_info += "\n"
    
    # 创建state.json
    state = {
        "project_info": {
            "title": title,
            "type": type_name,
            "genre": mode,
            "platform": platform,
            "target_words": int(words),
            "target_chapters": int(chapters),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "progress": {"current_chapter": 0, "total_words": 0},
        "chapter_meta": {},
        "references": ref_ids
    }
    
    with open(project_dir / "state.json", 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    
    # 询问是否用AI生成大纲
    outline = ""
    if concept:
        use_ai_outline = input("\n是否用AI生成大纲? (y/n, 默认y): ").strip().lower()
        if use_ai_outline != 'n':
            print("\n正在生成大纲...")
            ai_outline = generate_outline_ai(title, concept, mode, platform, int(chapters), reference_info)
            if ai_outline:
                outline = ai_outline
                print("大纲生成成功！")
    
    # 如果没有AI大纲，用模板
    if not outline:
        chapter_plan = ""
        for i in range(1, int(chapters)+1):
            chapter_plan += f"{i}. 第{i}章: [本章任务]\n"
        
        outline = f"""# {title} 总大纲

## 一句话核心概念
{concept or '[填写一句话概括你的小说]'}

## 核心卖点
1. [卖点1]
2. [卖点2]
3. [卖点3]

## 主要人物
### 主角
- 姓名: [名字]
- 核心创伤/执念: [填写]
- 核心目标: [填写]

### 关键配角
- [角色名]: [简要描述]
- [角色名]: [简要描述]

{reference_info}

## 章节规划（每章约2000字）
{chapter_plan}
"""
    
    with open(project_dir / "大纲" / "总大纲.md", 'w', encoding='utf-8') as f:
        f.write(outline)
    
    # 生成每章的提示词准备
    chapter_plan_file = project_dir / "大纲" / "章节规划.md"
    with open(chapter_plan_file, 'w', encoding='utf-8') as f:
        f.write(f"# {title} 章节规划\n\n")
        for i in range(1, int(chapters)+1):
            f.write(f"## 第{i}章\n")
            f.write(f"- 任务: [填写本章内容]\n")
            f.write(f"- 要点: [填写本章钩子/爽点]\n\n")
    
    print(f"\n项目创建成功！")
    print(f"  路径: {project_dir}")
    print(f"  书名: {title}")
    print(f"  类型: {type_name}")
    print(f"  模式: {mode}")
    print(f"  平台: {platform}")
    print(f"  目标字数: {words}")
    print(f"  目标章节: {chapters}")
    print(f"  参考小说: {len(ref_ids)} 本")
    print(f"\n已生成文件:")
    print(f"  - 大纲/总大纲.md")
    print(f"  - 大纲/章节规划.md")
    print(f"\n请先完成大纲，再开始写章节！")
    
    return project_dir


def get_previous_chapters(project_dir, current_chapter, max_chapters=2):
    """读取前面的章节，作为上下文"""
    content_dir = project_dir / "正文"
    if not content_dir.exists():
        return ""
    
    prev_chapters = []
    # 从当前章往前读
    for ch_num in range(max(1, current_chapter - max_chapters), current_chapter):
        # 找第 ch_num 章的文件
        possible_files = list(content_dir.glob(f"第{ch_num}章*.txt"))
        if possible_files:
            try:
                content = possible_files[0].read_text(encoding='utf-8')
                prev_chapters.append((ch_num, content))
            except Exception:
                pass
    
    if not prev_chapters:
        return ""
    
    result = "## 前面的章节（上下文参考）\n\n"
    for ch_num, content in prev_chapters:
        result += f"### 第{ch_num}章\n\n"
        # 只取前1500字，避免太长
        result += content[:1500]
        if len(content) > 1500:
            result += "\n...（本章内容较长，只显示前1500字）"
        result += "\n\n"
    
    return result


def write_chapter(project_dir):
    """写新章节"""
    state_file = project_dir / "state.json"
    if not state_file.exists():
        print("不是有效的项目目录！")
        return
    
    state = json.loads(state_file.read_text(encoding='utf-8'))
    current_chapter = state["progress"]["current_chapter"] + 1
    
    print(f"\n准备写第 {current_chapter} 章")
    print("="*60)
    
    # 读取章节规划
    chapter_plan_file = project_dir / "大纲" / "章节规划.md"
    planned_task = ""
    if chapter_plan_file.exists():
        content = chapter_plan_file.read_text(encoding='utf-8')
        # 找当前章节
        section_head = f"## 第{current_chapter}章"
        if section_head in content:
            lines = content.split(section_head, 1)[1].split("## ", 1)[0].strip()
            print(f"\n从章节规划中找到内容:")
            print("-"*40)
            print(lines)
            print("-"*40)
            # 解析任务
            if "- 任务:" in lines:
                task_part = lines.split("- 任务:", 1)[1].split("- 要点:", 1)[0].strip()
                planned_task = task_part
    
    default_task = planned_task if planned_task else ""
    prompt_text = f"\n这章要写什么? 简要描述 (默认使用规划: {default_task[:30]}): "
    chapter_task = input(prompt_text).strip()
    if not chapter_task:
        chapter_task = default_task
    if not chapter_task:
        chapter_task = input("请输入本章任务: ").strip()
    
    word_count = input("目标字数 (默认2000, 网文标准): ").strip() or "2000"
    
    mode = state["project_info"]["genre"]
    platform = state["project_info"]["platform"]
    
    # 读取前面的章节（上下文）
    context_content = ""
    if current_chapter > 1:
        use_context = input("\n是否自动读取前面章节作为上下文? (y/n, 默认y): ").strip().lower()
        if use_context != 'n':
            context_content = get_previous_chapters(project_dir, current_chapter)
            if context_content:
                print("\n[OK] 已读取前序章节作为上下文")
            else:
                print("\n⚠️  未找到前面的章节")
    
    # 显示参考小说（如果有）
    ref_ids = state.get("references", [])
    if ref_ids:
        db = init_db()
        if db:
            print(f"\n本项目参考小说:")
            for rid in ref_ids:
                book = db.get_book(rid)
                if book:
                    print(f"  - {book['title']}")
    
    # 询问是否需要查看参考
    ref_choice = input("\n是否需要查看参考? (y/n, 默认n): ").strip().lower()
    if ref_choice == 'y' and ref_ids:
        db = init_db()
        if db:
            for rid in ref_ids[:3]:
                book = db.get_book(rid)
                if book:
                    print(f"\n{'='*60}")
                    print(f"{book['title']}")
                    print(f"{'='*60}")
                    chaps = db.get_chapters(rid)
                    if chaps and chaps[0].get('content', ''):
                        preview = chaps[0]['content'][:500]
                        print(preview)
                        print(f"\n... (预览前500字)")
    
    # 加载模式配置
    mode_config = {}
    mode_file = MODES_DIR / f"{mode}.json"
    if mode_file.exists():
        mode_config = json.loads(mode_file.read_text(encoding='utf-8'))
    
    print(f"\n配置信息:")
    print(f"  模式: {mode_config.get('name', mode)}")
    print(f"  平台: {platform}")
    print(f"  任务: {chapter_task}")
    print(f"  字数: {word_count}")
    if context_content:
        print(f"  上下文: 已加载前序章节")
    
    # 生成参考提示词（如果有参考）
    ref_prompt = ""
    if ref_ids:
        db = init_db()
        if db and ReferencePromptGenerator:
            rid = ref_ids[0]
            book = db.get_book(rid)
            chaps = db.get_chapters(rid)
            if book and chaps and chaps[0].get('content', ''):
                generator = ReferencePromptGenerator()
                ref_prompt = generator.generate_full_prompt(
                    book_title=book.get('title', ''),
                    genre=state["project_info"]["genre"],
                    author=book.get('author', ''),
                    chapter_content=chaps[0]['content'],
                    mode_name=mode,
                    platform=platform
                )
    
    print(f"""
{'='*60}
写作说明:

当前使用模拟模式（未配置LLM API Key）

你可以:
1. 直接根据提示手动写作
2. 或复制下面的提示词给AI（Claude/DeepSeek等）

提示词模板:
{'='*60}
""")
    
    # 生成完整的写作提示词
    if ref_prompt:
        prompt = ref_prompt + f"""

{context_content}

## 本书本章任务
{chapter_task}

## 请直接输出正文！
"""
    else:
        prompt = f"""# 写作任务

## 书名
{state['project_info']['title']}

{context_content}

## 本章任务
{chapter_task}

## 创作模式
{json.dumps(mode_config, ensure_ascii=False, indent=2)}

## 字数要求
{word_count} 字

## 请直接输出正文！
"""
    print(prompt)
    print(f"\n{'='*60}")
    
    # 询问是否用AI生成
    use_ai = False
    selected_model = None
    if HAS_REQUESTS:
        choice = input("\n是否让AI自动生成？(y/n, 默认n): ").strip().lower()
        if choice == "y":
            use_ai = True
            
            # 选择模型
            print(f"\n当前模型: {CONFIG['model']}")
            print("\n可用模型:")
            print("1. deepseek-v4-flash (默认，速度快，适合写小说)")
            print("2. deepseek-v4-pro (性能强，适合复杂任务)")
            print("3. deepseek-chat (旧版，即将停止支持)")
            print("4. deepseek-reasoner (旧版推理模型)")
            print("5. deepseek-coder (代码生成)")
            print("6. 保持当前")
            
            model_choice = input("\n选择模型 (1-6, 默认6): ").strip()
            
            if model_choice == "1":
                selected_model = "deepseek-v4-flash"
            elif model_choice == "2":
                selected_model = "deepseek-v4-pro"
            elif model_choice == "3":
                selected_model = "deepseek-chat"
            elif model_choice == "4":
                selected_model = "deepseek-reasoner"
            elif model_choice == "5":
                selected_model = "deepseek-coder"
    
    generated_content = None
    if use_ai:
        generated_content = call_ai(prompt, model=selected_model)
    
    if generated_content:
        # 保存AI生成的内容
        chapter_file = project_dir / "正文" / f"第{current_chapter}章.txt"
        with open(chapter_file, 'w', encoding='utf-8') as f:
            f.write(generated_content)
        print(f"\n[OK] AI生成的内容已保存到: {chapter_file}")
        print("\n现在你可以：")
        print("1. 直接使用")
        print("2. 修改完善")
        print("3. 重命名（如: 第1章_太空觉醒.txt）")
    else:
        # 保存草稿
        chapter_draft_file = project_dir / "正文" / f"第{current_chapter}章_草稿.txt"
        with open(chapter_draft_file, 'w', encoding='utf-8') as f:
            f.write(f"# 第{current_chapter}章\n\n")
            f.write(f"任务: {chapter_task}\n\n")
            f.write(f"[在这里写正文，约{word_count}字]\n")
        
        print(f"\n已生成章节草稿: {chapter_draft_file}")
        print(f"写好后可以重命名为正式文件名（如: 第{current_chapter}章_章节标题.txt）")
    
    # 更新状态
    state["progress"]["current_chapter"] = current_chapter
    state["chapter_meta"][f"chapter_{current_chapter}"] = {
        "task": chapter_task,
        "target_words": int(word_count),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ai_generated": use_ai
    }
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def check_project(project_dir):
    """检查项目状态"""
    state_file = project_dir / "state.json"
    if not state_file.exists():
        print("不是有效的项目目录！")
        return
    
    state = json.loads(state_file.read_text(encoding='utf-8'))
    info = state.get("project_info", {})
    progress = state.get("progress", {})
    
    print("\n" + "="*60)
    print("项目状态")
    print("="*60)
    print(f"  书名: {info.get('title', 'N/A')}")
    print(f"  类型: {info.get('type', 'N/A')}")
    print(f"  模式: {info.get('genre', 'N/A')}")
    print(f"  平台: {info.get('platform', 'N/A')}")
    print(f"  进度: 第 {progress.get('current_chapter', 0)} 章 / {info.get('target_chapters', '?')}")
    print(f"  字数: {progress.get('total_words', 0)} / {info.get('target_words', '?')}")
    print(f"  创建: {info.get('created_at', 'N/A')}")
    
    # 显示参考小说
    ref_ids = state.get("references", [])
    if ref_ids:
        print(f"\n  参考小说 ({len(ref_ids)}本):")
        db = init_db()
        if db:
            for rid in ref_ids:
                book = db.get_book(rid)
                if book:
                    print(f"   - {book['title']}")
    
    print("="*60)


def clean_ai_output(content):
    """清理 AI 的输出，去掉废话和格式"""
    if not content:
        return content
    
    # 常见的废话开头
    prefixes_to_remove = [
        r'^好的[，,。！!]?\s*',
        r'^好的[，,。！!]?我来[帮你帮我]?',
        r'^好的，我将',
        r'^好的，让我',
        r'^好的，这是',
        r'^好的，以下是',
        r'^好的，请看',
        r'^好的，为你',
        r'^好的，我为你',
        r'^好的，这一章',
        r'^好的，没问题',
        r'^没问题，这就',
        r'^收到，这就',
        r'^好的，收到',
        r'^好的，明白',
        r'^明白了，这就',
        r'^好的，让我来',
        r'^好的，让我帮你',
        r'^好的，我来写',
        r'^好的，我来生成',
        r'^好的，我来帮你生成',
        r'^好的，我来帮你写',
        r'^好的，我来帮你',
        r'^好的，我来',
        r'^好的，我会',
        r'^好的，我会帮你',
        r'^好的，我会为你',
        r'^好的，我会为你写',
        r'^好的，我会为你生成',
    ]
    
    # 去掉开头的废话
    for pattern in prefixes_to_remove:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE)
    
    # 去掉开头的 Markdown 标题（如 # 第一章 或 ## 标题）
    content = re.sub(r'^#+\s*.+?\s*\n', '', content)
    
    # 去掉开头的空行
    content = content.strip()
    
    return content


def call_ai(prompt, model=None, api_key=None, base_url=None):
    """
    调用AI生成内容
    默认用DeepSeek API的OpenAI兼容接口
    支持重试机制和输出清理
    """
    if not HAS_REQUESTS:
        print("警告：未安装requests库，无法调用AI")
        return None
    
    # 使用配置
    cfg = CONFIG
    model = model or cfg["model"]
    api_key = api_key or cfg["api_key"]
    base_url = base_url or cfg["base_url"]
    
    if not api_key:
        print("\n未配置API Key！")
        return None
    
    # 重试循环
    last_error = None
    for attempt in range(cfg["retry_times"]):
        try:
            if attempt > 0:
                print(f"重试 {attempt}/{cfg['retry_times']}...")
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": cfg["temperature"],
                "max_tokens": cfg["max_tokens"]
            }
            
            print(f"正在调用AI ({model})...")
            response = requests.post(
                f"{base_url}/chat/completions", 
                json=data, 
                headers=headers, 
                timeout=cfg["timeout"]
            )
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            # 清理输出
            content = clean_ai_output(content)
            
            print("[OK] AI生成完成！")
            return content
            
        except requests.exceptions.Timeout:
            last_error = "请求超时"
            print(f"[ERR] 超时（尝试 {attempt + 1}/{cfg['retry_times']}）")
            if attempt < cfg["retry_times"] - 1:
                time.sleep(2)  # 等待2秒再试
            continue
            
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            print(f"[ERR] 网络错误: {e}")
            if attempt < cfg["retry_times"] - 1:
                time.sleep(2)
                continue
            
        except Exception as e:
            last_error = str(e)
            print(f"[ERR] 错误: {e}")
            if attempt < cfg["retry_times"] - 1:
                time.sleep(2)
                continue
    
    print(f"[ERR] 所有重试失败！最后错误: {last_error}")
    return None


def show_help():
    print("""
====================================================================
                      盘古写作系统 Plus
====================================================================

参考库功能:
  pangu_plus.py ref stats          - 查看参考库统计
  pangu_plus.py ref search         - 搜索参考小说
  pangu_plus.py ref view           - 查看参考小说内容（可分析）
  pangu_plus.py ref analyze <ID>   - 分析指定小说第1章
  pangu_plus.py ref prompt <ID>    - 生成参考提示词

写作功能:
  pangu_plus.py new                - 创建新项目
  pangu_plus.py list               - 列出所有创作模式
  pangu_plus.py write <项目名>      - 写新章节（支持AI自动生成）
  pangu_plus.py status <项目名>     - 查看项目状态
  pangu_plus.py help               - 显示帮助

AI功能:
  已配置DeepSeek API，写章节时可选择自动生成

创作模式 (12种):
  治愈生活流、都市职业异能、无CP大女主、历史考据流
  中式民俗悬疑、规则怪谈、言情、发疯文学、世情爽文等

参考库:
  146本经典网文开篇，涵盖各大题材和知名作者

分析功能:
  自动分析章节的钩子类型、节奏分布、段落结构
  给出写作参考建议
  一键生成可直接使用的完整提示词
""")


def list_projects():
    """列出所有项目"""
    project_dirs = [d for d in PROJECTS_DIR.iterdir() if d.is_dir()]
    if not project_dirs:
        print("\n还没有项目")
        return []
    
    # 按修改时间排序
    project_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    
    print("\n" + "="*60)
    print("项目列表")
    print("="*60)
    
    projects = []
    for i, pd in enumerate(project_dirs, 1):
        state_file = pd / "state.json"
        name = pd.name
        title = name
        progress = ""
        
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text(encoding='utf-8'))
                title = state.get("project_info", {}).get("title", name)
                current_ch = state.get("progress", {}).get("current_chapter", 0)
                total_ch = state.get("project_info", {}).get("target_chapters", "?")
                progress = f" (第{current_ch}章/{total_ch}章)"
            except:
                pass
        
        print(f"  [{i}] {title}{progress}")
        projects.append(pd)
    
    print("="*60)
    return projects


def interactive_menu():
    """交互式菜单主界面"""
    while True:
        print("\n" + "="*60)
        print("  盘古写作系统 Plus")
        print("="*60)
        print(f"  当前模型: {CONFIG['model']}")
        print("="*60)
        print("  [1] 创建新项目")
        print("  [2] 查看项目列表")
        print("  [3] 打开最近项目")
        print("  [4] 参考库")
        print("  [5] 创作模式列表")
        print("  [6] 设置默认模型")
        print("  [7] 帮助")
        print("  [0] 退出")
        print("="*60)
        
        choice = input("\n请选择: ").strip()
        
        if choice == "0":
            print("再见！")
            break
        
        elif choice == "1":
            create_project()
        
        elif choice == "2":
            projects = list_projects()
            if projects:
                idx_choice = input("\n输入项目编号打开（0返回）: ").strip()
                if idx_choice.isdigit():
                    idx = int(idx_choice) - 1
                    if 0 <= idx < len(projects):
                        project_menu(projects[idx])
                    elif idx != -1:
                        print("无效编号")
        
        elif choice == "3":
            projects = list_projects()
            if projects:
                project_menu(projects[0])
        
        elif choice == "4":
            ref_menu()
        
        elif choice == "5":
            list_modes()
            show_db_stats()
        
        elif choice == "6":
            # 设置默认模型
            print("\n可用模型:")
            print("1. deepseek-v4-flash (默认，速度快，适合写小说)")
            print("2. deepseek-v4-pro (性能强，适合复杂任务)")
            print("3. deepseek-chat (旧版，即将停止支持)")
            print("4. deepseek-reasoner (旧版推理模型)")
            print("5. deepseek-coder (代码生成)")
            print("6. 取消")
            
            model_choice = input("\n选择默认模型 (1-6): ").strip()
            
            selected_model = None
            if model_choice == "1":
                selected_model = "deepseek-v4-flash"
            elif model_choice == "2":
                selected_model = "deepseek-v4-pro"
            elif model_choice == "3":
                selected_model = "deepseek-chat"
            elif model_choice == "4":
                selected_model = "deepseek-reasoner"
            elif model_choice == "5":
                selected_model = "deepseek-coder"
            
            if selected_model:
                # 更新配置
                CONFIG["model"] = selected_model
                print(f"\n[OK] 默认模型已设置为: {selected_model}")
        
        elif choice == "7":
            show_help()
        
        else:
            print("无效选项")


def open_file(file_path):
    """打开文件（跨平台）"""
    import subprocess
    import platform
    if platform.system() == "Windows":
        os.startfile(file_path)
    elif platform.system() == "Darwin":
        subprocess.run(["open", str(file_path)])
    else:
        subprocess.run(["xdg-open", str(file_path)])


def find_latest_chapter(project_dir, current_chapter):
    """找到最新章节文件"""
    content_dir = project_dir / "正文"
    if not content_dir.exists():
        return None
    # 找第 current_chapter 章或最近的
    for ch_num in range(current_chapter, 0, -1):
        possible_files = list(content_dir.glob(f"第{ch_num}章*.txt"))
        if possible_files:
            return possible_files[0]
    return None


def project_menu(project_dir):
    """项目内部菜单"""
    state_file = project_dir / "state.json"
    
    if not state_file.exists():
        print(f"无效项目: {project_dir.name}")
        return
    
    while True:
        state = json.loads(state_file.read_text(encoding='utf-8'))
        info = state.get("project_info", {})
        progress = state.get("progress", {})
        
        title = info.get("title", project_dir.name)
        current_ch = progress.get("current_chapter", 0)
        total_ch = info.get("target_chapters", "?")
        
        print("\n" + "="*60)
        print(f"  项目: {title}")
        print("="*60)
        print(f"  进度: 第{current_ch}章 / {total_ch}章")
        print("="*60)
        print("  [1] 写新章节")
        print("  [2] 查看项目状态")
        print("  [3] 打开总大纲")
        print("  [4] 打开最新章节")
        print("  [5] 打开项目文件夹")
        print("  [0] 返回")
        print("="*60)
        
        choice = input("\n请选择: ").strip()
        
        if choice == "0":
            break
        
        elif choice == "1":
            write_chapter(project_dir)
        
        elif choice == "2":
            check_project(project_dir)
        
        elif choice == "3":
            outline_file = project_dir / "大纲" / "总大纲.md"
            if outline_file.exists():
                print(f"正在打开: {outline_file}")
                open_file(outline_file)
            else:
                print(f"未找到: {outline_file}")
        
        elif choice == "4":
            latest_file = find_latest_chapter(project_dir, current_ch)
            if latest_file:
                print(f"正在打开: {latest_file}")
                open_file(latest_file)
            else:
                print("未找到已写的章节")
        
        elif choice == "5":
            print(f"正在打开文件夹: {project_dir}")
            open_file(project_dir)


def ref_menu():
    """参考库菜单"""
    while True:
        print("\n" + "="*60)
        print("  参考库")
        print("="*60)
        print("  [1] 查看统计")
        print("  [2] 搜索参考小说")
        print("  [3] 查看参考小说")
        print("  [0] 返回")
        print("="*60)
        
        choice = input("\n请选择: ").strip()
        
        if choice == "0":
            break
        
        elif choice == "1":
            show_db_stats()
        
        elif choice == "2":
            search_reference_books()
        
        elif choice == "3":
            view_reference_book()


def main():
    print_banner()
    
    # 如果没有参数，进入交互模式
    if len(sys.argv) < 2:
        try:
            interactive_menu()
            return
        except (KeyboardInterrupt, EOFError):
            print("\n再见！")
            return
    
    # 否则执行命令模式
    cmd = sys.argv[1].lower()
    
    if cmd == "new" or cmd == "init":
        create_project()
    elif cmd == "list" or cmd == "modes":
        list_modes()
        show_db_stats()
    elif cmd == "projects":
        list_projects()
    elif cmd == "write":
        if len(sys.argv) < 3:
            print("请提供项目名！")
            print("  用法: pangu_plus.py write <项目名>")
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
    elif cmd == "ref" or cmd == "reference":
        if len(sys.argv) < 3:
            ref_menu()
        else:
            sub_cmd = sys.argv[2].lower()
            if sub_cmd == "stats":
                show_db_stats()
            elif sub_cmd == "search":
                search_reference_books()
            elif sub_cmd == "view":
                view_reference_book()
            elif sub_cmd == "analyze":
                if len(sys.argv) < 4:
                    print("请提供小说ID！")
                    print("  用法: pangu_plus.py ref analyze <ID>")
                else:
                    try:
                        book_id = int(sys.argv[3])
                        db = init_db()
                        if db is not None:
                            analyze_chapter(db, book_id, 0)
                    except ValueError:
                        print("无效的ID格式")
            elif sub_cmd == "prompt":
                if len(sys.argv) < 4:
                    print("请提供小说ID！")
                    print("  用法: pangu_plus.py ref prompt <ID> [模式] [平台]")
                else:
                    try:
                        book_id = int(sys.argv[3])
                        mode_name = sys.argv[4] if len(sys.argv) > 4 else "通用"
                        platform = sys.argv[5] if len(sys.argv) > 5 else "番茄"
                        db = init_db()
                        if db is not None:
                            generate_reference_prompt(db, book_id, 0, mode_name, platform)
                    except ValueError:
                        print("无效的ID格式")
    elif cmd == "help" or cmd == "-h" or cmd == "--help":
        show_help()
    else:
        print(f"未知命令: {cmd}")
        show_help()


if __name__ == '__main__':
    main()
