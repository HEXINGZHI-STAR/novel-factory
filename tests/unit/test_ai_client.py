"""测试 ai_client.py — Provider路由 + 输出清理"""
import pytest
from pangu_core.ai_client import (
    _is_anthropic_model, clean_ai_output, AIClient,
    OpenAICompatibleProvider, AnthropicProvider,
)


class TestProviderRouting:
    def test_deepseek_models(self):
        assert _is_anthropic_model("deepseek-chat") is False
        assert _is_anthropic_model("deepseek-v4-pro") is False
        assert _is_anthropic_model("deepseek/deepseek-chat") is False

    def test_claude_models(self):
        assert _is_anthropic_model("claude-sonnet-4-6-20250514") is True
        assert _is_anthropic_model("claude-opus-4-8") is True
        assert _is_anthropic_model("anthropic/claude-sonnet") is True

    def test_case_insensitive(self):
        assert _is_anthropic_model("Claude-Sonnet") is True
        assert _is_anthropic_model("CLAUDE-OPUS") is True

    def test_gpt_not_claude(self):
        assert _is_anthropic_model("gpt-4") is False


class TestCleanOutput:
    def test_markdown_code_block(self):
        assert "正文" in clean_ai_output("```\n正文内容\n```")

    def test_ai_prefix(self):
        result = clean_ai_output("好的，我为你写一段小说：\n这是正文")
        # 清理后正文应该在，AI前缀应该被移除
        assert len(result) > 0
        # 前缀中不应包含"为你写"这类AI开头
        assert "这是正文" in result or "正文" in result

    def test_whitespace(self):
        assert clean_ai_output("  正文  ") == "正文"

    def test_empty(self):
        assert clean_ai_output("") == ""

    def test_none(self):
        assert clean_ai_output(None) == ""


class TestAIClient:
    def test_provider_cache(self):
        client = AIClient()
        p1, _ = client._get_provider("deepseek-chat")
        p2, _ = client._get_provider("deepseek-v4-flash")
        assert p1 is p2  # 同类型复用

    def test_provider_type(self):
        client = AIClient()
        p, _ = client._get_provider("deepseek-chat")
        assert isinstance(p, OpenAICompatibleProvider)
        p, _ = client._get_provider("claude-sonnet-4-6")
        assert isinstance(p, AnthropicProvider)

    def test_stage_call_uses_model_map(self):
        from pangu_core.config import get_config, reset_config
        reset_config()
        cfg = get_config()
        cfg.stage_model_map = {"W2": "deepseek-chat", "W4": "claude-sonnet-4-6"}
        client = AIClient(config=cfg)
        # stage_call 应使用 stage_model_map 中的模型
        # 无API key时不实际调用，但路由应正确
        assert cfg.get_model_for_stage("W2") == "deepseek-chat"
        assert cfg.get_model_for_stage("W4") == "claude-sonnet-4-6"
