"""测试 config.py — 配置单例 + Provider路由"""
import pytest
from pangu_core.config import Config, get_config, reset_config


class TestConfig:
    def test_singleton(self):
        reset_config()
        c1 = get_config()
        c2 = get_config()
        assert c1 is c2

    def test_defaults(self):
        reset_config()
        cfg = Config()
        assert cfg.model == "deepseek-chat"
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 8192
        assert cfg.retry_times == 3

    def test_anthropic_defaults(self):
        cfg = Config()
        assert cfg.anthropic_model == "claude-sonnet-4-6-20250514"
        assert cfg.anthropic_base_url == "https://api.anthropic.com/v1"
        assert cfg.anthropic_max_tokens == 8192

    def test_stage_model_map_empty(self):
        cfg = Config()
        assert cfg.get_model_for_stage("W2") == cfg.model
        assert cfg.get_model_for_stage("W4") == cfg.model

    def test_stage_model_map_routing(self):
        cfg = Config()
        cfg.stage_model_map = {
            "W2": "deepseek-chat",
            "W4": "claude-sonnet-4-6-20250514",
        }
        assert cfg.get_model_for_stage("W2") == "deepseek-chat"
        assert cfg.get_model_for_stage("W4") == "claude-sonnet-4-6-20250514"
        assert cfg.get_model_for_stage("W3") == cfg.model  # 未配置 → 默认

    def test_to_dict_masks_keys(self):
        cfg = Config()
        cfg.api_key = "sk-secret123"
        cfg.anthropic_api_key = "sk-ant-secret456"
        d = cfg.to_dict()
        assert d["api_key"] == "***"
        assert d["anthropic_api_key"] == "***"
