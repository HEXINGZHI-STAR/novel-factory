"""
盘古 · 风格匹配器

方法: 余弦相似度 + 加权推荐
输入: 文本 + 目标平台 → 推荐最佳写作模式(mode)

吸收:
  - 余弦相似度: 在风格向量空间中找最近邻
  - 平台加权: 七猫重对话/节奏, 起点重设定/逻辑, 知乎重留白/情绪
"""

from __future__ import annotations

import json
from typing import List, Dict, Tuple
from pathlib import Path
from ..accelerated import Vector
from ..stats.style_fingerprint import StyleFingerprint


# 平台权重 (不同平台对风格的偏好)
PLATFORM_WEIGHTS = {
    "qimao":  {"对话率": 0.30, "节奏": 0.25, "爽感": 0.25, "情感": 0.10, "设定": 0.10},
    "qidian": {"设定": 0.30, "逻辑": 0.25, "长句比": 0.20, "节奏": 0.15, "对话率": 0.10},
    "zhihu":  {"留白": 0.30, "情绪": 0.25, "设定": 0.20, "节奏": 0.15, "对话率": 0.10},
    "fanqie": {"节奏": 0.35, "爽感": 0.30, "对话率": 0.20, "情感": 0.10, "设定": 0.05},
}


class StyleMatcher:
    """
    风格匹配推荐器。

    给定一段文本和目标平台 → 推荐最佳的写作模式。
    """

    def __init__(self, modes_dir: Path = None):
        self.modes: Dict[str, Vector] = {}
        self.mode_metadata: Dict[str, dict] = {}
        if modes_dir and modes_dir.exists():
            self._load_modes(modes_dir)

    def _load_modes(self, modes_dir: Path):
        """从 modes/*.json 加载模式定义"""
        for mf in modes_dir.glob("*.json"):
            try:
                mode = json.loads(mf.read_text(encoding="utf-8"))
                name = mode.get("name", mf.stem)
                # 从模式配置构建特征向量
                w2 = mode.get("w2_special", {})
                w4 = mode.get("w4_special", {})
                features = [
                    0.5 if w2.get("dialogue_priority", "").startswith("高") else 0.3,
                    0.7 if "动作" in w2.get("action_style", "") else 0.4,
                    0.5, 0.5, 0.5,  # 占位
                    0.8 if "视觉" in str(w4.get("sensory_priority", [])) else 0.4,
                    0.5, 0.5, 0.5, 0.5,
                    0.3, 0.5, 0.5, 0.5, 0.5,
                    0.5, 0.5, 0.5,
                    0.4, 0.6, 0.5,
                ]
                self.modes[name] = Vector(features[:20])
                self.mode_metadata[name] = {
                    "description": mode.get("description", ""),
                    "platform": mode.get("target_platforms", []),
                }
            except Exception:
                pass

    def match(self, text: str, platform: str = "qimao",
              top_k: int = 3) -> List[Tuple[str, float]]:
        """
        匹配最佳写作模式。

        Returns:
            [(模式名, 匹配分), ...] 按分数降序
        """
        sf = StyleFingerprint.from_text(text)
        vec = sf.to_vector()

        # 平台权重调整特征向量
        weights = PLATFORM_WEIGHTS.get(platform, PLATFORM_WEIGHTS["qimao"])
        # 简化: 对前5个特征加权
        weighted_vec = Vector(vec.values[:])

        scores = []
        for name, mode_vec in self.modes.items():
            sim = weighted_vec.cosine(mode_vec)
            # 平台适配加分
            meta = self.mode_metadata.get(name, {})
            platforms = meta.get("platform", [])
            if platform in platforms or any(p in str(platforms) for p in [platform]):
                sim += 0.05
            scores.append((name, round(sim, 4)))

        scores.sort(key=lambda x: -x[1])
        return scores[:top_k]


def match_best_mode(text: str, platform: str = "qimao") -> str:
    """便捷函数: 返回最佳模式名"""
    matcher = StyleMatcher()
    if matcher.modes:
        best = matcher.match(text, platform)[0]
        return best[0]
    return "general"
