#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""快速测试主程序导入功能"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / 'knowledge'))

print("=" * 60)
print("  盘古AI系统 - 快速测试")
print("=" * 60)

print("\n[1] 测试数据库连接...")
try:
    from unified_db_manager import UnifiedDBManager
    db = UnifiedDBManager()
    print("  [OK] 数据库连接成功")
    stats = db.get_stats()
    print(f"  统计: {stats}")
except Exception as e:
    print(f"  [FAIL] 数据库连接失败: {e}")

print("\n[2] 测试模式配置读取...")
try:
    from unified_db_manager import UnifiedDBManager
    db = UnifiedDBManager()
    mode = db.get_mode('general')
    if mode:
        print(f"  [OK] 成功读取模式: {mode.get('name', '无')}")
    else:
        print(f"  [FAIL] 模式未找到")
except Exception as e:
    print(f"  [FAIL] 模式读取失败: {e}")

print("\n[3] 测试平台配置读取...")
try:
    from unified_db_manager import UnifiedDBManager
    db = UnifiedDBManager()
    platform = db.get_platform('qimao')
    if platform:
        print(f"  [OK] 成功读取平台: {platform.get('name', '无')}")
    else:
        print(f"  [FAIL] 平台未找到")
except Exception as e:
    print(f"  [FAIL] 平台读取失败: {e}")

print("\n" + "=" * 60)
print("  快速测试完成！")
print("  现在您可以运行 'python pangu_optimized.py' 来启动完整系统")
print("=" * 60)
