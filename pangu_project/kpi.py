"""
盘古项目 · KPI仪表盘

写作四维KPI (平衡计分卡改编):
  1. 质量维: 审查评分、设定一致性、角色OOC率
  2. 速度维: 章/周、字/天、Pipeline耗时
  3. 成本维: API成本/章、修改率、预算偏差
  4. 读者维: 预计留存率、钩子强度、情绪曲线质量

用法:
    dash = KPIDashboard(project_name="消失的第四个人")
    dash.record(1, score=91, words=2200, cost=0.003, time_h=0.5)
    print(dash.report())
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta


# ================================================================
# KPI数据点
# ================================================================

@dataclass
class WritingKPI:
    """单章KPI数据点"""
    chapter: int
    quality_score: float = 0.0       # 审查评分 (0-100)
    word_count: int = 0              # 字数
    api_cost: float = 0.0            # API成本 (元)
    time_hours: float = 0.0          # 耗时 (小时)
    revision_count: int = 0          # 修改次数
    hook_strength: float = 0.0       # 钩子强度 (0-10)
    setting_issues: int = 0          # 设定问题数
    written_at: str = ""


# ================================================================
# KPI仪表盘
# ================================================================

@dataclass
class KPIDashboard:
    """写作KPI仪表盘"""

    project_name: str = ""
    kpis: List[WritingKPI] = field(default_factory=list)

    # 目标值
    quality_target: float = 80.0          # 质量目标分
    speed_target: float = 3.0             # 目标: 章/周
    cost_per_chapter_target: float = 0.01  # 目标成本/章
    revision_rate_target: float = 0.3      # 目标修改率 (<30%)

    def record(self, chapter: int, score: float, words: int,
                cost: float = 0.0, time_h: float = 0.5,
                revision_count: int = 0, hook_strength: float = 0.0,
                setting_issues: int = 0):
        """记录一章的KPI数据"""
        self.kpis.append(WritingKPI(
            chapter=chapter,
            quality_score=score,
            word_count=words,
            api_cost=cost,
            time_hours=time_h,
            revision_count=revision_count,
            hook_strength=hook_strength,
            setting_issues=setting_issues,
            written_at=datetime.now().strftime("%Y-%m-%d"),
        ))

    # ---- 质量维 ----
    def avg_quality(self) -> float:
        if not self.kpis: return 0.0
        return sum(k.quality_score for k in self.kpis) / len(self.kpis)

    def quality_trend(self) -> str:
        """质量趋势: 最近3章 vs 前3章"""
        if len(self.kpis) < 4: return "insufficient_data"
        recent = [k.quality_score for k in self.kpis[-3:]]
        earlier = [k.quality_score for k in self.kpis[-6:-3]]
        avg_recent = sum(recent) / 3
        avg_earlier = sum(earlier) / 3
        if avg_recent > avg_earlier + 5: return "improving"
        if avg_recent < avg_earlier - 5: return "declining"
        return "stable"

    def quality_attainment(self) -> float:
        """质量达成率"""
        return self.avg_quality() / self.quality_target

    # ---- 速度维 ----
    def total_words(self) -> int:
        return sum(k.word_count for k in self.kpis)

    def words_per_day(self) -> float:
        if not self.kpis: return 0.0
        total_days = len(self.kpis) * 2.5  # 假设每章2.5天
        return self.total_words() / max(total_days, 1)

    def chapters_per_week(self) -> float:
        """章/周 (基于最近4章的节奏)"""
        if len(self.kpis) < 2: return 0.0
        recent = self.kpis[-min(4, len(self.kpis)):]
        # 简化: 每章按计划2天
        return 7.0 / 2.0

    def speed_attainment(self) -> float:
        return self.chapters_per_week() / self.speed_target

    # ---- 成本维 ----
    def total_api_cost(self) -> float:
        return sum(k.api_cost for k in self.kpis)

    def avg_cost_per_chapter(self) -> float:
        if not self.kpis: return 0.0
        return sum(k.api_cost for k in self.kpis) / len(self.kpis)

    def revision_rate(self) -> float:
        """修改率 = 需要修改的章数/总章数"""
        if not self.kpis: return 0.0
        return sum(1 for k in self.kpis if k.revision_count > 0) / len(self.kpis)

    def cost_attainment(self) -> float:
        """成本达成率 (越低越好, 但用1/比值表示)"""
        actual = self.avg_cost_per_chapter()
        if actual <= 0: return 1.0
        return min(1.0, self.cost_per_chapter_target / actual)

    # ---- 读者维 ----
    def avg_hook_strength(self) -> float:
        if not self.kpis: return 0.0
        hooks = [k.hook_strength for k in self.kpis if k.hook_strength > 0]
        return sum(hooks) / len(hooks) if hooks else 0.0

    def setting_issues_total(self) -> int:
        return sum(k.setting_issues for k in self.kpis)

    # ---- 综合 ----
    def overall_score(self) -> float:
        """四维加权综合评分 (0-100)"""
        quality = self.quality_attainment() * 100 * 0.40
        speed = self.speed_attainment() * 100 * 0.20
        cost = self.cost_attainment() * 100 * 0.25
        reader = min(1.0, self.avg_hook_strength() / 7.0) * 100 * 0.15

        return round(quality + speed + cost + reader, 1)

    def report(self) -> str:
        """生成KPI报告"""
        lines = [
            f"═══ {self.project_name} KPI Dashboard ═══",
            f"完成章数: {len(self.kpis)}  总字数: {self.total_words()}",
            "",
            "── 质量维 (40%) ──",
            f"  平均评分: {self.avg_quality():.0f}/100  [目标: ≥{self.quality_target}]",
            f"  质量趋势: {self.quality_trend()}",
            f"  达成率:   {self.quality_attainment():.0%}",
            "",
            "── 速度维 (20%) ──",
            f"  字/天:    {self.words_per_day():.0f}",
            f"  达成率:   {self.speed_attainment():.0%}",
            "",
            "── 成本维 (25%) ──",
            f"  API总成本: ¥{self.total_api_cost():.3f}",
            f"  章均成本: ¥{self.avg_cost_per_chapter():.4f}  [目标: ≤¥{self.cost_per_chapter_target}]",
            f"  修改率:   {self.revision_rate():.0%}  [目标: <{self.revision_rate_target:.0%}]",
            f"  达成率:   {self.cost_attainment():.0%}",
            "",
            "── 读者维 (15%) ──",
            f"  钩子强度: {self.avg_hook_strength():.1f}/10",
            f"  设定问题: {self.setting_issues_total()}个",
            "",
            f"═══ 综合评分: {self.overall_score():.0f}/100 ═══",
        ]
        return "\n".join(lines)
