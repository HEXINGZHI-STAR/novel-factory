"""
盘古 · 说服力引擎 (Persuasion Engine)

广告学/媒体传播学在写作中的应用:
  - AIDA漏斗:    Attention(标题/开篇) → Interest(悬念) → Desire(共鸣) → Action(追读)
  - 好奇心缺口:   读者知道的不够多 → 必须翻页 (Loewenstein信息差理论)
  - 蔡格尼克效应: 未完成的事比已完成的事更让人记住 → 每章结尾必须留"开口"
  - 模式打断:     读者习惯后突然打破预期 → 注意力重新聚焦
  - 社交证明:     别人都在看 → 我也要看
  - 稀缺性:       限时/限量 → 紧迫感
  - 叙事传输:     读者被"传送"进故事 → 失去对现实的感知

盘古应用:
  - 检测章节是否遵守AIDA漏斗
  - 测量"好奇心缺口"大小
  - 评估蔡格尼克效应强度 (开口悬念)
"""

from __future__ import annotations

import re
import math
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field


# ================================================================
# AIDA 漏斗检测
# ================================================================

@dataclass
class AIDAScore:
    """AIDA四阶段评分"""
    attention: float = 0.0    # 开篇抓眼力 (0-1)
    interest: float = 0.0     # 中段维持兴趣 (0-1)
    desire: float = 0.0       # 情感渴望/共情 (0-1)
    action: float = 0.0       # 追读冲动 (0-1)
    funnel_health: float = 0.0  # 漏斗健康度

    @property
    def dropout_zone(self) -> Optional[str]:
        """检测漏斗哪个阶段断裂"""
        if self.attention < 0.3:
            return "开篇——读者没被抓住，根本不会往下看"
        if self.interest < 0.3:
            return "中段——开头不错但中间无聊，读者会划走"
        if self.desire < 0.2:
            return "情感——读者在追剧情但不在乎角色死活"
        if self.action < 0.3:
            return "结尾——看完这章不想点下一章，弃书高发区"
        return None


# 开篇抓眼词 (触发注意力)
_ATTENTION_HOOKS = [
    "死", "杀", "血", "尖叫", "爆炸", "碎", "裂", "断",
    "突然", "那天", "最后", "第一", "从未", "没人",
    "秘密", "真相", "谎言", "不", "错", "不是",
]

# 兴趣维持词 (触发好奇心)
_INTEREST_KEEPERS = [
    "为什么", "怎么会", "难道", "莫非", "如果", "万一",
    "但", "可是", "然而", "不过", "却", "反而",
    "奇怪", "不对", "异常", "反常", "不对劲",
]

# 情感共鸣词 (触发Desire)
_DESIRE_TRIGGERS = [
    "她", "他", "我", "我们", "一起", "陪伴",
    "笑", "哭", "拥抱", "握住", "靠", "依偎",
    "记得", "想起", "想起", "曾经", "那年",
]

# 行动驱动词 (触发Action)
_ACTION_DRIVERS = [
    "然后呢", "后来", "接着", "下一秒", "立刻",
    "?", "!", "未完", "待续",
]


