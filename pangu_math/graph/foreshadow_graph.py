"""
盘古数学 · 伏笔网络分析

将总纲伏笔表建模为有向图:
  - 埋设节点 → 回收节点
  - 检测孤儿伏笔 (无回收章的伏笔)
  - 检测过期伏笔 (回收章<当前章但status=open)
  - 伏笔密度: 每章的伏笔操作数分布
  - 伏笔跨度: 埋设→回收的平均章节间隔
  - 回收瓶颈: 太多伏笔集中在同一章回收

用法:
    fg = ForeshadowGraph.from_state(state_json)
    print(f"过期伏笔: {fg.expired_threads()}")
    print(f"回收瓶颈章: {fg.bottleneck_chapter()}")
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any


# ================================================================
# 伏笔网络
# ================================================================

@dataclass
class ForeshadowGraph:
    """伏笔网络"""
    threads: List[Dict] = field(default_factory=list)  # 伏笔列表

    # 统计
    total_open: int = 0
    total_resolved: int = 0
    avg_span: float = 0.0              # 平均伏笔跨度 (章)
    density_per_chapter: Dict[int, int] = field(default_factory=dict)  # 每章的伏笔操作密度

    # 问题检测
    orphan_threads: List[str] = field(default_factory=list)
    expired_threads: List[str] = field(default_factory=list)
    bottleneck_chapters: List[int] = field(default_factory=list)

    @classmethod
    def from_threads(cls, threads: List[Dict], current_chapter: int = 0):
        fg = cls(threads=threads)
        fg._analyze(current_chapter)
        return fg

    @classmethod
    def from_state(cls, state: dict):
        """从 state.json 构建伏笔网络"""
        foreshadow = state.get("foreshadowing", {})
        if isinstance(foreshadow, list):
            threads = foreshadow
        else:
            threads = foreshadow.get("active_threads", [])

        current = state.get("progress", {}).get("current_chapter", 0)
        return cls.from_threads(threads, current)

    def _analyze(self, current_chapter: int):
        spans = []
        planted_density: Dict[int, int] = {}
        resolved_density: Dict[int, int] = {}

        for t in self.threads:
            planted = t.get("planted_ch", 0)
            resolved = t.get("resolved_ch")
            status = t.get("status", "open")

            # 计数
            if status == "open":
                self.total_open += 1
            else:
                self.total_resolved += 1

            # 密度
            if planted:
                planted_density[planted] = planted_density.get(planted, 0) + 1
            if resolved:
                resolved_density[resolved] = resolved_density.get(resolved, 0) + 1

            # 跨度
            if planted and resolved:
                spans.append(resolved - planted)

            # 孤儿检测
            if status == "open" and resolved is None:
                desc = t.get("description", t.get("id", "?"))
                self.orphan_threads.append(desc[:60])

            # 过期检测
            if status == "open" and resolved is None and current_chapter > 0:
                if planted and planted < current_chapter - 3:
                    self.expired_threads.append(
                        t.get("description", t.get("id", "?"))[:60])

        # 合并密度
        all_chapters = set(planted_density.keys()) | set(resolved_density.keys())
        for ch in all_chapters:
            self.density_per_chapter[ch] = (
                planted_density.get(ch, 0) + resolved_density.get(ch, 0))

        # 平均跨度
        self.avg_span = sum(spans) / len(spans) if spans else 0.0

        # 回收瓶颈: 单章回收≥3条
        self.bottleneck_chapters = [
            ch for ch, cnt in resolved_density.items() if cnt >= 3]

    def bottleneck_chapter(self) -> Optional[int]:
        """返回最严重的回收瓶颈章 (单章回收最多伏笔)"""
        if not self.bottleneck_chapters:
            return None
        return max(self.bottleneck_chapters)

    def urgency_score(self, thread: Dict, current_chapter: int) -> float:
        """
        计算单条伏笔的紧急度 (0-1, 越高越急)。

        因素: 距回收章的剩余章数、已埋设时间、是否为主线索
        """
        planted = thread.get("planted_ch", 0)
        resolved = thread.get("resolved_ch")
        status = thread.get("status", "open")

        if status != "open" or resolved is None:
            return 0.0

        age = current_chapter - planted
        # 埋设超过5章未提 → 高紧急
        if age >= 5:
            return 0.9
        if age >= 3:
            return 0.6
        if age >= 1:
            return 0.3
        return 0.1

    def health_score(self) -> float:
        """
        伏笔网络健康度 (0-1)。

        扣分项: 孤儿伏笔、过期伏笔、回收瓶颈、密度不均
        """
        score = 1.0
        score -= min(0.3, len(self.orphan_threads) * 0.1)
        score -= min(0.3, len(self.expired_threads) * 0.15)
        score -= min(0.2, len(self.bottleneck_chapters) * 0.1)

        # 密度分布检查: 如果有章节0操作和其他章节差异过大
        if self.density_per_chapter:
            densities = list(self.density_per_chapter.values())
            mean_d = sum(densities) / len(densities)
            if mean_d > 0 and max(densities) / mean_d > 4:
                score -= 0.1

        return max(0.0, score)

    def summary(self) -> str:
        return (
            f"活跃={self.total_open} 已回收={self.total_resolved} "
            f"孤儿={len(self.orphan_threads)} 过期={len(self.expired_threads)} "
            f"健康度={self.health_score():.2f}"
        )


def build_foreshadow_graph(state: dict) -> ForeshadowGraph:
    """便捷函数"""
    return ForeshadowGraph.from_state(state)
