#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扫描素材库，对比数据库，导入剩余所有书籍
"""

import sys
import os
from pathlib import Path
from db_manager import NovelReferenceDB
import re

# 定义分类映射
CATEGORY_MAP = {
    "二次元": {"genre": "二次元", "mode": "general"},
    "仙侠": {"genre": "仙侠", "mode": "general"},
    "体育": {"genre": "体育", "mode": "general"},
    "军事": {"genre": "军事", "mode": "general"},
    "历史": {"genre": "历史", "mode": "history_scholar"},
    "奇幻": {"genre": "奇幻", "mode": "general"},
    "悬疑": {"genre": "悬疑", "mode": "folk_horror"},
    "武侠": {"genre": "武侠", "mode": "general"},
    "游戏": {"genre": "游戏", "mode": "general"},
    "玄幻": {"genre": "玄幻", "mode": "general"},
    "科幻": {"genre": "科幻", "mode": "general"},
    "言情": {"genre": "言情", "mode": "romance"},
    "都市": {"genre": "都市", "mode": "urban_power"}
}


def scan_novel_directories(base_path):
    """扫描网络文学目录"""
    novels = []
    base_dir = Path(base_path)
    
    if not base_dir.exists():
        print(f"目录不存在: {base_path}")
        return novels
    
    # 遍历所有分类目录
    for category_dir in base_dir.iterdir():
        if not category_dir.is_dir():
            continue
            
        dir_name = category_dir.name
        
        # 跳过一些目录
        if dir_name in ['目录', '中国网络文学二十年', 'index', '听书音频', '期刊杂志', '科幻奇幻']:
            continue
            
        # 检查是否是分类目录
        category_type = None
        for cat in CATEGORY_MAP.keys():
            if cat in dir_name:
                category_type = cat
                break
                
        if not category_type:
            continue
            
        print(f"\n处理分类: {category_type}")
        
        # 遍历作家目录
        for author_dir in category_dir.iterdir():
            if not author_dir.is_dir():
                continue
                
            author_name = author_dir.name.strip("「」")
            print(f"  作家: {author_name}")
            
            # 遍历作品文件
            for novel_file in author_dir.iterdir():
                if not novel_file.is_file():
                    continue
                    
                # 只处理文本文件
                if not novel_file.suffix.lower() in ['.txt', '.epub', '.mobi', '.azw3', '.pdf']:
                    continue
                    
                # 提取书名
                file_name = novel_file.name
                title = file_name
                
                # 清理书名
                if title.startswith(('《', '"')):
                    title = title[1:]
                if title.endswith(('》', '"')):
                    title = title[:-1]
                    
                # 去掉后缀
                for ext in ['.txt', '.epub', '.mobi', '.azw3', '.pdf']:
                    if title.lower().endswith(ext.lower()):
                        title = title[:-len(ext)]
                        break
                        
                # 去掉校对版、全本等标记
                clean_title = title
                for tag in ['（校对版全本）', '（精校版全本）', '（精校全本）', 
                           '（校对全本）', '[校对版全本]', '[精校版全本]',
                           '（全本）', '（连载）', '[21册][多看版]', '']:
                    if tag in clean_title:
                        clean_title = clean_title.replace(tag, '')
                        
                # 提取作者
                book_author = author_name
                if "作者：" in title:
                    parts = title.split("作者：")
                    if len(parts) > 1:
                        book_author = parts[1].strip()
                        clean_title = parts[0].strip()
                elif "作者:" in title:
                    parts = title.split("作者:")
                    if len(parts) > 1:
                        book_author = parts[1].strip()
                        clean_title = parts[0].strip()
                        
                clean_title = clean_title.strip()
                if not clean_title:
                    clean_title = title
                    
                novels.append({
                    'title': clean_title,
                    'author': book_author,
                    'genre': CATEGORY_MAP[category_type]['genre'],
                    'mode': CATEGORY_MAP[category_type]['mode'],
                    'file_path': str(novel_file),
                    'file_type': novel_file.suffix.lower(),
                    'category': category_type,
                    'notes': f"分类: {category_type}, 文件: {novel_file.name}"
                })
                
    return novels


def parse_first_chapters(file_path, num_chapters=3):
    """只解析前N章"""
    content = ""
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='gbk') as f:
                content = f.read()
        except Exception as e:
            print(f"  无法读取文件: {e}")
            return []
            
    if not content:
        return []
        
    # 常见的章节标题格式
    chapter_patterns = [
        r'第[0-9一二三四五六七八九十百千万]+章.*?(?=第[0-9一二三四五六七八九十百千万]+章|$)',
        r'第[0-9一二三四五六七八九十百千万]+节.*?(?=第[0-9一二三四五六七八九十百千万]+节|$)',
        r'Chapter\s+\d+.*?(?=Chapter\s+\d+|$)',
    ]
    
    chapters = []
    
    for pattern in chapter_patterns:
        matches = list(re.finditer(pattern, content, re.DOTALL))
        if len(matches) >= 1:
            for i, match in enumerate(matches[:num_chapters]):
                chapter_title = f"第{i+1}章"
                first_line = match.group(0).strip().split('\n')[0]
                if '章' in first_line or '节' in first_line:
                    chapter_title = first_line
                    
                chapters.append({
                    'chapter_num': i + 1,
                    'title': chapter_title,
                    'content': match.group(0).strip()
                })
            break
    
    # 如果分章失败，取前1万字
    if not chapters:
        preview_length = min(10000, len(content))
        chapters.append({
            'chapter_num': 1,
            'title': '开篇预览',
            'content': content[:preview_length]
        })
        
    return chapters


def main():
    """主函数"""
    print("="*70)
    print("扫描素材库，对比数据库，导入剩余所有书籍")
    print("="*70)
    
    # 连接数据库
    db = NovelReferenceDB()
    
    # 获取现有书籍
    existing_books = db.list_books()
    existing_titles = set((b['title'], b['author']) for b in existing_books)
    print(f"\n数据库现有: {len(existing_books)} 本")
    
    # 网络文学目录路径
    novels_base_path = r"d:\study\近思录\小说\素材库\网络文学"
    
    # 扫描目录
    print(f"\n扫描目录: {novels_base_path}")
    novels = scan_novel_directories(novels_base_path)
    
    if not novels:
        print("\n未找到任何小说文件！")
        return
        
    print(f"\n找到 {len(novels)} 本小说！")
    
    # 筛选未导入的
    new_novels = []
    for novel in novels:
        key = (novel['title'], novel['author'])
        if key not in existing_titles:
            new_novels.append(novel)
    
    print(f"\n其中: {len(new_novels)} 本未导入")
    
    if not new_novels:
        print("\n没有新书籍需要导入！")
        return
        
    # 添加到数据库
    print("\n开始添加到数据库...")
    added_count = 0
    skipped_count = 0
    
    for novel in new_novels:
        try:
            book_id = db.add_book(
                title=novel['title'],
                author=novel['author'],
                platform="qidian",  # 默认起点
                genre=novel['genre'],
                mode=novel['mode'],
                notes=novel['notes'],
                is_reference=True
            )
            
            # 添加标签
            db.tag_book(book_id, novel['genre'])
            db.tag_book(book_id, novel['category'])
            
            added_count += 1
            if added_count % 10 == 0:
                print(f"  已添加: {added_count} / {len(new_novels)}")
                
        except Exception as e:
            print(f"  错误: {novel['title']} - {e}")
            skipped_count += 1
            
    print(f"\n完成！")
    print(f"  新增: {added_count} 本")
    print(f"  跳过: {skipped_count} 本")
    
    # 显示统计
    stats = db.get_stats()
    print(f"\n数据库统计:")
    print(f"  总书籍: {stats['total_books']} 本")
    print(f"  参考书籍: {stats['reference_books']} 本")
    
    # 现在导入章节
    print(f"\n" + "="*70)
    print("开始导入书籍的前3章内容")
    print("="*70)
    
    # 获取所有参考书籍（优先经典作者）
    all_books = db.list_books()
    classic_authors = ['我吃西红柿', '忘语', '天蚕土豆', '唐家三少', '猫腻', 
                      '辰东', '烽火戏诸侯', '耳根', '月关', '蝴蝶蓝',
                      '会说话的肘子', '国王陛下', '南派三叔', '天下霸唱',
                      '顾漫', '丁墨', '紫金陈', '梦入神机', '流浪的蛤蟆', '血红', '萧鼎']
    
    # 先处理没有章节的书籍
    books_to_process = []
    for book in all_books:
        chapters = db.get_chapters(book['id'])
        if not chapters:
            books_to_process.append(book)
    
    # 优先经典作者
    books_to_process.sort(key=lambda b: 0 if any(a in (b.get('author') or '') for a in classic_authors) else 1)
    
    print(f"\n需要导入章节的书籍: {len(books_to_process)} 本")
    
    imported_count = 0
    skipped_count = 0
    total_words = 0
    
    for book in books_to_process[:200]:  # 先导入200本
        # 查找文件路径
        file_path = None
        if book.get('notes') and '文件:' in book['notes']:
            notes = book['notes']
            file_name = notes.split('文件:')[-1].strip()
            base_path = Path(r"d:\study\近思录\小说\素材库\网络文学")
            for root, dirs, files in os.walk(base_path):
                if file_name in files:
                    file_path = Path(root) / file_name
                    break
                        
        if not file_path:
            skipped_count += 1
            continue
            
        print(f"\n处理: {book['title']} ({book['author']})")
        
        # 解析前3章
        chapters = parse_first_chapters(file_path, num_chapters=3)
        
        if not chapters:
            print(f"  无法解析内容")
            skipped_count += 1
            continue
            
        # 导入章节
        book_word_count = 0
        for chapter_data in chapters:
            try:
                db.add_chapter(
                    book_id=book['id'],
                    chapter_num=chapter_data['chapter_num'],
                    title=chapter_data['title'],
                    content=chapter_data['content'],
                    is_opening=True
                )
                book_word_count += len(chapter_data['content'])
            except Exception as e:
                print(f"  错误: {e}")
                
        imported_count += 1
        total_words += book_word_count
        print(f"  成功导入 {len(chapters)} 章，共 {book_word_count:,} 字")
        
        if imported_count % 20 == 0:
            print(f"\n  进度: {imported_count} / {min(200, len(books_to_process))}")
        
    print("\n" + "="*70)
    print("完成！")
    print(f"  导入章节: {imported_count} 本")
    print(f"  跳过: {skipped_count} 本")
    print(f"  总字数: {total_words:,} 字")
    
    stats = db.get_stats()
    print(f"\n数据库统计:")
    print(f"  总书籍: {stats['total_books']} 本")
    print(f"  参考书籍: {stats['reference_books']} 本")
    print(f"  总章节: {stats['total_chapters']} 章")


if __name__ == '__main__':
    main()
