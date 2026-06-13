"""
盘古分析 · 写作经济学

经济学原理在写作中的应用:
  1. 供需分析: 平台读者需求 vs 内容供给 → 题材选择策略
  2. 边际效用: 每增加1字的边际读者满意度 (递减)
  3. 机会成本: 写这个方向 = 放弃了那个方向
  4. 比较优势: 不同模式/题材的效率差异
  5. 弹性: 读者对价格/质量的敏感度

用法:
    econ = WritingEconomics(platform="知乎盐选", genre="悬疑")
    print(f"最优定价: {econ.optimal_price():.1f}元")
    print(f"边际效用递减点: {econ.diminishing_returns_point()}字")
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional


# ================================================================
# 市场分析器
# ================================================================

@dataclass
class MarketAnalyzer:
    """平台市场供需分析"""
    platform: str = "qimao"
    genre: str = "悬疑"

    # 市场数据 (可配置)
    _market_data: Dict = field(default_factory=lambda: {
        "知乎盐选": {"悬疑": {"demand": 85, "supply": 60, "avg_price": 9.9},
                    "治愈": {"demand": 70, "supply": 40, "avg_price": 6.9},
                    "言情": {"demand": 90, "supply": 95, "avg_price": 6.9}},
        "七猫": {"爽文": {"demand": 95, "supply": 90, "avg_price": 0},
                 "悬疑": {"demand": 60, "supply": 45, "avg_price": 0},
                 "言情": {"demand": 80, "supply": 85, "avg_price": 0}},
        "起点": {"玄幻": {"demand": 90, "supply": 95, "avg_price": 0.3},
                 "悬疑": {"demand": 75, "supply": 60, "avg_price": 0.25},
                 "都市": {"demand": 85, "supply": 80, "avg_price": 0.25}},
    })

    def market_gap(self) -> float:
        """供需缺口: 正=需求>供给(机会), 负=供给过剩(竞争激烈)"""
        d = self._get_data()
        return d.get("demand", 50) - d.get("supply", 50)

    def _get_data(self) -> dict:
        return self._market_data.get(self.platform, {}).get(self.genre, {})

    def competition_index(self) -> float:
        """竞争指数 (0-1, 越高越激烈) = 供给/(供给+需求)"""
        d = self._get_data()
        demand, supply = d.get("demand", 50), d.get("supply", 50)
        return supply / (supply + demand) if (supply + demand) > 0 else 0.5

    def market_recommendation(self) -> str:
        """基于供需分析的市场建议"""
        gap = self.market_gap()
        comp = self.competition_index()

        if gap > 20 and comp < 0.4:
            return "STRONG_ENTER — 供需缺口大，竞争低，强烈建议进入"
        elif gap > 10 and comp < 0.5:
            return "ENTER — 有利可图，建议进入但需差异化"
        elif gap > 0:
            return "CAUTIOUS — 市场有利但竞争存在"
        elif gap > -10:
            return "NICHE — 需要找到细分切口"
        else:
            return "AVOID — 供给严重过剩，除非有独特优势"


# ================================================================
# 写作经济学模型
# ================================================================

@dataclass
class WritingEconomics:
    """写作经济学: 边际效用 + 机会成本 + 最优定价"""

    platform: str = "知乎盐选"
    genre: str = "悬疑"
    target_chapters: int = 12
    target_words: int = 30000

    # 效用函数参数
    base_readers: int = 5000          # 初始读者
    quality_decay: float = 0.03       # 每千字质量衰减率
    reader_loyalty: float = 0.85      # 读者留存率

    # 成本参数
    cost_per_word_api: float = 0.0001  # API每字成本 (DeepSeek约此处)
    cost_per_hour_writer: float = 50   # 作者时薪 (机会成本)
    words_per_hour: int = 1000          # 每小时写字数

    def marginal_utility(self, word_count: int) -> float:
        """
        边际效用: 在第word_count字处，增加1字的边际读者满意度。

        U(w) = ln(w) × quality_decay_factor
        MU(w) = dU/dw = 1/w × quality_decay_factor

        边际效用递减: 字数越多，每增加1字的收益越低。
        """
        if word_count <= 0:
            return 1.0
        quality = math.exp(-self.quality_decay * word_count / 1000)
        return  quality / max(word_count, 1)

    def total_utility(self, word_count: int) -> float:
        """总效用: 写word_count字获得的总读者满意度"""
        if word_count <= 0:
            return 0.0
        # U = ∫(1/w × e^(-λw)) dw ≈ ln(w+1) × e^(-λw)
        utility = math.log(word_count + 1) * math.exp(
            -self.quality_decay * word_count / 2000)
        return utility

    def diminishing_returns_point(self) -> int:
        """
        边际效用递减到"不值得继续"的点。

        当 MU < 阈值 (初始MU的10%) 时，建议停止扩展字数。
        """
        mu_initial = self.marginal_utility(100)
        threshold = mu_initial * 0.1
        for w in range(100, 100000, 100):
            if self.marginal_utility(w) < threshold:
                return w
        return 50000

    def marginal_cost(self, word_count: int) -> float:
        """边际成本: 再写1字的成本 (API + 时间)"""
        # API成本
        api_cost = self.cost_per_word_api
        # 时间成本 (后期更贵——改稿时间增加)
        time_cost = self.cost_per_hour_writer / self.words_per_hour
        fatigue_multiplier = 1.0 + 0.2 * (word_count / 10000)
        return api_cost + time_cost * fatigue_multiplier

    def optimal_stop_point(self) -> int:
        """
        最优停止点: 边际效用 = 边际成本

        MU(w) = MC(w) → 解出w
        """
        for w in range(100, 200000, 100):
            mu = self.marginal_utility(w) * self.base_readers / 1000
            mc = self.marginal_cost(w)
            if mu <= mc:
                return w
        return self.target_words

    def opportunity_cost(self, alt_genre: str) -> float:
        """
        机会成本: 写当前题材而放弃alt_genre的潜在收益。

        Returns: 被放弃的净收益
        """
        analyzer = MarketAnalyzer(self.platform, alt_genre)
        current = MarketAnalyzer(self.platform, self.genre)
        return max(0, analyzer.market_gap() - current.market_gap())

    def optimal_price(self) -> float:
        """
        最优定价 (基于平台和市场数据)。

        知乎盐选: 通常6.9-19.9元/部
        """
        analyzer = MarketAnalyzer(self.platform, self.genre)
        d = analyzer._get_data()
        avg_price = d.get("avg_price", 9.9)
        gap = analyzer.market_gap()

        # 供需缺口 → 价格溢价
        if gap > 20:
            return round(avg_price * 1.3, 1)
        elif gap > 10:
            return round(avg_price * 1.15, 1)
        elif gap > 0:
            return round(avg_price, 1)
        else:
            return round(avg_price * 0.85, 1)

    def reader_lifecycle_value(self) -> float:
        """
        读者生命周期价值 (LTV)。

        LTV = Σ(每章收益 × 留存率^章号)
        """
        ltv = 0.0
        readers = self.base_readers
        for ch in range(self.target_chapters):
            # 每章每位读者收益
            ch_revenue = self.optimal_price() / self.target_chapters
            ltv += readers * ch_revenue
            readers *= self.reader_loyalty
        return round(ltv, 0)

    def summary(self) -> str:
        return (
            f"[{self.platform}/{self.genre}] "
            f"最优定价={self.optimal_price():.1f}元 "
            f"LTV={self.reader_lifecycle_value():.0f}元 "
            f"边际递减点={self.diminishing_returns_point()}字"
        )
