# -*- coding: utf-8 -*-
"""
盘古AI 任务队列和异步处理系统
支持请求排队、异步执行、任务状态追踪
"""

import json
import uuid
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from queue import Queue
from threading import Thread, Lock
from enum import Enum


class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Task:
    """任务对象"""
    
    def __init__(self, task_id: str, data: dict, priority: int = 1):
        self.task_id = task_id
        self.data = data
        self.priority = priority
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None
        self.result = None
        self.error = None
        self.progress = 0
        self.logs = []
    
    def start(self):
        """开始执行"""
        self.status = TaskStatus.PROCESSING
        self.started_at = datetime.now()
    
    def complete(self, result: dict):
        """完成任务"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        self.result = result
        self.progress = 100
    
    def fail(self, error: str):
        """任务失败"""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
        self.error = error
    
    def update_progress(self, progress: int, message: str = ""):
        """更新进度"""
        self.progress = progress
        if message:
            self.logs.append({
                "time": datetime.now().isoformat(),
                "progress": progress,
                "message": message
            })
    
    def to_dict(self):
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress,
            "logs": self.logs,
            "error": self.error
        }


class TaskQueue:
    """任务队列管理器"""
    
    def __init__(self, max_workers: int = 2):
        self.queue = Queue()
        self.tasks: Dict[str, Task] = {}
        self.workers: List[Thread] = []
        self.max_workers = max_workers
        self.lock = Lock()
        self.running = False
        self.process_fn = None
    
    def set_process_fn(self, process_fn):
        """设置任务处理函数"""
        self.process_fn = process_fn
    
    def enqueue(self, data: dict, priority: int = 1) -> str:
        """入队任务"""
        task_id = str(uuid.uuid4())[:8]
        task = Task(task_id, data, priority)
        
        with self.lock:
            self.tasks[task_id] = task
        
        # 根据优先级插入队列
        self.queue.put((priority, task_id))
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务状态"""
        with self.lock:
            return self.tasks.get(task_id)
    
    def get_tasks(self, status: Optional[TaskStatus] = None) -> List[Task]:
        """获取任务列表"""
        with self.lock:
            if status:
                return [t for t in self.tasks.values() if t.status == status]
            return list(self.tasks.values())
    
    def remove_task(self, task_id: str):
        """移除任务"""
        with self.lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
    
    def worker(self):
        """工作线程"""
        while self.running:
            try:
                priority, task_id = self.queue.get(timeout=1)
                
                with self.lock:
                    task = self.tasks.get(task_id)
                    if not task:
                        self.queue.task_done()
                        continue
                
                task.start()
                
                try:
                    # 执行任务
                    result = self.process_fn(task)
                    task.complete(result)
                except Exception as e:
                    task.fail(str(e))
                
                self.queue.task_done()
            except Exception:
                continue
    
    def start(self):
        """启动队列"""
        if not self.process_fn:
            raise ValueError("process_fn 未设置")
        
        self.running = True
        for _ in range(self.max_workers):
            worker = Thread(target=self.worker, daemon=True)
            worker.start()
            self.workers.append(worker)
    
    def stop(self):
        """停止队列"""
        self.running = False
        for worker in self.workers:
            worker.join(timeout=5)


class TaskMonitor:
    """任务监控器"""
    
    def __init__(self):
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "pending_tasks": 0,
            "processing_tasks": 0,
            "avg_processing_time": 0,
            "total_processing_time": 0,
            "error_counts": {},
            "daily_stats": {}
        }
        self.lock = Lock()
    
    def record_task(self, task: Task):
        """记录任务统计"""
        with self.lock:
            self.stats["total_tasks"] += 1
            
            today = datetime.now().strftime("%Y-%m-%d")
            if today not in self.stats["daily_stats"]:
                self.stats["daily_stats"][today] = {
                    "total": 0,
                    "completed": 0,
                    "failed": 0
                }
            self.stats["daily_stats"][today]["total"] += 1
            
            if task.status == TaskStatus.COMPLETED:
                self.stats["completed_tasks"] += 1
                self.stats["daily_stats"][today]["completed"] += 1
                
                if task.started_at and task.completed_at:
                    duration = (task.completed_at - task.started_at).total_seconds()
                    self.stats["total_processing_time"] += duration
                    self.stats["avg_processing_time"] = \
                        self.stats["total_processing_time"] / self.stats["completed_tasks"]
            
            elif task.status == TaskStatus.FAILED:
                self.stats["failed_tasks"] += 1
                self.stats["daily_stats"][today]["failed"] += 1
                
                error_type = task.error.split(":")[0] if ":" in task.error else "Unknown"
                self.stats["error_counts"][error_type] = \
                    self.stats["error_counts"].get(error_type, 0) + 1
    
    def update_status_counts(self):
        """更新状态计数"""
        # 由外部调用更新
        pass
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        with self.lock:
            return self.stats.copy()


# 全局队列实例
task_queue = TaskQueue(max_workers=2)
task_monitor = TaskMonitor()


def init_task_queue(process_fn):
    """初始化任务队列"""
    task_queue.set_process_fn(process_fn)
    task_queue.start()


def submit_task(data: dict, priority: int = 1) -> str:
    """提交任务到队列"""
    return task_queue.enqueue(data, priority)


def get_task_status(task_id: str) -> Optional[dict]:
    """获取任务状态"""
    task = task_queue.get_task(task_id)
    if task:
        return task.to_dict()
    return None


def get_all_tasks() -> List[dict]:
    """获取所有任务"""
    return [t.to_dict() for t in task_queue.get_tasks()]


def get_task_stats() -> dict:
    """获取任务统计"""
    return task_monitor.get_stats()


def shutdown_task_queue():
    """关闭任务队列"""
    task_queue.stop()