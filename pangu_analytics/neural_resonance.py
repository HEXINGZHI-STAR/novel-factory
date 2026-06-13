"""
盘古 · 神经共鸣模型 (Neural Resonance)

脑科学在写作中的应用:
  - 镜像神经元:  读"他伸手拿杯子"→运动皮层激活。具体动作>抽象叙述
  - 催产素触发:  社交温暖场景→催产素释放→角色依恋
  - 杏仁核激活:  威胁/危险描写→恐惧共鸣。不靠怪物靠心理预期
  - 感觉-运动模拟: "指尖碰到冰凉的杯壁"→触觉皮层激活。感官即代入
  - 默认模式网络: 自我参照思考→角色共情。'如果是我，我也会...'
  - 神经耦合:     好写作让读者大脑与作者同步。Predictability破坏耦合

应用:
  - 检测章节是否"冷"——镜像神经元未被激活，读者无法代入
  - 检测情感共鸣是否足够——催产素触发点密度
  - 感官密度评分——3种以上感官=高神经参与度
"""

from __future__ import annotations

import re
from typing import List, Dict, Tuple
from dataclasses import dataclass, field


# ================================================================
# 神经标记词库
# ================================================================

# 镜像神经元触发词 (具体动作 → 运动皮层激活)
_MIRROR_ACTION_WORDS = {
    "触": 0.8, "碰": 0.8, "推": 0.7, "拉": 0.7, "握": 0.9, "抓": 0.8,
    "放": 0.5, "拿": 0.6, "抬": 0.6, "举": 0.7, "转": 0.5, "伸": 0.7,
    "走": 0.4, "跑": 0.6, "跳": 0.7, "站": 0.3, "坐": 0.3, "蹲": 0.6,
    "咬": 0.9, "嚼": 0.7, "咽": 0.8, "喝": 0.6, "吃": 0.6,
    "笑": 0.7, "哭": 0.9, "皱眉": 0.8, "眨眼": 0.7,
}

# 催产素触发词 (社交温暖 → 催产素释放)
_OXYTOCIN_TRIGGERS = {
    "拥抱": 1.0, "握住手": 0.9, "靠": 0.7, "依偎": 0.9, "摸头": 0.8,
    "微笑": 0.6, "笑": 0.5, "默默": 0.6, "陪伴": 0.8, "在": 0.4,
    "帮忙": 0.7, "照顾": 0.8, "记得": 0.7, "等着": 0.6, "担心": 0.7,
    "善意": 0.8, "温柔": 0.7, "轻声": 0.6,
    # 食物相关 (分享食物=原始社交纽带)
    "递给": 0.6, "分": 0.5, "一起吃": 0.8, "多做了": 0.9, "留了": 0.8,
}

# 杏仁核触发词 (威胁/悬疑 → 杏仁核激活)
_AMYGDALA_TRIGGERS = {
    "突然": 0.5, "猛地": 0.6, "停住": 0.5, "僵": 0.7, "屏住": 0.8,
    "不对": 0.4, "奇怪": 0.4, "异常": 0.5, "暗": 0.3, "黑": 0.3,
    "影子": 0.6, "声音": 0.4, "脚步声": 0.7, "背后": 0.6, "身后": 0.6,
    "盯着": 0.7, "看": 0.2, "注视": 0.6, "偷": 0.5, "跟踪": 0.8,
}

# 感官词 (感觉-运动模拟 → 对应皮层激活)
_SENSORY_WORDS = {
    "触觉": {"凉": 0.7, "冰": 0.7, "温": 0.6, "热": 0.5, "烫": 0.8,
             "粗糙": 0.8, "光滑": 0.7, "柔软": 0.7, "硬": 0.5, "湿": 0.7,
             "干": 0.4, "黏": 0.8, "指尖": 0.9, "手掌": 0.8, "皮肤": 0.8},
    "味觉": {"甜": 0.7, "苦": 0.7, "酸": 0.8, "辣": 0.8, "咸": 0.6,
             "腥": 0.9, "涩": 0.8, "回甘": 0.7, "入味": 0.6},
    "嗅觉": {"香": 0.6, "臭": 0.7, "焦": 0.7, "霉": 0.8, "腥": 0.8,
             "泥土": 0.7, "雨后": 0.8, "消毒水": 0.9, "咖啡": 0.6},
    "听觉": {"安静": 0.5, "沉默": 0.6, "嗡嗡": 0.6, "咔嚓": 0.7, "滴答": 0.7,
             "回音": 0.6, "远处": 0.5, "隔壁": 0.6},
    "视觉": {"光": 0.3, "影": 0.5, "色": 0.3, "闪": 0.5, "暗": 0.4,
             "亮": 0.3, "模糊": 0.5, "清晰": 0.4},
}


