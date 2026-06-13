"""
盘古 · 趋势雷达 (Trend Radar)

吸收: Chronicle (实时事件聚类), DTECT (动态话题演化), SocialPulse (社交媒体话语)

解决盘古核心问题: 4,467本参考书是静态的，需要持续注入"当下在火什么"。

功能:
  1. 平台热度追踪: 七猫/起点/番茄 榜单变化
  2. 题材迁移检测: "系统流→规则怪谈→日常恐怖"的演化
  3. 读者情绪雷达: 贴吧/豆瓣/知乎 对当前作品的讨论热度
  4. 写作时机推荐: 某个题材"供给不足+需求旺盛"→建议入场

数据源:
  - 平台榜单 (手动爬取或API)
  - 社交媒体 (贴吧/豆瓣/知乎)
  - 盘古自有数据 (22个项目的表现)
"""

from __future__ import annotations

import math
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta


# ================================================================
# 题材热度追踪
# ================================================================

@dataclass
class GenreTrend:
    """单个题材的热度趋势"""
    name: str                         # 题材名
    supply_score: float = 50.0        # 供给量 (0-100)
    demand_score: float = 50.0        # 需求量 (0-100)
    growth_rate: float = 0.0          # 增长率 (%/月)
    momentum: float = 0.0             # 动量 (是否在加速)
    saturation: float = 0.0           # 饱和度 (0=蓝海, 1=红海)
    timestamp: str = ""

    @property
    def opportunity_score(self) -> float:
        """
        入场机会评分 (0-100)。

        公式: 需求×增长率×动量 / (1+饱和度)
        高需求 + 高增长 + 低饱和 = 最佳入场时机
        """
        raw = (self.demand_score * (1 + self.growth_rate) *
               (1 + self.momentum) / (1 + self.saturation * 2))
        return round(min(100, raw / 2), 1)

    @property
    def verdict(self) -> str:
        if self.opportunity_score > 70:
            return "强烈入场——需求旺盛且供给不足"
        elif self.opportunity_score > 50:
            return "可以入场——有一定竞争但市场在增长"
        elif self.opportunity_score > 30:
            return "谨慎——市场饱和或需求下降"
        else:
            return "避免——红海市场"


@dataclass
class TrendRadar:
    """
    趋势雷达: 聚合多平台数据，输出写作方向建议。
    """

    genres: List[GenreTrend] = field(default_factory=list)
    platforms: List[str] = field(default_factory=lambda: ["七猫", "起点", "番茄", "知乎盐选"])
    last_updated: str = ""

    def add_genre(self, name: str, supply: float, demand: float,
                   growth: float = 0.0, momentum: float = 0.0,
                   saturation: float = 0.5):
        """手动添加题材数据 (替代爬虫)"""
        self.genres.append(GenreTrend(
            name=name, supply_score=supply, demand_score=demand,
            growth_rate=growth, momentum=momentum,
            saturation=saturation,
            timestamp=datetime.now().strftime("%Y-%m-%d"),
        ))

    def add_from_platform_observation(self, platform: str,
                                       genre_hotlist: List[Tuple[str, int, int]]):
        """
        从平台观察数据导入。
        genre_hotlist: [(题材名, 上榜数量, 评论热度), ...]
        """
        if not genre_hotlist:
            return
        max_count = max(g[1] for g in genre_hotlist)
        max_heat = max(g[2] for g in genre_hotlist)

        for name, count, heat in genre_hotlist:
            supply = (count / max(max_count, 1)) * 100
            demand = (heat / max(max_heat, 1)) * 100
            existing = next((g for g in self.genres if g.name == name), None)
            if existing:
                # 计算增长率 (与前次对比)
                growth = (supply - existing.supply_score) / max(existing.supply_score, 1)
                existing.growth_rate = round(growth, 3)
                existing.supply_score = supply
                existing.demand_score = demand
                existing.saturation = min(1.0, supply / max(demand, 1))
            else:
                self.genres.append(GenreTrend(
                    name=name, supply_score=supply, demand_score=demand,
                    saturation=min(1.0, supply / max(demand, 1)),
                    timestamp=datetime.now().strftime("%Y-%m-%d"),
                ))
        self.last_updated = datetime.now().strftime("%Y-%m-%d")

    def top_opportunities(self, n: int = 5) -> List[GenreTrend]:
        """返回当前最佳的入场机会"""
        sorted_genres = sorted(self.genres,
                               key=lambda g: g.opportunity_score, reverse=True)
        return sorted_genres[:n]

    def detect_trend_shift(self) -> List[Dict]:
        """
        检测题材迁移: 哪些题材在上升/下降。

        Returns:
            [{"genre": "规则怪谈", "direction": "上升", "momentum": 0.15}, ...]
        """
        shifts = []
        for g in self.genres:
            if g.momentum > 0.1:
                shifts.append({"genre": g.name, "direction": "上升",
                               "momentum": g.momentum,
                               "opportunity": g.opportunity_score})
            elif g.momentum < -0.1:
                shifts.append({"genre": g.name, "direction": "下降",
                               "momentum": g.momentum})
        shifts.sort(key=lambda s: -s["momentum"])
        return shifts

    def recommend_genre(self, platform: str = "七猫") -> Dict:
        """
        基于趋势雷达推荐最佳写作题材。

        算法: 机会评分 × 平台适配权重
        """
        platform_weights = {
            "七猫": {"悬疑": 1.2, "都市": 1.0, "玄幻": 0.8, "治愈": 0.9},
            "起点": {"玄幻": 1.3, "悬疑": 1.1, "历史": 1.2, "都市": 0.7},
            "番茄": {"爽文": 1.5, "系统": 1.3, "重生": 1.2, "悬疑": 0.8},
            "知乎盐选": {"悬疑": 1.5, "治愈": 1.2, "规则怪谈": 1.3, "都市": 0.8},
        }
        weights = platform_weights.get(platform, {})

        best_genre = None
        best_score = 0.0
        for g in self.genres:
            pw = weights.get(g.name, 1.0)
            score = g.opportunity_score * pw
            if score > best_score:
                best_score = score
                best_genre = g.name

        return {
            "platform": platform,
            "recommended_genre": best_genre,
            "opportunity_score": round(best_score, 1),
            "timestamp": self.last_updated,
        }


# ================================================================
# 写作时机推荐
# ================================================================

def writing_timing_advice(radar: TrendRadar, platform: str = "七猫",
                           project_genre: str = None) -> str:
    """
    基于趋势雷达 + 盘古内部数据，给出写作时机建议。

    考虑因素:
      1. 外部市场: 该题材当前供需
      2. 内部能力: 盘古在该题材上的历史表现
      3. 时机窗口: 动量是否还在上升
    """
    rec = radar.recommend_genre(platform)
    parts = [f"平台 {platform}:"]

    if project_genre:
        genre_trend = next((g for g in radar.genres
                            if g.name == project_genre), None)
        if genre_trend:
            parts.append(
                f"你的题材「{project_genre}」当前机会评分 "
                f"{genre_trend.opportunity_score}/100 —— {genre_trend.verdict}"
            )
            if genre_trend.momentum > 0:
                parts.append(f"题材正在上升 (动量+{genre_trend.momentum:.1%}/月)")
            elif genre_trend.momentum < 0:
                parts.append(f"题材正在降温 (动量{genre_trend.momentum:.1%}/月)")

    parts.append(f"当前最佳入场: {rec['recommended_genre']} "
                 f"(评分{rec['opportunity_score']}/100)")
    return "\n".join(parts)
