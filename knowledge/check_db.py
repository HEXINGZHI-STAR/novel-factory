#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查数据库状态"""

from db_manager import NovelReferenceDB

db = NovelReferenceDB()
stats = db.get_stats()
print('='*60)
print('数据库统计')
print('='*60)
print(f'  总书籍: {stats["total_books"]} 本')
print(f'  参考书籍: {stats["reference_books"]} 本')
print(f'  总章节: {stats["total_chapters"]} 章')
if stats.get('by_genre'):
    print(f'\n  按题材分布:')
    for genre, cnt in stats['by_genre'].items():
        print(f'    - {genre}: {cnt} 本')

print(f'\n当前书籍列表:')
books = db.list_books()
for i, book in enumerate(books[:20], 1):
    chapters = db.get_chapters(book['id'])
    has_chapters = len(chapters) > 0
    print(f'  [{i}] {book["title"]} - {book["author"]} {("[有章节]" if has_chapters else "[无章节]")}')

if len(books) > 20:
    print(f'  ... 还有 {len(books)-20} 本')
print(f'\n共 {len(books)} 本书籍')
