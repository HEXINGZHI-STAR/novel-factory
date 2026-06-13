#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
对比测试优化前后的性能
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'knowledge'))

print("=" * 60)
print("  车间数据库性能对比测试")
print("=" * 60)

# 测试原始版
print("\n[测试1: 原始版车间数据库...")
start_time = time.time()

try:
    from workshop_db_manager import WorkshopDBManager
    db_old = WorkshopDBManager()
    
    for i in range(3):
        print(f"  生成章节{i+1}/3...")
        
        task_id = db_old.create_task(
            project_name="性能测试项目",
            chapter_num=i+1,
            title=f"测试章节{i+1}",
            mode="general",
            platform="qimao"
        )
        db_old.update_task_status(task_id, "running")
        
        step_id = db_old.create_workshop_step(task_id, 2, "测试输入")
        db_old.start_workshop_step(step_id)
        
        time.sleep(0.1)
        
        db_old.complete_workshop_step(
            step_id, "测试输出内容", "deepseek-v4-flash", 0.7, 100, 0.1
        )
        
        db_old.save_chapter_output(task_id, f"测试章节{i+1}", "测试内容...", is_final=True)
        db_old.update_task_status(task_id, "completed")
    
    end_time = time.time()
    time_old = end_time - start_time
    print(f"[OK] 原始版完成，耗时: {time_old:.2f}秒")
except Exception as e:
    print(f"[ERROR] 原始版测试失败: {e}")
    time_old = None

# 测试优化版
print("\n[测试2: 优化版车间数据库...")
start_time = time.time()

try:
    from workshop_db_manager_optimized import WorkshopDBManagerOptimized
    db_new = WorkshopDBManagerOptimized()
    
    for i in range(3):
        print(f"  生成章节{i+1}/3...")
        
        task_id = db_new.create_task(
            project_name="性能测试项目",
            chapter_num=i+1,
            title=f"测试章节{i+1}",
            mode="general",
            platform="qimao"
        )
        db_new.update_task_status(task_id, "running")
        
        step_id = db_new.create_workshop_step(task_id, 2, "测试输入")
        db_new.start_workshop_step(step_id)
        
        time.sleep(0.1)
        
        db_new.complete_workshop_step(
            step_id, "测试输出内容", "deepseek-v4-flash", 0.7, 100, 0.1
        )
        
        db_new.save_chapter_output(task_id, f"测试章节{i+1}", "测试内容...", is_final=True)
        db_new.update_task_status(task_id, "completed")
    
    end_time = time.time()
    time_new = end_time - start_time
    print(f"[OK] 优化版完成，耗时: {time_new:.2f}秒")
    db_new.close()
except Exception as e:
    print(f"[ERROR] 优化版测试失败: {e}")
    time_new = None

# 对比结果
if time_old and time_new:
    print("\n" + "=" * 60)
    print("  性能对比结果")
    print("=" * 60)
    print(f"  原始版: {time_old:.2f}秒")
    print(f"  优化版: {time_new:.2f}秒")
    print(f"  性能提升: {((time_old - time_new)/time_old*100):.1f}%")
    print(f"  速度提升: {(time_old/time_new):.1f}倍")
    
    print("\n" + "=" * 60)
    print("  优化措施")
    print("=" * 60)
    print("  1. 保持数据库连接 - 避免重复打开/关闭")
    print("  2. 使用事务批量提交 - 减少磁盘IO")
    print("  3. 优化SQL操作 - 提高执行效率")
    print("=" * 60)
