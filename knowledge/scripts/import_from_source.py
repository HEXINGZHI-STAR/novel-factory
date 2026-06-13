#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接从素材库导入经典小说
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


def extract_genre_from_path(dir_name):
    """从目录名提取题材"""
    if '仙侠' in dir_name:
        return '仙侠', 'general'
    elif '都市' in dir_name:
        return '都市', 'urban_power'
    elif '玄幻' in dir_name:
        return '玄幻', 'general'
    elif '科幻' in dir_name:
        return '科幻', 'general'
    elif '游戏' in dir_name:
        return '游戏', 'general'
    elif '武侠' in dir_name:
        return '武侠', 'general'
    elif '悬疑' in dir_name:
        return '悬疑', 'folk_horror'
    elif '历史' in dir_name:
        return '历史', 'history_scholar'
    elif '言情' in dir_name:
        return '言情', 'romance'
    elif '二次元' in dir_name:
        return '二次元', 'general'
    return '其他', 'general'


def main():
    """主函数"""
    print("="*70)
    print("直接从素材库导入经典小说！")
    print("="*70)
    
    db = NovelReferenceDB()
    
    # 素材库路径
    base_path = Path(r"d:\study\近思录\小说\素材库\网络文学")
    
    if not base_path.exists():
        print(f"路径不存在: {base_path}")
        return
    
    # 经典作家
    classic_authors = ['我吃西红柿', '忘语', '天蚕土豆', '唐家三少', '猫腻', 
                      '辰东', '烽火戏诸侯', '耳根', '月关', '蝴蝶蓝',
                      '会说话的肘子', '国王陛下', '南派三叔', '天下霸唱',
                      '丁墨', '紫金陈', '梦入神机', '流浪的蛤蟆', '血红']
    
    imported_count = 0
    skipped_count = 0
    total_words = 0
    
    # 遍历分类目录
    for category_dir in base_path.iterdir():
        if not category_dir.is_dir():
            continue
            
        dir_name = category_dir.name
        
        genre, mode = extract_genre_from_path(dir_name)
        print(f"\n处理分类: {dir_name} ({genre})")
        
        # 遍历作家目录
        for author_dir in category_dir.iterdir():
            if not author_dir.is_dir():
                continue
                
            author_name = author_dir.name.strip('「」')
            
            # 只处理经典作家
            is_classic = any(keyword in author_name for keyword in classic_authors)
            if not is_classic:
                continue
                
            print(f"  作家: {author_name}")
            
            # 遍历作品文件
            for book_file in author_dir.iterdir():
                if not book_file.is_file():
                    continue
                    
                if not book_file.suffix.lower() in ['.txt', '.epub', '.mobi']:
                    continue
                    
                # 提取书名
                book_name = book_file.stem
                # 清理书名
                if book_name.startswith('《'):
                    book_name = book_name[1:]
                if book_name.endswith('》'):
                    book_name = book_name[:-1]
                    
                # 检查是否已存在
                existing_books = db.list_books()
                exists = any(b['title'] == book_name and b['author'] == author_name for b in existing_books)
                
                if exists:
                    continue
                
                # 添加书
                try:
                    book_id = db.add_book(
                        title=book_name,
                        author=author_name,
                        platform='qidian',
                        genre=genre,
                        mode=mode,
                        notes=f"分类: {dir_name}, 文件: {book_file.name}",
                        is_reference=True
                    )
                    
                    # 导入前3章
                    chapters = parse_first_chapters(book_file, num_chapters=3)
                    
                    if chapters:
                        book_word_count = 0
                        for chapter_data in chapters:
                            try:
                                db.add_chapter(
                                    book_id=book_id,
                                    chapter_num=chapter_data['chapter_num'],
                                    title=chapter_data['title'],
                                    content=chapter_data['content'],
                                    is_opening=True
                                )
                                book_word_count += len(chapter_data['content'])
                            except Exception as e:
                                print(f"    错误: {e}")
                                
                        imported_count += 1
                        total_words += book_word_count
                        print(f"    导入: {book_name} ({len(chapters)}章, {book_word_count:,}字)")
                    else:
                        skipped_count += 1
                        print(f"    跳过: {book_name} (无法解析)")
                        
                except Exception as e:
                    print(f"    错误: {book_name} - {e}")
                    skipped_count += 1
    
    print("\n" + "="*70)
    print("完成！")
    print(f"  成功导入: {imported_count} 本")
    print(f"  总字数: {total_words:,} 字")
    
    stats = db.get_stats()
    print(f"\n数据库统计:")
    print(f"  总书籍: {stats['total_books']} 本")
    print(f"  总章节: {stats['total_chapters']} 章")
    
    # 列出已导入的
    print(f"\n已导入开篇的小说：")
    all_books = db.list_books()
    for book in all_books:
        if db.get_chapters(book['id']):
            print(f"  - {book['title']} ({book['author']}) - {book['genre']}")


if __name__ == '__main__':
    main()
