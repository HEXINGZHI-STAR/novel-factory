#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
继续导入更多经典小说
"""

import sys
import os
from pathlib import Path
from db_manager import NovelReferenceDB
import re


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
    print("继续导入更多经典小说！")
    print("="*70)
    
    # 连接数据库
    db = NovelReferenceDB()
    
    # 获取所有书籍
    books = db.list_books()
    
    # 列出所有作者
    print("\n数据库中的作家：")
    authors = set()
    for book in books:
        if book.get('author'):
            authors.add(book['author'])
    for author in sorted(authors):
        print(f"  - {author}")
    
    # 更多经典作家
    more_authors = ['我吃西红柿', '忘语', '天蚕土豆', '唐家三少', '猫腻', 
                   '辰东', '烽火戏诸侯', '耳根', '月关', '蝴蝶蓝',
                   '会说话的肘子', '国王陛下', '南派三叔', '天下霸唱',
                   '丁墨', '紫金陈', '梦入神机', '流浪的蛤蟆', '血红']
                      
    print(f"\n尝试导入更多经典作家的作品...")
    
    target_books = []
    for book in books:
        if book.get('author') and any(author in book['author'] for author in more_authors):
            existing = db.get_chapters(book['id'])
            if not existing:
                target_books.append(book)
                
    print(f"找到 {len(target_books)} 本待导入的经典小说\n")
    
    if not target_books:
        print("没有更多可导入的书籍了！")
        return
        
    imported_count = 0
    skipped_count = 0
    total_words = 0
    
    for book in target_books:
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
            
        print(f"处理: {book['title']} ({book['author']})")
        
        chapters = parse_first_chapters(file_path, num_chapters=3)
        
        if not chapters:
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
        print(f"  成功导入 {len(chapters)} 章，共 {book_word_count:,} 字\n")
        
    print("="*70)
    print("完成！")
    print(f"  本次导入: {imported_count} 本")
    print(f"  总字数: {total_words:,} 字")
    
    stats = db.get_stats()
    print(f"\n数据库统计:")
    print(f"  总书籍: {stats['total_books']} 本")
    print(f"  总章节: {stats['total_chapters']} 章")
    
    # 列出有章节的书
    print(f"\n已导入开篇的小说：")
    books_with_content = [b for b in books if db.get_chapters(b['id'])]
    for book in books_with_content:
        print(f"  - {book['title']} ({book['author']}) - {book['genre']}")


if __name__ == '__main__':
    main()
