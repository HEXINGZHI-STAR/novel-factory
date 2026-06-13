#!/usr/bin/env python3
# 检查关键表的数据

import sqlite3

conn = sqlite3.connect('knowledge/novel_reference.db')
cursor = conn.cursor()

# 检查关键表
for table in ['hooks', 'emotion_anchors', 'writing_techniques', 'books', 'chapters']:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"{table}: {count} 条记录")

conn.close()
