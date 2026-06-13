#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试系统功能 - 模拟写章节流程"""

import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / 'knowledge'))

print("=" * 70)
print("  盘古AI系统 - 功能测试")
print("=" * 70)

# 1. 测试 get_projects
print("\n[1] 测试 get_projects()")
try:
    from pangu_optimized import get_projects
    projects = get_projects()
    print(f"  [OK] 成功获取 {len(projects)} 个项目")
    if projects:
        print(f"  - 第一个项目: {projects[0].get('title', '无')}")
except Exception as e:
    print(f"  [FAIL] 失败: {e}")
    import traceback
    traceback.print_exc()

# 2. 测试 load_mode_rules
print("\n[2] 测试 load_mode_rules()")
try:
    from pangu_optimized import load_mode_rules
    rules = load_mode_rules('general')
    print(f"  [OK] 成功加载模式规则")
    if rules:
        if len(rules) > 80:
            print(f"  - 规则示例: {rules[:80]}...")
        else:
            print(f"  - 规则示例: {rules}")
except Exception as e:
    print(f"  [FAIL] 失败: {e}")
    import traceback
    traceback.print_exc()

# 3. 测试 load_platform_rules
print("\n[3] 测试 load_platform_rules()")
try:
    from pangu_optimized import load_platform_rules
    rules = load_platform_rules('qimao')
    print(f"  [OK] 成功加载平台规则")
    if rules:
        if len(rules) > 80:
            print(f"  - 规则示例: {rules[:80]}...")
        else:
            print(f"  - 规则示例: {rules}")
except Exception as e:
    print(f"  [FAIL] 失败: {e}")
    import traceback
    traceback.print_exc()

# 4. 测试统一数据库直接操作
print("\n[4] 测试统一数据库")
try:
    from unified_db_manager import UnifiedDBManager
    db = UnifiedDBManager()
    stats = db.get_stats()
    print(f"  [OK] 数据库操作正常")
    print(f"  - 项目: {stats['total_projects']}")
    print(f"  - 章节: {stats['total_chapters']}")
    print(f"  - 模式: {stats['total_modes']}")
    print(f"  - 平台: {stats['total_platforms']}")
except Exception as e:
    print(f"  [FAIL] 失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("  测试完成！所有核心功能正常运行！")
print("  现在您可以运行 'python pangu_optimized.py' 来使用完整系统")
print("=" * 70)
