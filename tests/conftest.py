"""
pytest fixtures — 盘古AI 测试基础设施
"""
import sys
import json
import pytest
from pathlib import Path

# 确保盘古在路径中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ================================================================
# 文本 Fixtures
# ================================================================

@pytest.fixture
def sample_chapter_zh() -> str:
    """标准中文测试章节 (治愈系片段)"""
    return """她把插头插回去。琴键上的灰已经擦干净了。

这一次她没有站起来就跑。第一个音落下去的时候，窗外的雨刚好停了一拍。

那首曲子她弹了三年。每一个音符都记得——不是用脑子记的，是用手指记的。手指放在正确的位置上，自己会动。

她弹完最后一个音。手从琴键上拿下来，放在膝盖上。雨不知道什么时候又下起来了。

她坐了很久。没有哭。就是坐着。"""


@pytest.fixture
def sample_chapter_suspense() -> str:
    """悬疑片段"""
    return """林屿注意到404室的门关着的那个周三，南京西路上的梧桐刚开始落叶。

事情本身不奇怪。合租的人不常见面是常态。他端着便利店买回来的咖啡站在玄关。404室的门是关着的。

他不记得这扇门上次开着是什么时候。

那天晚上十一点十七分，微信群里多了一条新消息。是朋友圈的更新提示。第四个人的头像出现在通知栏里。他划开。一张天空的照片——天色是一种洗褪了色的灰。配文：这个季节的月亮很冷。

林屿盯着这行字大概五秒钟。然后退出来，给陈柏发了一条私聊。苏西最近是不是不太对劲？陈柏过了二十分钟才回。苏西是谁？"""


# ================================================================
# State Fixtures
# ================================================================

@pytest.fixture
def sample_state() -> dict:
    """标准项目状态"""
    return {
        "project_info": {
            "title": "测试作品",
            "genre": "悬疑",
            "platform": "知乎盐选",
            "target_chapters": 12,
            "target_words": 30000,
        },
        "progress": {"current_chapter": 1, "total_words": 0},
        "characters": {
            "protagonist": {"name": "林屿", "current_state": "开始调查"},
            "key_characters": [
                {"name": "陈柏", "role": "室友"},
                {"name": "江予安", "role": "室友"},
                {"name": "苏西", "role": "消失的第四个人"},
            ],
        },
        "foreshadowing": {
            "active_threads": [
                {"id": "f001", "planted_ch": 1, "description": "合照异常", "status": "open"},
                {"id": "f002", "planted_ch": 1, "description": "朋友圈定时", "status": "open"},
                {"id": "f003", "planted_ch": 1, "description": "群聊无邀请记录", "status": "open"},
            ]
        },
        "setting_log": {"locked_rules": ["Ch1: 无超自然", "Ch1: 404无钥匙"]},
        "review_checkpoints": [],
        "chapter_meta": {},
    }


# ================================================================
# Config Fixtures
# ================================================================

@pytest.fixture(autouse=True)
def reset_config():
    """每个测试前重置配置单例"""
    from pangu_core.config import reset_config, get_config
    reset_config()
    cfg = get_config()
    # 确保测试时不依赖真实 API Key
    cfg.api_key = cfg.api_key or "test_key"
    return cfg


@pytest.fixture
def mock_ai_client(monkeypatch):
    """Mock AI Client — 不调用真实API"""
    from pangu_core.ai_client import AIClient

    def mock_call(self, prompt, model=None, system_msg=None):
        return "测试生成内容。" * 100  # ~500字

    monkeypatch.setattr(AIClient, "__call__", mock_call)
    return AIClient()
