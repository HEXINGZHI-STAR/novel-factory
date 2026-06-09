#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速导入脚本 - 只导入每个分类的少量章节来测试流程
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from db_manager import NovelReferenceDB
from organize_database import (
    read_file_with_encoding, split_chapters, CATEGORY_CONFIG
)


def quick_import():
    """快速导入测试"""
    print("="*60)
    print("快速导入测试")
    print("="*60)
    
    # 初始化数据库
    db = NovelReferenceDB()
    
    # 清空数据库
    print("清空数据库...")
    db.clear_all_data()
    
    # 素材库根目录
    material_root = Path(__file__).parent.parent / "素材库" / "网络文学"
    print(f"素材库路径: {material_root}")
    print(f"路径存在: {material_root.exists()}")
    
    total_chapters = 0
    total_novels = 0
    
    # 只处理前3个分类，每个分类导入1-2本小说，每本小说导入前3章
    categories = list(CATEGORY_CONFIG.keys())[:3]
    
    for category in categories:
        config = CATEGORY_CONFIG[category]
        category_path = material_root / config["path"]
        
        if not category_path.exists():
            continue
        
        print(f"\n处理分类: {category}")
        
        txt_files = list(category_path.glob("*.txt"))[:3]  # 每类最多3本
        
        for txt_file in txt_files:
            file_name = txt_file.name
            
            print(f"  处理: {file_name}")
            
            # 读取内容
            content = read_file_with_encoding(txt_file)
            if not content:
                continue
            
            # 分割章节
            chapters = split_chapters(content)
            if len(chapters) == 0:
                continue
            
            # 导入前3章
            chapters = chapters[:3]
            print(f"    找到 {len(chapters)} 章")
            
            # 添加到数据库
            book_title = file_name.replace(".txt", "")
            book_id = db.add_book(
                title=book_title,
                category=category,
                is_reference=(file_name in config.get("reference", []))
            )
            
            for i, (chapter_title, chapter_content) in enumerate(chapters):
                is_opening = (i == 0)
                hook_strength = 8 if is_opening else 7
                
                db.add_chapter(
                    book_id=book_id,
                    chapter_num=i+1,
                    title=chapter_title[:100],
                    content=chapter_content,
                    is_opening=is_opening,
                    hook_strength=hook_strength
                )
            
            total_chapters += len(chapters)
            total_novels += 1
            print(f"    ✓ 已导入")
    
    print(f"\n{'='*60}")
    print("快速导入完成！")
    print(f"总计: {total_novels} 本小说，{total_chapters} 章")
    print('='*60)
    
    stats = db.get_stats()
    print(f"\n数据库统计:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == '__main__':
    quick_import()
