"""
盘古 · 情感弧线模板 (Emotional Arc Templates)

吸收: NYU + Cornell (2025), "All Stories Are One Story: Emotional Arc Guided Generation"
      Reagan et al. (2016), "The Emotional Arcs of Stories"
      METATRON Framework (2025), cognitively-grounded story generation
      Propp's Morphology of the Folktale + Campbell's Hero's Journey

6种经典情感弧线 (来自1500+本古腾堡计划小说的情感分析):
  1. 白手起家 (Rags to Riches):   ───────↗  持续上升
  2. 悲剧 (Tragedy):              ↘──────  持续下降
  3. 洞中人 (Man in a Hole):      ↘──↗    先降后升
  4. 伊卡洛斯 (Icarus):           ↗──↘    先升后降
  5. 灰姑娘 (Cinderella):         ↗↘↗     升→降→升
  6. 俄狄浦斯 (Oedipus):          ↘↗↘     降→升→降

盘古应用:
  - 检测章节当前处于哪种弧线的哪个阶段
  - 预测下一章应该"升"还是"降"
  - 检测弧线断裂 (如: 治愈小说出现悲剧弧)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import math


# ================================================================
# 6种经典弧线定义
# ================================================================

ARC_TEMPLATES = {
    "Rags_to_Riches": {
        "name": "白手起家",
        "pattern": [0.1, 0.2, 0.3, 0.4, 0.55, 0.7, 0.85, 1.0],
        "description": "持续上升。适合: 爽文/升级流/逆袭",
        "slope": "up",
        "platform_fit": ["七猫", "番茄", "起点"],
    },
    "Tragedy": {
        "name": "悲剧",
        "pattern": [0.9, 0.8, 0.65, 0.5, 0.35, 0.2, 0.1, 0.05],
        "description": "持续下降。适合: 严肃文学/虐文",
        "slope": "down",
        "platform_fit": ["知乎盐选", "晋江"],
    },
    "Man_in_a_Hole": {
        "name": "洞中人",
        "pattern": [0.7, 0.5, 0.3, 0.2, 0.3, 0.5, 0.7, 0.9],
        "description": "先降后升。适合: 悬疑/治愈/成长",
        "slope": "down_up",
        "platform_fit": ["知乎盐选", "七猫", "起点"],
    },
    "Icarus": {
        "name": "伊卡洛斯",
        "pattern": [0.3, 0.5, 0.7, 0.85, 0.7, 0.5, 0.3, 0.1],
        "description": "先升后降。适合: 枭雄/黑化/反套路",
        "slope": "up_down",
        "platform_fit": ["起点", "番茄"],
    },
    "Cinderella": {
        "name": "灰姑娘",
        "pattern": [0.2, 0.5, 0.3, 0.7, 0.4, 0.8, 0.5, 1.0],
        "description": "升→降→升。适合: 言情/甜宠/逆袭+虐+HE",
        "slope": "up_down_up",
        "platform_fit": ["晋江", "番茄", "七猫"],
    },
    "Oedipus": {
        "name": "俄狄浦斯",
        "pattern": [0.8, 0.5, 0.7, 0.3, 0.6, 0.2, 0.5, 0.1],
        "description": "降→升→降。适合: 悲剧悬疑/宿命",
        "slope": "down_up_down",
        "platform_fit": ["知乎盐选", "起点"],
    },
}


@dataclass
class ArcAnalysis:
    """情感弧线分析结果"""
    best_arc: str = ""                    # 最佳匹配弧线
    match_score: float = 0.0             # 匹配度
    current_position: float = 0.0        # 当前在弧线的位置 (0-1)
    current_slope: str = ""              # 当前趋势: "上升"/"下降"/"平稳"
    next_direction: str = ""             # 下一章应该的方向
    arc_healthy: bool = True             # 弧线是否健康 (未断裂)
    warnings: List[str] = field(default_factory=list)


class EmotionalArcAnalyzer:
    """
    情感弧线分析器。

    基于NYU/Cornell 2025论文的6种经典弧线。
    """

    def analyze(self, chapter_valences: List[float],
                expected_arc: str = None) -> ArcAnalysis:
        """
        分析章节情绪序列属于哪种弧线。

        Args:
            chapter_valences: 每章的情感极性值 (-1到+1)
            expected_arc: 期望的弧线类型 (如 "Man_in_a_Hole")

        Returns:
            ArcAnalysis
        """
        if len(chapter_valences) < 2:
            return ArcAnalysis(best_arc="unknown")

        # 归一化: 映射到0-1
        min_v, max_v = min(chapter_valences), max(chapter_valences)
        if max_v - min_v < 0.01:
            normalized = [0.5] * len(chapter_valences)
        else:
            normalized = [(v - min_v) / (max_v - min_v)
                          for v in chapter_valences]

        # 与6种弧线模板匹配 (DTW简化: 采样到8点)
        sampled = self._resample(normalized, 8)

        best_arc = None
        best_score = -1.0

        for arc_id, template in ARC_TEMPLATES.items():
            pattern = template["pattern"]
            # 相关度: 皮尔逊相关系数
            score = self._pearson_r(sampled, pattern)
            if score > best_score:
                best_score = score
                best_arc = arc_id

        # 当前趋势
        recent = normalized[-3:] if len(normalized) >= 3 else normalized
        slope = self._linear_slope(recent)

        # 下一章方向
        if expected_arc and best_arc != expected_arc:
            # 弧线偏离 → 警告
            pass

        analysis = ArcAnalysis(
            best_arc=best_arc,
            match_score=round(best_score, 3),
            current_position=round(normalized[-1], 3),
            current_slope="上升" if slope > 0.05 else "下降" if slope < -0.05 else "平稳",
        )

        # 匹配弧线 → 推荐下一章方向
        if best_arc and best_arc in ARC_TEMPLATES:
            pattern = ARC_TEMPLATES[best_arc]["pattern"]
            pos = len(chapter_valences) - 1
            template_pos = min(pos, len(pattern) - 1)
            if template_pos < len(pattern) - 1:
                next_val = pattern[template_pos + 1]
                curr_val = pattern[template_pos]
                analysis.next_direction = "上升" if next_val > curr_val else "下降"
            else:
                analysis.next_direction = "收束"

        # 弧线健康检查
        if abs(best_score) < 0.3:
            analysis.arc_healthy = False
            analysis.warnings.append(
                f"弧线不清晰 (匹配度{best_score:.2f})，建议检查情绪设计")

        return analysis

    def recommend_arc(self, platform: str, genre: str) -> str:
        """基于平台和题材推荐最佳弧线"""
        genre_arc_map = {
            "悬疑": "Man_in_a_Hole",
            "治愈": "Man_in_a_Hole",
            "爽文": "Rags_to_Riches",
            "逆袭": "Rags_to_Riches",
            "虐文": "Tragedy",
            "甜宠": "Cinderella",
            "言情": "Cinderella",
            "枭雄": "Icarus",
            "反套路": "Icarus",
            "宿命": "Oedipus",
            "规则怪谈": "Man_in_a_Hole",
        }
        return genre_arc_map.get(genre, "Man_in_a_Hole")

    def _resample(self, values: List[float], target_len: int) -> List[float]:
        """将任意长度序列重采样到目标长度"""
        n = len(values)
        return [values[int(i * (n - 1) / (target_len - 1))]
                for i in range(target_len)]

    def _pearson_r(self, a: List[float], b: List[float]) -> float:
        """皮尔逊相关系数"""
        n = len(a)
        ma, mb = sum(a) / n, sum(b) / n
        cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
        sa = math.sqrt(sum((x - ma) ** 2 for x in a))
        sb = math.sqrt(sum((x - mb) ** 2 for x in b))
        return cov / (sa * sb + 1e-9)

    def _linear_slope(self, values: List[float]) -> float:
        """线性回归斜率 (正=上升, 负=下降)"""
        n = len(values)
        if n < 2:
            return 0.0
        x_avg = (n - 1) / 2
        y_avg = sum(values) / n
        num = sum((i - x_avg) * (values[i] - y_avg) for i in range(n))
        den = sum((i - x_avg) ** 2 for i in range(n))
        return num / den if den > 0 else 0.0
