#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量导入网络文学到SQL数据库
扫描素材库中的网络文学目录
"""

import sys
import os
from pathlib import Path
from db_manager import NovelReferenceDB

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


def main():
    """主函数"""
    print("="*70)
    print("批量导入网络文学到SQL数据库")
    print("="*70)
    
    # 网络文学目录路径
    novels_base_path = r"d:\study\近思录\小说\素材库\网络文学"
    
    # 扫描目录
    print(f"\n扫描目录: {novels_base_path}")
    novels = scan_novel_directories(novels_base_path)
    
    if not novels:
        print("\n未找到任何小说文件！")
        return
        
    print(f"\n找到 {len(novels)} 本小说！")
    
    # 连接数据库
    db = NovelReferenceDB()
    
    # 添加到数据库
    print("\n开始添加到数据库...")
    added_count = 0
    skipped_count = 0
    
    for novel in novels:
        # 检查是否已存在
        existing_books = db.list_books()
        exists = any(b['title'] == novel['title'] and b['author'] == novel['author'] for b in existing_books)
        
        if exists:
            skipped_count += 1
            continue
            
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
            if added_count % 20 == 0:
                print(f"  已添加: {added_count} / {len(novels)}")
                
        except Exception as e:
            print(f"  错误: {novel['title']} - {e}")
            skipped_count += 1
            
    print(f"\n完成！")
    print(f"  新增: {added_count} 本")
    print(f"  跳过: {skipped_count} 本（已存在）")
    
    # 显示统计
    stats = db.get_stats()
    print(f"\n数据库统计:")
    print(f"  总书籍: {stats['total_books']} 本")
    print(f"  参考书籍: {stats['reference_books']} 本")
    if stats['by_genre']:
        print(f"  按题材: {stats['by_genre']}")


if __name__ == '__main__':
    main()
