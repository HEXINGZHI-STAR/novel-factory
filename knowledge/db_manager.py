#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI小说参考库数据库管理器
用于管理和分析网文小说参考资料
"""

import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime


class NovelReferenceDB:
    """小说参考库数据库管理器"""
    
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = Path(__file__).parent / 'novel_reference.db'
        self.db_path = db_path
        self._init_db()
    
    def _get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """初始化数据库结构"""
        schema_path = Path(__file__).parent / 'db_schema.sql'
        if not schema_path.exists():
            print(f"警告：架构文件不存在 {schema_path}")
            self._create_default_tables()
            return
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = f.read()
        
        conn = self._get_connection()
        conn.executescript(schema)
        conn.commit()
        conn.close()
        self._insert_default_tags()
    
    def _create_default_tables(self):
        """创建默认表结构（备用）"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 简化的表结构
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT,
                platform TEXT,
                genre TEXT,
                mode TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                chapter_num INTEGER NOT NULL,
                title TEXT,
                content TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (book_id) REFERENCES books(id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _insert_default_tags(self):
        """插入默认风格标签"""
        default_tags = [
            # 情绪类
            ('治愈', 'emotion', '温暖治愈的叙事风格', '#4CAF50'),
            ('爽文', 'emotion', '高情绪回报的爽文风格', '#FF9800'),
            ('压抑', 'emotion', '压抑紧张的氛围', '#607D8B'),
            ('轻松', 'emotion', '轻松幽默的风格', '#FFEB3B'),
            ('热血', 'emotion', '热血沸腾的感觉', '#F44336'),
            # 节奏类
            ('快节奏', 'rhythm', '情节紧凑快速推进', '#E91E63'),
            ('慢热', 'rhythm', '铺垫充分节奏较慢', '#3F51B5'),
            ('张弛有度', 'rhythm', '节奏把控得当', '#00BCD4'),
            # 叙事类
            ('第一人称', 'narrative', '第一人称叙述', '#9C27B0'),
            ('第三人称', 'narrative', '第三人称叙述', '#673AB7'),
            ('多视角', 'narrative', '多视角切换', '#009688'),
            # 平台适配
            ('番茄风', 'platform', '适合番茄小说的风格', '#FF5722'),
            ('起点风', 'platform', '适合起点中文的风格', '#795548'),
        ]
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        for name, category, desc, color in default_tags:
            try:
                cursor.execute(
                    'INSERT OR IGNORE INTO style_tags (name, category, description, color) VALUES (?, ?, ?, ?)',
                    (name, category, desc, color)
                )
            except:
                pass
        
        conn.commit()
        conn.close()
    
    # ========== 书籍管理 ==========
    def add_book(self, title, author=None, platform=None, genre=None, mode=None, 
                 word_count=None, chapter_count=None, is_reference=True, notes=None):
        """添加一本书"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO books (title, author, platform, genre, mode, word_count, 
                             chapter_count, is_reference, notes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (title, author, platform, genre, mode, word_count, chapter_count, 
              1 if is_reference else 0, notes))
        
        book_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return book_id
    
    def get_book(self, book_id):
        """获取书籍信息"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM books WHERE id = ?', (book_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def list_books(self, platform=None, genre=None, mode=None, only_reference=False, limit=100):
        """列出书籍"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM books WHERE 1=1'
        params = []
        
        if platform:
            query += ' AND platform = ?'
            params.append(platform)
        if genre:
            query += ' AND genre = ?'
            params.append(genre)
        if mode:
            query += ' AND mode = ?'
            params.append(mode)
        if only_reference:
            query += ' AND is_reference = 1'
        
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    # ========== 章节管理 ==========
    def add_chapter(self, book_id, chapter_num, title=None, content=None, 
                    is_opening=False, hook_strength=None):
        """添加章节"""
        word_count = len(content) if content else None
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO chapters (book_id, chapter_num, title, content, word_count, 
                                is_opening, hook_strength)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (book_id, chapter_num, title, content, word_count, 
              1 if is_opening else 0, hook_strength))
        
        chapter_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return chapter_id
    
    def get_chapters(self, book_id, limit=None):
        """获取书籍的所有章节"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM chapters WHERE book_id = ? ORDER BY chapter_num'
        if limit:
            query += ' LIMIT ?'
            cursor.execute(query, (book_id, limit))
        else:
            cursor.execute(query, (book_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    # ========== 风格标签管理 ==========
    def add_style_tag(self, name, category=None, description=None, color=None):
        """添加风格标签"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR IGNORE INTO style_tags (name, category, description, color)
            VALUES (?, ?, ?, ?)
        ''', (name, category, description, color))
        
        tag_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return tag_id
    
    def tag_book(self, book_id, tag_name, confidence=1.0):
        """给书籍打标签"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 获取或创建标签
        cursor.execute('SELECT id FROM style_tags WHERE name = ?', (tag_name,))
        row = cursor.fetchone()
        
        if row:
            tag_id = row[0]
        else:
            cursor.execute('INSERT INTO style_tags (name) VALUES (?)', (tag_name,))
            tag_id = cursor.lastrowid
        
        # 关联
        cursor.execute('''
            INSERT OR REPLACE INTO book_style_tags (book_id, tag_id, confidence)
            VALUES (?, ?, ?)
        ''', (book_id, tag_id, confidence))
        
        conn.commit()
        conn.close()
    
    def get_book_tags(self, book_id):
        """获取书籍的标签"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT st.*, bst.confidence 
            FROM style_tags st
            JOIN book_style_tags bst ON st.id = bst.tag_id
            WHERE bst.book_id = ?
        ''', (book_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    # ========== 统计信息 ==========
    def get_stats(self):
        """获取数据库统计信息"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        cursor.execute('SELECT COUNT(*) FROM books')
        stats['total_books'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM books WHERE is_reference = 1')
        stats['reference_books'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM chapters')
        stats['total_chapters'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM style_tags')
        stats['total_tags'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT platform, COUNT(*) as cnt FROM books GROUP BY platform')
        stats['by_platform'] = {row[0]: row[1] for row in cursor.fetchall() if row[0]}
        
        cursor.execute('SELECT genre, COUNT(*) as cnt FROM books GROUP BY genre')
        stats['by_genre'] = {row[0]: row[1] for row in cursor.fetchall() if row[0]}
        
        conn.close()
        return stats
    
    # ========== 数据清理 ==========
    def clear_all_data(self):
        """清空所有数据（保留表结构）"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 按顺序删除，避免外键约束问题
        cursor.execute('DELETE FROM emotion_anchors')
        cursor.execute('DELETE FROM hooks')
        cursor.execute('DELETE FROM chapters')
        cursor.execute('DELETE FROM book_style_tags')
        cursor.execute('DELETE FROM style_tags')
        cursor.execute('DELETE FROM books')
        
        conn.commit()
        conn.close()


def main():
    """测试数据库"""
    db = NovelReferenceDB()
    
    print("="*60)
    print("盘古AI小说参考库数据库")
    print("="*60)
    
    stats = db.get_stats()
    print(f"\n统计信息:")
    print(f"  总书籍数: {stats['total_books']}")
    print(f"  参考书籍: {stats['reference_books']}")
    print(f"  总章节数: {stats['total_chapters']}")
    print(f"  标签总数: {stats['total_tags']}")
    
    if stats['by_platform']:
        print(f"\n按平台: {stats['by_platform']}")
    
    print("\n数据库初始化完成！")
    print(f"数据库位置: {db.db_path}")


if __name__ == '__main__':
    main()
