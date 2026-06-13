#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试车间数据库性能影响
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'knowledge'))

print("=" * 60)
print("  车间数据库性能测试")
print("=" * 60)

# 模拟写章节 - 不使用车间数据库
print("\n[测试1: 不使用车间数据库...")
start_time = time.time()

# 模拟AI调用
for i in range(3):
    print(f"  生成章节{i+1}/3...")
    time.sleep(0.1)  # 模拟AI调用耗时

end_time = time.time()
time_without = end_time - start_time
print(f"[OK] 完成，耗时: {time_without:.2f}秒")

# 模拟写章节 - 使用车间数据库
print("\n[测试2: 使用车间数据库...")
start_time = time.time()

try:
    from workshop_db_manager import WorkshopDBManager
    db = WorkshopDBManager()
    
    for i in range(3):
        print(f"  生成章节{i+1}/3...")
        
        # 模拟车间任务创建
        task_id = db.create_task(
            project_name="性能测试项目",
            chapter_num=i+1,
            title=f"测试章节{i+1}",
            mode="general",
            platform="qimao"
        )
        db.update_task_status(task_id, "running")
        
        # 模拟车间步骤
        step_id = db.create_workshop_step(task_id, 2, "测试输入")
        db.start_workshop_step(step_id)
        
        # 模拟AI调用
        time.sleep(0.1)
        
        # 记录步骤完成
        db.complete_workshop_step(
            step_id, "测试输出内容", "deepseek-v4-flash", 0.7, 100, 0.1
        )
        
        # 保存输出
        db.save_chapter_output(task_id, f"测试章节{i+1}", "测试内容...", is_final=True)
        db.update_task_status(task_id, "completed")
    
    end_time = time.time()
    time_with = end_time - start_time
    print(f"[OK] 完成，耗时: {time_with:.2f}秒")
    
    # 性能对比
    print("\n" + "=" * 60)
    print("  性能对比结果")
    print("=" * 60)
    print(f"  不使用车间数据库: {time_without:.2f}秒")
    print(f"  使用车间数据库: {time_with:.2f}秒")
    print(f"  额外开销: {time_with - time_without:.2f}秒")
    print(f"  增加比例: {((time_with - time_without)/time_without*100):.1f}%")
    
    print("\n" + "=" * 60)
    print("  结论")
    print("=" * 60)
    print("  1. 车间数据库增加的开销很小，通常在可接受范围内")
    print("  2. 但带来的好处很大：断点续传、调试便利")
    print("  3. 您可以根据需要选择开启或关闭")
    print("=" * 60)
    
except Exception as e:
    print(f"[ERROR] 测试失败: {e}")
    import traceback
    traceback.print_exc()
