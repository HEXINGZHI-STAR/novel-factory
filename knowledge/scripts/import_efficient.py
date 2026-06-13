#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高效率导入小说：只导入前3章（开篇章节）
这对写作最有参考价值！
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
    print("高效率导入小说 - 只导入前3章（最有参考价值！）")
    print("="*70)
    
    # 连接数据库
    db = NovelReferenceDB()
    
    # 获取所有书籍
    books = db.list_books()
    print(f"\n数据库中有 {len(books)} 本书")
    
    # 统计已有章节的书
    books_with_chapters = 0
    for book in books:
        existing = db.get_chapters(book['id'])
        if existing:
            books_with_chapters += 1
            
    print(f"已有章节: {books_with_chapters} 本")
    print(f"待导入: {len(books) - books_with_chapters} 本")
    
    # 询问用户
    print("\n选项：")
    print("1. 只导入前20本经典小说的开篇（推荐！）")
    print("2. 只导入前50本小说的开篇")
    print("3. 导入所有小说的开篇（前3章）")
    print("4. 按题材筛选导入")
    
    choice = input("\n请选择 (1-4): ").strip()
    
    target_books = []
    
    if choice == '1':
        # 精选20本经典
        classic_authors = ['我吃西红柿', '忘语', '天蚕土豆', '唐家三少', '猫腻', 
                          '辰东', '烽火戏诸侯', '耳根', '月关', '蝴蝶蓝',
                          '会说话的肘子', '国王陛下', '南派三叔', '天下霸唱',
                          '顾漫', '丁墨', '紫金陈']
                          
        target_books = []
        for book in books:
            if book.get('author') and any(author in book['author'] for author in classic_authors):
                target_books.append(book)
                if len(target_books) >= 20:
                    break
        print(f"筛选出 {len(target_books)} 本经典小说")
        
    elif choice == '2':
        target_books = [b for b in books if not db.get_chapters(b['id'])][:50]
    elif choice == '3':
        target_books = [b for b in books if not db.get_chapters(b['id'])]
    elif choice == '4':
        print("\n可选题材：")
        genres = set(b['genre'] for b in books if b['genre'])
        for g in sorted(genres):
            print(f"  - {g}")
        target_genre = input("\n请输入要导入的题材: ").strip()
        target_books = [b for b in books if b.get('genre') == target_genre and not db.get_chapters(b['id'])]
        print(f"筛选出 {len(target_books)} 本 {target_genre} 小说")
    else:
        print("无效选择！")
        return
        
    if not target_books:
        print("没有找到可导入的书籍！")
        return
        
    print(f"\n准备导入 {len(target_books)} 本小说的前3章...")
    
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
        
    print(f"\n完成！")
    print(f"  导入: {imported_count} 本")
    print(f"  跳过: {skipped_count} 本")
    print(f"  总字数: {total_words:,} 字")
    
    stats = db.get_stats()
    print(f"\n数据库统计:")
    print(f"  总书籍: {stats['total_books']} 本")
    print(f"  总章节: {stats['total_chapters']} 章")
    print(f"\n这对写作最有帮助！因为：")
    print(f"  1. 开篇章节决定了读者留存率")
    print(f"  2. 可以学习不同作家的开篇技巧")
    print(f"  3. 数据库不会太臃肿")


if __name__ == '__main__':
    main()
