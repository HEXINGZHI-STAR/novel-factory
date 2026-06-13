"""
盘古AI核心库 (pangu_core)

借鉴 Go/Rust 的模块设计思想:
- 每个模块职责单一，只做一件事
- 显式导出公共API（__all__），内部实现私有化
- 统一入口，消除重复代码
- 配置集中管理，一处定义处处使用
"""

from .config import Config, get_config, PIPELINE_CONFIG
from .ai_client import AIClient, call_ai, clean_ai_output
from .db import DatabaseManager, get_db
from .prompts import KnowledgeInjector, SentenceParams, build_system_prompt
from .pipeline import (
    WritingPipeline, PipelineConfig, PipelineContext,
    PipelineResult, StageOutput,
)
from .stages import (
    BaseStage, W0AnchorStage, W1SetupStage, W2DraftStage,
    W3QCStage, W4PolishStage, W5ExportStage,
)
from .prompt_builder import PromptBuilder

__all__ = [
    "Config", "get_config", "PIPELINE_CONFIG",
    "AIClient", "call_ai", "clean_ai_output",
    "DatabaseManager", "get_db",
    "KnowledgeInjector", "SentenceParams", "build_system_prompt",
    "WritingPipeline", "PipelineConfig", "PipelineContext",
    "PipelineResult", "StageOutput",
    "BaseStage", "W0AnchorStage", "W1SetupStage", "W2DraftStage",
    "W3QCStage", "W4PolishStage", "W5ExportStage",
    "PromptBuilder",
]
