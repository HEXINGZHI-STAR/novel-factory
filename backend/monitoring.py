# -*- coding: utf-8 -*-
"""
盘古AI 监控和统计系统
追踪 LLM 调用、性能指标、错误日志
"""

import time
import json
from datetime import datetime
from typing import Dict, List, Any
from threading import Lock


class LLMCallStats:
    """LLM 调用统计"""
    
    def __init__(self):
        self.stats = {
            "total_calls": 0,
            "success_calls": 0,
            "failed_calls": 0,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_latency": 0,
            "avg_latency": 0,
            "call_history": [],
            "model_usage": {},
            "workshop_usage": {},
            "error_types": {}
        }
        self.lock = Lock()
    
    def record_call(self, workshop: str, model: str, success: bool, 
                   latency: float, prompt_tokens: int = 0, 
                   completion_tokens: int = 0, error: str = ""):
        """记录 LLM 调用"""
        with self.lock:
            self.stats["total_calls"] += 1
            self.stats["total_tokens"] += prompt_tokens + completion_tokens
            self.stats["prompt_tokens"] += prompt_tokens
            self.stats["completion_tokens"] += completion_tokens
            self.stats["total_latency"] += latency
            
            # 更新模型使用统计
            if model not in self.stats["model_usage"]:
                self.stats["model_usage"][model] = {
                    "calls": 0,
                    "success": 0,
                    "failed": 0,
                    "total_tokens": 0
                }
            self.stats["model_usage"][model]["calls"] += 1
            self.stats["model_usage"][model]["total_tokens"] += prompt_tokens + completion_tokens
            
            # 更新车间使用统计
            if workshop not in self.stats["workshop_usage"]:
                self.stats["workshop_usage"][workshop] = {
                    "calls": 0,
                    "success": 0,
                    "failed": 0,
                    "avg_latency": 0,
                    "total_latency": 0
                }
            self.stats["workshop_usage"][workshop]["calls"] += 1
            self.stats["workshop_usage"][workshop]["total_latency"] += latency
            
            if success:
                self.stats["success_calls"] += 1
                self.stats["model_usage"][model]["success"] += 1
                self.stats["workshop_usage"][workshop]["success"] += 1
            else:
                self.stats["failed_calls"] += 1
                self.stats["model_usage"][model]["failed"] += 1
                self.stats["workshop_usage"][workshop]["failed"] += 1
                
                # 记录错误类型
                error_type = error.split(":")[0] if ":" in error else "Unknown"
                self.stats["error_types"][error_type] = \
                    self.stats["error_types"].get(error_type, 0) + 1
            
            # 更新平均延迟
            if self.stats["total_calls"] > 0:
                self.stats["avg_latency"] = self.stats["total_latency"] / self.stats["total_calls"]
            
            for workshop in self.stats["workshop_usage"]:
                calls = self.stats["workshop_usage"][workshop]["calls"]
                if calls > 0:
                    self.stats["workshop_usage"][workshop]["avg_latency"] = \
                        self.stats["workshop_usage"][workshop]["total_latency"] / calls
            
            # 记录最近调用历史（保留最近100条）
            call_record = {
                "timestamp": datetime.now().isoformat(),
                "workshop": workshop,
                "model": model,
                "success": success,
                "latency": latency,
                "tokens": prompt_tokens + completion_tokens,
                "error": error[:100] if error else ""
            }
            self.stats["call_history"].append(call_record)
            if len(self.stats["call_history"]) > 100:
                self.stats["call_history"].pop(0)
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        with self.lock:
            return self.stats.copy()
    
    def reset_stats(self):
        """重置统计"""
        with self.lock:
            self.stats = {
                "total_calls": 0,
                "success_calls": 0,
                "failed_calls": 0,
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_latency": 0,
                "avg_latency": 0,
                "call_history": [],
                "model_usage": {},
                "workshop_usage": {},
                "error_types": {}
            }


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics = {
            "requests": {
                "total": 0,
                "success": 0,
                "failed": 0,
                "avg_response_time": 0,
                "total_response_time": 0
            },
            "pipeline": {
                "total_runs": 0,
                "success_runs": 0,
                "failed_runs": 0,
                "avg_duration": 0,
                "total_duration": 0,
                "workshop_timings": {}
            },
            "memory": {
                "current_tasks": 0,
                "max_concurrent_tasks": 0,
                "queue_length": 0
            },
            "errors": []
        }
        self.lock = Lock()
    
    def record_request(self, success: bool, response_time: float):
        """记录请求"""
        with self.lock:
            self.metrics["requests"]["total"] += 1
            self.metrics["requests"]["total_response_time"] += response_time
            
            if success:
                self.metrics["requests"]["success"] += 1
            else:
                self.metrics["requests"]["failed"] += 1
            
            if self.metrics["requests"]["total"] > 0:
                self.metrics["requests"]["avg_response_time"] = \
                    self.metrics["requests"]["total_response_time"] / \
                    self.metrics["requests"]["total"]
    
    def record_pipeline_run(self, success: bool, duration: float, workshop_timings: dict = None):
        """记录流水线运行"""
        with self.lock:
            self.metrics["pipeline"]["total_runs"] += 1
            self.metrics["pipeline"]["total_duration"] += duration
            
            if success:
                self.metrics["pipeline"]["success_runs"] += 1
            else:
                self.metrics["pipeline"]["failed_runs"] += 1
            
            if self.metrics["pipeline"]["total_runs"] > 0:
                self.metrics["pipeline"]["avg_duration"] = \
                    self.metrics["pipeline"]["total_duration"] / \
                    self.metrics["pipeline"]["total_runs"]
            
            # 记录各车间耗时
            if workshop_timings:
                for workshop, timing in workshop_timings.items():
                    if workshop not in self.metrics["pipeline"]["workshop_timings"]:
                        self.metrics["pipeline"]["workshop_timings"][workshop] = {
                            "total": 0,
                            "count": 0,
                            "avg": 0
                        }
                    self.metrics["pipeline"]["workshop_timings"][workshop]["total"] += timing
                    self.metrics["pipeline"]["workshop_timings"][workshop]["count"] += 1
                    self.metrics["pipeline"]["workshop_timings"][workshop]["avg"] = \
                        self.metrics["pipeline"]["workshop_timings"][workshop]["total"] / \
                        self.metrics["pipeline"]["workshop_timings"][workshop]["count"]
    
    def record_error(self, error: str, context: dict = None):
        """记录错误"""
        with self.lock:
            error_record = {
                "timestamp": datetime.now().isoformat(),
                "error": error,
                "context": context or {}
            }
            self.metrics["errors"].append(error_record)
            if len(self.metrics["errors"]) > 50:
                self.metrics["errors"].pop(0)
    
    def update_memory_stats(self, current_tasks: int, queue_length: int):
        """更新内存统计"""
        with self.lock:
            self.metrics["memory"]["current_tasks"] = current_tasks
            self.metrics["memory"]["queue_length"] = queue_length
            if current_tasks > self.metrics["memory"]["max_concurrent_tasks"]:
                self.metrics["memory"]["max_concurrent_tasks"] = current_tasks
    
    def get_metrics(self) -> dict:
        """获取性能指标"""
        with self.lock:
            return self.metrics.copy()
    
    def get_health_status(self) -> dict:
        """获取健康状态"""
        with self.lock:
            requests = self.metrics["requests"]
            pipeline = self.metrics["pipeline"]
            
            # 计算成功率
            request_success_rate = requests["success"] / max(requests["total"], 1) * 100
            pipeline_success_rate = pipeline["success_runs"] / max(pipeline["total_runs"], 1) * 100
            
            # 健康状态判断
            status = "healthy"
            if request_success_rate < 90 or pipeline_success_rate < 90:
                status = "degraded"
            if request_success_rate < 70 or pipeline_success_rate < 70:
                status = "unhealthy"
            
            return {
                "status": status,
                "request_success_rate": round(request_success_rate, 2),
                "pipeline_success_rate": round(pipeline_success_rate, 2),
                "avg_request_time": round(self.metrics["requests"]["avg_response_time"], 2),
                "avg_pipeline_duration": round(self.metrics["pipeline"]["avg_duration"], 2),
                "current_tasks": self.metrics["memory"]["current_tasks"],
                "queue_length": self.metrics["memory"]["queue_length"],
                "recent_errors": len(self.metrics["errors"])
            }


