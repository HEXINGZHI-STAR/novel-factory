#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试车间数据库集成
"""

import sys
from pathlib import Path

# 添加知识目录到路径
sys.path.insert(0, str(Path(__file__).parent / 'knowledge'))

print("=" * 60)
print("  测试车间数据库集成")
print("=" * 60)

try:
    from workshop_db_manager import WorkshopDBManager
    print("\n[OK] 车间数据库管理器导入成功！")
    
    db = WorkshopDBManager()
    print("[OK] 数据库连接成功！")
    
    # 测试数据库操作
    print("\n测试数据库操作:")
    
    # 1. 创建任务
    task_id = db.create_task(
        project_name="测试项目",
        chapter_num=1,
        title="测试章节",
        mode="general",
        platform="qimao"
    )
    print(f"  [OK] 创建任务成功，任务ID: {task_id}")
    
    # 2. 更新任务状态
    db.update_task_status(task_id, "running")
    print(f"  [OK] 更新任务状态为 running")
    
    # 3. 创建车间步骤
    step_id = db.create_workshop_step(task_id, 2, "测试输入")
    print(f"  [OK] 创建车间步骤成功，步骤ID: {step_id}")
    
    # 4. 完成车间步骤
    db.start_workshop_step(step_id)
    import time
    time.sleep(0.1)
    db.complete_workshop_step(
        step_id, "测试输出内容", "deepseek-v4-flash", 0.7, 100, 0.1
    )
    print(f"  [OK] 完成车间步骤")
    
    # 5. 保存章节输出
    db.save_chapter_output(task_id, "测试章节", "这是测试的章节内容...", is_final=True)
    print(f"  [OK] 保存章节输出")
    
    # 6. 更新任务状态为完成
    db.update_task_status(task_id, "completed")
    print(f"  [OK] 更新任务状态为 completed")
    
    # 7. 测试查询
    print("\n测试查询功能:")
    task = db.get_task(task_id)
    print(f"  [OK] 获取任务信息: {task['title']}")
    
    steps = db.get_workshop_steps(task_id)
    print(f"  [OK] 获取车间步骤: {len(steps)} 个步骤")
    
    outputs = db.get_chapter_outputs(task_id)
    print(f"  [OK] 获取章节输出: {len(outputs)} 个输出")
    
    stats = db.get_workshop_stats()
    print(f"  [OK] 获取统计: {stats.get('total_tasks', 0)} 个任务")
    
    print("\n" + "=" * 60)
    print("  所有测试通过！车间数据库集成成功！")
    print("=" * 60)
    
except Exception as e:
    print(f"\n[ERROR] 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
