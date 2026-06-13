"""
盘古数学 · 运筹学优化层

运筹学在写作中的应用:
  - dynamic_programming: 最优节奏分配 (每章字数/爽点/钩子的最优配置)
  - game_theory:        角色冲突博弈 (囚徒困境/智猪博弈/鹰鸽博弈)
  - decision_tree:      情节分支决策树 (期望效用最大化)
  - queue_theory:       Pipeline任务队列优化 (M/M/1模型)
  - linear_programming: 多约束下的资源最优分配
"""

from .dynamic_programming import PacingOptimizer, optimal_pacing
from .game_theory import ConflictGame, plot_conflict_matrix

__all__ = [
    "PacingOptimizer", "optimal_pacing",
    "ConflictGame", "plot_conflict_matrix",
]