# ================================================================
# 神经共鸣分析器
# ================================================================

@dataclass
class NeuralResonanceReport:
    """神经共鸣分析报告"""
    mirror_score: float = 0.0       # 镜像神经元参与度 (0-1)
    oxytocin_score: float = 0.0     # 催产素触发密度
    amygdala_score: float = 0.0     # 杏仁核激活度
    sensory_score: float = 0.0      # 感官模拟度
    sensory_breakdown: dict = field(default_factory=dict)  # 五感分布

    resonance_index: float = 0.0    # 综合共鸣指数
    is_cold: bool = True            # 是否"冷"——读者无法代入
    emotional_arc: str = ""         # 情绪弧线描述
    suggestions: List[str] = field(default_factory=list)


class NeuralResonanceAnalyzer:
    """
    神经共鸣分析器。

    分析文本对读者大脑各区域的激活程度。
    """

    def analyze(self, text: str) -> NeuralResonanceReport:
        r = NeuralResonanceReport()
        total_chars = max(len(re.sub(r'[^一-鿿]', '', text)), 1)
        per_1k = total_chars / 1000  # 每千字标准化

        # 1. 镜像神经元评分 (每千字触发次数/阈值)
        mirror_hits = sum(text.count(w) * s
                          for w, s in _MIRROR_ACTION_WORDS.items())
        r.mirror_score = min(1.0, mirror_hits / (per_1k * 15))

        # 2. 催产素评分
        oxy_hits = sum(text.count(w) * s
                       for w, s in _OXYTOCIN_TRIGGERS.items())
        r.oxytocin_score = min(1.0, oxy_hits / (per_1k * 8))

        # 3. 杏仁核评分 (悬疑/恐惧)
        amyg_hits = sum(text.count(w) * s
                        for w, s in _AMYGDALA_TRIGGERS.items())
        r.amygdala_score = min(1.0, amyg_hits / (per_1k * 10))

        # 4. 感官模拟评分 (五感分解)
        senses = {}
        for sense_name, words in _SENSORY_WORDS.items():
            score = sum(text.count(w) * s for w, s in words.items())
            senses[sense_name] = min(1.0, score / (per_1k * 5))
        r.sensory_score = sum(senses.values()) / len(senses)
        r.sensory_breakdown = {k: round(v, 2) for k, v in senses.items()}

        # 5. 综合共鸣指数
        r.resonance_index = (
            r.mirror_score * 0.30 +      # 镜像神经元=代入感
            r.oxytocin_score * 0.25 +    # 催产素=情感依恋
            r.sensory_score * 0.25 +     # 感官=沉浸感
            r.amygdala_score * 0.20      # 杏仁核=紧张/投入
        )

        # 6. 判定
        r.is_cold = r.resonance_index < 0.35

        suggestions = []
        if r.mirror_score < 0.3:
            suggestions.append("镜像神经元参与不足——增加具体动作描写，减少抽象叙述")
        if r.oxytocin_score < 0.2:
            suggestions.append("催产素触发不足——增加社交温暖场景/微小善意/食物分享")
        if r.sensory_score < 0.3:
            weakest = min(senses, key=senses.get)
            suggestions.append(f"感官描写不足——特别是{weakest}，至少补1处")
        if r.amygdala_score < 0.15:
            suggestions.append("悬疑感弱——增加'不对劲'的小细节，让读者比角色先紧张")
        r.suggestions = suggestions

        # 7. 情绪弧线描述
        if r.amygdala_score > 0.6 and r.oxytocin_score < 0.2:
            r.emotional_arc = "高紧张·低温暖——悬疑驱动，适合中段"
        elif r.oxytocin_score > 0.5 and r.amygdala_score < 0.3:
            r.emotional_arc = "高温暖·低紧张——治愈驱动，适合开篇/结尾"
        elif r.resonance_index > 0.6:
            r.emotional_arc = "全面激活——沉浸感强，是高分章节"
        elif r.is_cold:
            r.emotional_arc = "冷章节——读者大脑未被激活，需重写"
        else:
            r.emotional_arc = "平衡——有代入但不极致"

        return r


def neural_resonance(text: str) -> NeuralResonanceReport:
    """便捷函数"""
    return NeuralResonanceAnalyzer().analyze(text)
