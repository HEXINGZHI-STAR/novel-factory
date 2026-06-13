"""
盘古数学 · 动态规划节奏优化

问题: 一本书有N章，每章分配字数/爽点/钩子/情绪释放等资源，
     在总约束下最大化读者留存和满意度。

DP状态: dp[ch][tension][hook_type] = 到第ch章为止的最优累积价值

应用场景:
  1. 字数分配: 总字数预算在12章中的最优分配
  2. 钩子类型调度: 连续2章不能用同类型钩子 (约束满足)
  3. 情绪释放调度: 每3-4章1个大释放，不能连续重复释放方式
  4. 伏笔密度: 每章的伏笔操作数应均匀分布

用法:
    opt = PacingOptimizer(total_chapters=12, total_budget=30000)
    plan = opt.optimize_word_budget()
    print(f"每章字数: {plan}")
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional


# ================================================================
# 节奏优化器
# ================================================================

@dataclass
class PacingOptimizer:
    """
    动态规划节奏优化器。

    将"节奏"建模为资源分配问题:
    - 决策变量: 每章的字数/爽点数/钩子类型/情绪释放类型
    - 约束: 总字数预算、钩子不连续重复、释放方式多样化
    - 目标: 最大化读者累积满意度
    """
    total_chapters: int = 12
    total_budget: int = 30000           # 总字数预算
    min_per_chapter: int = 1800         # 每章最少字数
    max_per_chapter: int = 2800         # 每章最多字数
    hook_types: List[str] = field(default_factory=lambda: [
        "悬念", "反转", "期待", "情感", "危机", "余韵"
    ])
    release_types: List[str] = field(default_factory=lambda: [
        "善意崩溃", "诉说", "无声胜利", "雨水/眼泪", "食物触发", "沉默"
    ])

    def _default_importance(self, n: int) -> List[float]:
        """基于叙事结构的默认章重要性"""
        imp = []
        for i in range(n):
            chapter = i + 1  # 1-indexed
            if chapter == 1:
                imp.append(1.8)        # 开篇: 最高权重 (黄金首章)
            elif chapter <= 3:
                imp.append(1.4)        # 前三章
            elif chapter == n:
                imp.append(2.0)        # 终章: 最高潮
            elif chapter >= n - 2:
                imp.append(1.6)        # 倒数章节
            elif chapter % 4 == 0:
                imp.append(1.5)        # 卷末高潮
            elif chapter % 4 == 1:
                imp.append(1.1)        # 卷首铺垫 (可轻)
            else:
                imp.append(1.0)        # 过渡章
        return imp

    def _optimal_for_chapter(self, i: int, n: int) -> int:
        """基于章节位置的最优字数"""
        chapter = i + 1
        if chapter == 1 or chapter == n:
            return 2600    # 开篇和终章更厚重
        elif chapter <= 3 or chapter >= n - 2:
            return 2400    # 关键章节
        elif chapter % 4 == 0:
            return 2500    # 卷末
        elif chapter % 4 == 1:
            return 2000    # 卷首: 轻盈开卷
        else:
            return 2200    # 过渡章

    @classmethod
    def from_outline(cls, project_dir: str) -> "PacingOptimizer":
        """从项目总纲加载章重要性权重"""
        import json
        outline_path = Path(project_dir) / "大纲" / "总纲.md"
        state_path = Path(project_dir) / ".webnovel" / "state.json"
        # fallback
        if not state_path.exists():
            state_path = Path(project_dir) / "state.json"

        total_ch = 12
        if state_path.exists():
            try:
                s = json.loads(state_path.read_text(encoding="utf-8"))
                total_ch = s.get("project_info", {}).get("target_chapters", 12)
            except Exception:
                pass

        return cls(total_chapters=total_ch,
                    total_budget=total_ch * 2500)

    def optimize_word_budget(self,
                              importance: List[float] = None) -> List[int]:
        """
        用DP分配每章字数。

        importance[i] = 第i章的重要性权重 (默认为均匀，但高潮章节应更重)

        DP: dp[i][w] = 前i章用了w字的最大满意度
        """
        n = self.total_chapters
        B = self.total_budget

        if importance is None:
            importance = self._default_importance(n)

        # DP表: dp[i][w] = (max_value, prev_w)
        INF_NEG = -1e9
        dp = [[(INF_NEG, -1) for _ in range(B + 1)] for _ in range(n + 1)]
        dp[0][0] = (0.0, -1)

        for i in range(n):
            imp = importance[i]
            optimal_words = self._optimal_for_chapter(i, n)
            for w in range(B + 1):
                if dp[i][w][0] <= INF_NEG / 2:
                    continue
                for c in range(self.min_per_chapter,
                                self.max_per_chapter + 1, 50):
                    if w + c > B:
                        break
                    # 满意度: 越接近最优字数越好，重要性加权
                    deviation = abs(c - optimal_words) / optimal_words
                    satisfaction = imp * max(0.15, 1.0 - 0.5 * deviation)
                    satisfaction *= 1.0 + 0.1 * (imp - 1.0)  # 加权溢价

                    new_val = dp[i][w][0] + satisfaction
                    if new_val > dp[i + 1][w + c][0]:
                        dp[i + 1][w + c] = (new_val, w)

        # 回溯: 找最优预算使用
        best_w = B
        best_val = dp[n][B][0]
        for w in range(B + 1):
            if dp[n][w][0] > best_val:
                best_val = dp[n][w][0]
                best_w = w

        # 回溯路径
        plan = [0] * n
        w = best_w
        for i in range(n, 0, -1):
            prev_w = dp[i][w][1]
            plan[i - 1] = w - prev_w
            w = prev_w

        return plan

    def schedule_hooks(self) -> List[str]:
        """
        调度钩子类型: 满足"连续2章不能同类型"约束。

        贪心算法 + 回溯。
        """
        n = self.total_chapters
        hooks = self.hook_types[:]
        schedule = []

        for i in range(n):
            # 可选: 不与前1章相同
            available = [h for h in hooks if not schedule or h != schedule[-1]]

            if not available:
                available = hooks[:]

            # 选择: 轮换使用频率最低的
            used_count = {h: schedule.count(h) for h in available}
            best = min(available, key=lambda h: used_count.get(h, 0))
            schedule.append(best)

        return schedule

    def schedule_releases(self) -> List[Optional[str]]:
        """
        调度情绪释放: 每3-4章1个大释放，不能连续重复方式。

        Returns: [每章的释放方式或None]
        """
        n = self.total_chapters
        releases = self.release_types[:]
        schedule: List[Optional[str]] = [None] * n

        # 大释放章节: 第3, 6, 9, 12章
        release_chapters = [3, 6, 9, 12]
        # 小释放章节: 第1, 2, 5, 8, 11章
        minor_release = [1, 2, 5, 8, 11]

        used_recently: List[str] = []

        for ch in range(1, n + 1):
            if ch in release_chapters:
                available = [r for r in releases if r not in used_recently[-2:]]
                if not available:
                    available = releases[:]
                chosen = min(available, key=lambda r: schedule.count(r))
                schedule[ch - 1] = chosen
                # 避免最近重复
                if len(used_recently) >= 3:
                    used_recently.pop(0)
                used_recently.append(chosen)
            elif ch in minor_release:
                available = [r for r in releases if r not in used_recently[-1:]]
                if not available:
                    available = releases[:]
                schedule[ch - 1] = random_choice(available)

        return schedule


def random_choice(items: list) -> str:
    import random
    return random.choice(items)


def optimal_pacing(total_chapters: int, total_words: int) -> Dict:
    """便捷函数: 一次调用获取最优节奏方案"""
    opt = PacingOptimizer(total_chapters=total_chapters, total_budget=total_words)
    return {
        "word_plan": opt.optimize_word_budget(),
        "hook_schedule": opt.schedule_hooks(),
        "release_schedule": opt.schedule_releases(),
    }
