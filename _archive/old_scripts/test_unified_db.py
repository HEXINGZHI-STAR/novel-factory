#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""统一数据库测试脚本"""

import sys
sys.path.insert(0, 'knowledge')
from unified_db_manager import UnifiedDBManager

print("=" * 50)
print("统一数据库测试")
print("=" * 50)

db = UnifiedDBManager()

print("\n=== 数据库统计:")
stats = db.get_stats()
for key, value in stats.items():
    print(f"  {key}: {value}")

print("\n=== 测试模式配置读取 ===")
mode = db.get_mode('general')
if mode:
    print(f"  模式名称: {mode.get('name', '无')}")
    core_principle = mode.get('core_principle', '无')
    if len(core_principle) > 100:
        print(f"  核心原则: {core_principle[:100]}...")
    else:
        print(f"  核心原则: {core_principle}")

print("\n=== 测试平台配置读取 ===")
platform = db.get_platform('qimao')
if platform:
    print(f"  平台名称: {platform.get('name', '无')}")
    core_logic = platform.get('core_logic', '无')
    if len(core_logic) > 100:
        print(f"  核心逻辑: {core_logic[:100]}...")
    else:
        print(f"  核心逻辑: {core_logic}")

print("\n=== 测试项目读取 ===")
projects = db.get_all_projects()
if projects:
    print(f"  项目数量: {len(projects)}")
    if projects:
        print(f"  第一个项目: {projects[0].get('title', '无')}")

print("\n" + "=" * 50)
print("测试完成!")
