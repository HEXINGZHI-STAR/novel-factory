#!/usr/bin/env python3
# 检查数据库结构

import sqlite3

conn = sqlite3.connect('knowledge/unified_novel.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
print("数据库表列表:", tables)

# 检查 hooks, emotion_anchors, writing_techniques 表
for table in ['hooks', 'emotion_anchors', 'writing_techniques']:
    if table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"{table}: {count} 条记录")
    else:
        print(f"{table}: 不存在")

conn.close()
