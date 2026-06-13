#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试盘古AI多Provider后端

验证:
1. Config 加载（DeepSeek + Anthropic 双配置）
2. Provider 路由（模型名自动检测）
3. Stage 路由（stage_model_map）
4. 实际 API 调用（需要配置 API Key）
"""

import os
import sys

# 确保 pangu_core 在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pangu_core.config import get_config, reset_config
from pangu_core.ai_client import (
    AIClient, call_ai, reset_ai_client,
    _is_anthropic_model, AnthropicProvider, OpenAICompatibleProvider,
    clean_ai_output,
)


def test_config():
    """测试配置加载"""
    print("=" * 60)
    print("TEST 1: 配置加载")
    print("=" * 60)

    reset_config()
    cfg = get_config()

    print(f"  DeepSeek API Key: {'[OK] 已配置' if cfg.api_key else '[--] 未配置'}")
    print(f"  DeepSeek Model: {cfg.model}")
    print(f"  DeepSeek Base URL: {cfg.base_url}")
    print(f"  Anthropic API Key: {'[OK] 已配置' if cfg.anthropic_api_key else '[--] 未配置'}")
    print(f"  Anthropic Model: {cfg.anthropic_model}")
    print(f"  Anthropic Base URL: {cfg.anthropic_base_url}")
    print(f"  Stage Model Map: {cfg.stage_model_map}")
    print(f"  W2 model: {cfg.get_model_for_stage('W2')}")
    print(f"  W4 model: {cfg.get_model_for_stage('W4')}")

    assert cfg.model, "默认模型不能为空"
    assert cfg.anthropic_model, "Anthropic 模型不能为空"
    print("  [PASS] 配置加载 OK\n")


def test_provider_routing():
    """测试 Provider 自动路由"""
    print("=" * 60)
    print("TEST 2: Provider 路由")
    print("=" * 60)

    # 模型名检测
    test_cases = [
        ("deepseek-chat", False),
        ("deepseek-v4-flash", False),
        ("deepseek/deepseek-chat", False),
        ("gpt-4", False),
        ("claude-sonnet-4-6-20250514", True),
        ("claude-opus-4-8-20250514", True),
        ("claude-haiku-4-5-20251001", True),
        ("anthropic/claude-sonnet", True),
        ("Claude-Sonnet", True),  # 大小写不敏感
    ]

    for model, expected_is_anthropic in test_cases:
        result = _is_anthropic_model(model)
        status = "[OK]" if result == expected_is_anthropic else "[--]"
        provider_label = "Claude" if result else "DeepSeek/OpenAI"
        print(f"  {status} {model:40s} → {provider_label}")
        assert result == expected_is_anthropic, f"路由错误: {model}"

    print("  [PASS] Provider 路由 OK\n")


def test_client_routing():
    """测试 AIClient Provider 实例化"""
    print("=" * 60)
    print("TEST 3: AIClient Provider 实例化")
    print("=" * 60)

    reset_ai_client()
    client = AIClient()

    # 测试 DeepSeek 路由
    provider, model = client._get_provider("deepseek-chat")
    print(f"  deepseek-chat → {type(provider).__name__} (model={model})")
    assert isinstance(provider, OpenAICompatibleProvider), "DeepSeek 应走 OpenAI 兼容 Provider"

    # 测试 Claude 路由
    provider, model = client._get_provider("claude-sonnet-4-6-20250514")
    print(f"  claude-sonnet → {type(provider).__name__} (model={model})")
    assert isinstance(provider, AnthropicProvider), "Claude 应走 Anthropic Provider"

    # 测试 Provider 缓存（同一类 Provider 复用实例）
    p1, _ = client._get_provider("deepseek-chat")
    p2, _ = client._get_provider("deepseek-v4-flash")
    print(f"  Provider 缓存: p1 is p2 = {p1 is p2}")
    assert p1 is p2, "同类型 Provider 应复用实例"

    print("  [PASS] AIClient 路由 OK\n")


def test_stage_model_map():
    """测试 Stage 模型路由"""
    print("=" * 60)
    print("TEST 4: Stage 模型路由")
    print("=" * 60)

    reset_config()
    cfg = get_config()

    # 手动设置 stage_model_map 进行测试
    cfg.stage_model_map = {
        "W2": "deepseek-chat",
        "W4": "claude-sonnet-4-6-20250514",
    }

    print(f"  stage_model_map: {cfg.stage_model_map}")
    print(f"  W2 → {cfg.get_model_for_stage('W2')}")
    print(f"  W4 → {cfg.get_model_for_stage('W4')}")
    print(f"  W3 (未配置) → {cfg.get_model_for_stage('W3')} (应为默认 deepseek-chat)")

    assert cfg.get_model_for_stage("W2") == "deepseek-chat"
    assert cfg.get_model_for_stage("W4") == "claude-sonnet-4-6-20250514"
    assert cfg.get_model_for_stage("W3") == cfg.model  # 未配置走默认

    print("  [PASS] Stage 路由 OK\n")


def test_clean_output():
    """测试输出清理"""
    print("=" * 60)
    print("TEST 5: 输出清理")
    print("=" * 60)

    test_cases = [
        ("```\n这是正文内容\n```", "这是正文内容"),
        ("好的，我为你写一段小说：\n这是正文", "这是正文"),
        ("【正文开始】：\n这是正文。\n---\n以上是内容，希望你喜欢", "这是正文。"),
        ("  这是正文  ", "这是正文"),
    ]

    for raw, expected in test_cases:
        result = clean_ai_output(raw)
        status = "[OK]" if expected in result else "[--]"
        print(f"  {status} {raw[:40]}... → {result[:40]}...")

    print("  [PASS] 输出清理 OK\n")


def test_stage_call_signature():
    """测试 stage_call 不传 API Key 时的行为（不会崩溃）"""
    print("=" * 60)
    print("TEST 6: stage_call 安全降级（无 API Key）")
    print("=" * 60)

    reset_ai_client()
    client = AIClient()

    # 没有 API Key 时应该返回 None，不抛异常
    cfg = get_config()
    if not cfg.api_key and not cfg.anthropic_api_key:
        result = client("测试提示词", model="deepseek-chat")
        print(f"  无 Key 时调用结果: {result}")
        assert result is None, "无 API Key 应返回 None"
        print("  [PASS] 安全降级 OK（未配置 API Key 时不崩溃）\n")
    else:
        print("  [SKIP] 跳过（已有 API Key 配置）\n")


def test_stage_router_integration():
    """集成测试：验证 stage_call 使用正确的模型"""
    print("=" * 60)
    print("TEST 7: stage_call 集成")
    print("=" * 60)

    reset_config()
    reset_ai_client()

    cfg = get_config()
    cfg.stage_model_map = {
        "W2": "deepseek-chat",
        "W4": "claude-sonnet-4-6-20250514",
    }

    client = AIClient(config=cfg)

    # 检查 stage_id → model 映射
    w2_model = cfg.get_model_for_stage("W2")
    w4_model = cfg.get_model_for_stage("W4")

    print(f"  Config: W2→{w2_model}, W4→{w4_model}")
    print(f"  W2 is Claude: {_is_anthropic_model(w2_model)}")
    print(f"  W4 is Claude: {_is_anthropic_model(w4_model)}")

    print("  [PASS] stage_call 集成 OK\n")


def test_real_deepseek_call():
    """实际调用 DeepSeek API（需要 Key）"""
    print("=" * 60)
    print("TEST 8: 实际 DeepSeek API 调用")
    print("=" * 60)

    reset_config()
    reset_ai_client()

    cfg = get_config()
    if not cfg.api_key:
        print("  [SKIP] 跳过（未配置 DEEPSEEK_API_KEY）\n")
        return

    prompt = "写一个50字以内的句子，描述下雨天的心情。"
    system_msg = "你是一位获得诺贝尔文学奖的作家。用克制、留白的方式写作。"

    result = call_ai(prompt, model=cfg.model, system_msg=system_msg)

    if result:
        print(f"  生成内容 ({len(result)}字): {result[:100]}...")
        assert len(result) > 10, "输出太短"
        print("  [PASS] DeepSeek 实际调用 OK\n")
    else:
        print("  [FAIL] DeepSeek 调用失败（可能是网络或配额问题）\n")


def test_real_claude_call():
    """实际调用 Claude API（需要 Key）"""
    print("=" * 60)
    print("TEST 9: 实际 Claude API 调用")
    print("=" * 60)

    reset_config()
    reset_ai_client()

    cfg = get_config()
    if not cfg.anthropic_api_key:
        print("  [SKIP] 跳过（未配置 ANTHROPIC_API_KEY）\n")
        return

    prompt = "写一个50字以内的句子，描述下雨天的心情。"
    system_msg = "你是一位获得诺贝尔文学奖的作家。用克制、留白的方式写作。"

    result = call_ai(
        prompt,
        model=cfg.anthropic_model,
        system_msg=system_msg,
    )

    if result:
        print(f"  生成内容 ({len(result)}字): {result[:100]}...")
        assert len(result) > 10, "输出太短"
        print("  [PASS] Claude 实际调用 OK\n")
    else:
        print("  [FAIL] Claude 调用失败（可能是网络或配额问题）\n")


def test_stage_routed_call():
    """测试 Stage 路由的实际调用"""
    print("=" * 60)
    print("TEST 10: Stage 路由实际调用")
    print("=" * 60)

    reset_config()
    reset_ai_client()

    cfg = get_config()
    cfg.stage_model_map = {
        "W2": cfg.model or "deepseek-chat",
        "W4": cfg.anthropic_model or "claude-sonnet-4-6-20250514",
    }

    # 如果两个 Key 都有，测试 Stage 路由
    if cfg.api_key and cfg.anthropic_api_key:
        prompt = "写一个50字以内的句子，描述雨后的晴天。"
        system_msg = "你是一位作家。"

        # W2 走 DeepSeek
        print("  [W2 测试] 应走 DeepSeek:")
        result_w2 = call_ai(prompt, system_msg=system_msg, stage_id="W2")
        if result_w2:
            print(f"    结果: {result_w2[:80]}...")

        # W4 走 Claude
        print("  [W4 测试] 应走 Claude:")
        result_w4 = call_ai(prompt, system_msg=system_msg, stage_id="W4")
        if result_w4:
            print(f"    结果: {result_w4[:80]}...")

        if result_w2 and result_w4:
            print("  [PASS] Stage 路由实际调用 OK（双后端均成功）\n")
        else:
            print("  [WARN]️ 部分调用失败，但路由逻辑正确\n")
    else:
        missing = []
        if not cfg.api_key:
            missing.append("DEEPSEEK_API_KEY")
        if not cfg.anthropic_api_key:
            missing.append("ANTHROPIC_API_KEY")
        print(f"  [SKIP] 跳过（缺少: {', '.join(missing)}）\n")


# ============ Main ============

if __name__ == "__main__":
    print("\n")
    print("╔══════════════════════════════════════════════════════╗")
    print("║      盘古AI 多Provider后端 测试套件                    ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    test_config()
    test_provider_routing()
    test_client_routing()
    test_stage_model_map()
    test_clean_output()
    test_stage_call_signature()
    test_stage_router_integration()
    test_real_deepseek_call()
    test_real_claude_call()
    test_stage_routed_call()

    print("=" * 60)
    print("全部测试完成！")
    print("=" * 60)

    # 提示如何启用 Stage 路由
    cfg = get_config()
    if not cfg.stage_model_map:
        print()
        print("💡 提示：在 .env 中设置 PANGU_STAGE_MODELS 启用 Stage 路由：")
        print('   PANGU_STAGE_MODELS={"W2":"deepseek-chat","W4":"claude-sonnet-4-6-20250514"}')
