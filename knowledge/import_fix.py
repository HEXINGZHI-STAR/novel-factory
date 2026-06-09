#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修正导入脚本，处理作者名中的'作品'后缀
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
    print("导入更多经典小说！（修正版）")
    print("="*70)
    
    db = NovelReferenceDB()
    books = db.list_books()
    
    # 经典作家关键词
    classic_keywords = ['我吃西红柿', '忘语', '天蚕土豆', '唐家三少', '猫腻', 
                       '辰东', '烽火戏诸侯', '耳根', '月关', '蝴蝶蓝',
                       '会说话的肘子', '国王陛下', '南派三叔', '天下霸唱',
                       '丁墨', '紫金陈', '梦入神机', '流浪的蛤蟆', '血红']
                      
    print("\n查找经典小说...")
    
    target_books = []
    for book in books:
        if book.get('author'):
            author_str = book['author']
            for keyword in classic_keywords:
                if keyword in author_str:
                    existing = db.get_chapters(book['id'])
                    if not existing:
                        target_books.append(book)
                    break
                    
    print(f"找到 {len(target_books)} 本待导入的经典小说\n")
    
    if not target_books:
        print("没有更多可导入的书籍了！")
        # 列出已有的
        print("\n已导入开篇的小说：")
        for book in books:
            if db.get_chapters(book['id']):
                print(f"  - {book['title']} ({book['author']})")
        return
        
    imported_count = 0
    skipped_count = 0
    total_words = 0
    
    for book in target_books:
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
    
    print(f"\n已导入开篇的小说：")
    for book in books:
        if db.get_chapters(book['id']):
            print(f"  - {book['title']} ({book['author']}) - {book['genre']}")


if __name__ == '__main__':
    main()
