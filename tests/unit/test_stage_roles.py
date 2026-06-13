"""测试 prompt_builder.py — W2/W3/W4 stage roles + 模式差异化"""
import pytest
from pangu_core.prompt_builder import PromptBuilder, _get_w4_mode_rules, _W4_MODE_RULES
from pangu_core.pipeline import PipelineContext


class TestStageRoles:
    def test_w2_dialogue_first(self):
        """W2 现在是对话优先模式，不再强制禁止项"""
        builder = PromptBuilder()
        role = builder._get_stage_role("W2", PipelineContext())
        assert "对话" in role, f"W2应强调对话，实际: {role[:80]}"
        assert "X说：" in role or "\"X说" in role, "W2应包含对话格式示例"

    def test_w2_has_dialogue_pct(self):
        """W2 必须指定对话占比"""
        role = PromptBuilder()._get_stage_role("W2", PipelineContext())
        assert "%" in role, "W2应指定对话占比百分比"

    def test_w3_outputs_fixed_skeleton(self):
        """W3 必须输出修正后的骨架供W4使用"""
        role = PromptBuilder()._get_stage_role("W3", PipelineContext())
        assert "fixed_skeleton" in role, "W3输出必须有fixed_skeleton字段"

    def test_w4_no_plot_changes(self):
        """W4 只化妆不动刀"""
        role = PromptBuilder()._get_stage_role("W4", PipelineContext())
        assert "不改" in role or "不动刀" in role or "不添加" in role


class TestW4ModeRules:
    def test_all_modes_have_rules(self):
        """所有核心模式都应有W4差异化规则"""
        core_modes = ["healing_life", "mystery", "rule_mystery", "urban_power", "general"]
        for mode in core_modes:
            rules = _get_w4_mode_rules(mode)
            assert len(rules) > 50, f"{mode} 的W4规则不应为空"

    def test_healing_mode_sensory_priority(self):
        """治愈系: 触觉优先"""
        rules = _get_w4_mode_rules("healing_life")
        assert "触觉" in rules
        assert "触觉 > 听觉" in rules or "触觉 >" in rules

    def test_mystery_mode_cinematography(self):
        """悬疑模式: 镜头语言差异化"""
        rules = _get_w4_mode_rules("mystery")
        assert "固定机位" in rules or "主观镜头" in rules or "跳切" in rules

    def test_rule_mystery_differs_from_mystery(self):
        """规则怪谈 ≠ 悬疑"""
        assert _get_w4_mode_rules("rule_mystery") != _get_w4_mode_rules("mystery")

    def test_fallback_to_general(self):
        """未知模式降级到 general"""
        rules = _get_w4_mode_rules("nonexistent_mode_xyz")
        assert len(rules) > 50
        assert "通用" in rules

    def test_fuzzy_match(self):
        """模糊匹配: healing_life_v2 → healing_life 规则"""
        rules = _get_w4_mode_rules("healing_life_v2")
        assert "触觉" in rules

    def test_w4_role_includes_mode_rules(self):
        """W4 role 应包含模式差异化规则"""
        ctx = PipelineContext()
        ctx.set("mode_name", "mystery")
        role = PromptBuilder()._get_stage_role("W4", ctx)
        assert "悬疑" in role or "mystery" in role or "视觉" in role
