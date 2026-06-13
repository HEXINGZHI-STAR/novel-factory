#!/usr/bin/env python3
# 测试监控 API

import requests

def test_monitoring():
    print("=== 测试监控 API ===")
    
    # 测试仪表盘
    print("\n1. 综合仪表盘")
    response = requests.get("http://127.0.0.1:5001/api/v7/dashboard")
    result = response.json()
    print(f"   状态: {response.status_code}")
    print(f"   LLM调用数: {result.get('llm_stats', {}).get('total_calls', 0)}")
    print(f"   健康状态: {result.get('health', {}).get('status', 'unknown')}")
    
    # 测试 LLM 统计
    print("\n2. LLM 调用统计")
    response = requests.get("http://127.0.0.1:5001/api/v7/observability/stats")
    result = response.json()
    print(f"   状态: {response.status_code}")
    stats = result.get('stats', result)
    print(f"   总调用: {stats.get('total_calls', 0)}")
    print(f"   成功: {stats.get('success_calls', 0)}")
    print(f"   失败: {stats.get('failed_calls', 0)}")
    print(f"   平均延迟: {stats.get('avg_latency', 0):.2f}s")
    
    # 测试健康状态
    print("\n3. 健康状态")
    response = requests.get("http://127.0.0.1:5001/api/v7/observability/health")
    result = response.json()
    print(f"   状态: {response.status_code}")
    health = result.get('health', result)
    print(f"   系统状态: {health.get('status', 'unknown')}")
    print(f"   请求成功率: {health.get('request_success_rate', 0):.2f}%")
    print(f"   流水线成功率: {health.get('pipeline_success_rate', 0):.2f}%")
    
    # 测试任务列表
    print("\n4. 任务列表")
    response = requests.get("http://127.0.0.1:5001/api/v7/tasks")
    result = response.json()
    print(f"   状态: {response.status_code}")
    print(f"   任务数: {len(result.get('tasks', []))}")

if __name__ == "__main__":
    test_monitoring()
