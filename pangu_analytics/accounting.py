"""
盘古分析 · 管理会计 + 财务会计

写作的成本会计模型:
  - 成本归集: 按章/按模式/按平台归集AI调用成本
  - 标准成本 vs 实际成本: 预算偏差分析
  - 盈亏平衡: 多少字/多少读者才能回本
  - 资产估值: IP价值 = 累积读者LTV + 平台权重

用法:
    ca = CostAccounting(project_name="消失的第四个人")
    ca.record_chapter(1, word_count=2200, api_calls=2, mode="mystery")
    print(f"单章成本: {ca.chapter_cost(1):.2f}元")
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from datetime import datetime


# ================================================================
# 成本会计
# ================================================================

@dataclass
class ChapterCost:
    """单章成本条目"""
    chapter_num: int
    word_count: int
    api_calls: int
    api_cost: float = 0.0           # API调用成本
    time_hours: float = 0.5         # 耗时 (估算)
    mode: str = "general"
    quality_score: float = 0.0
    revision_count: int = 0         # 修改次数
    written_at: str = ""

@dataclass
class CostAccounting:
    """写作成本会计系统"""

    project_name: str = ""
    rate_per_1k_tokens: float = 0.001     # DeepSeek: ~¥0.001/1K tokens
    rate_anthropic_1k: float = 0.015      # Claude: ~¥0.015/1K tokens
    hourly_labor_rate: float = 50.0       # 作者时间成本/小时

    chapters: List[ChapterCost] = field(default_factory=list)

    # 预算
    budget_total: float = 0.0
    budget_api: float = 0.0
    budget_labor: float = 0.0

    def record_chapter(self, chapter_num: int, word_count: int,
                        api_calls: int, mode: str = "general",
                        quality_score: float = 0.0,
                        revision_count: int = 0,
                        used_claude: bool = False):
        """记录一章的成本"""
        tokens_per_call = word_count * 1.5  # 输入+输出
        rate = self.rate_anthropic_1k if used_claude else self.rate_per_1k_tokens
        api_cost = api_calls * tokens_per_call / 1000 * rate

        # 时间: 基础0.5h + 每修一次加0.2h
        time_hours = 0.5 + revision_count * 0.2

        self.chapters.append(ChapterCost(
            chapter_num=chapter_num,
            word_count=word_count,
            api_calls=api_calls,
            api_cost=round(api_cost, 4),
            time_hours=round(time_hours, 2),
            mode=mode,
            quality_score=quality_score,
            revision_count=revision_count,
            written_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        ))

    def total_api_cost(self) -> float:
        return sum(c.api_cost for c in self.chapters)

    def total_labor_cost(self) -> float:
        return sum(c.time_hours * self.hourly_labor_rate for c in self.chapters)

    def total_cost(self) -> float:
        return self.total_api_cost() + self.total_labor_cost()

    def cost_per_word(self) -> float:
        total_words = sum(c.word_count for c in self.chapters)
        return self.total_cost() / max(total_words, 1)

    def cost_per_chapter(self) -> float:
        return self.total_cost() / max(len(self.chapters), 1)

    def api_cost_breakdown(self) -> Dict[str, float]:
        """API成本按模式归集"""
        breakdown = {}
        for c in self.chapters:
            breakdown[c.mode] = breakdown.get(c.mode, 0.0) + c.api_cost
        return breakdown

    def project_to_completion(self, target_chapters: int) -> float:
        """
        完工成本估算 (Estimate to Complete)。

        ETC = (已完成每章平均成本) × 剩余章数
        """
        if not self.chapters:
            return 0.0
        avg_per_ch = self.cost_per_chapter()
        remaining = target_chapters - len(self.chapters)
        return round(avg_per_ch * remaining, 2)


# ================================================================
# 预算偏差分析
# ================================================================

@dataclass
class BudgetVariance:
    """标准成本 vs 实际成本偏差分析"""

    standard_cost_per_chapter: float = 0.0
    actual_costs: List[float] = field(default_factory=list)

    def variances(self) -> List[float]:
        """每章的偏差金额"""
        return [actual - self.standard_cost_per_chapter
                for actual in self.actual_costs]

    def total_variance(self) -> float:
        """总偏差"""
        return sum(self.variances())

    def favorable_count(self) -> int:
        """有利偏差章数 (实际<标准)"""
        return sum(1 for v in self.variances() if v < 0)

    def unfavorable_count(self) -> int:
        """不利偏差章数 (实际>标准)"""
        return sum(1 for v in self.variances() if v > 0)

    def variance_report(self) -> str:
        """偏差分析报告"""
        total_var = self.total_variance()
        fav, unfav = self.favorable_count(), self.unfavorable_count()
        avg_var = sum(abs(v) for v in self.variances()) / max(len(self.variances()), 1)

        if abs(total_var) < 1.0 and fav + unfav < 3:
            return "ON_BUDGET — 成本控制良好，在预算范围内"
        elif total_var < 0:
            return f"UNDER_BUDGET — 节约{abs(total_var):.1f}元 ({fav}章有利)"
        elif total_var < 10:
            return f"SLIGHT_OVER — 超支{total_var:.1f}元 ({unfav}章不利)"
        else:
            return f"OVER_BUDGET — 严重超支{total_var:.1f}元，需审查"

    def break_even_readers(self, price_per_book: float) -> int:
        """盈亏平衡读者数 = 总成本 / 单价"""
        total_cost = sum(self.actual_costs)
        if price_per_book <= 0:
            return 999999
        return math.ceil(total_cost / price_per_book)


# ================================================================
# IP资产估值
# ================================================================

def ip_valuation(total_readers: int, reader_ltv: float,
                  platform_weight: float = 1.0,
                  adaptation_potential: float = 0.0) -> Dict[str, float]:
    """
    IP资产估值模型。

    IP价值 = 当前读者价值 + 改编潜力溢价

    Args:
        total_readers: 累积读者数
        reader_ltv: 单读者生命周期价值
        platform_weight: 平台权重 (知乎盐选=0.8, 起点=1.5, 番茄=0.6)
        adaptation_potential: 改编潜力 (0-1, 影视/游戏/有声)
    """
    base_value = total_readers * reader_ltv * platform_weight
    adaptation_premium = base_value * adaptation_potential * 3.0
    total = base_value + adaptation_premium

    return {
        "base_value": round(base_value, 0),
        "adaptation_premium": round(adaptation_premium, 0),
        "total_ip_value": round(total, 0),
        "valuation_multiple": round(1.0 + adaptation_potential * 3.0, 1),
    }