class PersuasionAnalyzer:
    """
    说服力分析器: 检测章节是否遵守广告学的AIDA漏斗。
    """

    def analyze_aida(self, text: str) -> AIDAScore:
        score = AIDAScore()

        # 分四段分析
        total = max(len(text), 1)
        quarter = total // 4

        opening = text[:quarter]           # 前25%
        middle = text[quarter:quarter*3]   # 25%-75%
        ending = text[quarter*3:]          # 后25%

        # Attention: 开篇抓眼力
        att_hits = sum(opening.count(w) for w in _ATTENTION_HOOKS)
        score.attention = min(1.0, att_hits / max(len(opening)/50, 1))

        # Interest: 中段好奇心维持
        int_hits = sum(middle.count(w) for w in _INTEREST_KEEPERS)
        score.interest = min(1.0, int_hits / max(len(middle)/80, 1))

        # Desire: 整章情感共鸣 (偏后半段更关键)
        des_hits = sum(text.count(w) for w in _DESIRE_TRIGGERS)
        score.desire = min(1.0, des_hits / max(total/100, 1))

        # Action: 结尾追读驱动
        act_hits = sum(ending.count(w) for w in _ACTION_DRIVERS)
        # 额外: 结尾是否有问号
        last_100 = text[-100:] if len(text) > 100 else text
        if "?" in last_100 or "?" in last_100:
            act_hits += 3
        score.action = min(1.0, act_hits / max(len(ending)/50, 1))

        # 漏斗健康度: 四阶段平均
        score.funnel_health = (score.attention * 0.3 +
                                score.interest * 0.25 +
                                score.desire * 0.25 +
                                score.action * 0.2)
        return score

    def analyze_curiosity_gap(self, text: str) -> float:
        """
        好奇心缺口 (Loewenstein信息差理论)。

        测度: 章节提出了多少"未知"但没回答。
        开口越多 → 好奇心缺口越大 → 翻页冲动越强。
        但超过5个开放问题 → 读者会焦虑弃书。
        """
        # 检测开放问题 (问号结尾的句子)
        questions = len(re.findall(r'[？?]', text))

        # 检测未完成的叙事 (蔡格尼克效应)
        unfinished = len(re.findall(
            r'(?:未完|待续|不知道|不确定|未必|也许|可能|或许)',
            text[:3000]))

        # 检测信息差暗示
        info_gaps = len(re.findall(
            r'(?:秘密|真相|背后|不知道的是|没注意到)',
            text[:3000]))

        total_gaps = questions + unfinished * 2 + info_gaps * 3

        # 标准化: 3-7个缺口最佳
        if total_gaps < 2:
            return 0.3   # 太封闭，读者没好奇心
        elif total_gaps <= 7:
            return 0.7   # 最佳区间
        elif total_gaps <= 12:
            return 0.9   # 偏多但可接受
        else:
            return 1.0   # 太多，读者会焦虑

    def analyze_zeigarnik(self, text: str) -> float:
        """
        蔡格尼克效应强度: 未完成的事比已完成的事更让人记住。

        测度: 章末的"开口"有多大。
        开口 = 悬念/未回答的问题/未完成的动作。
        """
        ending = text[-300:] if len(text) > 300 else text

        score = 0.0

        # 问号结尾 (+0.3)
        if ending.strip().endswith("?") or ending.strip().endswith("?"):
            score += 0.3

        # 动作中断 (+0.2)
        if re.search(r'(?:停住|僵住|愣住|没动|没有)', ending):
            score += 0.2

        # 对话中断 (+0.25)
        if re.search(r'[""][^""]{10,30}$', ending) and "说" not in ending[-50:]:
            score += 0.25

        # 视觉悬念 (+0.15)
        if re.search(r'(?:影子|光|门|窗|背后|身后)', ending):
            score += 0.15

        return min(1.0, score)

    def full_report(self, text: str) -> Dict:
        """完整说服力分析报告"""
        aida = self.analyze_aida(text)
        curiosity = self.analyze_curiosity_gap(text)
        zeigarnik = self.analyze_zeigarnik(text)

        # 综合说服力: AIDA漏斗 × 好奇心驱动 × 蔡格尼克粘性
        persuasion_index = (aida.funnel_health * 0.5 +
                            curiosity * 0.25 +
                            zeigarnik * 0.25)

        suggestions = []
        dropout = aida.dropout_zone
        if dropout:
            suggestions.append(f"漏斗断裂: {dropout}")
        if aida.attention < 0.4:
            suggestions.append("开篇Hook不够强: 前三句话内必须有冲突/异常/悬念")
        if aida.action < 0.4:
            suggestions.append("结尾追读驱动弱: 用问句/中断对话/视觉悬念收尾")
        if zeigarnik < 0.4:
            suggestions.append("蔡格尼克效应不足: 结尾必须留一个'未完成的事'")
        if curiosity < 0.5:
            suggestions.append("好奇心缺口太小: 本章需要在开头提出一个'为什么'")

        return {
            "persuasion_index": round(persuasion_index, 3),
            "aida": {
                "attention": round(aida.attention, 2),
                "interest": round(aida.interest, 2),
                "desire": round(aida.desire, 2),
                "action": round(aida.action, 2),
                "funnel_health": round(aida.funnel_health, 2),
            },
            "curiosity_gap": round(curiosity, 2),
            "zeigarnik_effect": round(zeigarnik, 2),
            "dropout_zone": dropout,
            "suggestions": suggestions,
            "verdict": (
                "高说服力——AIDA漏斗完整" if persuasion_index > 0.65
                else "中等——需要强化某个AIDA阶段" if persuasion_index > 0.4
                else "弱说服力——读者大概率弃书"
            ),
        }
