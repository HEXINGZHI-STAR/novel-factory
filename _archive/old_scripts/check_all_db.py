#!/usr/bin/env python3
# 检查所有数据库

import sqlite3

dbs = [
    'knowledge/unified_novel.db',
    'knowledge/novel_reference.db',
    'knowledge/creative_engine.db'
]

for db_path in dbs:
    print(f"\n=== {db_path} ===")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cursor.fetchall()]
        print("表列表:", tables)
        
        for table in tables[:3]:  # 只显示前3个表的记录数
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count} 条记录")
        
        conn.close()
    except Exception as e:
        print(f"  错误: {e}")
