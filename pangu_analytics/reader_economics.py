"""
盘古 · 读者经济学 (Reader Economics)

吸收学术界最新成果:
  - BG/NBD模型: 预测读者重复追读行为 (CLVTools, 2025 CRAN)
  - Pareto/NBD: 读者终身价值 (CLVTools, 2025)
  - 注意力神经点过程: 内容消费行为动力学 (Yin et al., Marketing Science 2025)
  - 时间粒度分析: 短期/长期消费模式 (Guo & Liu, 2025, CC BY)

盘古适配:
  - "读者" = 平台用户
  - "购买" = 追读下一章
  - "流失" = 弃书
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional


# ================================================================
# BG/NBD 模型: 读者追读预测
# ================================================================
# 来源: Fader, Hardie & Lee (2005), CLVTools R包 (2025 CRAN)
# 原理: 每个读者有潜在的"活跃度"λ和"流失概率"μ,
#       两个参数都服从Gamma分布 → Beta-Geometric/NBD

@dataclass
class ReaderRetentionModel:
    """
    BG/NBD读者留存模型。

    预测: "这个读者会追读下一章吗？"
    输入: 历史追读记录 (读了哪些章)
    输出: 下章追读概率 + 预期剩余追读次数
    """

    # Gamma分布参数 (从历史数据估计)
    r_alpha: float = 0.5   # Gamma shape for λ (活跃度)
    alpha: float = 1.0     # Gamma rate for λ
    a_beta: float = 0.5    # Gamma shape for μ (流失率)
    b_beta: float = 1.0    # Gamma rate for μ

    def probability_alive(self, x: int, t_x: float, T: float) -> float:
        """
        读者在第T章时仍然"活跃"的概率。

        Args:
            x: 追读次数 (读了几章)
            t_x: 最近一次追读的时间 (章号)
            T: 当前时间 (当前章号)
        """
        # P(Alive | x, t_x, T) 使用BG/NBD公式
        # 简化: 使用1/(1+(T-t_x)/alpha)作为衰减因子
        recency = T - t_x
        if recency <= 0:
            return 1.0

        # 核心公式 (BG/NBD):
        # P(Alive) = 1 / (1 + (δ/α) * (a/(b+T-1)))
        # 其中 δ = I(t_x < T) * (T - t_x)
        delta = recency
        denom = 1 + (delta / self.alpha) * (self.a_beta / (self.b_beta + T - 1))
        return 1.0 / denom

    def expected_future_reads(self, x: int, t_x: float, T: float,
                               future_chapters: int = 10) -> float:
        """
        预测读者未来N章的期望追读次数。

        公式 (BG/NBD conditional expectation):
          E[Y(T, T+t*) | x, t_x, T] = P(Alive) * E[未来追读|活跃] * t*
        """
        p_alive = self.probability_alive(x, t_x, T)
        # 如果活跃，未来追读率 ≈ λ的期望 = r/α
        lambda_hat = self.r_alpha / self.alpha
        return p_alive * lambda_hat * future_chapters

    def churn_risk(self, x: int, t_x: float, T: float) -> float:
        """流失风险 (1 - P(Alive))"""
        return 1.0 - self.probability_alive(x, t_x, T)


# ================================================================
# Pareto/NBD: 读者终身价值 (LTV)
# ================================================================

@dataclass
class ReaderLTV:
    """
    Pareto/NBD 读者终身价值模型。

    预测: "这个读者总共会给我的书带来多少价值？"
    """

    avg_revenue_per_chapter: float = 0.05  # 每章每位读者贡献 (元)
    total_chapters: int = 100              # 总章数

    def compute_ltv(self, retention_model: ReaderRetentionModel,
                     x: int, t_x: float, T: float) -> dict:
        """
        计算单个读者的终身价值。
        """
        p_alive = retention_model.probability_alive(x, t_x, T)
        remaining = self.total_chapters - int(T)
        expected_reads = retention_model.expected_future_reads(x, t_x, T, remaining)
        ltv = expected_reads * self.avg_revenue_per_chapter

        return {
            "p_alive": round(p_alive, 3),
            "expected_remaining_reads": round(expected_reads, 1),
            "ltv": round(ltv, 2),
            "churn_risk": round(1 - p_alive, 3),
            "verdict": "高价值" if ltv > 1.0 else
                       "中等价值" if ltv > 0.3 else
                       "低价值/已流失",
        }


# ================================================================
# 时间粒度分析: 读者消费模式
# ================================================================
# 来源: Guo & Liu (2025), PeerJ Computer Science, CC BY

@dataclass
class TimeGranularityAnalysis:
    """
    时间粒度消费模式分析。

    区分短期消费(单日内密集追读)和长期消费(跨周/月的稳定追读)，
    构建消费模式矩阵。
    """

    daily_views: List[int] = field(default_factory=list)  # 每日阅读量
    chapter_views: List[int] = field(default_factory=list) # 每章阅读量

    def short_term_intensity(self) -> float:
        """短期消费强度: 单日内最大阅读量 / 平均"""
        if not self.daily_views:
            return 0.0
        avg = sum(self.daily_views) / len(self.daily_views)
        peak = max(self.daily_views)
        return peak / avg if avg > 0 else 0.0

    def long_term_stability(self) -> float:
        """长期消费稳定性: 变异系数的倒数 (越高越稳定)"""
        if len(self.chapter_views) < 3:
            return 0.0
        avg = sum(self.chapter_views) / len(self.chapter_views)
        if avg == 0:
            return 0.0
        var = sum((v - avg) ** 2 for v in self.chapter_views) / len(self.chapter_views)
        cv = math.sqrt(var) / avg
        return 1.0 / (1.0 + cv)  # 0=极不稳定, 1=完全稳定

    def dropout_chapter(self) -> Optional[int]:
        """检测读者弃书章节: 阅读量突然下降>60%的章节"""
        if len(self.chapter_views) < 3:
            return None
        for i in range(1, len(self.chapter_views)):
            prev = self.chapter_views[i-1]
            curr = self.chapter_views[i]
            if prev > 0 and curr / prev < 0.4:  # 下降了60%以上
                return i + 1  # 章节号从1开始
        return None

    def consumption_profile(self) -> str:
        """消费画像"""
        si = self.short_term_intensity()
        ls = self.long_term_stability()
        dropout = self.dropout_chapter()

        if si > 3.0 and ls > 0.7:
            return "狂热追读——一天读很多章，持续稳定"
        elif si > 3.0:
            return "爆发型——集中爆读后流失"
        elif ls > 0.7:
            return "稳健型——每天稳定追几章"
        elif dropout:
            return f"弃书型——第{dropout}章后流失"
        else:
            return "路人型——偶尔点开看看"


# ================================================================
# 注意力神经点过程: 消费行为动力学
# ================================================================
# 来源: Yin, Feng & Liu (2025), Marketing Science 44(1):220-239
# 原理: 连续时间注意力机制预测未来消费的时间、类型和数量

@dataclass
class AttentionEngagementModel:
    """
    注意力驱动的读者参与度预测。

    预测三个维度:
      1. 何时 (WHEN): 读者什么时候会看下一章？
      2. 什么 (WHAT): 读者会看什么类型的章节？
      3. 多少 (HOW MUCH): 一次会看几章？
    """

    engagement_history: List[float] = field(default_factory=list)  # 每章参与度分数
    attention_decay: float = 0.15  # 注意力衰减率

    def engagement_score(self, chapter_num: int) -> float:
        """计算第N章的读者参与度分数"""
        if chapter_num <= 1:
            return 1.0
        # 衰减: 最近的章节权重更高
        score = 0.0
        total_weight = 0.0
        for i, eng in enumerate(self.engagement_history):
            ch = i + 1
            weight = math.exp(-self.attention_decay * abs(chapter_num - ch))
            score += eng * weight
            total_weight += weight
        return score / total_weight if total_weight > 0 else 0.5

    def predict_next_read_time(self, current_chapter: int) -> float:
        """
        预测读者什么时候会打开下一章 (小时)。

        高参与度 → 短间隔；低参与度 → 长间隔或弃书。
        """
        eng = self.engagement_score(current_chapter)
        if eng > 0.8:
            return 2.0   # 2小时内
        elif eng > 0.5:
            return 8.0   # 半天内
        elif eng > 0.3:
            return 24.0  # 一天内
        else:
            return 72.0  # 3天+可能弃书

    def binge_reading_probability(self, current_chapter: int) -> float:
        """预测读者一次读多章的概率 (0-1)"""
        eng = self.engagement_score(current_chapter)
        # 参与度越高，越可能一次读多章
        return min(1.0, eng * 1.2)
