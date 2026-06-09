#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI小说参考库命令行工具
用于添加、管理和分析网文小说参考资料
"""

import sys
import os
from pathlib import Path
from db_manager import NovelReferenceDB


def print_banner():
    """打印欢迎信息"""
    print("="*70)
    print("盘古AI小说参考库管理工具")
    print("="*70)


def show_help():
    """显示帮助信息"""
    print("\n可用命令:")
    print("  status              - 查看数据库状态")
    print("  add-book            - 添加一本书")
    print("  add-chapter         - 添加章节")
    print("  list-books          - 列出书籍")
    print("  tag-book            - 给书籍打标签")
    print("  import-txt          - 从TXT文件导入小说")
    print("  help                - 显示此帮助")


def cmd_status(db):
    """查看数据库状态"""
    stats = db.get_stats()
    print("\n[统计] 数据库统计:")
    print(f"  总书籍数: {stats['total_books']}")
    print(f"  参考书籍: {stats['reference_books']}")
    print(f"  总章节数: {stats['total_chapters']}")
    print(f"  标签总数: {stats['total_tags']}")
    
    if stats['by_platform']:
        print(f"\n  按平台:")
        for platform, count in stats['by_platform'].items():
            print(f"    {platform}: {count}本")
    
    if stats['by_genre']:
        print(f"\n  按题材:")
        for genre, count in stats['by_genre'].items():
            print(f"    {genre}: {count}本")


def cmd_add_book(db):
    """添加书籍"""
    print("\n[添加] 添加新书籍")
    print("-"*40)
    
    title = input("书名: ").strip()
    if not title:
        print("书名不能为空！")
        return
    
    author = input("作者 (可选): ").strip() or None
    platform = input("平台 (fanqie/qidian/qimao/jinjiang, 可选): ").strip() or None
    genre = input("题材 (可选): ").strip() or None
    mode = input("创作模式 (可选): ").strip() or None
    word_count = input("总字数 (可选): ").strip()
    word_count = int(word_count) if word_count else None
    notes = input("备注 (可选): ").strip() or None
    
    book_id = db.add_book(
        title=title,
        author=author,
        platform=platform,
        genre=genre,
        mode=mode,
        word_count=word_count,
        notes=notes
    )
    
    print(f"\n✅ 书籍添加成功！ID: {book_id}")


def cmd_add_chapter(db):
    """添加章节"""
    print("\n[添加] 添加章节")
    print("-"*40)
    
    book_id = input("书籍ID: ").strip()
    if not book_id.isdigit():
        print("请输入有效的ID！")
        return
    
    book_id = int(book_id)
    book = db.get_book(book_id)
    if not book:
        print("找不到该书籍！")
        return
    
    print(f"添加到: {book['title']}")
    
    chapter_num = input("章节号: ").strip()
    if not chapter_num.isdigit():
        print("请输入有效的章节号！")
        return
    chapter_num = int(chapter_num)
    
    title = input("章节标题 (可选): ").strip() or None
    
    print("\n输入章节内容 (结束时输入 . 并回车):")
    content_lines = []
    while True:
        line = input()
        if line == '.':
            break
        content_lines.append(line)
    content = '\n'.join(content_lines)
    
    is_opening = input("是否是开篇章节? (y/n, 默认n): ").strip().lower() == 'y'
    
    chapter_id = db.add_chapter(
        book_id=book_id,
        chapter_num=chapter_num,
        title=title,
        content=content,
        is_opening=is_opening
    )
    
    print(f"\n✅ 章节添加成功！ID: {chapter_id}, 字数: {len(content)}")


def cmd_list_books(db):
    """列出书籍"""
    print("\n[列表] 书籍列表")
    print("-"*40)
    
    platform = input("按平台筛选 (可选): ").strip() or None
    genre = input("按题材筛选 (可选): ").strip() or None
    mode = input("按模式筛选 (可选): ").strip() or None
    only_ref = input("只显示参考书籍? (y/n, 默认n): ").strip().lower() == 'y'
    
    books = db.list_books(
        platform=platform,
        genre=genre,
        mode=mode,
        only_reference=only_ref
    )
    
    if not books:
        print("\n没有找到书籍")
        return
    
    print(f"\n找到 {len(books)} 本书:")
    for book in books:
        ref_mark = "[*]" if book['is_reference'] else "   "
        print(f"\n  {ref_mark} [{book['id']}] {book['title']}")
        if book['author']:
            print(f"      作者: {book['author']}")
        meta_parts = []
        if book['platform']:
            meta_parts.append(book['platform'])
        if book['genre']:
            meta_parts.append(book['genre'])
        if book['mode']:
            meta_parts.append(book['mode'])
        if meta_parts:
            print(f"      {' | '.join(meta_parts)}")


def cmd_tag_book(db):
    """给书籍打标签"""
    print("\n[标签] 给书籍打标签")
    print("-"*40)
    
    book_id = input("书籍ID: ").strip()
    if not book_id.isdigit():
        print("请输入有效的ID！")
        return
    
    book_id = int(book_id)
    book = db.get_book(book_id)
    if not book:
        print("找不到该书籍！")
        return
    
    print(f"书籍: {book['title']}")
    
    current_tags = db.get_book_tags(book_id)
    if current_tags:
        print(f"\n现有标签:")
        for tag in current_tags:
            print(f"  - {tag['name']} ({tag['category']})")
    
    print("\n输入标签名称 (多个标签用逗号分隔):")
    tag_input = input().strip()
    
    if tag_input:
        tag_names = [t.strip() for t in tag_input.split(',') if t.strip()]
        for tag_name in tag_names:
            db.tag_book(book_id, tag_name)
        print(f"\n✅ 添加了 {len(tag_names)} 个标签！")


def cmd_import_txt(db):
    """从TXT导入小说"""
    print("\n[导入] 从TXT文件导入小说")
    print("-"*40)
    
    file_path = input("TXT文件路径: ").strip()
    if not os.path.exists(file_path):
        print("文件不存在！")
        return
    
    # 先添加书籍
    title = input("书名: ").strip() or Path(file_path).stem
    author = input("作者 (可选): ").strip() or None
    platform = input("平台 (可选): ").strip() or None
    genre = input("题材 (可选): ").strip() or None
    
    book_id = db.add_book(
        title=title,
        author=author,
        platform=platform,
        genre=genre
    )
    
    print(f"\n书籍已创建 (ID: {book_id})，开始导入章节...")
    
    # 简单导入：每1000字一章（示例）
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 简单的章节分割逻辑
    chapter_size = 3000  # 每章约3000字
    chapters = []
    for i in range(0, len(content), chapter_size):
        chapter_content = content[i:i+chapter_size]
        chapters.append(chapter_content)
    
    for idx, chapter_content in enumerate(chapters, 1):
        db.add_chapter(
            book_id=book_id,
            chapter_num=idx,
            title=f"第{idx}章",
            content=chapter_content,
            is_opening=(idx <= 3)
        )
        print(f"  已导入第{idx}章 ({len(chapter_content)}字)")
    
    print(f"\n✅ 导入完成！共 {len(chapters)} 章")


def main():
    """主函数"""
    print_banner()
    
    db = NovelReferenceDB()
    
    if len(sys.argv) < 2:
        cmd_status(db)
        show_help()
        return
    
    cmd = sys.argv[1].lower()
    
    if cmd == 'status':
        cmd_status(db)
    elif cmd == 'add-book':
        cmd_add_book(db)
    elif cmd == 'add-chapter':
        cmd_add_chapter(db)
    elif cmd == 'list-books':
        cmd_list_books(db)
    elif cmd == 'tag-book':
        cmd_tag_book(db)
    elif cmd == 'import-txt':
        cmd_import_txt(db)
    elif cmd == 'help':
        show_help()
    else:
        print(f"未知命令: {cmd}")
        show_help()


if __name__ == '__main__':
    main()
