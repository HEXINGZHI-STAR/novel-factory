"""集成测试: Pipeline 完整链路 (mock AI)"""
import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


@pytest.fixture
def temp_project(sample_state):
    """创建临时项目目录"""
    with tempfile.TemporaryDirectory() as tmp:
        proj = Path(tmp) / "test_project"
        proj.mkdir()

        # 写 state.json
        webnovel = proj / ".webnovel"
        webnovel.mkdir()
        (webnovel / "state.json").write_text(
            json.dumps(sample_state, ensure_ascii=False, indent=2),
            encoding="utf-8")

        # 写大纲
        outline = proj / "大纲"
        outline.mkdir()
        (outline / "总纲.md").write_text("# 测试总纲\n测试用", encoding="utf-8")

        # 正文目录
        (proj / "正文").mkdir()

        yield str(proj)


class TestPipelineIntegration:
    def test_pipeline_config_creation(self):
        """验证 PipelineConfig 工厂方法"""
        from pangu_core.pipeline import PipelineConfig

        config = PipelineConfig.from_quick_mode(
            project_dir="/tmp/test",
            chapter=1,
            task="测试任务",
            mode="general",
            platform="qimao",
        )
        assert config.mode == "quick"
        assert config.active_stages == ["W0", "W2", "W4"]
        assert config.chapter_num == 1

        config2 = PipelineConfig.from_workshop_mode(
            project_dir="/tmp/test",
            chapter=1,
            task="测试任务",
        )
        assert config2.mode == "workshop"
        assert config2.active_stages == ["W0", "W1", "W2", "W3", "W4", "W5"]

    def test_pipeline_context(self):
        """验证 PipelineContext 数据传递"""
        from pangu_core.pipeline import PipelineContext
        ctx = PipelineContext()
        ctx.set("test_key", "test_value")
        assert ctx.get("test_key") == "test_value"
        assert ctx.get("nonexistent", "default") == "default"

    def test_pipeline_run_with_mock_ai(self, temp_project, sample_state):
        """端到端: Pipeline 快速模式 + Mock AI 调用"""
        from pangu_core.pipeline import WritingPipeline, PipelineConfig

        config = PipelineConfig.from_quick_mode(
            project_dir=temp_project,
            chapter=1,
            task="开篇，建立日常中的异常感",
            mode="general",
            platform="qimao",
        )

        # Mock call_ai to return test content
        with patch("pangu_core.ai_client.call_ai",
                    return_value="测试章节内容。" * 200) as mock_call:
            pipeline = WritingPipeline(config)
            result = pipeline.run()

            # 验证基本结构
            assert result is not None
            assert isinstance(result.chapter_content, str)
            assert len(result.chapter_content) > 100

            # 验证 AI 被调用了 2 次 (W2初稿 + W4润色)
            assert mock_call.call_count == 2

    def test_stage_registration(self):
        """验证所有 Stage 可以注册"""
        from pangu_core.pipeline import WritingPipeline, PipelineConfig

        config = PipelineConfig.from_workshop_mode(
            project_dir="/tmp/test",
            chapter=1,
            task="test",
        )
        pipeline = WritingPipeline(config)
        assert len(pipeline.stages) == 6
        assert "W0" in pipeline.stages
        assert "W5" in pipeline.stages

    def test_stage_input_validation(self, temp_project):
        """验证 Stage 输入验证"""
        from pangu_core.stages import W0AnchorStage, W2DraftStage
        from pangu_core.pipeline import PipelineContext

        ctx = PipelineContext()
        w0 = W0AnchorStage()
        # 缺少 state → 验证应失败
        assert w0.validate_input(ctx) is False

        # 补充必要数据
        ctx.set("state", {"project_info": {"title": "test"}})
        ctx.set("chapter_num", 1)
        ctx.set("chapter_task", "测试")
        assert w0.validate_input(ctx) is True