# 全局监控实例
llm_stats = LLMCallStats()
performance_monitor = PerformanceMonitor()


def record_llm_call(workshop: str, model: str, success: bool, 
                   latency: float, prompt_tokens: int = 0, 
                   completion_tokens: int = 0, error: str = ""):
    """记录 LLM 调用"""
    llm_stats.record_call(workshop, model, success, latency, 
                         prompt_tokens, completion_tokens, error)


def record_request(success: bool, response_time: float):
    """记录请求"""
    performance_monitor.record_request(success, response_time)


def record_pipeline_run(success: bool, duration: float, workshop_timings: dict = None):
    """记录流水线运行"""
    performance_monitor.record_pipeline_run(success, duration, workshop_timings)


def record_error(error: str, context: dict = None):
    """记录错误"""
    performance_monitor.record_error(error, context)


def update_memory_stats(current_tasks: int, queue_length: int):
    """更新内存统计"""
    performance_monitor.update_memory_stats(current_tasks, queue_length)


def get_llm_stats() -> dict:
    """获取 LLM 统计"""
    return llm_stats.get_stats()


def get_performance_metrics() -> dict:
    """获取性能指标"""
    return performance_monitor.get_metrics()


def get_health_status() -> dict:
    """获取健康状态"""
    return performance_monitor.get_health_status()


def reset_stats():
    """重置统计"""
    llm_stats.reset_stats()