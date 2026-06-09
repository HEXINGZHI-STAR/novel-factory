#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导入小说正文内容到数据库
"""

import sys
import os
from pathlib import Path
from db_manager import NovelReferenceDB
import re


def parse_novel_content(file_path):
    """解析小说文件内容，尝试分章节"""
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
            return None, None
            
    if not content:
        return None, None
        
    # 简单尝试分章节
    # 常见的章节标题格式：第X章、第X节、Chapter X等
    chapter_patterns = [
        r'第[0-9一二三四五六七八九十百千万]+章.*?(?=第[0-9一二三四五六七八九十百千万]+章|$)',
        r'第[0-9一二三四五六七八九十百千万]+节.*?(?=第[0-9一二三四五六七八九十百千万]+节|$)',
        r'Chapter\s+\d+.*?(?=Chapter\s+\d+|$)',
    ]
    
    chapters = []
    
    for pattern in chapter_patterns:
        matches = list(re.finditer(pattern, content, re.DOTALL))
        if len(matches) >= 3:  # 至少找到3章才算成功
            for i, match in enumerate(matches):
                chapter_title = f"第{i+1}章"
                # 尝试提取标题
                first_line = match.group(0).strip().split('\n')[0]
                if '章' in first_line or '节' in first_line:
                    chapter_title = first_line
                    
                chapters.append({
                    'chapter_num': i + 1,
                    'title': chapter_title,
                    'content': match.group(0).strip()
                })
            break
    
    # 如果分章失败，就作为单个章节
    if not chapters:
        chapters.append({
            'chapter_num': 1,
            'title': '全文',
            'content': content
        })
        
    return content, chapters


def main():
    """主函数"""
    print("="*70)
    print("导入小说正文内容到数据库")
    print("="*70)
    
    # 连接数据库
    db = NovelReferenceDB()
    
    # 获取所有书籍
    books = db.list_books()
    print(f"\n数据库中有 {len(books)} 本书")
    
    # 询问用户要导入哪些书
    print("\n选项：")
    print("1. 导入前10本小说的正文")
    print("2. 导入前50本小说的正文")
    print("3. 导入所有小说的正文")
    print("4. 只导入特定的一本书")
    
    choice = input("\n请选择 (1-4): ").strip()
    
    target_books = []
    
    if choice == '1':
        target_books = books[:10]
    elif choice == '2':
        target_books = books[:50]
    elif choice == '3':
        target_books = books
    elif choice == '4':
        book_id = input("请输入书籍ID: ").strip()
        book = db.get_book(int(book_id))
        if book:
            target_books = [book]
        else:
            print("找不到该书籍！")
            return
    else:
        print("无效选择！")
        return
        
    print(f"\n准备导入 {len(target_books)} 本小说的正文...")
    
    imported_count = 0
    skipped_count = 0
    
    for book in target_books:
        # 检查是否已有章节
        existing_chapters = db.get_chapters(book['id'])
        if existing_chapters:
            print(f"\n跳过: {book['title']} (已有章节)")
            skipped_count += 1
            continue
            
        # 从notes中提取文件路径
        file_path = None
        if book.get('notes') and '文件:' in book['notes']:
            # 尝试从notes中提取
            notes = book['notes']
            if '文件:' in notes:
                file_name = notes.split('文件:')[-1].strip()
                # 重建路径
                base_path = Path(r"d:\study\近思录\小说\素材库\网络文学")
                # 尝试查找文件
                for root, dirs, files in os.walk(base_path):
                    if file_name in files:
                        file_path = Path(root) / file_name
                        break
                        
        if not file_path:
            print(f"\n跳过: {book['title']} (找不到文件)")
            skipped_count += 1
            continue
            
        print(f"\n处理: {book['title']}")
        print(f"  文件: {file_path}")
        
        # 解析文件
        full_content, chapters = parse_novel_content(file_path)
        
        if not full_content:
            print(f"  无法解析内容")
            skipped_count += 1
            continue
            
        print(f"  字数: {len(full_content):,} 字")
        print(f"  章节: {len(chapters)}")
        
        # 导入章节
        for chapter_data in chapters:
            try:
                db.add_chapter(
                    book_id=book['id'],
                    chapter_num=chapter_data['chapter_num'],
                    title=chapter_data['title'],
                    content=chapter_data['content'],
                    is_opening=(chapter_data['chapter_num'] <= 3)
                )
            except Exception as e:
                print(f"  错误: {e}")
                
        imported_count += 1
        print(f"  成功导入!")
        
    print(f"\n完成！")
    print(f"  导入: {imported_count} 本")
    print(f"  跳过: {skipped_count} 本")
    
    # 更新统计
    stats = db.get_stats()
    print(f"\n数据库统计:")
    print(f"  总书籍: {stats['total_books']} 本")
    print(f"  总章节: {stats['total_chapters']} 章")


if __name__ == '__main__':
    main()
