"""
盘古数学 · 张力包络线

提取章节文本的叙事张力曲线:
  - 逐段张力评分: 基于事件密度+冲突强度+情绪唤醒
  - 包络线: 连接局部极大值的上包络
  - 张力峰值: 本章最紧张的位置
  - 张力谷值: 最舒缓的位置
  - 张力梯度: 张力变化速率

用法:
    te = TensionEnvelope.from_text(chapter_text)
    print(f"峰值在 {te.peak_position:.0%} 处")
    print(f"张力梯度: {te.gradient:.3f}")
"""

from __future__ import annotations

import re
import math
from dataclasses import dataclass, field
from typing import List, Tuple


# ================================================================
# 张力信号提取
# ================================================================

# 高张力词 (事件/冲突/威胁)
_HIGH_TENSION = {
    "杀","死","血","砍","刺","轰","炸","裂","碎","断",
    "冲","撞","击","倒","摔","坠","爆","炸","劈","斩",
    "怒吼","暴喝","尖啸","尖叫","惨叫","惊叫",
    "发现","突然","竟然","居然","原来","真相",
    "威胁","危险","恐怖","恐怖","诡异","阴森",
    "攻击","防御","反击","追杀","逃跑",
    "警告","阻止","拦住","抓住","制住",
}

# 低张力词 (日常/舒缓)
_LOW_TENSION = {
    "坐","站","走","等","看","听","说","笑",
    "喝茶","吃饭","休息","睡觉","发呆","散步",
    "安静","平静","温暖","舒适","暖和","轻柔",
    "慢慢","缓缓","轻轻","渐渐","好好",
    "阳光","微风","花香","鸟鸣","水流",
}

# 冲突指示词
_CONFLICT = {
    "但是","可是","然而","不过","却","反而",
    "对峙","对抗","冲突","矛盾","对立",
    "争吵","争论","反驳","顶撞","质问",
    "拒绝","反对","否定","推翻",
}


# ================================================================
# 张力包络线
# ================================================================

@dataclass
class TensionEnvelope:
    """张力包络线分析结果"""
    segment_signals: List[float] = field(default_factory=list)   # 每段张力值
    envelope: List[float] = field(default_factory=list)          # 上包络线
    peak_value: float = 0.0         # 峰值张力
    peak_position: float = 0.0      # 峰值位置 (0-1，在文本中的相对位置)
    valley_value: float = 0.0       # 谷值张力
    mean_tension: float = 0.0       # 平均张力
    gradient: float = 0.0           # 平均张力梯度 (正=上升趋势)
    rising_ratio: float = 0.0       # 上升段落占比
    climax_quality: float = 0.0     # 高潮质量 (峰值/平均)

    @classmethod
    def from_text(cls, text: str):
        te = cls()

        # 1. 按段落切分
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
        if not paragraphs:
            return te

        # 2. 每段张力评分
        signals = []
        for para in paragraphs:
            score = cls._score_tension(para)
            signals.append(score)

        te.segment_signals = signals
        n = len(signals)

        # 3. 基本统计
        te.peak_value = max(signals)
        te.peak_position = signals.index(te.peak_value) / max(n - 1, 1)
        te.valley_value = min(signals)
        te.mean_tension = sum(signals) / n
        te.climax_quality = te.peak_value / max(te.mean_tension, 0.01)

        # 4. 上包络线 (连接相邻局部极大值)
        te.envelope = _compute_envelope(signals)

        # 5. 张力梯度和趋势
        if n >= 2:
            # 线性拟合的斜率 (简化: 前半vs后半)
            mid = n // 2
            first_half = sum(signals[:mid]) / max(mid, 1)
            second_half = sum(signals[mid:]) / max(n - mid, 1)
            te.gradient = (second_half - first_half) / max(first_half, 0.01)

            # 上升段落占比
            rising = sum(1 for i in range(1, n) if signals[i] > signals[i-1])
            te.rising_ratio = rising / (n - 1)

        return te

    @staticmethod
    def _score_tension(para: str) -> float:
        """对一段文本进行张力评分 (0-10)"""
        score = 3.0  # 基准分
        chars = len(re.sub(r'[^一-鿿]', '', para))
        if chars < 10:
            return score

        # 高张力词加分
        high_hits = sum(para.count(w) for w in _HIGH_TENSION)
        score += min(3.0, high_hits * 0.4)

        # 低张力词减分
        low_hits = sum(para.count(w) for w in _LOW_TENSION)
        score -= min(1.5, low_hits * 0.25)

        # 冲突词加分
        conflict_hits = sum(para.count(w) for w in _CONFLICT)
        score += min(2.0, conflict_hits * 0.5)

        # 对话加轻度张力
        dia_count = para.count('"') + para.count('"') + para.count('「')
        if dia_count >= 4:
            score += 0.5

        # 问号/叹号加张力
        score += min(1.0, para.count('？') * 0.2 + para.count('！') * 0.3)

        # 句长对张力的影响: 短句→高张力
        sentences = re.split(r'[。！？]', para)
        if sentences:
            avg_len = sum(len(s) for s in sentences) / len(sentences)
            if avg_len < 15:
                score += 0.5  # 短句加快节奏
            elif avg_len > 35:
                score -= 0.3  # 长句减缓节奏

        return max(0.5, min(10.0, score))

    def pacing_quality(self) -> float:
        """
        节奏质量评估 (0-1)。
        好的节奏: 有张有弛，梯度适中，高潮占比合理。
        """
        score = 0.0
        # 峰谷比要适中
        if 2.0 <= self.peak_value / max(self.valley_value, 0.1) <= 8.0:
            score += 0.3
        # 上升段占比在40-60%最好
        if 0.35 <= self.rising_ratio <= 0.65:
            score += 0.3
        # 高潮在65-90%位置最好 (黄金分割)
        if 0.60 <= self.peak_position <= 0.90:
            score += 0.2
        # 平均张力适中
        if 3.0 <= self.mean_tension <= 7.0:
            score += 0.2

        return score

    def summary(self) -> str:
        return (
            f"峰值={self.peak_value:.1f}@{self.peak_position:.0%} "
            f"平均={self.mean_tension:.1f} "
            f"梯度={self.gradient:+.2f} "
            f"节奏={self.pacing_quality():.2f}"
        )


def _compute_envelope(signals: List[float], window: int = 3) -> List[float]:
    """计算上包络线 (滑动窗口取局部极大值)"""
    n = len(signals)
    envelope = signals[:]
    for i in range(n):
        lo = max(0, i - window)
        hi = min(n, i + window + 1)
        envelope[i] = max(signals[lo:hi])
    return envelope


def compute_tension_envelope(text: str) -> TensionEnvelope:
    """便捷函数"""
    return TensionEnvelope.from_text(text)
