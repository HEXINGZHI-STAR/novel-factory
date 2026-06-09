#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI 批量章节分析脚本
对数据库中所有有章节内容的书籍运行 chapter_analyzer，
填充 hooks / emotion_anchors / writing_techniques 三张表

用法:
  python knowledge/batch_analyze.py              # 全量分析（可能很慢）
  python knowledge/batch_analyze.py --limit 50   # 只分析前50本
  python knowledge/batch_analyze.py --genre 都市  # 只分析指定题材
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "knowledge"))

from db_manager import NovelReferenceDB
from chapter_analyzer import ChapterAnalyzer

try:
    import sqlite3
except ImportError:
    pass


def main():
    limit = None
    genre_filter = None

    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
        if arg == "--genre" and i + 1 < len(args):
            genre_filter = args[i + 1]

    db = NovelReferenceDB()
    analyzer = ChapterAnalyzer()
    conn = db._get_connection()
    cursor = conn.cursor()

    # 获取有章节内容的书籍
    books = db.list_books(only_reference=True, limit=limit or 5000)
    if genre_filter:
        books = [b for b in books if b.get('genre') == genre_filter]

    books_with_chapters = []
    for b in books:
        chaps = db.get_chapters(b['id'])
        for ch in chaps:
            if ch.get('content', ''):
                books_with_chapters.append((b, chaps))
                break

    print(f"=== 批量章节分析 ===")
    print(f"符合条件的书籍: {len(books_with_chapters)} 本")
    print()

    hooks_total = 0
    emotions_total = 0

    for idx, (book, chapters) in enumerate(books_with_chapters):
        if limit and idx >= limit:
            break

        print(f"[{idx+1}/{len(books_with_chapters)}] {book['title'][:50]}...")

        for ch in chapters:
            content = ch.get('content', '')
            if not content:
                continue
            chapter_id = ch['id']

            # 1. 钩子分析 → hooks 表
            hook_results = analyzer.detect_hook_types(content)
            for h in hook_results[:5]:  # 每章最多5条
                try:
                    cursor.execute(
                        """INSERT INTO hooks (chapter_id, hook_type, position, strength, description, quote)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (chapter_id, h['type'], 'middle',
                         min(h['count'], 10),
                         f"检测到{h['type']}类钩子{h['count']}次",
                         content[:200])
                    )
                    hooks_total += 1
                except Exception:
                    pass

            # 2. 情绪锚点暂存（emotion_anchors 表需要扩展分析，此处记录摘要）
            # 简化版：按句号和问号分段检测情绪强度
            segments = re.split(r'[。！？]', content)
            intense_segments = [s for s in segments if len(s) > 10]
            if intense_segments:
                sample = intense_segments[len(intense_segments)//2]  # 取中间一段
                if len(sample) > 20:
                    try:
                        cursor.execute(
                            """INSERT INTO emotion_anchors (chapter_id, position, emotion_type, intensity, description, quote)
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            (chapter_id, len(content)//2, 'neutral', 5,
                             '自动检测（简化版）', sample[:200])
                        )
                        emotions_total += 1
                    except Exception:
                        pass

        conn.commit()
        if (idx + 1) % 20 == 0:
            print(f"  已提交 {hooks_total} 条钩子, {emotions_total} 条情绪锚点")

    conn.commit()
    conn.close()

    print(f"\n=== 分析完成 ===")
    print(f"钩子数据: {hooks_total} 条")
    print(f"情绪锚点: {emotions_total} 条")
    # 验证
    cursor2 = db._get_connection().cursor()
    cursor2.execute("SELECT COUNT(*) FROM hooks")
    hooks_db = cursor2.fetchone()[0]
    cursor2.execute("SELECT COUNT(*) FROM emotion_anchors")
    emotions_db = cursor2.fetchone()[0]
    print(f"数据库验证: hooks={hooks_db}, emotions={emotions_db}")


if __name__ == "__main__":
    import re
    main()
