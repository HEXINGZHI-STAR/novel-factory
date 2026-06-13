"""
盘古AI - 统一配置管理

之前: load_config() 在 pangu_optimized.py/pangu_plus.py/pangu_pipeline.py 各写一份
现在: 一处定义，全局单例，所有模块共享
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 项目根目录（所有路径的锚点）
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECTS_DIR = BASE_DIR / "projects"
PROJECTS_DIR.mkdir(exist_ok=True)


@dataclass
class Config:
    """
    全局配置，单例模式。
    借鉴 Rust 的 Config 思想：不可变配置，启动时加载一次。

    Provider 支持:
    - deepseek: OpenAI-compatible API (api.deepseek.com/v1)
    - anthropic: Anthropic Messages API (api.anthropic.com/v1)
    - openai_compatible: 通用 OpenAI-compatible 端点

    Stage→模型路由:
    stage_model_map 可为每个 Stage 指定不同模型/Provider，
    实现 "DeepSeek 打骨架 + Claude 做精装" 的分层策略。
    """
    # === DeepSeek / OpenAI-compatible 默认配置 ===
    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: int = 8192
    timeout: int = 120
    retry_times: int = 3

    # === Anthropic (Claude) 配置 ===
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6-20250514"
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    anthropic_max_tokens: int = 8192
    anthropic_timeout: int = 180
    anthropic_retry_times: int = 3

    # === Stage→模型路由（按 stage_id 指定模型） ===
    # 示例: {"W2": "deepseek-chat", "W4": "claude-sonnet-4-6-20250514"}
    # 未配置的 Stage 使用默认 model
    stage_model_map: Dict[str, str] = field(default_factory=dict)

    # === 通用 ===
    auto_context: bool = True
    context_chapters: int = 3

    # 路径
    base_dir: Path = field(default_factory=lambda: BASE_DIR)
    projects_dir: Path = field(default_factory=lambda: PROJECTS_DIR)

    # 项目模板
    project_templates: Dict[str, Any] = field(default_factory=lambda: {
        "七猫爽文": {"mode": "都市_power", "platform": "qimao", "default_words": 400000, "default_chapters": 200},
        "二次元": {"mode": "female_solo", "platform": "qidian", "default_words": 300000, "default_chapters": 150},
        "玄幻仙侠": {"mode": "general", "platform": "qidian", "default_words": 1000000, "default_chapters": 500},
        "历史架空": {"mode": "general", "platform": "zongheng", "default_words": 600000, "default_chapters": 300},
        "体育竞技": {"mode": "general", "platform": "qimao", "default_words": 500000, "default_chapters": 250},
    })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "api_key": "***" if self.api_key else "",
            "base_url": self.base_url,
            "model": self.model,
            "anthropic_api_key": "***" if self.anthropic_api_key else "",
            "anthropic_model": self.anthropic_model,
            "stage_model_map": self.stage_model_map,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "retry_times": self.retry_times,
        }

    def get_model_for_stage(self, stage_id: str) -> str:
        """获取指定 Stage 应使用的模型。"""
        return self.stage_model_map.get(stage_id, self.model)


# 全局单例
_instance: Optional[Config] = None


def get_config() -> Config:
    """获取全局配置单例（懒加载）"""
    global _instance
    if _instance is None:
        _instance = _load_from_env()
    return _instance


def _load_from_env() -> Config:
    """从环境变量/.env文件加载配置"""
    cfg = Config()

    # === DeepSeek / OpenAI-compatible ===
    cfg.api_key = os.getenv("DEEPSEEK_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    cfg.base_url = os.getenv("DEEPSEEK_BASE_URL", os.getenv("OPENAI_BASE_URL", cfg.base_url))
    cfg.model = os.getenv("PANGU_MODEL", os.getenv("AI_MODEL", cfg.model))
    cfg.temperature = float(os.getenv("PANGU_TEMPERATURE", str(cfg.temperature)))
    cfg.max_tokens = int(os.getenv("PANGU_MAX_TOKENS", str(cfg.max_tokens)))
    cfg.timeout = int(os.getenv("PANGU_TIMEOUT", str(cfg.timeout)))
    cfg.retry_times = int(os.getenv("PANGU_RETRY_TIMES", str(cfg.retry_times)))

    # === Anthropic (Claude) ===
    cfg.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
    cfg.anthropic_model = os.getenv("ANTHROPIC_MODEL", cfg.anthropic_model)
    cfg.anthropic_base_url = os.getenv("ANTHROPIC_BASE_URL", cfg.anthropic_base_url)
    cfg.anthropic_max_tokens = int(os.getenv("ANTHROPIC_MAX_TOKENS", str(cfg.anthropic_max_tokens)))
    cfg.anthropic_timeout = int(os.getenv("ANTHROPIC_TIMEOUT", str(cfg.anthropic_timeout)))
    cfg.anthropic_retry_times = int(os.getenv("ANTHROPIC_RETRY_TIMES", str(cfg.anthropic_retry_times)))

    # === Stage→模型路由 ===
    stage_map_raw = os.getenv("PANGU_STAGE_MODELS", "")
    if stage_map_raw:
        try:
            import json
            cfg.stage_model_map = json.loads(stage_map_raw)
        except json.JSONDecodeError:
            # 兼容 key=value,key=value 格式
            for pair in stage_map_raw.split(","):
                if "=" in pair:
                    k, v = pair.strip().split("=", 1)
                    cfg.stage_model_map[k.strip()] = v.strip()

    # === 从 .env 文件读取（仅当环境变量未设置时） ===
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        _parse_env_file(env_file, cfg)

    return cfg


def _parse_env_file(env_file, cfg: Config) -> None:
    """解析 .env 文件，仅填充尚未从环境变量获取的配置。"""
    raw = {}
    for line in env_file.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            raw[key.strip()] = value.strip().strip('"').strip("'")

    if not cfg.api_key:
        cfg.api_key = raw.get("DEEPSEEK_API_KEY", raw.get("OPENAI_API_KEY", ""))
    if cfg.base_url == Config.base_url:
        cfg.base_url = raw.get("DEEPSEEK_BASE_URL", raw.get("OPENAI_BASE_URL", cfg.base_url))
    if cfg.model == Config.model:
        cfg.model = raw.get("LLM_MODEL", raw.get("PANGU_MODEL", cfg.model))

    # Anthropic from .env
    if not cfg.anthropic_api_key:
        cfg.anthropic_api_key = raw.get("ANTHROPIC_API_KEY", "")
    if cfg.anthropic_model == Config.anthropic_model:
        cfg.anthropic_model = raw.get("ANTHROPIC_MODEL", cfg.anthropic_model)
    if cfg.anthropic_base_url == Config.anthropic_base_url:
        cfg.anthropic_base_url = raw.get("ANTHROPIC_BASE_URL", cfg.anthropic_base_url)

    # Stage map from .env
    if not cfg.stage_model_map:
        stage_map_raw = raw.get("PANGU_STAGE_MODELS", "")
        if stage_map_raw:
            try:
                import json
                cfg.stage_model_map = json.loads(stage_map_raw)
            except json.JSONDecodeError:
                for pair in stage_map_raw.split(","):
                    if "=" in pair:
                        k, v = pair.strip().split("=", 1)
                        cfg.stage_model_map[k.strip()] = v.strip()


def reset_config():
    """重置配置（主要用于测试）"""
    global _instance
    _instance = None


# ============ Pipeline配置 ============

PIPELINE_CONFIG = {
    # 快速模式激活的Stage列表
    "quick_mode_stages": ["W0", "W2", "W4"],
    # 工坊模式激活的Stage列表
    "workshop_mode_stages": ["W0", "W1", "W2", "W3", "W4", "W5"],
    # RAG检索参数
    "rag_top_k": 5,
    "rag_rerank_top_n": 3,
    # 投影配置
    "projection_enabled": True,
    # WriteGates配置
    "write_gates_enabled": True,
    # Stage执行超时(秒)
    "stage_timeout": 300,
}
