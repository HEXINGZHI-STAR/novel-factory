#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
盘古AI系统 - 数据库迁移脚本
将所有JSON配置和项目数据迁移到统一数据库
"""

import sys
from pathlib import Path

# 添加知识目录到路径
sys.path.insert(0, str(Path(__file__).parent / 'knowledge'))

from unified_db_manager import UnifiedDBManager

def main():
    """主迁移函数"""
    print("=" * 70)
    print("盘古AI系统 - 数据库迁移工具")
    print("=" * 70)

    # 初始化数据库
    print("\n[1/4] 初始化数据库...")
    db = UnifiedDBManager()
    print("[OK] 数据库初始化完成！")

    # 导入模式配置
    print("\n[2/4] 导入模式配置...")
    modes_dir = Path(__file__).parent / 'modes'

    if modes_dir.exists():
        for mode_file in modes_dir.glob('*.json'):
            if mode_file.name in ['index.json']:
                continue
            try:
                db.import_mode_from_json(str(mode_file))
            except Exception as e:
                print(f"[ERROR] 导入模式失败 {mode_file}: {e}")
                import traceback
                traceback.print_exc()
    else:
        print(f"[WARN] 模式目录不存在: {modes_dir}")

    # 导入平台配置
    print("\n[3/4] 导入平台配置...")
    platform_file = Path(__file__).parent / 'knowledge' / 'platform_writing_profiles.json'
    if platform_file.exists():
        db.import_platforms_from_json(str(platform_file))
    else:
        print(f"[WARN] 平台配置文件不存在: {platform_file}")

    # 迁移现有项目
    print("\n[4/4] 迁移现有项目...")
    projects_dir = Path(__file__).parent / 'projects'
    if projects_dir.exists():
        db.migrate_existing_projects(str(projects_dir))
    else:
        print(f"[WARN] 项目目录不存在: {projects_dir}")

    # 显示统计
    print("\n" + "=" * 70)
    print("迁移完成！数据库统计:")
    print("=" * 70)

    stats = db.get_stats()
    print(f"[项目] 项目数: {stats['total_projects']}")
    print(f"[章节] 章节数: {stats['total_chapters']}")
    print(f"[模式] 模式数: {stats['total_modes']}")
    print(f"[平台] 平台数: {stats['total_platforms']}")
    print(f"[车间] 车间任务: {stats['total_workshop_tasks']}")
    print(f"[书籍] 参考书籍: {stats['total_books']}")

    # 显示模式列表
    print("\n[模式] 已导入的模式:")
    modes = db.get_all_modes()
    for mode in modes:
        print(f"  - {mode['mode_id']}: {mode['name']}")

    # 显示平台列表
    print("\n[平台] 已导入的平台:")
    platforms = db.get_all_platforms()
    for platform in platforms:
        print(f"  - {platform['platform_id']}: {platform['name']}")

    print("\n" + "=" * 70)
    print("[OK] 迁移成功完成！现在可以使用统一数据库了！")
    print("=" * 70)
    
    db.close()


if __name__ == '__main__':
    main()
